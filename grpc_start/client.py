from __future__ import print_function

import logging
import sys
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

import grpc
from grpc_start import lock_pb2_grpc
from grpc_start import lock_pb2

channel = grpc.insecure_channel("localhost:50051")
stub = lock_pb2_grpc.LockServiceStub(channel)
id = 0

def status_str(x):
    if x == 0:
        return "Success"
    elif x == 1:
        return "File error"
    else: return "Failure"

def RPC_init():
    global id

    response = stub.client_init(lock_pb2.Int(rc=id))
    id = response.rc
    print("client_init received: " + str(response.rc))

def RPC_lock_acquire(seq):
    # Acquire lock
    response = stub.lock_acquire(lock_pb2.lock_args(client_id=id, seq=seq))
    print("lock_acquire received: " + status_str(response.status))

def RPC_append_file(seq):
    # Append to file
    response = stub.file_append(lock_pb2.file_args(filename="file_1", content="Hello".encode(), client_id=id, seq=seq))
    print("file_append received: " + status_str(response.status))

def RPC_lock_release(seq):
    # Release lock
    response = stub.lock_release(lock_pb2.lock_args(client_id=id, seq=seq))
    print("lock_release received: " + status_str(response.status))

def RPC_client_close():
    # Close client
    response = stub.client_close(lock_pb2.Int(rc=id))
    print("client_close received: " + str(response.rc))


def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    print("Will try to greet world ...")
    
    RPC_init()
    RPC_lock_acquire(1)
    RPC_append_file(2)
    RPC_lock_release(3)
    RPC_client_close()

if __name__ == "__main__":
    logging.basicConfig()
    run()
