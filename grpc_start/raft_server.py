import grpc

from grpc_start import raft_pb2, raft_pb2_grpc  # noqa: F401

class RaftServer(raft_pb2_grpc.RaftServiceServicer):
    def append_entries(self, request, context):
        # return super().append_entries(request, context)

        raise NotImplementedError

    def request_vote(self, request, context):
        # return super().request_vote(request, context)
    
        raise NotImplementedError