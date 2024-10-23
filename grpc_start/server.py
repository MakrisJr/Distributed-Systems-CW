from concurrent import futures
import logging

import grpc
import lock_pb2_grpc
import lock_pb2


class LockServer(lock_pb2_grpc.LockServiceServicer):
    def client_init(self, request, context):
        print("client_init received: " + str(request.rc))
        return lock_pb2.Int(rc=0)
    
    def lock_acquire(self, request, context):
        print("lock_acquire received: " + str(request.client_id))
        return lock_pb2.Response(status=lock_pb2.Status.SUCCESS)
    
    def lock_release(self, request, context):
        print("lock_release received: " + str(request.client_id))
        return lock_pb2.Response(status=lock_pb2.Status.SUCCESS)
    
    def file_append(self, request, context):
        print("file_append received: " + str(request.filename))
        return lock_pb2.Response(status=lock_pb2.Status.SUCCESS)
    
    def client_close(self, request, context):
        print("client_close received: " + str(request.rc))
        return lock_pb2.Int(rc=0)
    

def serve():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    lock_pb2_grpc.add_LockServiceServicer_to_server(LockServer(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig()
    serve()