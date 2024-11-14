from dataclasses import dataclass

@dataclass
class Command:
    pass

@dataclass
class AddClientCommand(Command):
    def __init__(self, client_id: int, client_ip: str):
        self.client_id = client_id
        self.client_ip = client_ip

@dataclass
class IncrementClientSeqCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

@dataclass
class ChangeLockHolderCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

@dataclass
class AddAppendCommand(Command):
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content

@dataclass
class ExecuteAppendsCommand(Command):
    pass

@dataclass
class RemoveClientCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id