import grpc
import lock_pb2_grpc
import lock_pb2

def RPC_init():
    raise NotImplementedError("pbbbbbt")

def RPC_lock_acquire():
    raise NotImplementedError("pbbbbbt")

def RPC_lock_release():
    raise NotImplementedError("pbbbbbt")

def RPC_append_file():
    raise NotImplementedError("pbbbbbt")

def RPC_close():
    raise NotImplementedError("pbbbbbt")

if __name__ == "__main__":
    channel = grpc.insecure_channel('localhost:50051')
    stub = lock_pb2_grpc.LockServiceStub(channel)

    response = stub.client_init(lock_pb2.Int(rc=0))
    print(str(response.rc))