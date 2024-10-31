from __future__ import print_function

import logging
import sys
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

import grpc
from grpc_start import lock_pb2_grpc
from grpc_start import lock_pb2


def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    print("Will try to greet world ...")
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = lock_pb2_grpc.LockServiceStub(channel)

        # Initialise client
        response = stub.client_init(lock_pb2.Int(rc=0))
        print("client_init received: " + str(response.rc))

        # Acquire lock
        response = stub.lock_acquire(lock_pb2.lock_args(client_id=1))
        print("lock_acquire received: " + str(response.status))

        # Release lock
        response = stub.lock_release(lock_pb2.lock_args(client_id=1))
        print("lock_release received: " + str(response.status))

        # Append to file
        response = stub.file_append(lock_pb2.file_args(filename="file_1", content="Hello".encode(), client_id=1))
        print("file_append received: " + str(response.status))

        # Close client
        response = stub.client_close(lock_pb2.Int(rc=0))
        print("client_close received: " + str(response.rc))

if __name__ == "__main__":
    logging.basicConfig()
    run()
