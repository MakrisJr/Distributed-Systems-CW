from __future__ import print_function

import logging
import sys
import time
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

import grpc  # noqa: E402

from grpc_start import lock_pb2, lock_pb2_grpc  # noqa: E402

RETRY_LIMIT = 3
RETRY_DELAY = 3
DEBUG = True
POSSIBLE_SERVERS = ["localhost:50051", "localhost:50052", "localhost:50053"]


def status_str(x):
    status_strings = [
        "Success",
        "File error - not found",
        "Failure",
        "Sequence error",
        "Didn't call client_init",
        "Lock expired",
    ]

    if x < len(status_strings):
        return status_strings[x]
    else:
        raise Exception("Not a valid status integer")


class LeaderChangeException(Exception):
    pass


class Client:
    def __init__(self, id):
        self.client_id = id
        self.seq = 0
        self.request_history = {}  # {seq: request}
        self.server_ip = "localhost"
        self.server_port = 50051
        self.channel = grpc.insecure_channel(f"{self.server_ip}:{self.server_port}")
        self.stub = lock_pb2_grpc.LockServiceStub(self.channel)
        # client's port :

    def RPC_client_init(self):
        try:
            response = self.stub.client_init(lock_pb2.Int(rc=self.client_id))

            if response and len(str(response.leader)):
                print("accidentally contacted follower - retry")

                # update channel and stub info to point to new leader
                leader_str = str(response.leader)

                self.server_ip = leader_str.split(":")[0]
                self.server_port = leader_str.split(":")[1]
                self.channel = grpc.insecure_channel(
                    f"{self.server_ip}:{self.server_port}"
                )
                self.stub = lock_pb2_grpc.LockServiceStub(self.channel)

                return self.RPC_client_init()
            self.client_id = response.rc
            self.seq = response.seq  # sequence number of next expected request
            if DEBUG:
                print("client_init: " + str(response.rc))
            self.request_history[self.seq - 1] = "client_init"
            return True
        except grpc.RpcError as e:
            print(
                f"Client {self.client_id}: RPC call client init failed with error: {e}"
            )
            return False

    def retry_rpc_call(self, func_type, *args, **kwargs):
        for attempt in range(RETRY_LIMIT):
            match func_type:
                case "lock_acquire":
                    rpc_func = self.stub.lock_acquire
                case "file_append":
                    rpc_func = self.stub.file_append
                case "lock_release":
                    rpc_func = self.stub.lock_release
                case "client_close":
                    rpc_func = self.stub.client_close

            try:
                response = rpc_func(*args, **kwargs)
                if len(str(response.leader)):
                    raise LeaderChangeException
                return response
            except grpc.RpcError as e:
                print(
                    f"Client {self.client_id}: RPC call failed with error: {e}. Retrying {attempt + 1}/{RETRY_LIMIT}..."
                )
                self.RPC_where_is_server()
                time.sleep(RETRY_DELAY)

            except LeaderChangeException:
                # successful connection, but it was a follower instead

                # update channel and stub info to point to new leader
                leader_str = str(response.leader)

                self.server_ip = leader_str.split(":")[0]
                self.server_port = leader_str.split(":")[1]
                self.channel = grpc.insecure_channel(
                    f"{self.server_ip}:{self.server_port}"
                )
                self.stub = lock_pb2_grpc.LockServiceStub(self.channel)

                time.sleep(RETRY_DELAY)

            print(f"Client {self.client_id}: Retrying...")

        print(
            f"Client {self.client_id}: RETRY_RPC_CALL: Failed to receive response after retries."
        )
        return None

    def RPC_lock_acquire(self):
        print("CALLED RPC_LOCK_ACQUIRE")
        response = self.retry_rpc_call(
            "lock_acquire",
            lock_pb2.lock_args(client_id=self.client_id, seq=self.seq),
        )

        if response and len(str(response.leader)):
            print("accidentally contacted follower - retry")

            return self.RPC_lock_acquire()
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            if DEBUG:
                print(
                    f"Client {self.client_id}: seq={self.seq}, response.seq={response.seq}"
                )
            if response.seq > self.seq:
                # the server has processed the request already and updated the sequence number, but was lost on the way back
                self.seq = response.seq
            else:
                self.seq_recovery(response.seq)
            return False
        if response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: lock_acquire received: "
                + status_str(response.status)
            )
            self.seq = response.seq
            self.request_history[self.seq] = "lock_acquire"
            return True
        else:
            print(f"Client {self.client_id}: Failed. Status: {response.status}")
            return False

    def RPC_append_file(
        self, file_number, text, lost_before_server=False, lost_after_server=False
    ):
        print("CALLED RPC_APPEND_FILE")
        if lost_before_server:  # simulate packet loss
            if DEBUG:
                print(f"Client {self.client_id}: Simulating packet loss.")
            return False

        response = self.retry_rpc_call(
            "file_append",
            lock_pb2.file_args(
                filename=f"file_{file_number}",
                content=f"{text}".encode(),
                client_id=self.client_id,
                seq=self.seq,
            ),
        )
        if lost_after_server:
            return False

        if response and len(str(response.leader)):
            print("accidentally contacted follower - retry")

            return self.RPC_append_file(
                file_number, text, lost_before_server, lost_after_server
            )  # potential infinite recursion????
        elif response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: file_append received: "
                + status_str(response.status)
            )
            self.request_history[self.seq] = ("file_append", file_number, text)
            self.seq = response.seq
            return True
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            if DEBUG:
                print(
                    f"Client {self.client_id}: seq={self.seq}, response.seq={response.seq}"
                )
            if response.seq > self.seq:
                # the server has processed the request already and updated the sequence number, but was lost on the way back
                self.seq = response.seq
            else:
                self.seq_recovery(response.seq)
            return False
        elif response and response.status == lock_pb2.Status.LOCK_EXPIRED:
            print(f"Client {self.client_id}: Lock expired. Need to recover.")
            self.seq = response.seq
            return False

        elif response and response.status == lock_pb2.Status.FILE_ERROR:
            print("Invalid filename")
            self.seq = response.seq
            return False
        else:
            print(
                f"Client {self.client_id}: Failed to append file after {RETRY_LIMIT} retries."
            )

            return False

    def RPC_lock_release(self):
        print("CALLED RPC_LOCK_RELEASE")
        response = self.retry_rpc_call(
            "lock_release",
            lock_pb2.lock_args(client_id=self.client_id, seq=self.seq),
        )

        if response and len(str(response.leader)):
            print("accidentally contacted follower - retry")

            return self.RPC_lock_release()
        elif response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: lock_release received: "
                + status_str(response.status)
            )
            self.seq = response.seq
            self.request_history[self.seq] = "lock_release"
            return True
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            if DEBUG:
                print(
                    f"Client {self.client_id}: seq={self.seq}, response.seq={response.seq}"
                )
            if response.seq > self.seq:
                # the server has processed the request already and updated the sequence number, but was lost on the way back
                self.seq = response.seq
            else:
                self.seq_recovery(response.seq)
            return False
        else:  # response and response.status == lock_pb2.Status.FAILURE:
            self.seq = response.seq
            print(f"Client {self.client_id}: Failed to release lock after retries.")
            return False

    def RPC_client_close(self):
        print("CALLED RPC_CLIENT_CLOSE")
        response = self.retry_rpc_call(
            "client_close", lock_pb2.Int(rc=self.client_id, seq=self.seq)
        )

        if response and len(str(response.leader)):
            print("accidentally contacted follower - retry")

            self.RPC_client_close()
        elif response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: client_close received: "
                + status_str(response.status)
            )
            self.request_history[self.seq] = "client_close"
            self.seq = response.seq
            # reset client_id and seq
            self.client_id = 0
            self.seq = 0
            return True
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            if DEBUG:
                print(
                    f"Client {self.client_id}: seq={self.seq}, response.seq={response.seq}"
                )
            if response.seq > self.seq:
                # the server has processed the request already and updated the sequence number, but was lost on the way back
                self.seq = response.seq
            else:
                self.seq_recovery(response.seq)
            return False
        else:
            self.seq = response.seq
            print(f"Client {self.client_id}: Failed to close client after retries.")
            return False

    def RPC_where_is_server(self):
        print(f"Calling where_is_server for client {self.client_id}")
        for server in POSSIBLE_SERVERS:
            try:
                self.channel = grpc.insecure_channel(
                    f"{server}"  # f"{self.server_ip}:{self.server_port}"
                )
                self.stub = lock_pb2_grpc.LockServiceStub(self.channel)

                response = self.stub.where_is_server(lock_pb2.Int(rc=self.client_id))
                if response.port != -1:
                    self.server_ip = response.ip
                    self.server_port = response.port
                    print("Server found at " + response.ip + ":" + str(response.port))
                    self.channel = grpc.insecure_channel(
                        f"{self.server_ip}:{self.server_port}"
                    )
                    self.stub = lock_pb2_grpc.LockServiceStub(self.channel)
                    print(
                        f"Client {self.client_id}: Server found at {self.server_ip}:{self.server_port}"
                    )
                    return True
            except grpc.RpcError as e:
                print(f"Client {self.client_id}: Could not contact server {server}.")
                print(e)
                continue  # try next server
        return False

    def seq_recovery(self, seq):
        print(f"Client {self.client_id}: Attempting to recover lost calls.")
        for i in range(seq, self.seq):
            if self.request_history[i][0] == "lock_acquire":
                response = self.retry_rpc_call(
                    "lock_acquire",
                    lock_pb2.lock_args(client_id=self.client_id, seq=i),
                )
            elif self.request_history[i][0] == "file_append":
                response = self.retry_rpc_call(
                    "file_append",
                    lock_pb2.file_args(
                        filename=f"file_{self.request_history[i][1]}",
                        content=f"{self.request_history[i][2]}".encode(),
                        client_id=self.client_id,
                        seq=i,
                    ),
                )
            elif self.request_history[i] == "lock_release":
                response = self.retry_rpc_call(
                    "lock_release",
                    lock_pb2.lock_args(client_id=self.client_id, seq=i),
                )
            else:
                print(
                    f"Client {self.client_id}: Unknown request type {self.request_history[i][0]}"
                )
                return False
            if response and response.status == lock_pb2.Status.SUCCESS:
                print(
                    f"Client {self.client_id}: Recovered request {i}: "
                    + status_str(response.status)
                )
                self.seq = response.seq
            else:
                print(f"Client {self.client_id}: Failed to recover request {i}.")
                return False
        return True


# def run():
#     # NOTE(gRPC Python Team): .close() is possible on a channel and should be
#     # used in circumstances in which the with statement does not fit the needs
#     # of the code.
#     print("Will try to greet world ...")

#     client = Client()
#     client.RPC_client_init()
#     client.RPC_lock_acquire()
#     client.RPC_append_file(1, "Hello, world!")
#     client.RPC_lock_release()
#     client.RPC_client_close()


if __name__ == "__main__":
    logging.basicConfig()
    # run()
