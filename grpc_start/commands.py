from dataclasses import dataclass
import base64

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
            "type": "AddClientCommand",
            "client_id": self.client_id,
            "client_ip": self.client_ip,
        }


@dataclass
class IncrementClientSeqCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

    def toJson(self):
        return {"type": "IncrementClientSeqCommand", "client_id": self.client_id}


@dataclass
class ChangeLockHolderCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

    def toJson(self):
        return {"type": "ChangeLockHolderCommand", "client_id": self.client_id}


@dataclass
class AddAppendCommand(Command):
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content

    def toJson(self):
        return {
            "type": "AddAppendCommand",
            "filename": self.filename,
            "content": base64.b64encode(self.content).decode('utf-8')
        }


@dataclass
class ExecuteAppendsCommand(Command):
    pass

    def toJson(self):
        return {"type": "ExecuteAppendsCommand"}


@dataclass
class RemoveClientCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

    def toJson(self):
        return {"type": "RemoveClientCommand", "client_id": self.client_id}


# def json_to_command(cs_json):
