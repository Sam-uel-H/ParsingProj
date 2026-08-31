class ProviderError(RuntimeError):
    """Base error raised by provider adapters."""


class RetryableProviderError(ProviderError):
    """A transient provider failure that orchestration may retry later."""
