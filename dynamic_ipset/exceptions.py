"""Custom exceptions for dynamic-ipset."""


class DynamicIPSetError(Exception):
    """Base exception for all dynamic-ipset errors."""

    pass


class ConfigError(DynamicIPSetError):
    """Configuration-related errors."""

    pass


class IPSetError(DynamicIPSetError):
    """IPset operation errors."""

    pass


class FetchError(DynamicIPSetError):
    """URL fetching errors."""

    pass


class ValidationError(DynamicIPSetError):
    """Validation errors for IPs, names, URLs."""

    pass


class SystemdError(DynamicIPSetError):
    """Systemd operation errors."""

    pass
