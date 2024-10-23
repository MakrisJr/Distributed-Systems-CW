from concurrent import futures

import grpc
import lock_pb2
import lock_pb2_grpc

class LockServer(lock_pb2_grpc.LockServiceServicer):
    def client_init(self, request, context):
        print("client_init called")
        return lock_pb2.Response(status=lock_pb2.Status.SUCCESS) # is this sensible????
    
    def lock_acquire(self, request, context):
        raise NotImplementedError("pbbbbbt")
    
    def client_close(self, request, context):
        raise NotImplementedError("pbbbbbt")
        

port = "50051"
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
lock_pb2_grpc.add_LockServiceServicer_to_server(LockServer(), server)
server.add_insecure_port("[::]:" + port)
server.start()
print("Server started, listening on " + port)
server.wait_for_termination()   
