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

        self.current_term = 0
        self.voted_for = None
        self.log = []  # entries all of type LogEntry

        self.commit_index = 0
        self.last_applied = 0

        self.raft_servers = RAFT_SERVERS.copy()
        self.raft_servers.remove(f"{self.server_ip}:{self.server_port}")

        self.establish_channels_stubs()

        self.election_timer = threading.Timer(
            random.randint(MIN_ELECTION_TIMEOUT, MAX_ELECTION_TIMEOUT),
            self.begin_election,
        )
        self.election_lost = False

        if is_leader:
            self.leader_setup()
        else:
            self.follower_setup()

    def leader_setup(self):
        # called when first coming into power
        self.state = RaftServerState.LEADER
        self.send_append_entries()  # TODO send empty heartbeats to all other servers so they know you're leader

        self.next_index = dict()
        self.match_index = dict()

        for follower in self.raft_servers:
            if self.log:
                nextIndex = len(self.log)
            else:
                nextIndex = 0

            self.next_index[follower] = nextIndex
            self.match_index[follower] = nextIndex

        # assumption: if leader elected, it is up-to-date
        # TODO when leader comes online, tell LockServer to actually apply changes

    def follower_setup(self):
        self.state = RaftServerState.FOLLOWER  # placeholder
        print(f"Raft server {self.server_port}: Initialized as follower.")

        self.start_election_timer()

        # is this needed??
        # self.leader = self.find_leader()

        # if self.leader:
        #     print(f"Raft server {self.server_port}: Found leader: {self.leader}")
        # else:
        #     print(f"Raft server {self.server_port}: No leader found.")

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

        self.current_election_tasks = []

    def kill_election(self):
        # new elections can start while a prior election is still running
        # the old one needs to be 'killed' before the new one can start in earnest
        if self.current_election_tasks:
            print("Cancelling previous election tasks")
            for task in self.current_election_tasks:
                task.cancel()  # Cancel the previous election's tasks

            self.current_election_tasks = []

    def send_vote_requests(self):
        # one asynchronous task per vote request
        for server in self.raft_servers:
            stub = self.stubs[server]

            task = asyncio.create_task(
                self.retry_rpc_call(
                    stub.request_vote,
                    raft_pb2.request_vote_args(
                        term=self.current_term,
                        candidateID=int(self.port),
                        lastLogIndex=(len(self.log) - 1),
                        lastLogTerm=self.log[-1].term,
                    ),
                )
            )

            self.current_election_tasks.append(task)

    async def begin_election(self):
        if self.state == RaftServerState.FOLLOWER:
            self.kill_election()

            self.state = RaftServerState.CANDIDATE
            self.election_lost = False
            self.current_term += 1

            # candidate votes for itself
            nr_votes_received = 1

            # one asynchronous task per vote request -- tasks added to election tasks list
            self.send_vote_requests()

            # the election timer should be allowed to fire while waiting for votes
            # but obviously begin_election is only called once the election timer has already concluded
            # therefore, needs to be restarted here
            self.start_election_timer()

            # returns tasks in order of completion
            for completed_task in asyncio.as_completed(self.current_election_tasks):
                # counting votes
                try:
                    response = await completed_task
                    if response.voteGranted:
                        nr_votes_received += 1

                    # election WIN
                    if nr_votes_received >= 2:
                        print("Cancelling remaining tasks - this one is the new leader")
                        self.leader_setup()

                        for task in self.current_election_tasks:
                            task.cancel()  # Cancel remaining tasks
                        break

                except asyncio.CancelledError:
                    print("Task was cancelled")

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
        candidate_generated_no = request.generatedNo
        candidate_id = request.leaderID

        if candidate_generated_no > self.generated_no or (
            candidate_generated_no == self.generated_no and candidate_id > self.id
        ):
            return raft_pb2.ReqVoteResponse(voteGranted=True)

        return raft_pb2.ReqVoteResponse(voteGranted=False)

    # this is where this server calls the append_entries rpc on other servers
    def send_append_entries(self, entries: List[log.LogEntry]):
        if self.state == RaftServerState.LEADER:
            raise NotImplementedError
