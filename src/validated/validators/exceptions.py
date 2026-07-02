class ValidatorCheckError(Exception):
    """Raised when a Check predicate itself throws an exception during evaluation."""

    def __init__(self, message: str, original_exception: Exception):
        super().__init__(message)
        self.original_exception = original_exception
