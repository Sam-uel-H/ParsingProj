class ProviderError(RuntimeError):
    """Base error raised by provider adapters."""


class RetryableProviderError(ProviderError):
    """A transient provider failure that orchestration may retry later."""


class RateLimitProviderError(RetryableProviderError):
    """A provider throttle, optionally carrying Retry-After seconds."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("Provider rate limit reached.")
        self.retry_after = retry_after
