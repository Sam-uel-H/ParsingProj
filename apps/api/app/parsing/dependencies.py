from functools import lru_cache

from app.providers.fakes import FakeLLMProvider
from app.providers.llm import LLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    return FakeLLMProvider()
