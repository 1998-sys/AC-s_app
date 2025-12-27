class ValidationIssue:
    def __init__(
        self,
        key,
        title,
        message,
        action=None,
        blocking=False
    ):
        self.key = key
        self.title = title
        self.message = message
        self.action = action      
        self.blocking = blocking  