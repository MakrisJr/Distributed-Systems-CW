import grpc
import lock_pb2_grpc
import lock_pb2

channel = grpc.insecure_channel('localhost:50051')
stub = lock_pb2_grpc.LockServiceStub(channel)

response = stub.client_init(lock_pb2.Int(rc=0))
print(str(response.status))

# from __future__ import print_function

# import logging

# import grpc
# import lock_pb2
# import lock_pb2_grpc


# def run():
#     # NOTE(gRPC Python Team): .close() is possible on a channel and should be
#     # used in circumstances in which the with statement does not fit the needs
#     # of the code.
#     print("Will try to greet world ...")
#     with grpc.insecure_channel("localhost:50051") as channel:
#         stub = lock_pb2_grpc.LockServiceStub(channel)
#         # call all methods:
#         response = stub.client_init(lock_pb2.Int(rc=0))
#         print("client_init received: " + str(response.rc))
#         response = stub.lock_acquire(lock_pb2.lock_args(client_id=1))
#         print("lock_acquire received: " + str(response.status))


# if __name__ == "__main__":
#     logging.basicConfig()
#     run()