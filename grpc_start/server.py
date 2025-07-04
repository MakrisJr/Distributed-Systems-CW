import logging
import os
import sys
import threading
import time
from collections import deque
from concurrent import futures
from pathlib import Path

import grpc

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

from grpc_start import commands as cs  # noqa: E402
from grpc_start import lock_pb2, lock_pb2_grpc, raft_pb2_grpc, raft_server  # noqa: E402
from grpc_start import log_entries as log  # noqa: E402

DEBUG = True
LOCK_TIMEOUT = 8


class LockServer(lock_pb2_grpc.LockServiceServicer):
    def __init__(self, ip="localhost", port="50051", is_leader_debug=False):
        self.lock_owner = None  # does not need to be synced independently; always equal to waiting_list[0]

        self.clients = {}  # needs to be synced - 'add client' action, 'increment client's expected seq number' action
        self.waiting_list = deque()
        self.newClientId = 1  # needs to be synced - 'increment' action
        self.appends = (
            deque()
        )  # needs to be synced - 'add operation' action, 'execute all' action
        # so any time any of these change, it's a log entry

        self.lock_timer = threading.Timer(
            LOCK_TIMEOUT, self.force_release_lock
        )  # would be difficult and stupid to sync
        # lock timer DOES NOT GET STARTED NOW: only starts with the very first call to lock_acquire
        self.ip = ip
        self.port = port

        self.raft_server: raft_server.RaftServer  # purely for type hints

        self.file_folder = "./files_" + str(port)
        self.lock_owner_lock = threading.Lock()

        self.is_leader_debug = is_leader_debug

    def start_lock_timer(self):
        """Start or restart the lock timeout timer for the current lock owner."""
        if DEBUG:
            print(
                f"Server: start_lock_timer called: lock_owner={self.lock_owner}, waiting_list={self.waiting_list}"
            )
        if self.lock_timer:
            self.lock_timer.cancel()
        self.lock_timer = threading.Timer(LOCK_TIMEOUT, self.force_release_lock)
        self.lock_timer.daemon = True
        self.lock_timer.start()

    def force_release_lock(self):
        """Release the lock if the owner is unresponsive."""
        if DEBUG:
            print(
                f"Server: force_release_lock called: lock_owner={self.lock_owner}, waiting_list={self.waiting_list}"
            )
        if self.lock_owner:
            if DEBUG:
                print(f"Lock timed out for client {self.lock_owner}. Releasing lock.")
            self.lock_owner = None
            if self.waiting_list:
                self.grant_lock_to_next_client()

            self.appends = (
                deque()
            )  # delete any append operations that weren't carried out

    def grant_lock_to_next_client(self):
        """Grant the lock to the next client in the queue."""
        if DEBUG:
            print(
                f"Server: grant_lock_to_next_client called: lock_owner={self.lock_owner}, waiting_list={self.waiting_list}"
            )
        if self.waiting_list:
            self.waiting_list.popleft()
            if self.waiting_list:
                self.lock_owner = self.waiting_list[0]
            else:
                self.lock_owner = None
            print(f"Lock granted to client {self.lock_owner}")
            self.start_lock_timer()

    def check_client_seq(self, client_id, request_seq) -> lock_pb2.Response:
        """Check if a) the client has called client_init beforehand, and b) if the request is a duplicate or not"""
        if client_id in self.clients:
            client_seq = self.clients[client_id]["seq"]
            if request_seq != client_seq:
                return lock_pb2.Response(
                    status=lock_pb2.Status.SEQ_ERROR, seq=client_seq
                )
            else:
                return None  # no error here, carry on
        else:
            return lock_pb2.Response(
                status=lock_pb2.Status.CLIENT_NOT_INIT, seq=client_seq
            )

    def increment_client_seq(self, client_id):
        self.raft_server.send_append_entry_rpcs(
            log.LogEntry(cs.IncrementClientSeqCommand(client_id))
        )
        self.clients[client_id]["seq"] += 1

    def client_init(self, request, context):
        while self.raft_server.pause:
            time.sleep(0.1)

        if not (self.raft_server.is_leader()):
            return lock_pb2.Int(leader=self.raft_server.leader)
        print("client_init received from " + str(context.peer()))
        client_ip = context.peer()
        client_id = request.rc
        client_seq = 1  # sequence number of next expected request

        if client_id in self.clients:
            existing_seq = self.clients[client_id]["seq"]
            # client is attempting to rejoin a server that already has a record for it
            print(f"duplicate client_init from {client_id}")
            return lock_pb2.Int(rc=client_id, seq=existing_seq)

        self.raft_server.send_append_entry_rpcs(
            log.LogEntry(cs.AddClientCommand(client_id, client_ip))
        )
        self.clients[client_id] = {"ip": client_ip, "seq": client_seq}
        if DEBUG:
            print("client_init received: " + str(request.rc))
            print("connected clients: " + str(self.clients))
        return lock_pb2.Int(rc=client_id, seq=client_seq)

    def lock_acquire(self, request, context) -> lock_pb2.Response:
        while self.raft_server.pause or not self.raft_server.leader:
            time.sleep(0.1)

        if not (self.raft_server.is_leader()):
            print(f"Server {self.port}: lock_acquire not leader: ")
            return lock_pb2.Response(leader=self.raft_server.leader)

        client_id = request.client_id
        request_seq = request.seq

        check_response = self.check_client_seq(client_id, request_seq)
        if check_response:
            return check_response

        client_seq = self.clients[client_id]["seq"]

        print(
            f"Server {self.port}: lock_acquire received: {request.client_id}, requesting lock owned by {self.lock_owner}"
        )
        self.lock_owner_lock.acquire()
        print(f"server {self.port} lock_owner_lock acquired")
        if self.lock_owner is None:
            self.waiting_list.append(request.client_id)

            self.raft_server.send_append_entry_rpcs(
                log.LogEntry(cs.ChangeLockHolderCommand(client_id))
            )
            self.lock_owner = client_id
            self.lock_owner_lock.release()
            self.start_lock_timer()

            self.increment_client_seq(client_id)

            return lock_pb2.Response(
                status=lock_pb2.Status.SUCCESS, seq=self.clients[client_id]["seq"]
            )
        elif self.lock_owner == request.client_id:
            self.lock_owner_lock.release()
            print(f"Client {client_id} already has the lock.")
            self.start_lock_timer()
            self.increment_client_seq(client_id)

            return lock_pb2.Response(
                status=lock_pb2.Status.SUCCESS, seq=self.clients[client_id]["seq"]
            )

        self.lock_owner_lock.release()

        self.waiting_list.append(request.client_id)
        while True:
            if self.waiting_list[0] == request.client_id:
                # essentially, head of waiting list is always current owner
                self.increment_client_seq(client_id)

                print(f"LOCK OWNER: {self.lock_owner}")

                self.raft_server.send_append_entry_rpcs(
                    log.LogEntry(cs.ChangeLockHolderCommand(client_id))
                )

                return lock_pb2.Response(
                    status=lock_pb2.Status.SUCCESS, seq=client_seq + 1
                )
            else:
                # if not context.is_active():

                # else:
                time.sleep(0.1)

    def execute_appends(self):
        # execute all stashed changes to files - this also removes all append entries
        self.raft_server.send_append_entry_rpcs(
            log.LogEntry(cs.ExecuteAppendsCommand())
        )

        while self.appends:
            file_path, bytes = self.appends.popleft()

            with open(file_path, "ab") as file:
                file.write(bytes)

    def lock_release(self, request, context) -> lock_pb2.Response:
        while self.raft_server.pause or not self.raft_server.leader:
            time.sleep(0.1)

        if not (self.raft_server.is_leader()):
            return lock_pb2.Response(leader=self.raft_server.leader)

        client_id = request.client_id
        request_seq = request.seq

        check_response = self.check_client_seq(client_id, request_seq)
        if check_response:
            return check_response

        print("lock_release received: " + str(request.client_id))

        if self.lock_owner == request.client_id:
            self.grant_lock_to_next_client()
            # resets timer, as this is a call from the current lock owner, proving that client is alive
            self.increment_client_seq(client_id)

            self.start_lock_timer()

            self.execute_appends()
            return lock_pb2.Response(
                status=lock_pb2.Status.SUCCESS, seq=self.clients[client_id]["seq"]
            )
        else:
            self.increment_client_seq(client_id)

            # good idea to have this anyhow, as client could call release before ever calling acquire
            return lock_pb2.Response(
                status=lock_pb2.Status.FAILURE, seq=self.clients[client_id]["seq"]
            )

    def file_append(self, request, context) -> lock_pb2.Response:
        while self.raft_server.pause or not self.raft_server.leader:
            time.sleep(0.1)

        if not (self.raft_server.is_leader()):
            return lock_pb2.Response(leader=self.raft_server.leader)

        client_id = request.client_id
        request_seq = request.seq

        check_response = self.check_client_seq(client_id, request_seq)
        if check_response:
            return check_response

        print(
            f"Server: file_append received: {request.client_id}, {request.filename}, deque: {self.waiting_list}"
        )

        self.increment_client_seq(client_id)

        if self.lock_owner == request.client_id:
            # resets timer, as this is a call from the current lock owner, proving that client is alive
            self.start_lock_timer()

            filename = request.filename

            file_path = self.file_folder + "/" + filename
            # file_path = f"./files/{filename}"

            if os.path.isfile(file_path):
                # add file append operation to appends queue
                self.raft_server.send_append_entry_rpcs(
                    log.LogEntry(
                        cs.AddAppendCommand(filename=filename, content=request.content)
                    )
                )
                self.appends.append((file_path, request.content))
                print("QUEUED APPENDS: " + str(self.appends))

                return lock_pb2.Response(
                    status=lock_pb2.Status.SUCCESS,
                    seq=self.clients[client_id]["seq"],
                )
            else:
                if DEBUG:
                    print(f"File {file_path} error.")
                return lock_pb2.Response(
                    status=lock_pb2.Status.FILE_ERROR,
                    seq=self.clients[client_id]["seq"],
                )
        else:
            if DEBUG:
                print(f"Lock expired for client {client_id}.")
            return lock_pb2.Response(
                status=lock_pb2.Status.LOCK_EXPIRED, seq=self.clients[client_id]["seq"]
            )

    def client_close(self, request, context):
        while self.raft_server.pause or not self.raft_server.leader:
            time.sleep(0.1)

        if not (self.raft_server.is_leader()):
            return lock_pb2.Int(leader=self.raft_server.leader)

        # get process id and remove from set
        client_id = request.rc

        self.raft_server.send_append_entry_rpcs(
            log.LogEntry(cs.RemoveClientCommand(client_id))
        )

        if client_id in self.clients:
            while self.lock_owner == client_id:
                time.sleep(0.01)
            del self.clients[client_id]

        if DEBUG:
            print("client_close received: " + str(request.rc))
            print("connected clients: " + str(self.clients))
            print()
        return lock_pb2.Int(rc=client_id, seq=0)

    # ONLY EXECUTED BY LOCKSERVERS ATTACHED TO FOLLOWER NODES
    # got a command from the leader, apply to internal state
    def commit_command(self, command: cs.Command):
        print(f"Committing command {str(command)} on machine {self.ip}:{self.port}")
        if isinstance(command, cs.AddClientCommand):
            client_ip = command.client_ip
            client_id = command.client_id

            self.newClientId = client_id + 1  # this seems stupid
            client_seq = 1

            self.clients[client_id] = {"ip": client_ip, "seq": client_seq}

        elif isinstance(command, cs.IncrementClientSeqCommand):
            self.clients[command.client_id]["seq"] += 1

        elif isinstance(command, cs.ChangeLockHolderCommand):
            self.lock_owner = command.client_id
            self.waiting_list = deque()  # ensure follower does not at any point have a waiting list independent of leader
            self.waiting_list.append(self.lock_owner)

        elif isinstance(command, cs.AddAppendCommand):
            self.appends.append(
                (self.file_folder + "/" + command.filename, command.content)
            )
            print("QUEUED APPENDS: " + str(self.appends))

        elif isinstance(command, cs.ExecuteAppendsCommand):
            while self.appends:
                file_path, bytes = self.appends.popleft()

                with open(file_path, "ab") as file:
                    file.write(bytes)

        elif isinstance(command, cs.RemoveClientCommand):
            client_id = command.client_id
            if client_id in self.clients:
                # while self.lock_owner == client_id:
                #     time.sleep(0.01)
                del self.clients[client_id]

    def serve(self):
        self.raft_server = raft_server.RaftServer(
            self.ip, self.port, f"./log/{self.port}.log", self, self.is_leader_debug
        )
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        raft_pb2_grpc.add_RaftServiceServicer_to_server(self.raft_server, self.server)
        lock_pb2_grpc.add_LockServiceServicer_to_server(self, self.server)

        self.server.add_insecure_port(f"[::]:{self.port}")
        self.server.start()
        print("Initializing raft server")
        self.raft_server.serve()
        print("Server started, listening on ", self.port)
        time.sleep(5)

    def stop(self):
        self.lock_timer.cancel()
        if self.raft_server.new_leader_timeout:
            self.raft_server.new_leader_timeout.cancel()
        self.raft_server.state = raft_server.RaftServerState.DEAD
        self.server.stop(0)

    def where_is_server(self, request, context):
        leader = self.raft_server.leader
        print(f"Server {self.port} Leader is {leader}")
        ip = leader.split(":")[0]
        port = leader.split(":")[1]
        return lock_pb2.Address(ip=ip, port=port)

    def reset_own_files(self):
        for i in range(100):
            with open(f"./files_{self.port}/file_{i}", "w") as f:
                f.write("")


def create_files(n=100):
    # needs to be modified to account for multiple servers

    # create directory & files if necessary:
    for port in ["50051", "50052", "50053"]:
        if not os.path.exists("./files_" + str(port)):
            os.makedirs("./files_" + str(port))

            for i in range(n):
                with open(f"./files_{port}/file_{i}", "w") as f:
                    f.write("")


def reset_files(n=100):
    # they might or might not exist:
    # print("RESET FILE IS CALLED")
    for port in ["50051", "50052", "50053"]:
        if not os.path.exists(f"./files_{port}"):
            os.makedirs(f"./files_{port}")

        for i in range(n):
            with open(f"./files_{port}/file_{i}", "w") as f:
                f.write("")

    # delete files in ./log/*
    if not os.path.exists("./log"):
        os.makedirs("./log")
    for file in os.listdir("./log"):
        print(file)
        os.remove(os.path.join("./log", file))


if __name__ == "__main__":
    create_files()  # presumably the server object should do this, rather than it being randomly outside??
    logging.basicConfig()
    server = LockServer()
    server.serve()
