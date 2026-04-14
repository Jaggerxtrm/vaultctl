class VaultctlError(Exception):
    """Base error for vaultctl."""


class ConfigError(VaultctlError):
    """Configuration is invalid."""


class NotFoundError(VaultctlError):
    """Requested entity was not found."""


class LLMConfigError(VaultctlError):
    """LLM provider configuration is invalid or missing."""


class LLMRequestError(VaultctlError):
    """LLM provider request failed."""


class TranslationError(VaultctlError):
    """Translation operation failed."""
