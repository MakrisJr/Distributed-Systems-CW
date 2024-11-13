import asyncio
import random
import threading
import time
from enum import Enum

import grpc

from grpc_start import commands as cs
from grpc_start import raft_pb2, raft_pb2_grpc  # noqa: F401


class RaftServerState(Enum):
    LEADER = 1
    FOLLOWER = 2
    CANDIDATE = 3


class LogEntry:
    def __init__(self, term: int, command: cs.Command):
        self.term = term
        self.command = command


# probably change these - raft paper says 150-300 ms
MIN_ELECTION_TIMEOUT = 1
MAX_ELECTION_TIMEOUT = 2

RETRY_LIMIT = 3
RETRY_DELAY = 2

RAFT_SERVER_PORTS = [
    "50051",
    "50052",
    "50053",
]  # find less stupid way of doing this lmao


class RaftServer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, port):
        self.current_term = 0
        self.voted_for = None
        self.log = []  # entries all of type LogEntry

        self.commit_index = 0
        self.last_applied = 0

        self.next_index = 0
        self.match_index = 0

        self.state = RaftServerState.FOLLOWER  # placeholder

        self.port = port

        self.election_timer = threading.Timer(
            random.randint(MIN_ELECTION_TIMEOUT, MAX_ELECTION_TIMEOUT),
            self.begin_election,
        )

        self.election_lost = False

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

    def kill_old_election(self):
        # new elections can start while a prior election is still running
        # the old one needs to be 'killed' before the new one can start in earnest
        if self.current_election_tasks:
            print("Cancelling previous election tasks")
            for task in self.current_election_tasks:
                task.cancel()  # Cancel the previous election's tasks

            self.current_election_tasks = []

    def send_vote_requests(self):
        # one asynchronous task per vote request
        for port in RAFT_SERVER_PORTS:
            if port != self.port:
                channel = grpc.aio.insecure_channel("localhost:" + port)
                stub = raft_pb2_grpc.RaftServiceStub(channel)

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
            self.kill_old_election()

            self.state = RaftServerState.CANDIDATE
            self.election_lost = False
            self.current_term += 1

            # send vote requests to other raft nodes
            nr_votes_received = 1

            # one asynchronous task per vote request -- tasks added to election tasks list
            self.send_vote_requests()

            # the election timer should be allowed to fire while waiting for votes
            # but obviously begin_election is only called once the election timer has already concluded
            # therefore, needs to be restarted here
            self.start_election_timer()

            # returns tasks in order of completion
            for completed_task in asyncio.as_completed(self.current_election_tasks):
                # election LOSS - break out of loop
                if self.election_lost:  # becomes true in append_entries
                    print("Cancelling remaining tasks - other leader found")
                    for task in self.current_election_tasks:
                        task.cancel()  # Cancel remaining tasks
                    break

                # counting votes
                try:
                    response = await completed_task
                    if response.voteGranted:
                        nr_votes_received += 1

                    # election WIN
                    if nr_votes_received >= 2:
                        print("Cancelling remaining tasks - this one is the new leader")
                        self.state = RaftServerState.LEADER
                        self.send_append_entries()  # placeholder -- intended behaviour is to send heartbeats to all other servers, so they know you're a leader

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
            self.state = RaftServerState.FOLLOWER

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
        for entry in request.entries[i:]:
            self.log.append(entry)

        # Step 5
        if request.leaderCommit > self.commit_index:
            self.commit_index = min(request.leaderCommit, len(self.log) - 1)

        return raft_pb2.AppendResponse(term=self.current_term, success=True)

    # this bit is executed on the voters, not the candidate - this is the CONSEQUENCE of the RPC call, not the call itself
    def request_vote(self, request, context):
        # return super().request_vote(request, context)
        candidate_term = request.term
        candidate_id = request.candidateID
        candidate_last_log_index = request.lastLogIndex
        candidate_last_log_term = request.lastLogTerm

        if candidate_term >= self.current_term:
            if not self.voted_for or self.voted_for == candidate_id:
                if (
                    self.log[-1].term <= candidate_last_log_term
                    or len(self.log) - 1 <= candidate_last_log_index
                ):
                    return raft_pb2.ReqVoteResponse(
                        term=self.current_term, voteGranted=True
                    )

        return raft_pb2.ReqVoteResponse(term=self.current_term, voteGranted=False)

    # this is where this server calls the append_entries rpc on other servers
    def send_append_entries(self):
        if self.state == RaftServerState.LEADER:
            raise NotImplementedError
