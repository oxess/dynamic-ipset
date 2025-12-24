"""Validation utilities for IP addresses, CIDRs, URLs, and list names."""

import ipaddress
import re
from urllib.parse import urlparse

from .constants import LIST_NAME_PATTERN
from .exceptions import ValidationError


def validate_list_name(name: str) -> bool:
    """
    Validate ipset list name.

    Rules:
    - Must start with letter
    - Max 31 characters (ipset limit)
    - Only alphanumeric, underscore, hyphen

    Args:
        name: The list name to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If the name is invalid
    """
    if not name:
        raise ValidationError("List name cannot be empty")

    if not re.match(LIST_NAME_PATTERN, name):
        raise ValidationError(
            f"Invalid list name '{name}'. Must start with letter, "
            "contain only alphanumeric/underscore/hyphen, max 31 chars."
        )
    return True


def validate_ipv4(ip: str) -> bool:
    """
    Validate IPv4 address.

    Args:
        ip: The IP address string

    Returns:
        True if valid IPv4, False otherwise
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.version == 4
    except ValueError:
        return False


def validate_ipv6(ip: str) -> bool:
    """
    Validate IPv6 address.

    Args:
        ip: The IP address string

    Returns:
        True if valid IPv6, False otherwise
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.version == 6
    except ValueError:
        return False


def validate_ip(ip: str) -> tuple[bool, int]:
    """
    Validate IP address (IPv4 or IPv6).

    Args:
        ip: The IP address string

    Returns:
        Tuple of (is_valid, version) where version is 4 or 6
    """
    try:
        addr = ipaddress.ip_address(ip)
        return True, addr.version
    except ValueError:
        return False, 0


def validate_cidr(cidr: str) -> tuple[str, int, str]:
    """
    Validate CIDR notation (e.g., 192.168.1.0/24 or 2001:db8::/32).

    Args:
        cidr: The CIDR string to validate

    Returns:
        Tuple of (network_address, prefix_length, family)
        where family is 'inet' for IPv4 or 'inet6' for IPv6

    Raises:
        ValidationError: If the CIDR is invalid
    """
    cidr = cidr.strip()

    if "/" not in cidr:
        # Plain IP address - assume /32 for IPv4, /128 for IPv6
        try:
            addr = ipaddress.ip_address(cidr)
            if addr.version == 4:
                return str(addr), 32, "inet"
            else:
                return str(addr), 128, "inet6"
        except ValueError as e:
            raise ValidationError(f"Invalid IP address: {cidr}") from e

    try:
        network = ipaddress.ip_network(cidr, strict=False)
        family = "inet" if network.version == 4 else "inet6"
        return str(network.network_address), network.prefixlen, family
    except ValueError as e:
        raise ValidationError(f"Invalid CIDR: {cidr} - {e}") from e


def validate_url(url: str) -> bool:
    """
    Validate URL format.

    Args:
        url: The URL to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If the URL is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValidationError("URL must start with http:// or https://")

    if not parsed.netloc:
        raise ValidationError("URL must have a valid hostname")

    return True


def validate_oncalendar(spec: str) -> bool:
    """
    Validate systemd OnCalendar specification.

    Examples: *-*-* 0/3:00:00, daily, hourly, weekly

    Args:
        spec: The OnCalendar specification

    Returns:
        True if valid

    Raises:
        ValidationError: If the specification is invalid
    """
    if not spec:
        raise ValidationError("OnCalendar specification cannot be empty")

    spec = spec.strip()

    # Special keywords that systemd recognizes
    keywords = {
        "minutely",
        "hourly",
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "semiannually",
        "yearly",
        "annually",
    }

    if spec.lower() in keywords:
        return True

    # Basic pattern validation for calendar specs
    # Full format: [DOW] YYYY-MM-DD HH:MM:SS [timezone]
    # Simplified validation - systemd will do final validation

    # Must contain at least some valid calendar characters
    valid_chars = set("0123456789*/-:, ")
    if not spec or not all(c in valid_chars or c.isalpha() for c in spec):
        raise ValidationError(f"Invalid OnCalendar specification: {spec}")

    # Must have either time component (:) or date component (-)
    if ":" not in spec and "-" not in spec and spec.lower() not in keywords:
        raise ValidationError(f"Invalid OnCalendar specification: {spec}")

    return True


def parse_ip_entry(entry: str) -> tuple[str, str]:
    """
    Parse an IP entry from a list file.

    Handles:
    - Plain IPs (192.168.1.1)
    - CIDR notation (192.168.1.0/24)
    - Removes inline comments

    Args:
        entry: The entry string from the file

    Returns:
        Tuple of (normalized_entry, family)

    Raises:
        ValidationError: If the entry is invalid
    """
    entry = entry.strip()

    # Remove inline comments
    for comment_char in ("#", ";"):
        if comment_char in entry:
            entry = entry.split(comment_char)[0].strip()

    if not entry:
        raise ValidationError("Empty entry")

    # Validate and normalize
    network_addr, prefix, family = validate_cidr(entry)

    # Return in CIDR format
    return f"{network_addr}/{prefix}", family
