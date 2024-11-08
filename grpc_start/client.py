from __future__ import print_function

import logging
import sys
import threading
import time
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

import grpc  # noqa: E402

from grpc_start import lock_pb2, lock_pb2_grpc  # noqa: E402

channel = grpc.insecure_channel("localhost:50051")
stub = lock_pb2_grpc.LockServiceStub(channel)
client_id = 0

RETRY_LIMIT = 3
RETRY_DELAY = 2
KEEP_ALIVE_INTERVAL = 5
request_history = {}
keep_alive_thread = None
keep_alive_running = False


def status_str(x):
    if x == 0:
        return "Success"
    elif x == 1:
        return "File error"
    elif x == 2:
        return "Failure"
    else:
        return "Sequence error"


def RPC_init():
    global client_id

    response = stub.client_init(lock_pb2.Int(rc=client_id))
    client_id = response.rc
    print("client_init received: " + str(response.rc))
    return response.seq


def retry_rpc_call(rpc_func, *args, **kwargs):
    for attempt in range(RETRY_LIMIT):
        try:
            response = rpc_func(*args, **kwargs)
            return response
        except grpc.RpcError as e:
            print(
                f"RPC call failed with error: {e}. Retrying {attempt + 1}/{RETRY_LIMIT}..."
            )
            time.sleep(RETRY_DELAY)

    print("Failed to receive response after retries.")
    return None


def RPC_keep_alive():
    """Send periodic keep-alive messages to the server to maintain lock ownership."""
    global keep_alive_running
    while keep_alive_running:
        response = retry_rpc_call(
            stub.keep_alive, lock_pb2.lock_args(client_id=client_id)
        )
        if response:
            print("Keep-alive sent, status: " + status_str(response.status))
        else:
            print("Keep-alive failed.")
        time.sleep(KEEP_ALIVE_INTERVAL)


def start_keep_alive():
    """Start the keep-alive mechanism in a separate thread."""
    global keep_alive_thread, keep_alive_running
    keep_alive_running = True
    keep_alive_thread = threading.Thread(target=RPC_keep_alive)
    keep_alive_thread.start()


def stop_keep_alive():
    """Stop the keep-alive mechanism."""
    global keep_alive_running
    keep_alive_running = False
    if keep_alive_thread:
        keep_alive_thread.join()


def RPC_lock_acquire(seq):
    response = retry_rpc_call(
        stub.lock_acquire,
        lock_pb2.lock_args(client_id=client_id, seq=seq),
    )
    if response and response.status == lock_pb2.Status.SUCCESS:
        print("lock_acquire received: " + status_str(response.status))
        start_keep_alive()
        return response.seq
    else:
        print("Failed to acquire lock after retries.")
        return seq


def RPC_append_file(seq):
    response = retry_rpc_call(
        stub.file_append,
        lock_pb2.file_args(
            filename="file_1",
            content="Hello".encode(),
            client_id=client_id,
            seq=seq,
        ),
    )
    if response:
        print("file_append received: " + status_str(response.status))
        return response.seq
    else:
        print("Failed to append to file after retries.")
        return seq


def RPC_lock_release(seq):
    response = retry_rpc_call(
        stub.lock_release,
        lock_pb2.lock_args(client_id=client_id, seq=seq),
    )
    if response and response.status == lock_pb2.Status.SUCCESS:
        print("lock_release received: " + status_str(response.status))
        stop_keep_alive()
        return response.seq
    else:
        print("Failed to release lock after retries.")
        return seq


def RPC_client_close():
    response = retry_rpc_call(stub.client_close, lock_pb2.Int(rc=client_id))
    if response:
        print("client_close received: " + str(response.rc))
    else:
        print("Failed to close client after retries.")


def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    print("Will try to greet world ...")

    seq = RPC_init()
    seq = RPC_lock_acquire(seq)
    seq = RPC_append_file(seq)
    seq = RPC_lock_release(seq)
    RPC_client_close()


if __name__ == "__main__":
    logging.basicConfig()
    run()
