import asyncio
import random
import threading
import time
from enum import Enum
from typing import List

import grpc

from grpc_start import log_entries as log
from grpc_start import raft_pb2, raft_pb2_grpc  # noqa: F401

RAFT_SERVERS = ["localhost:50051", "localhost:50052", "localhost:50053"]


class RaftServerState(Enum):
    LEADER = 1
    FOLLOWER = 2


# probably change these - raft paper says 150-300 ms
MIN_ELECTION_TIMEOUT = 1
MAX_ELECTION_TIMEOUT = 10

RETRY_LIMIT = 3
RETRY_DELAY = 2


class RaftServer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, ip, port, is_leader=False):
        self.server_ip = ip
        self.server_port = port

        self.log = []  # entries all of type LogEntry

        self.raft_servers = RAFT_SERVERS.copy()
        self.raft_servers.remove(f"{self.server_ip}:{self.server_port}")

        self.establish_channels_stubs()

        self.election_timer = threading.Timer(
            random.randint(MIN_ELECTION_TIMEOUT, MAX_ELECTION_TIMEOUT),
            self.begin_election,
        )

        if is_leader:
            self.leader_setup()
        else:
            self.follower_setup()

    def leader_setup(self):
        # called when first coming into power
        self.state = RaftServerState.LEADER
        self.send_append_entries()  # TODO send empty heartbeats to all other servers so they know you're leader


    def follower_setup(self):
        self.state = RaftServerState.FOLLOWER  # placeholder
        print(f"Raft server {self.server_port}: Initialized as follower.")

        self.start_election_timer()

    def establish_channels_stubs(self):
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

    def start_election_timer(self):
        """Start or restart the election timer for this Raft node."""
        if self.election_timer:
            self.election_timer.cancel()

        self.election_timer = threading.Timer(
            random.randint(MIN_ELECTION_TIMEOUT, MAX_ELECTION_TIMEOUT),
            self.begin_election,
        )
        self.election_timer.start()

    def begin_election(self):
        if self.state == RaftServerState.FOLLOWER:
            generated_no = random.randint(1, 10)

            for server in self.raft_servers:
                if server != self.leader: 
                    # there is only one other follower
                    response = self.retry_rpc_call(
                        self.stubs[server].request_vote,
                        raft_pb2.ElectionContest(
                            generatedNo=generated_no
                        )
                    )

                    if response.generatedNo < generated_no:
                        self.leader = server
                        self.
                    elif response.generatedNo > generated_no:
                        self.leader_setup()
                    else:
                        self.start_election_timer()

    # this bit is executed on the followers - this is the CONSEQUENCE of the RPC call, not the call itself
    def append_entries(self, request, context):
        # Step 1
        if request.term < self.current_term:
            return raft_pb2.AppendResponse(term=self.current_term, success=False)

        if request.term > self.current_term:
            self.current_term = request.term
            self.voted_for = None

            self.kill_election()  # if any election running on this node, force-kills it
            self.state = RaftServerState.FOLLOWER

            self.leader = request.leaderID

        # Step 2
        if (
            len(self.log) <= request.prevLogIndex
            and self.log[request.prevLogIndex].term != request.prevLogIndex
        ):
            return raft_pb2.AppendResponse(term=self.current_term, success=False)

        # Step 3
        index = request.prevLogIndex + 1
        i = 0
        for i, entry in enumerate(request.entries):
            if index < len(self.log):
                if self.log[index].term != entry.term:
                    self.log = self.log[:index]
                    break
            else:
                break
            index += 1

        # Step 4
        if request.entries:
            for entry in request.entries[i:]:
                self.log.append(log.log_entry_grpc_to_object(entry))

        # Step 5
        if request.leaderCommit > self.commit_index:
            self.commit_index = min(request.leaderCommit, len(self.log) - 1)

        return raft_pb2.AppendResponse(term=self.current_term, success=True)

    # this bit is executed on the voters, not the candidate - this is the CONSEQUENCE of the RPC call, not the call itself
    def request_vote(self, request, context):
        # return super().request_vote(request, context)
        generated_no = random.randint(1, 10)
        
        self.election_timer.cancel()

        if request.generated_no > generated_no:
            self.leader = context.peer()
            self.follower_setup()
        elif request.generated_no < generated_no:
            self.leader_setup()
        
        return raft_pb2.ElectionContest(generatedNo=generated_no)

    # this is where this server calls the append_entries rpc on other servers
    def send_append_entries(self, entries: List[log.LogEntry]):
        if self.state == RaftServerState.LEADER:
            raise NotImplementedError
