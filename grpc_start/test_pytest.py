import sys
import threading
import time
from pathlib import Path

import pytest

root_directory = Path(__file__).resolve().parent.parent
sys.path.append(str(root_directory))

from grpc_start.client import Client  # noqa: E402
from grpc_start.server import LockServer, reset_files  # noqa: E402

FILE_PATH = "files/"


@pytest.fixture(autouse=True)
def reset_environment():
    reset_files()


def test_packet_delay():
    # Reset files and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize clients
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Simulate client 1 acquiring a lock
    client1.RPC_lock_acquire()

    # Simulate client 2 trying to acquire the same lock in a separate thread
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # Introduce artificial delay to simulate packet delay
    time.sleep(5)

    # Client 1 tries to append to the file while still holding the lock
    client1.RPC_append_file("0", "test1client1")

    # Ensure thread2 is done
    if thread2.is_alive():
        thread2.join()

    # Stop the server
    server.stop()

    # Read the file to verify the outcome
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert that the file is still empty because client 1's lock expired
    assert message == "", f"Expected file to be empty, but got: {message}"


def test_client_packet_loss():
    """
    Test for client packet loss simulation by introducing delays to mimic timeouts.
    """
    # Reset and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize clients
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 2 acquires the lock
    client2.RPC_lock_acquire()
    time.sleep(0.1)  # Simulate delay

    # Client 1 tries to acquire the lock in a separate thread
    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()

    # Client 2 appends to the file and releases the lock
    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    # Wait for thread1 to finish
    thread1.join()

    # Client 1 appends to the file and releases the lock
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    # Stop the server
    time.sleep(0.5)
    server.stop()

    # Read the file to verify the result
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert the expected content
    assert message == "BA", f"Unexpected file content: {message}"


def test_server_packet_loss():
    """
    Test for server packet loss simulation by re-sending lock acquire requests.
    """
    # Reset and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize clients
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 1 acquires the lock
    client1.RPC_lock_acquire()

    # Client 2 tries to acquire the lock in a separate thread
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # Client 1 re-sends lock acquire
    client1.RPC_lock_acquire()

    # Client 1 appends to the file and releases the lock
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    # Wait for thread2 to finish
    thread2.join()

    # Client 2 appends to the file and releases the lock
    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    # Stop the server
    time.sleep(0.5)
    server.stop()

    # Read the file to verify the result
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert the expected content
    assert message == "AB", f"Unexpected file content: {message}"


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
    assert not result, "Client 1 should not be able to release the lock"
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

    assert message == "ABBA", f"Unexpected file content: {message}"


def test_combined_network_failures():
    """
    Test handling of combined network failures, including lost requests and responses.
    """
    # Reset and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize clients
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 1 acquires the lock
    client1.RPC_lock_acquire()

    # Client 2 attempts to acquire the lock in a separate thread
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # Client 1 appends data with simulated network failures
    client1.RPC_append_file("0", "1")  # Normal append
    client1.RPC_append_file("0", "A", lost_before_server=True)  # Lost before server
    client1.RPC_append_file("0", "A", lost_after_server=True)  # Response lost
    client1.RPC_append_file("0", "A")  # Retransmit with correct sequence

    # Client 1 releases the lock
    client1.RPC_lock_release()

    # Wait for Client 2 to finish
    thread2.join()

    # Client 2 appends data and releases the lock
    client2.RPC_append_file("0", "B")
    client2.RPC_lock_release()

    # Stop the server
    time.sleep(0.5)
    server.stop()

    # Verify file content
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert the expected result
    assert message == "1AB", f"Unexpected file content: {message}"


def test_stuck_before_editing_file():
    """
    Test behavior when a client is stuck before editing the file and loses its lock.
    """
    # Reset and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize clients
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 1 acquires the lock
    client1.RPC_lock_acquire()

    # Client 2 attempts to acquire the lock in a separate thread
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # Simulate garbage collection causing Client 1 to lose its lock
    thread2.join()

    # Client 2 appends data while Client 1 is stuck
    client2.RPC_append_file("0", "B")
    client1.RPC_append_file("0", "A")  # Lock expired, append should fail
    client2.RPC_append_file("0", "B")

    # Client 1 re-acquires the lock and appends again
    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()
    client2.RPC_lock_release()
    thread1.join()

    # Client 1 appends multiple entries and releases the lock
    client1.RPC_append_file("0", "A")
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    # Stop the server
    time.sleep(0.5)
    server.stop()

    # Verify file content
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert the expected result
    assert message == "BBAA", f"Unexpected file content: {message}"


def test_stuck_after_editing_file():
    """
    Test behavior when a client is stuck after editing the file, causing append failures.
    """
    # Reset and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize clients
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 1 acquires the lock
    client1.RPC_lock_acquire()

    # Client 2 attempts to acquire the lock in a separate thread
    thread2 = threading.Thread(target=client2.RPC_lock_acquire)
    thread2.start()

    # Simulate Client 1 appending with network issues
    client1.RPC_append_file("0", "A", lost_after_server=True)  # Lost response

    # Garbage collection happens, Client 2 gets the lock
    thread2.join()

    # Client 2 appends data
    client2.RPC_append_file("0", "B")

    # Client 1 attempts to append again but lock expired
    client1.RPC_append_file("0", "A")  # Lock expired
    client2.RPC_append_file("0", "B")

    # Client 1 re-acquires the lock and appends multiple entries
    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()
    client2.RPC_lock_release()
    thread1.join()

    client1.RPC_append_file("0", "A")
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    # Stop the server
    time.sleep(0.5)
    server.stop()

    # Verify file content
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert the expected result
    assert message == "BBAA", f"Unexpected file content: {message}"


def test_single_server_fails_lock_free():
    """
    Test behavior when the server fails and restarts with no lock held.
    """
    # Reset files and start the server
    reset_files()
    server = LockServer()
    server.serve()

    # Initialize client
    client1 = Client(1)
    client1.RPC_client_init()

    # Client 1 acquires a lock, appends to the file, and releases the lock
    client1.RPC_lock_acquire()
    client1.RPC_append_file("0", "A")
    client1.RPC_append_file("0", "A")
    client1.RPC_lock_release()

    # Stop the server
    server.stop()
    print("Server stopped.")

    # Simulate server restart and lock acquisition
    time.sleep(0.5)
    thread1 = threading.Thread(target=client1.RPC_lock_acquire)
    thread1.start()

    server = LockServer()
    server.serve()

    thread1.join()

    # Client 1 appends again and releases the lock
    client1.RPC_append_file("0", "1")
    client1.RPC_lock_release()

    # Stop the server
    server.stop()

    # Verify file content
    with open(f"{server.file_folder}/file_0", "r") as file:
        message = file.read()

    # Assert the expected result
    assert message == "AA1", f"Unexpected file content: {message}"


def test_raft():
    """
    Test Raft protocol by starting multiple servers and a client.
    """
    # Reset files and start multiple servers
    reset_files()
    server1 = LockServer("localhost", 50051)
    server2 = LockServer("localhost", 50052)
    server3 = LockServer("localhost", 50053)

    # Start server threads
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread3 = threading.Thread(target=server3.serve)

    thread1.start()
    thread2.start()
    thread3.start()

    # Allow servers to initialize
    time.sleep(7)

    # Initialize a client
    client1 = Client(1)
    client1.RPC_client_init()

    # Simulate Raft operations and delay for leader election
    time.sleep(15)

    # Stop all servers
    servers = [server1, server2, server3]
    for server in servers:
        server.stop()

    print("Servers stopped")

    # Assert that the test completes without errors
    assert True  # No specific assertions in the original code


def test_single_server_fails_lock_held():
    """
    Test behavior when the server fails and restarts with a lock held.
    """
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

    assert message == "ABBA"


def test_replica_node_failures_fast_recovery():
    """
    Test scenario where a replica node fails and recovers quickly.
    """
    reset_files()

    # Initialize servers
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

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
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 1 acquires lock and appends to files
    client1.RPC_lock_acquire()
    client1.RPC_append_file("1", "A")
    client1.RPC_append_file("2", "A")

    # Simulate Server 2 failure
    server2.stop()
    time.sleep(1)

    # Continue appending with Server 2 down
    client1.RPC_append_file("3", "A")
    client1.RPC_lock_release()

    # Restart Server 2
    server2 = LockServer("localhost", 50052, False)
    thread2 = threading.Thread(target=server2.serve)
    thread2.start()
    time.sleep(5)

    # Client 2 acquires lock and appends to files
    client2.RPC_lock_acquire()
    client2.RPC_append_file("1", "B")
    client2.RPC_append_file("2", "B")
    client2.RPC_append_file("3", "B")
    client2.RPC_lock_release()

    # Stop all servers
    servers = [server1, server2, server3]
    for server in servers:
        server.stop()

    # Verify file contents
    expected = set(["AB", "BA"])
    first_content = None
    for server in servers:
        for i in range(1, 4):
            with open(f"{server.file_folder}/file_{i}", "r") as file:
                content = file.read()
                assert content in expected, f"Unexpected content in file_{i}: {content}"
                if first_content is None:
                    first_content = content
                else:
                    assert content == first_content, (
                        f"Inconsistent content in file_{i}: {content} "
                        f"(expected {first_content})"
                    )


def test_replica_node_failures_slow_recovery():
    """
    Test scenario where a replica node fails and recovers slowly.
    """
    reset_files()

    # Initialize servers
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

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
    client1 = Client(1)
    client2 = Client(2)
    client1.RPC_client_init()
    client2.RPC_client_init()

    # Client 1 acquires lock and appends to files
    client1.RPC_lock_acquire()
    client1.RPC_append_file("1", "A")
    client1.RPC_append_file("2", "A")

    # Simulate Server 2 failure
    server2.stop()

    # Continue appending with Server 2 down
    client1.RPC_append_file("3", "A")
    client1.RPC_lock_release()

    # Restart Server 2 after a delay
    server2 = LockServer("localhost", 50052, False)
    thread2 = threading.Thread(target=server2.serve)
    thread2.start()
    time.sleep(5)

    # Client 2 acquires lock and appends to files
    client2.RPC_lock_acquire()
    client2.RPC_append_file("1", "B")
    client2.RPC_append_file("2", "B")
    client2.RPC_append_file("3", "B")
    client2.RPC_lock_release()

    # Stop all servers
    servers = [server1, server2, server3]
    for server in servers:
        server.stop()

    # Verify file contents
    expected = set(["AB", "BA"])
    first_content = None
    for server in servers:
        for i in range(1, 4):
            with open(f"{server.file_folder}/file_{i}", "r") as file:
                content = file.read()
                assert content in expected, f"Unexpected content in file_{i}: {content}"
                if first_content is None:
                    first_content = content
                else:
                    assert content == first_content, (
                        f"Inconsistent content in file_{i}: {content} "
                        f"(expected {first_content})"
                    )


def test_primary_node_failures_slow_recovery_outside_critical_section():
    """
    Test scenario where the primary node fails and recovers slowly, outside critical sections.
    """
    reset_files()

    # Initialize servers
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

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
    client1 = Client(1)
    client2 = Client(2)
    client3 = Client(3)
    client1.RPC_client_init()
    client2.RPC_client_init()
    client3.RPC_client_init()

    # Client 1 acquires lock and appends to file multiple times
    client1.RPC_lock_acquire()
    for _ in range(5):
        client1.RPC_append_file("1", "A")
    client1.RPC_lock_release()

    # Simulate Server 1 failure
    server1.stop()
    time.sleep(2)

    # Client 2 acquires lock and appends to file multiple times
    client2.RPC_lock_acquire()
    for _ in range(5):
        client2.RPC_append_file("1", "B")
    client2.RPC_lock_release()

    # Client 3 acquires lock and appends to file multiple times
    client3.RPC_lock_acquire()
    for _ in range(5):
        client3.RPC_append_file("1", "C")
    client3.RPC_lock_release()

    # Restart Server 1
    server1 = LockServer("localhost", 50051, False)
    thread1 = threading.Thread(target=server1.serve)
    thread1.start()
    time.sleep(5)

    # Stop all servers
    servers = [server1, server2, server3]
    for server in servers:
        server.stop()

    # Verify file content
    expected = "AAAAABBBBBCCCCC"
    for server in servers:
        with open(f"{server.file_folder}/file_1", "r") as file:
            content = file.read()
            assert content == expected, f"Unexpected content in file_1: {content}"


def test_primary_node_failures_slow_recovery_during_critical_sections_and_test_for_atomicity():
    """
    Test slow recovery of the primary node during critical sections,
    ensuring atomicity is maintained.
    """
    reset_files()

    # Initialize servers
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

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
    client1 = Client(1)
    client2 = Client(2)
    client3 = Client(3)
    client1.RPC_client_init()
    client2.RPC_client_init()
    client3.RPC_client_init()

    # Client 1 acquires lock and appends to file 20 times
    client1.RPC_lock_acquire()
    for _ in range(20):
        client1.RPC_append_file("1", "A")
    client1.RPC_lock_release()

    # Simulate Server 1 failure
    server1.stop()
    time.sleep(2)

    # Client 2 appends half the entries before Server 1 stops
    client2.RPC_lock_acquire()
    for _ in range(10):
        client2.RPC_append_file("1", "B")
    server1.stop()
    time.sleep(2)

    # Append the remaining entries after Server 1 stops
    for _ in range(10):
        client2.RPC_append_file("1", "B")
    client2.RPC_lock_release()

    # Client 3 appends to file 20 times
    client3.RPC_lock_acquire()
    for _ in range(20):
        client3.RPC_append_file("1", "C")
    client3.RPC_lock_release()

    # Restart Server 1
    server1 = LockServer("localhost", 50051, False)
    thread1 = threading.Thread(target=server1.serve)
    thread1.start()
    time.sleep(10)

    # Stop all servers
    servers = [server1, server2, server3]
    for server in servers:
        server.stop()

    # Verify file content
    expected = "A" * 20 + "B" * 20 + "C" * 20
    for server in servers:
        with open(f"{server.file_folder}/file_1", "r") as file:
            content = file.read()
            assert content == expected, f"Unexpected content in file_1: {content}"


def test_primary_and_replica_node_failures():
    """
    Test behavior when both primary and replica nodes fail,
    ensuring all file updates are consistent.
    """
    reset_files()

    # Initialize servers
    server1 = LockServer("localhost", 50051, True)
    server2 = LockServer("localhost", 50052, False)
    server3 = LockServer("localhost", 50053, False)

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
    client1 = Client(1)
    client2 = Client(2)
    client3 = Client(3)
    client1.RPC_client_init()
    client2.RPC_client_init()
    client3.RPC_client_init()

    # Client 1 appends AA to files 1 to 5
    client1.RPC_lock_acquire()
    for i in range(1, 4):
        client1.RPC_append_file(str(i), "AA")
    server2.stop()
    time.sleep(2)

    for i in range(4, 6):
        client1.RPC_append_file(str(i), "AA")
    client1.RPC_lock_release()

    # Client 2 appends BB to files 1 to 5
    client2.RPC_lock_acquire()
    for i in range(1, 6):
        client2.RPC_append_file(str(i), "BB")
    client2.RPC_lock_release()

    # Simulate Server 1 and Server 2 failure
    server1.stop()
    server2.stop()
    time.sleep(2)

    # Client 3 appends CC to files 1 to 5
    client3.RPC_lock_acquire()
    for i in range(1, 6):
        client3.RPC_append_file(str(i), "CC")
    client3.RPC_lock_release()

    # Restart Server 1 and Server 2
    server1 = LockServer("localhost", 50051, False)
    server2 = LockServer("localhost", 50052, False)
    thread1 = threading.Thread(target=server1.serve)
    thread2 = threading.Thread(target=server2.serve)
    thread1.start()
    thread2.start()
    time.sleep(10)

    # Stop all servers
    servers = [server1, server2, server3]
    for server in servers:
        server.stop()

    # Verify file content
    expected = "AABBCC"
    for server in servers:
        for i in range(1, 6):
            with open(f"{server.file_folder}/file_{i}", "r") as file:
                content = file.read()
                assert content == expected, f"Unexpected content in file_{i}: {content}"
