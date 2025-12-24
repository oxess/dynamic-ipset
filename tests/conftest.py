"""Shared pytest fixtures for dynamic-ipset tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def config_dir(temp_dir):
    """Create a temporary config directory structure."""
    config_d = temp_dir / "config.d"
    config_d.mkdir(parents=True)
    return temp_dir


@pytest.fixture
def sample_ip_list():
    """Sample IP list content."""
    return """# Sample IP blocklist
# Comment line
192.168.1.0/24
10.0.0.0/8
172.16.0.0/12

# Single IPs
8.8.8.8
1.1.1.1

# IPv6
2001:db8::/32
::1
"""


@pytest.fixture
def sample_ip_list_with_errors():
    """Sample IP list with some invalid entries."""
    return """# Sample IP blocklist with errors
192.168.1.0/24
invalid_entry
10.0.0.0/8
256.256.256.256
8.8.8.8
not_an_ip
"""
