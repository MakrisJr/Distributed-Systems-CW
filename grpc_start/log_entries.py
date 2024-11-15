from grpc_start import commands as cs
from grpc_start import raft_pb2


class LogEntry:
    def __init__(self, command: cs.Command):
        self.command = command

    def toJson(self):
        return {
            "command": self.command.toJson(),
        }


def log_entry_json_to_object(entry: dict) -> LogEntry:
    command_json = entry["command"]

    match command_json["type"]:
        case "AddClientCommand":
            new_command = cs.AddClientCommand(
                client_id=command_json["client_id"], client_ip=command_json["client_ip"]
            )
        case "IncrementClientSeqCommand":
            new_command = cs.IncrementClientSeqCommand(
                client_id=command_json["client_id"]
            )
        case "ChangeLockHolderCommand":
            new_command = cs.ChangeLockHolderCommand(
                client_id=command_json["client_id"]
            )
        case "AddAppendCommand":
            new_command = cs.AddAppendCommand(
                filename=command_json["filename"], content=command_json["content"]
            )
        case "ExecuteAppendsCommand":
            new_command = cs.ExecuteAppendsCommand()
        case "RemoveClientCommand":
            new_command = cs.RemoveClientCommand(client_id=command_json["client_id"])

    return LogEntry(new_command)


def log_entry_grpc_to_object(entry: raft_pb2.LogEntry) -> LogEntry:
    if not entry or not entry.HasField("command"):
        return None
    # print(f"HAS FIELD ENTRY: {entry}")
    # mind you, clunky as all hell
    # entry is add_client {
    #   client_id: 1
    #   client_ip: "ipv6:%5B::1%5D:59094"
    # }
    if entry.HasField("add_client"):
        new_command = cs.AddClientCommand(
            entry.add_client.client_id, entry.add_client.client_ip
        )
    elif entry.HasField("increment_client_seq"):
        new_command = cs.IncrementClientSeqCommand(entry.increment_client_seq.client_id)
    elif entry.HasField("change_lock_holder"):
        new_command = cs.ChangeLockHolderCommand(entry.change_lock_holder.client_id)
    elif entry.HasField("add_append"):
        new_command = cs.AddAppendCommand(
            entry.add_append.filename, entry.add_append.content
        )
    elif entry.HasField("execute_appends"):
        new_command = cs.ExecuteAppendsCommand()
    elif entry.HasField("remove_client"):
        new_command = cs.RemoveClientCommand(entry.remove_client.client_id)
    else:
        raise Exception("Command not present in log entry GRPC message")

    return LogEntry(new_command)


def log_entry_object_to_grpc(entry: LogEntry) -> raft_pb2.LogEntry:
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
