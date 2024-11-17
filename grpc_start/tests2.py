import sys
import threading
import time
import warnings
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

from grpc_start.client import Client  # noqa: E402
from grpc_start.server import LockServer, reset_files  # noqa: E402

FILE_PATH = "files/"


def test_single_server_fails_lock_free():
    reset_files()
    server = LockServer()
    server.serve()

    client1 = Client(1)
    client1.RPC_client_init()
    client1.RPC_lock_acquire()
    client1.RPC_append_file("0", "A")
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    server.stop()

    print("Server stopped.")
    time.sleep(0.5)
    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()

    server = LockServer()
    server.serve()

    thread1.join()

    client1.RPC_append_file("0", "1")
    client1.RPC_lock_release()

    server.stop()

    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "AA1":
        return True
    return False


def test_raft():
    # remove files in ./log/
    reset_files()
    server1 = LockServer("localhost", 50051)
    server2 = LockServer("localhost", 50052)
    server3 = LockServer("localhost", 50053)

    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    time.sleep(7)

    client1 = Client(1)
    client1.RPC_client_init()

    time.sleep(15)

    servers = [server1, server2, server3]

    # Stop all servers
    for server in servers:
        server.stop()

    print("Servers stopped")

    return True


def test_single_server_fails_lock_held():
    client1 = Client(1)
    client2 = Client(2)
    server = LockServer()

    reset_files()
    server.serve()
    print("Server started")

    client1.RPC_client_init()
    client2.RPC_client_init()

    thread1 = threading.Thread(
        target=client1.RPC_lock_acquire
    )  # client 1 should acquire lock
    thread1.start()

    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    thread1.join()
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()  # now, client 2 should get the lock

    thread2.join()
    client2.RPC_append_file("0", "B")

    time.sleep(2)
    server.stop()

    thread3 = threading.Thread(
        target=client2.RPC_append_file, args=("0", "B")
    )  # starts with failure, retries
    thread3.start()

    server = LockServer()
    server.serve()  # server comes back online, client 2 append should work again

    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()

    thread3.join()
    client2.RPC_lock_release()

    thread1.join()
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()
    client1.RPC_client_close()

    client2.RPC_client_close()

    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    return message == "ABBA"


if __name__ == "__main__":
    # ignore warnings

    warnings.filterwarnings("ignore")
    # run all tests
    failed_tests = []

    if not test_single_server_fails_lock_free():
        failed_tests.append("test_single_server_fails_lock_free")
        print("test_single_server_fails_lock_free failed")
    else:
        print("test_single_server_fails_lock_free passed")

    time.sleep(3)

    if not test_single_server_fails_lock_held():
        failed_tests.append("test_single_server_fails_lock_held")
        print("test_single_server_fails_lock_held failed")

    time.sleep(3)

    if len(failed_tests) == 0:
        print("All tests passed")
    else:
        print(f"Failed tests: {failed_tests}")
