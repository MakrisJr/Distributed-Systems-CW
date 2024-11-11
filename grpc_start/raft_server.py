import grpc

from grpc_start import raft_pb2, raft_pb2_grpc  # noqa: F401
from enum import Enum

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

        self.state = RaftServerState.LEADER # placeholder

    def append_entries(self, request, context):
        # return super().append_entries(request, context)

        raise NotImplementedError

    def request_vote(self, request, context):
        # return super().request_vote(request, context)
    
        raise NotImplementedError