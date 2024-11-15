import sys
import threading
import time
from pathlib import Path

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

from grpc_start.client import Client  # noqa: E402
from grpc_start.server import LockServer, reset_files  # noqa: E402

FILE_PATH = "files/"


def test_packet_delay():
    client1 = Client(1)
    client2 = Client(2)

    reset_files()
    server = LockServer()
    server.serve()

    print("Server started")

    time.sleep(1)
    # test packet delay
    client1.RPC_client_init()
    client2.RPC_client_init()

    client1.RPC_lock_acquire()
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    time.sleep(5)

    client1.RPC_append_file("0", "test1client1")

    # terminate thread one with a keyboard interrupt

    if thread2.is_alive():
        thread2.join()

    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if not message == "":
        return False
    return True
    # expected result: client1 receives LOCK_EXPIRED, client2 has the lock and message is not written to file


def test_client_packet_loss():
    # since we are using TCP, the only way to simulate packet drop is to delay the packet until the client times out.
    client1 = Client(1)
    client2 = Client(2)

    server = LockServer()

    reset_files()
    server.serve()

    print("Server started")
    # test packet delay
    client1.RPC_client_init()
    client2.RPC_client_init()

    client2.RPC_lock_acquire()
    time.sleep(0.1)

    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()

    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    thread1.join()
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    time.sleep(0.5)
    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "BA":
        return True
    print(message)
    return False
    # c2 gets the lock, appends 'B', c1 gets lock, writes 'A'


def test_server_packet_loss():
    client1 = Client(1)
    client2 = Client(2)
    server = LockServer()

    reset_files()
    server.serve()
    print("Server started")

    client1.RPC_client_init()
    client2.RPC_client_init()

    client1.RPC_lock_acquire()
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # sends lock_acquire again
    client1.RPC_lock_acquire()

    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    thread2.join()
    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    time.sleep(0.5)
    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "AB":
        return True
    print(message)
    return False


def test_duplicated_packets():
    # duplicated lock_release shall not release other clients' locks
    client1 = Client(1)
    client2 = Client(2)
    server = LockServer()

    reset_files()
    server.serve()
    print("Server started")

    client1.RPC_client_init()
    client2.RPC_client_init()

    client1.RPC_lock_acquire()
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()
    print(f"Client 1 seq: {client1.seq}")
    client1.RPC_append_file("0", "A", lost_after_server=True)
    print(f"Client 1 seq: {client1.seq}")
    client1.RPC_append_file("0", "A")  # fails because of wrong SEQ number
    print(f"Client 1 seq: {client1.seq}")
    # send duplicated lock_release
    client1.RPC_lock_release()
    print(f"Client 1 seq: {client1.seq}")
    time.sleep(0.1)
    result = client1.RPC_lock_release()
    if result:
        return False
    print(f"Client 1 seq: {client1.seq}")

    thread2.join()
    client2.RPC_append_file("0", "B")

    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()

    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    thread1.join()
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    time.sleep(0.5)
    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "ABBA":
        return True
    print(message)
    return False


def test_combined_network_failures():
    # test combined network failures
    client1 = Client(1)
    client2 = Client(2)
    server = LockServer()

    reset_files()
    server.serve()
    print("Server started")

    client1.RPC_client_init()
    client2.RPC_client_init()

    client1.RPC_lock_acquire()
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    client1.RPC_append_file("0", "1")
    client1.RPC_append_file(
        "0", "A", lost_before_server=True
    )  # lost before reaching server
    client1.RPC_append_file("0", "A", lost_after_server=True)  # response is lost
    client1.RPC_append_file("0", "A")  # will have the previous SEQ number

    client1.RPC_lock_release()

    thread2.join()
    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    time.sleep(0.5)
    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "1AB":
        return True
    return False


# CLIENT FAILS/STUCK:


def test_stuck_before_editing_file():
    client1 = Client(1)
    client2 = Client(2)
    server = LockServer()

    reset_files()
    server.serve()
    print("Server started")

    client1.RPC_client_init()
    client2.RPC_client_init()

    client1.RPC_lock_acquire()
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # garbage collection, client1 loses lock
    thread2.join()
    client2.RPC_append_file("0", "B")
    client1.RPC_append_file("0", "A")  # lock expired
    client2.RPC_append_file("0", "B")

    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()
    client2.RPC_lock_release()

    thread1.join()
    client1.RPC_append_file("0", "A")
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    time.sleep(0.5)
    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "BBAA":
        return True
    print(message)
    return False


def test_stuck_after_editing_file():
    client1 = Client(1)
    client2 = Client(2)
    server = LockServer()

    reset_files()
    server.serve()
    print("Server started")

    client1.RPC_client_init()
    client2.RPC_client_init()

    client1.RPC_lock_acquire()
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    client1.RPC_append_file("0", "A", lost_after_server=True)
    # garbage collection happens
    thread2.join()
    # client2 gets the lock. client 1's append is lost
    client2.RPC_append_file("0", "B")
    client1.RPC_append_file("0", "A")  # lock expired

    client2.RPC_append_file("0", "B")

    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()
    client2.RPC_lock_release()

    thread1.join()
    client1.RPC_append_file("0", "A")
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()
    time.sleep(0.5)
    server.stop()

    # read file to check if message was written
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    if message == "BBAA":
        return True
    return False


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

    client1 = Client()
    client1.RPC_client_init()

    time.sleep(15)

    server1.stop()
    server2.stop()
    server3.stop()

    return True


if __name__ == "__main__":
    # run all tests
    failed_tests = []
    # if not test_packet_delay():
    #     failed_tests.append("test_packet_delay")
    #     print("test_packet_delay failed")

    # if not test_client_packet_loss():
    #     failed_tests.append("test_client_packet_loss")
    #     print("test_client_packet_loss failed")

    # if not test_server_packet_loss():
    #     failed_tests.append("test_server_packet_loss")
    #     print("test_server_packet_loss failed")

    # if not test_duplicated_packets():
    #     failed_tests.append("test_duplicated_packets")
    #     print("test_duplicated_packets failed")

    # if not test_combined_network_failures():
    #     failed_tests.append("test_combined_network_failures")
    #     print("test_combined_network_failures failed")

    # if not test_stuck_before_editing_file():
    #     failed_tests.append("test_stuck_before_editing_file")
    #     print("test_stuck_before_editing_file failed")

    # if not test_stuck_after_editing_file():
    #     failed_tests.append("test_stuck_after_editing_file")
    #     print("test_stuck_after_editing_file failed")

    if not test_single_server_fails_lock_free():
        failed_tests.append("test_single_server_fails_lock_free")
        print("test_single_server_fails_lock_free failed")
    # if not test_raft():
    #     failed_tests.append("test_raft")
    #     print("test_raft failed")

    if len(failed_tests) == 0:
        print("All tests passed")
    else:
        print(f"Failed tests: {failed_tests}")
