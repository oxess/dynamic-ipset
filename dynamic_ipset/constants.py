"""Constants and default values for dynamic-ipset."""

from pathlib import Path

# Paths
CONFIG_DIR = Path("/etc/dynamic-ipset")
CONFIG_FILE = CONFIG_DIR / "config"
CONFIG_D_DIR = CONFIG_DIR / "config.d"
SYSTEMD_UNIT_DIR = Path("/etc/systemd/system")
RUN_DIR = Path("/run/dynamic-ipset")

# Defaults
DEFAULT_PERIODIC = "*-*-* 0/3:00:00"  # Every 3 hours (OnCalendar format)
DEFAULT_IPSET_TYPE = "hash:net"
DEFAULT_IPSET_FAMILY = "inet"  # IPv4; use 'inet6' for IPv6
DEFAULT_TIMEOUT = 30  # HTTP timeout in seconds
DEFAULT_MAX_ENTRIES = 65536

# Systemd unit naming
SERVICE_PREFIX = "dynamic-ipset-"
TIMER_PREFIX = "dynamic-ipset-"

# Valid characters for list names (must match ipset naming rules)
# - Must start with letter
# - Max 31 characters
# - Only alphanumeric, underscore, hyphen
LIST_NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,30}$"

# IP list parsing
COMMENT_CHARS = ("#", ";")
