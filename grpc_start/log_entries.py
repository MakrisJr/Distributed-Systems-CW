from grpc_start import commands as cs
from grpc_start import raft_pb2


class LogEntry:
    def __init__(self, command: cs.Command):
        self.command = command


def log_entry_grpc_to_object(entry: raft_pb2.LogEntry) -> LogEntry:
    if not entry:
        return None
    # mind you, clunky as all hell
    if entry.hasField("add_client"):
        new_command = cs.AddClientCommand(entry.add_client.client_id)
    elif entry.hasField("increment_client_seq"):
        new_command = cs.IncrementClientSeqCommand(entry.increment_client_seq.client_id)
    elif entry.hasField("change_lock_holder"):
        new_command = cs.ChangeLockHolderCommand(entry.change_lock_holder.client_id)
    elif entry.hasField("add_append"):
        new_command = cs.AddAppendCommand(
            entry.add_append.filename, entry.add_append.content
        )
    elif entry.hasField("execute_appends"):
        new_command = cs.ExecuteAppendsCommand()
    elif entry.hasField("remove_client"):
        new_command = cs.RemoveClientCommand(entry.remove_client.client_id)
    else:
        raise Exception("Command not present in log entry GRPC message")

    return LogEntry(new_command)


def log_entry_object_to_grpc(entry: LogEntry) -> raft_pb2.LogEntry:
    print(id(cs.AddClientCommand))
    print(id(entry.command))

    # print(f"Converting {str(entry.command)}")
    print(f"Instance of entry.command: {entry.command}")
    if isinstance(entry.command, cs.AddClientCommand):
        return raft_pb2.LogEntry(
            add_client=raft_pb2.AddClientCommand(
                client_id=entry.command.client_id, client_ip=entry.command.client_ip
            )
        )
    elif isinstance(entry.command, cs.IncrementClientSeqCommand):
        return raft_pb2.LogEntry(
            increment_client_seq=raft_pb2.IncrementClientSeqCommand(
                client_id=entry.command.client_id
            )
        )
    elif isinstance(entry.command, cs.ChangeLockHolderCommand):
        return raft_pb2.LogEntry(
            change_lock_holder=raft_pb2.ChangeLockHolderCommand(
                client_id=entry.command.client_id
            )
        )
    elif isinstance(entry.command, cs.AddAppendCommand):
        return raft_pb2.LogEntry(
            add_append=raft_pb2.AddAppendCommand(
                filename=entry.command.filename, content=entry.command.content
            )
        )
    elif isinstance(entry.command, cs.ExecuteAppendsCommand):
        return raft_pb2.LogEntry(execute_appends=raft_pb2.ExecuteAppendsCommand())
    elif isinstance(entry.command, cs.RemoveClientCommand):
        return raft_pb2.LogEntry(
            execute_appends=raft_pb2.RemoveClientCommand(
                client_id=entry.command.client_id
            )
        )
    else:
        raise Exception("Invalid LogEntry object")
