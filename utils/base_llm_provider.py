from utils.providers.google_provider import GoogleProvider
from utils.providers.openai_provider import OpenAIProvider

class BaseLLMProvider:
    PROVIDERS = {
        "openai": OpenAIProvider,
        "gemini": GoogleProvider,
        "google": GoogleProvider,
    }

    def __init__(self, config: dict):
        provider_name = config["llm"]["provider"].lower()

        try:
            provider_cls = self.PROVIDERS[provider_name]
        except KeyError:
            raise ValueError(
                f"Unsupported provider: {provider_name}"
            )

        self.provider = provider_cls(config)

    def __getattr__(self, name):
        return getattr(self.provider, name)
