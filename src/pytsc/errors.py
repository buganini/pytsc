class PrintError(RuntimeError):
    """Transmission failed; result preserves known progress. Never auto-retry."""

    def __init__(self, message, result):
        super().__init__(message)
        self.result = result
