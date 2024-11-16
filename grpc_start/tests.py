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


# Complex test cases
def replica_node_failures_fast_recovery():
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

    client1 = Client(1)
    client2 = Client(2)

    reset_files()

    # Start server threads
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    print("Servers started")

    time.sleep(5)

    # Initialize clients
    client1.RPC_client_init()
    print("Client 1 initialized")
    client2.RPC_client_init()
    print("Client 2 initialized")

    # Client 1 acquires lock and appends to all files
    client1.RPC_lock_acquire()
    print("Client 1 acquired lock")
    client1.RPC_append_file("1", "A")
    print("Client 1 appended 'A' to file 1")
    client1.RPC_append_file("2", "A")
    print("Client 1 appended 'A' to file 2")

    # Simulate Server 2 failure
    server2.stop()
    print("Server 2 stopped")
    time.sleep(1)

    # Continue appending with Server 2 down
    client1.RPC_append_file("3", "A")
    print("Client 1 appended 'A' to file 3")
    client1.RPC_lock_release()
    print("Client 1 released lock")

    # Restart Server 2
    thread2 = threading.Thread(target=server2.serve)
    thread2.start()
    print("Server 2 restarting...")
    time.sleep(5)  # Allow Server 2 to fully recover

    # Client 2 acquires lock and appends to all files
    client2.RPC_lock_acquire()
    print("Client 2 acquired lock")
    client2.RPC_append_file("1", "B")
    print("Client 2 appended 'B' to file 1")
    client2.RPC_append_file("2", "B")
    print("Client 2 appended 'B' to file 2")
    client2.RPC_append_file("3", "B")
    print("Client 2 appended 'B' to file 3")
    client2.RPC_lock_release()
    print("Client 2 released lock")

    servers = [server1, server2, server3]

    # Stop all servers
    for server in servers:
        server.stop()

    print("Servers stopped")

    print("Checking files")
    expected = set(["AB", "BA"])
    first_content = None

    for server in servers:
        print(f"Checking files in {server.file_folder}")
        for i in range(1, 4):
            try:
                with open(f"{server.file_folder}/file_{i}", "r") as file:
                    content = file.read()
                    if content not in expected:
                        print(
                            f"Test failed for {server.file_folder}/file_{i}: {content} (unexpected content)"
                        )
                        exit(1)
                    if first_content is None:
                        first_content = content
                    elif content != first_content:
                        print(
                            f"Inconsistent content detected: {server.file_folder}/file_{i} contains {content}, expected {first_content}"
                        )
                        exit(1)

            except FileNotFoundError:
                print(f"File {server.file_folder}/file_{i} not found")
                exit(1)


def replica_node_failures_slow_recovery():
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

    client1 = Client(1)
    client2 = Client(2)

    reset_files()

    # Start server threads
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    print("Servers started")

    time.sleep(5)

    # Initialize clients
    client1.RPC_client_init()
    print("Client 1 initialized")
    client2.RPC_client_init()
    print("Client 2 initialized")

    # Client 1 acquires lock and appends to all files
    client1.RPC_lock_acquire()
    print("Client 1 acquired lock")
    client1.RPC_append_file("1", "A")
    print("Client 1 appended 'A' to file 1")
    client1.RPC_append_file("2", "A")
    print("Client 1 appended 'A' to file 2")

    # Simulate Server 2 failure
    server2.stop()
    print("Server 2 stopped")
    time.sleep(10)

    # Continue appending with Server 2 down
    client1.RPC_append_file("3", "A")
    print("Client 1 appended 'A' to file 3")
    client1.RPC_lock_release()
    print("Client 1 released lock")

    # Restart Server 2
    thread2 = threading.Thread(target=server2.serve)
    thread2.start()
    print("Server 2 restarting...")
    time.sleep(5)  # Allow Server 2 to fully recover

    # Client 2 acquires lock and appends to all files
    client2.RPC_lock_acquire()
    print("Client 2 acquired lock")
    client2.RPC_append_file("1", "B")
    print("Client 2 appended 'B' to file 1")
    client2.RPC_append_file("2", "B")
    print("Client 2 appended 'B' to file 2")
    client2.RPC_append_file("3", "B")
    print("Client 2 appended 'B' to file 3")
    client2.RPC_lock_release()
    print("Client 2 released lock")

    servers = [server1, server2, server3]

    # Stop all servers
    for server in servers:
        server.stop()

    print("Servers stopped")

    print("Checking files")
    expected = set(["AB", "BA"])
    first_content = None

    for server in servers:
        print(f"Checking files in {server.file_folder}")
        for i in range(1, 4):
            try:
                with open(f"{server.file_folder}/file_{i}", "r") as file:
                    content = file.read()
                    if content not in expected:
                        print(
                            f"Test failed for {server.file_folder}/file_{i}: {content} (unexpected content)"
                        )
                        exit(1)
                    if first_content is None:
                        first_content = content
                    elif content != first_content:
                        print(
                            f"Inconsistent content detected: {server.file_folder}/file_{i} contains {content}, expected {first_content}"
                        )
                        exit(1)

            except FileNotFoundError:
                print(f"File {server.file_folder}/file_{i} not found")
                exit(1)


def primary_node_failures_slow_recovery_outside_critical_section():
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

    client1 = Client(1)
    client2 = Client(2)
    client3 = Client(3)

    reset_files()

    # Start server threads
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    print("Servers started")

    time.sleep(5)

    # Initialize clients
    client1.RPC_client_init()
    print("Client 1 initialized")
    client2.RPC_client_init()
    print("Client 2 initialized")
    client3.RPC_client_init()
    print("Client 3 initialized")

    # Client 1 acquires lock and appends to one file 5 times
    client1.RPC_lock_acquire()
    print("Client 1 acquired lock")
    for _ in range(5):
        client1.RPC_append_file("1", "A")
    client1.RPC_lock_release()
    print("Client 1 released lock")

    # Simulate Server 1 failure
    server1.stop()
    print("Server 1 stopped")
    time.sleep(2)

    # Client 2 acquires lock and appends to one file 5 times
    client2.RPC_lock_acquire()
    print("Client 2 acquired lock")
    for _ in range(5):
        client2.RPC_append_file("1", "B")
    client2.RPC_lock_release()

    # Client 3 acquires lock and appends to one file 5 times
    client3.RPC_lock_acquire()
    print("Client 3 acquired lock")
    for _ in range(5):
        client3.RPC_append_file("1", "C")
    client3.RPC_lock_release()

    # Restart Server 1
    thread1 = threading.Thread(target=server1.serve)
    thread1.start()
    print("Server 1 restarting...")
    time.sleep(5)  # Allow Server 1 to fully recover

    servers = [server1, server2, server3]

    # Stop all servers
    for server in servers:
        server.stop()

    print("Servers stopped")

    print("Checking files")
    # expect file 1 on every server to contain "AAAAABBBBBCCCCC"
    expected = "AAAAABBBBBCCCCC"
    for server in servers:
        print(f"Checking files in {server.file_folder}")
        try:
            with open(f"{server.file_folder}/file_1", "r") as file:
                content = file.read()
                if content != expected:
                    print(
                        f"Test failed for {server.file_folder}/file_1: {content} (unexpected content)"
                    )
                    exit(1)
        except FileNotFoundError:
            print(f"File {server.file_folder}/file_1 not found")
            exit(1)


def primary_node_failures_slow_recovery_during_critical_sections_and_test_for_atomicity():
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

    client1 = Client(1)
    client2 = Client(2)
    client3 = Client(3)

    reset_files()

    # Start server threads
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    print("Servers started")

    time.sleep(5)

    # Initialize clients
    client1.RPC_client_init()
    print("Client 1 initialized")
    client2.RPC_client_init()
    print("Client 2 initialized")
    client3.RPC_client_init()
    print("Client 3 initialized")

    # Client 1 acquires lock and appends to one file 20 times
    client1.RPC_lock_acquire()
    print("Client 1 acquired lock")
    for _ in range(20):
        client1.RPC_append_file("1", "A")
    client1.RPC_lock_release()
    print("Client 1 released lock")

    # Simulate Server 1 failure
    server1.stop()
    print("Server 1 stopped")
    time.sleep(10)

    # Client 2 acquires lock and appends to one file 20 times
    client2.RPC_lock_acquire()
    print("Client 2 acquired lock")
    for _ in range(10):
        client2.RPC_append_file("1", "B")

    # Simulate Server 1 failure
    server1.stop()
    print("Server 1 stopped")
    time.sleep(2)

    for _ in range(10):
        client2.RPC_append_file("1", "B")

    client2.RPC_lock_release()

    # Client 3 acquires lock and appends to one file 20 times
    client3.RPC_lock_acquire()
    print("Client 3 acquired lock")
    for _ in range(20):
        client3.RPC_append_file("1", "C")
    client3.RPC_lock_release()

    # Restart Server 1
    thread1 = threading.Thread(target=server1.serve)
    thread1.start()
    print("Server 1 restarting...")
    time.sleep(10)  # Allow Server 1 to fully recover

    servers = [server1, server2, server3]

    # Stop all servers
    for server in servers:
        server.stop()

    print("Servers stopped")

    print("Checking files")
    # expect file 1 on every server to contain "A" * 20 + "B" * 20 + "C" * 20
    expected = "A" * 20 + "B" * 20 + "C" * 20
    for server in servers:
        print(f"Checking files in {server.file_folder}")
        try:
            with open(f"{server.file_folder}/file_1", "r") as file:
                content = file.read()
                if content != expected:
                    print(
                        f"Test failed for {server.file_folder}/file_1: {content} (unexpected content)"
                    )
                    exit(1)
        except FileNotFoundError:
            print(f"File {server.file_folder}/file_1 not found")
            exit(1)


# Very unsure about this test - weird behavior
def primary_and_replica_node_failures():
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

    client1 = Client(1)
    client2 = Client(2)
    client3 = Client(3)

    reset_files()

    # Start server threads
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    print("Servers started")

    time.sleep(5)

    # Initialize clients
    client1.RPC_client_init()
    print("Client 1 initialized")
    client2.RPC_client_init()
    print("Client 2 initialized")
    client3.RPC_client_init()
    print("Client 3 initialized")

    # Client 1 appends AA to files 1 to 5
    client1.RPC_lock_acquire()
    print("Client 1 acquired lock")
    for i in range(1, 3):
        client1.RPC_append_file(str(i), "AA")

    # Simulate Server 2 failure
    server2.stop()
    print("Server 2 stopped")
    time.sleep(2)

    for i in range(4, 6):
        client1.RPC_append_file(str(i), "AA")
    client1.RPC_lock_release()
    print("Client 1 released lock")

    # Client 2 appends BB to files 1 to
    client2.RPC_lock_acquire()
    print("Client 2 acquired lock")
    for i in range(1, 6):
        client2.RPC_append_file(str(i), "BB")
    client2.RPC_lock_release()
    print("Client 2 released lock")

    # Simulate Server 1 and 2 failure
    server1.stop()
    server2.stop()
    print("Server 1 and 2 stopped")
    time.sleep(2)

    # Client 3 appends CC to files 1 to 5
    client3.RPC_lock_acquire()
    print("Client 3 acquired lock")
    for i in range(1, 6):
        client3.RPC_append_file(str(i), "CC")
    client3.RPC_lock_release()
    print("Client 3 released lock")

    # Restart Server 1 and 2
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread1.start()
    thread2.start()
    print("Server 1 and 2 restarting...")
    time.sleep(10)  # Allow Server 1 and 2 to fully recover

    servers = [server1, server2, server3]

    # Stop all servers
    for server in servers:
        server.stop()

    print("Servers stopped")

    print("Checking files")
    # expect files 1 to 5 on every server to contain "AABBCC"
    expected = "AABBCC"
    for server in servers:
        print(f"Checking files in {server.file_folder}")
        for i in range(1, 6):
            try:
                with open(f"{server.file_folder}/file_{i}", "r") as file:
                    content = file.read()
                    if content != expected:
                        print(
                            f"Test failed for {server.file_folder}/file_{i}: {content} (unexpected content)"
                        )
                        exit(1)
            except FileNotFoundError:
                print(f"File {server.file_folder}/file_{i} not found")
                exit(1)


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

    # if not test_single_server_fails_lock_free():
    #     failed_tests.append("test_single_server_fails_lock_free")
    #     print("test_single_server_fails_lock_free failed")

    # if not test_single_server_fails_lock_held():
    #     failed_tests.append("test_single_server_fails_lock_held")
    #     print("test_single_server_fails_lock_held failed")

    if not replica_node_failures_fast_recovery():
        failed_tests.append("replica_node_failures_fast_recovery")
        print("replica_node_failures_fast_recovery failed")

    if not replica_node_failures_slow_recovery():
        failed_tests.append("replica_node_failures_slow_recovery")
        print("replica_node_failures_slow_recovery failed")

    if not primary_node_failures_slow_recovery_outside_critical_section():
        failed_tests.append(
            "primary_node_failures_slow_recovery_outside_critical_section"
        )
        print("primary_node_failures_slow_recovery_outside_critical_section failed")

    # This test case is not well defined
    # if not primary_node_failures_slow_recovery_during_critical_sections_and_test_for_atomicity():
    #     failed_tests.append(
    #         "primary_node_failures_slow_recovery_during_critical_sections_and_test_for_atomicity"
    #     )
    #     print(
    #         "primary_node_failures_slow_recovery_during_critical_sections_and_test_for_atomicity failed"
    #     )

    if not primary_and_replica_node_failures():
        failed_tests.append("primary_and_replica_node_failures")
        print("primary_and_replica_node_failures failed")

    if len(failed_tests) == 0:
        print("All tests passed")
    else:
        print(f"Failed tests: {failed_tests}")
