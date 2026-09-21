class ApiError(Exception):
    """An error that maps directly onto an HTTP response."""

    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra
