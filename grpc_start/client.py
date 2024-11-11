from __future__ import print_function

import logging
import sys
import time
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

import grpc  # noqa: E402

from grpc_start import lock_pb2, lock_pb2_grpc  # noqa: E402

channel = grpc.insecure_channel("localhost:50051")
stub = lock_pb2_grpc.LockServiceStub(channel)

RETRY_LIMIT = 3
RETRY_DELAY = 2
DEBUG = True


def status_str(x):
    if x == 0:
        return "Success"
    elif x == 1:
        return "File error"
    elif x == 2:
        return "Failure"
    else:
        return "Sequence error"


class Client:
    def __init__(self):
        self.client_id = 0
        self.seq = 0
        self.request_history = {}  # {seq: request}

    def RPC_client_init(self):
        try:
            response = stub.client_init(lock_pb2.Int(rc=self.client_id))
            self.client_id = response.rc
            self.seq = response.seq  # sequence number of next expected request
            if DEBUG:
                print("client_init: " + str(response.rc))
            self.request_history[self.seq - 1] = "client_init"
            return True
        except grpc.RpcError as e:
            print(
                f"Client {self.client_id}: RPC call client init failed with error: {e}"
            )
            return False

    def retry_rpc_call(self, rpc_func, *args, **kwargs):
        for attempt in range(RETRY_LIMIT):
            try:
                response = rpc_func(*args, **kwargs)
                return response
            except grpc.RpcError as e:
                print(
                    f"Client {self.client_id}: RPC call failed with error: {e}. Retrying {attempt + 1}/{RETRY_LIMIT}..."
                )
                time.sleep(RETRY_DELAY)

        print(
            f"Client {self.client_id}: RETRY_RPC_CALL: Failed to receive response after retries."
        )
        return None

    def RPC_lock_acquire(self):
        response = self.retry_rpc_call(
            stub.lock_acquire,
            lock_pb2.lock_args(client_id=self.client_id, seq=self.seq),
        )
        if response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            return False
        if response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: lock_acquire received: "
                + status_str(response.status)
            )
            self.seq = response.seq
            self.request_history[self.seq] = "lock_acquire"
            return True
        else:
            print(f"Client {self.client_id}: Failed. Status: {response.status}")
            return False

    def RPC_append_file(
        self, file_number, text, lost_before_server=False, lost_after_server=False
    ):
        if lost_before_server:  # simulate packet loss
            if DEBUG:
                print(f"Client {self.client_id}: Simulating packet loss.")
            return False

        response = self.retry_rpc_call(
            stub.file_append,
            lock_pb2.file_args(
                filename=f"file_{file_number}",
                content=f"{text}".encode(),
                client_id=self.client_id,
                seq=self.seq,
            ),
        )
        if lost_after_server:
            return False
        if response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: file_append received: "
                + status_str(response.status)
            )
            self.request_history[self.seq] = ("file_append", file_number, text)
            self.seq = response.seq
            return True
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            if DEBUG:
                print(
                    f"Client {self.client_id}: seq={self.seq}, response.seq={response.seq}"
                )
            if response.seq > self.seq:
                # the server has processed the request already and updated the sequence number, but was lost on the way back
                self.seq = response.seq
            return False
        elif response and response.status == lock_pb2.Status.LOCK_EXPIRED:
            print(f"Client {self.client_id}: Lock expired. Need to recover.")
            self.seq = response.seq
            return False
        else:  # response and response.status == lock_pb2.Status.FILE_ERROR:
            print(
                f"Client {self.client_id}: Failed to append file after {RETRY_LIMIT} retries."
            )
            self.seq = response.seq
            return False

    def RPC_lock_release(self):
        response = self.retry_rpc_call(
            stub.lock_release,
            lock_pb2.lock_args(client_id=self.client_id, seq=self.seq),
        )
        if response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: lock_release received: "
                + status_str(response.status)
            )
            self.seq = response.seq
            self.request_history[self.seq] = "lock_release"
            return True
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            return False
        else:  # response and response.status == lock_pb2.Status.FAILURE:
            self.seq = response.seq
            print(f"Client {self.client_id}: Failed to release lock after retries.")
            return False

    def RPC_client_close(self):
        response = self.retry_rpc_call(
            stub.client_close, lock_pb2.Int(rc=self.client_id, seq=self.seq)
        )
        if response and response.status == lock_pb2.Status.SUCCESS:
            print(
                f"Client {self.client_id}: client_close received: "
                + status_str(response.status)
            )
            self.request_history[self.seq] = "client_close"
            self.seq = response.seq
            return True
        elif response and response.status == lock_pb2.Status.SEQ_ERROR:
            print(f"Client {self.client_id}: Sequence error. Need to recover.")
            return False
        else:
            self.seq = response.seq
            print(f"Client {self.client_id}: Failed to close client after retries.")
            return False

    #


# def run():
#     # NOTE(gRPC Python Team): .close() is possible on a channel and should be
#     # used in circumstances in which the with statement does not fit the needs
#     # of the code.
#     print("Will try to greet world ...")

#     client = Client()
#     client.RPC_client_init()
#     client.RPC_lock_acquire()
#     client.RPC_append_file(1, "Hello, world!")
#     client.RPC_lock_release()
#     client.RPC_client_close()


if __name__ == "__main__":
    logging.basicConfig()
    # run()
