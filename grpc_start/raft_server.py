import json
import os
import random
import threading
import time
from enum import Enum

# idiot workaround lmao
from typing import TYPE_CHECKING

import grpc

from grpc_start import log_entries as log
from grpc_start import raft_pb2, raft_pb2_grpc, server  # noqa: F401

if TYPE_CHECKING:
    pass

RAFT_SERVERS = ["localhost:50051", "localhost:50052", "localhost:50053"]


class RaftServerState(Enum):  # if this is either-or, could just be a bool surely
    LEADER = 1
    FOLLOWER = 2


LEADER_HEARTBEAT_TIMEOUT = 0.1
MIN_LEADER_CHANGE_TIMEOUT = 0.5
MAX_LEADER_CHANGE_TIMEOUT = 2

RETRY_LIMIT = 3
RETRY_DELAY = 2


class RaftServer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, ip, port, log_file_path, lock_server, is_leader=False):
        self.server_ip = ip
        self.server_port = port

        self.log = []  # entries all of type LogEntry
        self.log_file_path = log_file_path
        self.new_leader_timeout = None
        self.lock_server = lock_server  # reference to the parent LockServer

        self.raft_servers = RAFT_SERVERS.copy()
        self.raft_servers.remove(f"{self.server_ip}:{self.server_port}")

        self.establish_channels_stubs()

        self.leader = None

        if os.path.exists(self.log_file_path):
            # assuming that if log file exists, that means this server died and came back
            self.initiate_recovery()
        else:
            # create path and file if they dont exist
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            open(self.log_file_path, "w").close()
            if is_leader:  # ONLY HERE FOR DEBUG PURPOSES!!!!
                self.leader_start()
            else:
                self.follower_start()

    def leader_start(self):
        # called when first coming into power
        self.state = RaftServerState.LEADER
        self.leader = f"{self.server_ip}:{self.server_port}"
        self.send_append_entry_rpcs(
            entry=None
        )  # TODO send heartbeats to all other servers so they know you're leader

        if self.new_leader_timeout:
            self.new_leader_timeout.cancel()

    def follower_start(self):
        self.state = RaftServerState.FOLLOWER  # placeholder
        print(f"Raft server {self.server_port}: Initialized as follower.")

        self.start_new_leader_timer()

    def establish_channels_stubs(self):
        self.channels = {}
        self.stubs = {}

        for raft_node in self.raft_servers:
            try:
                channel = grpc.insecure_channel(raft_node)
                stub = raft_pb2_grpc.RaftServiceStub(channel)
                self.channels[raft_node] = channel
                self.stubs[raft_node] = stub
                print(f"{self.server_port}: Connected to {raft_node}")
            except grpc.RpcError as e:
                print(
                    f"Raft server {self.server_port}: Error connecting to {raft_node}: {e}"
                )
                continue

    def retry_rpc_call(self, rpc_func, *args, **kwargs):
        for attempt in range(RETRY_LIMIT):
            try:
                response = rpc_func(*args, **kwargs)
                return response
            except grpc.RpcError as e:
                print(
                    f"Raft {self.server_port}: grpc error. Attempt {attempt + 1}/{RETRY_LIMIT}"
                )
                print(e)
                time.sleep(RETRY_DELAY)

        print(
            f"Raft {self.server_port}: RETRY_RPC_CALL: Failed to receive response after retries."
        )
        return None

    def find_leader(self):
        while True:
            print(f"Raft server {self.server_port}: Finding leader.")
            for server in self.raft_servers:
                try:
                    response = self.stubs[server].where_is_leader(raft_pb2.Empty())
                    if len(response.value) > 0:
                        print(
                            f"Raft server {self.server_port}: Found leader: {response.value}"
                        )
                        return response.value
                except grpc.RpcError:
                    print(
                        f"Raft server {self.server_port}: failed to contact node {server}"
                    )
                    continue

    def where_is_leader(self, request, context):
        return raft_pb2.String(value=self.leader)

    def start_new_leader_timer(self):
        """Start or restart the 'new leader' timer for this Raft node."""
        if self.new_leader_timeout and self.new_leader_timeout.is_alive():
            self.new_leader_timeout.cancel()

        self.new_leader_timeout = threading.Timer(
            random.uniform(MIN_LEADER_CHANGE_TIMEOUT, MAX_LEADER_CHANGE_TIMEOUT),
            self.become_new_leader,
        )

        self.new_leader_timeout.start()

    def become_new_leader(self):
        """The follower that detects the absence of the leader first becomes the new leader"""
        if self.state == RaftServerState.FOLLOWER:
            self.leader_start()

    def serialise_log(self):
        """Converts self.log to json file"""
        with open(self.log_file_path, "w") as f:
            json.dump(self.log, f)

    def deserialise_log(self):
        """Reads from logfile into self.log"""
        try:
            with open(self.log_file_path, "r") as f:
                self.log = json.load(f)
        except FileNotFoundError:
            print("Log file not found.")
        except json.JSONDecodeError:
            print("Log file is not a valid JSON.")

    # this bit is executed on the followers - this is the CONSEQUENCE of the RPC call, not the call itself
    def append_entry(self, request, context):
        # if we receive an append_entries message, we know not to become the new leader

        self.state = RaftServerState.FOLLOWER
        self.start_new_leader_timer()
        self.leader = request.leaderID
        # print("REQUEST: ", request.entry)

        if len(str(request.entry)) > 0:
            log_entry = log.log_entry_grpc_to_object(request.entry)
            self.log.append(log_entry)
            self.serialise_log()

            command = log_entry.command
            self.lock_server.commit_command(command)
        # else:
        #     print("heartbeat")

        return raft_pb2.Bool(value=True)

        # in what scenario does it return false?

    # this is where this server calls the append_entries rpc on other servers
    def send_append_entry_rpcs(self, entry: log.LogEntry):
        if self.state == RaftServerState.LEADER:
            # TODO: make asynchronous?
            for raft_node in self.raft_servers:
                try:
                    if entry:
                        self.retry_rpc_call(
                            self.stubs[raft_node].append_entry,
                            raft_pb2.AppendArgs(
                                leaderID=f"{self.server_ip}:{self.server_port}",
                                entry=log.log_entry_object_to_grpc(entry),
                            ),
                        )
                    else:
                        # print("Sending heartbeat")
                        response = self.retry_rpc_call(
                            self.stubs[raft_node].append_entry,
                            raft_pb2.AppendArgs(
                                leaderID=f"{self.server_ip}:{self.server_port}",
                                entry=None,
                            ),
                        )

                except grpc.RpcError as e:
                    print(
                        f"Raft server {self.server_port}: Error sending append_entry RPC to {raft_node}: {e}"
                    )
                    # remove node from raft_servers
                    self.raft_servers.remove(raft_node)
                    continue

            # execute command itself
            if entry:
                self.log.append(entry)
                self.serialise_log()
                self.lock_server.commit_command(entry.command)

    # follower gets data from log file, gets any missing logs from leader and reconstructs state from completed log
    def initiate_recovery(self):
        self.state = RaftServerState.FOLLOWER
        self.deserialise_log()  # get cached log entries
        self.leader = self.find_leader()

        # get missing log entries (if any) from leader
        missing_log_grpcs = self.retry_rpc_call(
            self.stubs[self.leader].recover_logs, raft_pb2.Int(value=len(self.log))
        )
        if missing_log_grpcs:
            for log_grpc in missing_log_grpcs:
                self.log.append(log.log_entry_grpc_to_object(log_grpc))

        for entry in self.log:
            self.lock_server.commit_command(entry.command)

        # now that this is an up-to-date follower, allow it to potentially become the leader
        self.start_new_leader_timer()

    # leader helpfully returns missing logs to idiot follower who had the temerity to die
    def recover_logs(self, request, context):
        follower_log_length = request.value

        remaining_log = self.log[follower_log_length:]
        log_grpcs = []

        for entry in remaining_log:
            log_grpcs.append(log.log_entry_object_to_grpc(entry))

        return raft_pb2.RecoveryResponse(log=log_grpcs)
