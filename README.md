# Dynamic IPSet

A CLI tool for managing Linux ipset rules by fetching IP address lists from URLs and updating them periodically via systemd timers.

## Features

- Fetch IP lists from HTTP/HTTPS URLs
- Support for IPv4 and IPv6 addresses and CIDR notation
- Atomic ipset updates (no traffic interruption during updates)
- Systemd timer-based periodic updates (default: every 3 hours)
- INI-based configuration
- Easy-to-use CLI

## Requirements

- Linux with ipset and systemd
- Python 3.9 or later
- Root privileges for ipset operations

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/oxess/dynamic-ipset.git
cd dynamic-ipset

# Install with pip
pip install .

# Or install system-wide with make (requires root)
sudo make install
```

### From Debian Package

```bash
# Build the package
dpkg-buildpackage -us -uc -b

# Install
sudo dpkg -i ../dynamic-ipset_*.deb
sudo apt-get install -f  # Install dependencies if needed
```

### Development Installation

```bash
# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Or use make
make dev-install
```

## Quick Start

```bash
# Create a new IP list from a URL (example: Spamhaus DROP list)
sudo dynamic-ipset create spamhaus-drop https://www.spamhaus.org/drop/drop.txt

# View the created list
sudo dynamic-ipset show spamhaus-drop

# Manually trigger an update
sudo dynamic-ipset run spamhaus-drop

# Enable automatic updates via systemd timer
sudo dynamic-ipset enable spamhaus-drop

# View all configured lists
sudo dynamic-ipset show
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `create <name> <url> [interval]` | Create a new ipset configuration |
| `delete <name>` | Delete an ipset configuration |
| `show [name]` | Show details of one or all lists |
| `edit <name>` | Open configuration in $EDITOR |
| `reload` | Sync configurations with systemd |
| `update <name>` | Fetch URL and update ipset |
| `enable <name>` | Enable systemd timer |
| `disable <name>` | Disable systemd timer |
| `run <name>` | Trigger immediate update |

## Configuration

### Global Configuration

The global configuration file is located at `/etc/dynamic-ipset/config`:

```ini
[global]
# Default update interval (systemd OnCalendar format)
default_periodic = *-*-* 0/3:00:00

# Default ipset type
default_ipset_type = hash:net

# Default address family (inet for IPv4, inet6 for IPv6)
default_family = inet

# Default maximum entries
default_max_entries = 65536

# Command paths
ipset_path = /usr/sbin/ipset
systemctl_path = /usr/bin/systemctl
```

### Per-List Configuration

Individual list configurations are stored in `/etc/dynamic-ipset/config.d/<name>.conf`:

```ini
[list]
name = spamhaus-drop
source_url = https://www.spamhaus.org/drop/drop.txt
periodic = *-*-* 0/3:00:00
ipset_type = hash:net
family = inet
max_entries = 65536
enabled = yes
```

### Systemd Timer Intervals

The `periodic` setting uses systemd's OnCalendar format:

| Example | Description |
|---------|-------------|
| `*-*-* 0/3:00:00` | Every 3 hours |
| `*-*-* 0/1:00:00` | Every hour |
| `*-*-* 0/6:00:00` | Every 6 hours |
| `*-*-* 00:00:00` | Daily at midnight |
| `Mon *-*-* 00:00:00` | Weekly on Monday |

## Supported IP List Formats

Dynamic IPSet can parse IP lists with:

- One IP address or CIDR per line
- Comments starting with `#` or `;`
- Inline comments
- Empty lines (ignored)
- Mixed IPv4 and IPv6 entries

Example:
```
# Blocklist
192.168.1.0/24
10.0.0.0/8  # Private network
2001:db8::/32

; Another comment style
172.16.0.0/12
```

## Using with iptables/nftables

### iptables

```bash
# Block incoming traffic from IPs in the set
iptables -I INPUT -m set --match-set spamhaus-drop src -j DROP

# Block outgoing traffic to IPs in the set
iptables -I OUTPUT -m set --match-set spamhaus-drop dst -j DROP
```

### nftables

```nft
table inet filter {
    set spamhaus-drop {
        type ipv4_addr
        flags interval
    }

    chain input {
        ip saddr @spamhaus-drop drop
    }
}
```

## Development

### Running Tests

```bash
# Run unit tests
make test

# Run with tox (multiple Python versions)
tox

# Run integration tests (requires root and ipset)
sudo -E pytest tests/test_integration.py -v
```

### Linting

```bash
# Check code style
make lint

# Auto-format code
make format
```

### Building Packages

```bash
# Build Python wheel
python -m build

# Build Debian package
dpkg-buildpackage -us -uc -b
```

## Project Structure

```
dynamic-ipset/
├── dynamic_ipset/           # Main Python package
│   ├── __init__.py
│   ├── cli.py              # CLI implementation
│   ├── config.py           # Configuration management
│   ├── constants.py        # Default values
│   ├── exceptions.py       # Custom exceptions
│   ├── fetcher.py          # URL fetching
│   ├── ipset.py            # IPset operations
│   ├── systemd.py          # Systemd integration
│   └── validator.py        # Input validation
├── tests/                   # Test suite
├── debian/                  # Debian packaging
├── systemd/                 # Systemd unit templates
├── etc/dynamic-ipset/       # Default configuration
├── bin/                     # CLI entry point
├── Makefile
├── pyproject.toml
└── README.md
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request
