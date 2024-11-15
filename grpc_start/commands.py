from dataclasses import dataclass


@dataclass
class Command:
    pass

    def toJson(self):
        return self.__dict__


@dataclass
class AddClientCommand(Command):
    def __init__(self, client_id: int, client_ip: str):
        self.client_id = client_id
        self.client_ip = client_ip

    def toJson(self):
        return {
            "command": "AddClientCommand",
            "client_id": self.client_id,
            "client_ip": self.client_ip,
        }


@dataclass
class IncrementClientSeqCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

    def toJson(self):
        return {"command": "IncrementClientSeqCommand", "client_id": self.client_id}


@dataclass
class ChangeLockHolderCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

    def toJson(self):
        return {"command": "ChangeLockHolderCommand", "client_id": self.client_id}


@dataclass
class AddAppendCommand(Command):
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content

    def toJson(self):
        return {
            "command": "AddAppendCommand",
            "filename": self.filename,
            "content": self.content,
        }


@dataclass
class ExecuteAppendsCommand(Command):
    pass

    def toJson(self):
        return {"command": "ExecuteAppendsCommand"}


@dataclass
class RemoveClientCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

    def toJson(self):
        return {"command": "RemoveClientCommand", "client_id": self.client_id}
