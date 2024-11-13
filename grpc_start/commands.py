class Command:
    pass

class AddClientCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

class IncrementClientSeqCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

class ChangeLockHolderCommand(Command):
    def __init__(self, client_id: int):
        self.client_id = client_id

class IncrementNewClientIDCommand(Command):
    pass

class AddAppendCommand(Command):
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content

class ExecuteAppendsCommand(Command):
    pass

class LogEntry:
    def __init__(self, term: int, command: Command):
        self.term = term
        self.command = command
