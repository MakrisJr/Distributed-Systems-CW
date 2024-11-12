import time
from enum import Enum

import grpc

from grpc_start import raft_pb2, raft_pb2_grpc  # noqa: F401

RAFT_SERVERS = ["localhost:50051", "localhost:50052", "localhost:50053"]
RETRY_LIMIT = 3
RETRY_DELAY = 2


class RaftServerState(Enum):
    LEADER = 1
    FOLLOWER = 2
    CANDIDATE = 3


class RaftServer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, ip, port):
        self.server_ip = ip
        self.server_port = port
        self.current_term = 0
        self.voted_for = None
        self.log = []

        self.commit_index = 0
        self.last_applied = 0

        self.next_index = 0
        self.match_index = 0

        self.channel = grpc.insecure_channel(f"{self.server_ip}:{self.server_port}")
        self.stub = raft_pb2_grpc.RaftServiceStub(self.channel)

        self.raft_servers = RAFT_SERVERS.copy()
        self.raft_servers.remove(f"{self.server_ip}:{self.server_port}")

        self.channels = {}
        self.stubs = {}
        print(f"SERVER LIST: {self.raft_servers}")
        for server in self.raft_servers:
            try:
                print(f"Raft server {self.server_port}: Connecting to {server}")
                channel = grpc.insecure_channel(server)
                stub = raft_pb2_grpc.RaftServiceStub(channel)
                self.channels[server] = channel
                self.stubs[server] = stub

            except grpc.RpcError as e:
                print(
                    f"Raft server {self.server_port}: Error connecting to {server}: {e}"
                )
                continue

        self.state = RaftServerState.FOLLOWER  # placeholder
        print(f"Raft server {self.server_port}: Initialized as follower.")
        # self.leader = self.find_leader()

        # if self.leader:
        #     print(f"Raft server {self.server_port}: Found leader: {self.leader}")
        # else:
        #     print(f"Raft server {self.server_port}: No leader found.")

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
        for server in self.raft_servers:
            try:
                print(
                    f"Raft server {self.server_port}: Checking if {server} is leader."
                )
                response = self.retry_rpc_call(
                    self.stubs[server].are_you_leader, raft_pb2.Empty()
                )
                if response == raft_pb2.Bool(value=True):
                    print(f"Raft server {self.server_port}: Found leader: {server}")
                    self.leader = server
                    return response
            except grpc.RpcError as e:
                print(f"Raft server {self.server_port}: Error finding leader: {e}")
                continue
        self.leader = None

        return None

    def are_you_leader(self, request, context):
        print(f"Raft server {self.server_port}: are_you_leader called.")
        if self.state == RaftServerState.LEADER:
            return raft_pb2.Bool(value=True)
        else:
            return raft_pb2.Bool(value=False)

    # this bit is executed on the followers - this is the CONSEQUENCE of the RPC call, not the call itself
    def append_entries(self, request, context):
        # return super().append_entries(request, context)

        raise NotImplementedError

    # this bit is executed on the followers - this is the CONSEQUENCE of the RPC call, not the call itself
    def request_vote(self, request, context):
        # return super().request_vote(request, context)

        raise NotImplementedError

    # this is where this server calls the request_vote rpc on other servers
    def send_request_vote(self):
        raise NotImplementedError

    # this is where this server calls the append_entries rpc on other servers
    def send_append_entries(self):
        if self.state == RaftServerState.LEADER:
            raise NotImplementedError
