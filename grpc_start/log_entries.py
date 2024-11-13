import commands as cs
from grpc_start import raft_pb2

class LogEntry:
    def __init__(self, term: int, command: cs.Command):
        self.term = term
        self.command = command

def log_entry_grpc_to_object(entry: raft_pb2.LogEntry) -> LogEntry:
    new_entry_term = entry.term

    # mind you, clunky as all hell
    if entry.hasField("add_client"):
        new_command = cs.AddClientCommand(entry.add_client.client_id)
    elif entry.hasField("increment_client_seq"):
        new_command = cs.IncrementClientSeqCommand(entry.increment_client_seq.client_id)
    elif entry.hasField("change_lock_holder"):
        new_command = cs.ChangeLockHolderCommand(entry.change_lock_holder.client_id)
    elif entry.hasField("increment_new_client_id"):
        new_command = cs.IncrementNewClientIDCommand()
    elif entry.hasField("add_append"):
        new_command = cs.AddAppendCommand(entry.add_append.filename, entry.add_append.content)
    elif entry.hasField("execute_appends"):
        new_command = cs.ExecuteAppendsCommand()
    else:
        raise Exception("Command not present in log entry GRPC message")

    return LogEntry(new_entry_term, new_command)

def log_entry_object_to_grpc(entry: LogEntry) -> raft_pb2.LogEntry:
    if isinstance(entry.command, cs.AddClientCommand):
        return raft_pb2.LogEntry(
            term=entry.term,
            add_client=raft_pb2.AddClientCommand(
                client_id=entry.command.client_id
            )
        )
    elif isinstance(entry.command, cs.IncrementClientSeqCommand):
        return raft_pb2.LogEntry(
            term=entry.term,
            increment_client_seq=raft_pb2.IncrementClientSeqCommand(
                client_id=entry.command.client_id
            )
        )
    elif isinstance(entry.command, cs.ChangeLockHolderCommand):
        return raft_pb2.LogEntry(
            term=entry.term,
            change_lock_holder=raft_pb2.ChangeLockHolderCommand(
                client_id=entry.command.client_id
            )
        )
    elif isinstance(entry.command, cs.IncrementNewClientIDCommand):
        return raft_pb2.LogEntry(
            term=entry.term,
            increment_new_client_id=raft_pb2.IncrementNewClientIdCommand()
        )
    elif isinstance(entry.command, cs.AddAppendCommand):
        return raft_pb2.LogEntry(
            term=entry.term,
            add_append=raft_pb2.AddAppendCommand(
                filename=entry.command.filename,
                content=entry.command.content
            )
        )
    elif isinstance(entry.command, cs.ExecuteAppendsCommand):
        return raft_pb2.LogEntry(
            term=entry.term,
            execute_appends=raft_pb2.ExecuteAppendsCommand()
        )
    else:
        raise Exception("Invalid LogEntry object")
