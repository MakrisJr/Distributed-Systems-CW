from collections import deque
from concurrent import futures

import grpc
import lock_pb2
import lock_pb2_grpc


class LockServer(lock_pb2_grpc.LockServiceServicer):
    def __init__(self):
        self.locked = False
        self.waiting_list = deque()

    def client_init(self, request, context):
        print("client_init called")
        return lock_pb2.Int(rc=0)

    def lock_acquire(self, request, context):
        if self.locked:
            pass
        else:
            self.locked = True
            return lock_pb2.Response(status=lock_pb2.Status.SUCCESS)

    def lock_release(self, request, context):
        raise NotImplementedError("pbbbbbt")

    def file_append(self, request, context):
        raise NotImplementedError("pbbbbbt")

    def client_close(self, request, context):
        raise NotImplementedError("pbbbbbt")


def start_server():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    lock_pb2_grpc.add_LockServiceServicer_to_server(LockServer(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()


if __name__ == "__main__":
    start_server()
