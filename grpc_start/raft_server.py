from enum import Enum

from grpc_start import raft_pb2, raft_pb2_grpc  # noqa: F401


class RaftServerState(Enum):
    LEADER = 1
    FOLLOWER = 2
    CANDIDATE = 3


class RaftServer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self):
        self.current_term = 0
        self.voted_for = None
        self.log = []

        self.commit_index = 0
        self.last_applied = 0

        self.next_index = 0
        self.match_index = 0

        self.state = RaftServerState.FOLLOWER  # placeholder

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

    # this bit is executed on the followers - this is the CONSEQUENCE of the RPC call, not the call itself
    def request_vote(self, request, context):
        # return super().request_vote(request, context)

        raise NotImplementedError

    # this is where this server calls the request_vote rpc on other servers
    def send_request_vote(self):
        raise NotImplementedError

    # this is where this server calls the append_entries rpc on other servers
    def send_append_entries(self):
        if self.state != RaftServerState.LEADER:
            return
