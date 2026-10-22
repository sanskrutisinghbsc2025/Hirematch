

class HireMatchError(Exception):

    def __init__(self, message: str, user_message: str = ""):
        super().__init__(message)
        self.user_message = user_message or message


class FileValidationError(HireMatchError):
    pass


class UnsupportedFileTypeError(FileValidationError):
    pass


class FileSizeExceededError(FileValidationError):
    pass


class BatchSizeExceededError(FileValidationError):
    pass


class CorruptFileError(FileValidationError):
    pass


class DuplicateFileError(FileValidationError):
    pass


class SessionLimitExceededError(HireMatchError):
    pass


class SessionNotFoundError(HireMatchError):
    pass


class ExtractionError(HireMatchError):
    pass


class DatabaseError(HireMatchError):
    pass


class ModelLoadError(HireMatchError):
    pass
