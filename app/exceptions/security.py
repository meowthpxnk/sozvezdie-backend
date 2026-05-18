class WrongSecret(Exception):
    def __init__(self, message: str = "Wrong secret") -> None:
        super().__init__(message)
