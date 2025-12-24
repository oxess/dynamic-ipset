"""Integration tests for ipset operations.

These tests require:
- Root privileges (sudo)
- ipset installed on the system

Run with: sudo -E env "PATH=$PATH" python -m pytest tests/test_integration_ipset.py -v
"""

import os
import subprocess
import tempfile

import pytest

from dynamic_ipset.config import ConfigManager, ListConfig
from dynamic_ipset.ipset import IPSetManager


def is_root():
    """Check if running as root."""
    return os.geteuid() == 0


def ipset_installed():
    """Check if ipset is installed."""
    try:
        subprocess.run(["ipset", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


pytestmark = [
    pytest.mark.skipif(not is_root(), reason="Requires root privileges"),
    pytest.mark.skipif(not ipset_installed(), reason="ipset not installed"),
]


class TestIPSetIntegration:
    """Integration tests for IPSetManager with real ipset commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = IPSetManager()
        self.test_set_name = "test_dynamic_ipset_integration"

    def teardown_method(self):
        """Clean up test sets."""
        try:
            self.manager.destroy(self.test_set_name)
        except Exception:
            pass
        try:
            self.manager.destroy(f"{self.test_set_name}_temp")
        except Exception:
            pass

    def test_create_and_destroy_ipv4_set(self):
        """Test creating and destroying an IPv4 ipset."""
        result = self.manager.create(self.test_set_name, family="inet")
        assert result is True
        assert self.manager.exists(self.test_set_name)

        result = self.manager.destroy(self.test_set_name)
        assert result is True
        assert not self.manager.exists(self.test_set_name)

    def test_create_and_destroy_ipv6_set(self):
        """Test creating and destroying an IPv6 ipset."""
        result = self.manager.create(self.test_set_name, family="inet6")
        assert result is True
        assert self.manager.exists(self.test_set_name)

        result = self.manager.destroy(self.test_set_name)
        assert result is True

    def test_add_and_list_entries(self):
        """Test adding entries and listing them."""
        self.manager.create(self.test_set_name, family="inet")

        self.manager.add(self.test_set_name, "192.168.1.0/24")
        self.manager.add(self.test_set_name, "10.0.0.0/8")

        entries = self.manager.list_entries(self.test_set_name)
        assert "192.168.1.0/24" in entries
        assert "10.0.0.0/8" in entries

    def test_atomic_update(self):
        """Test atomic update via temp set and swap."""
        self.manager.create(self.test_set_name, family="inet")
        self.manager.add(self.test_set_name, "192.168.1.0/24")

        new_entries = ["10.0.0.0/8", "172.16.0.0/12"]
        result = self.manager.update(self.test_set_name, new_entries, family="inet")
        assert result is True

        entries = self.manager.list_entries(self.test_set_name)
        assert "10.0.0.0/8" in entries
        assert "172.16.0.0/12" in entries
        assert "192.168.1.0/24" not in entries

    def test_add_many_entries(self):
        """Test batch adding entries."""
        self.manager.create(self.test_set_name, family="inet")

        entries = [f"10.0.{i}.0/24" for i in range(10)]
        result = self.manager.add_many(self.test_set_name, entries)
        assert result is True

        listed = self.manager.list_entries(self.test_set_name)
        assert len(listed) == 10

    def test_get_info(self):
        """Test getting ipset info."""
        self.manager.create(self.test_set_name, family="inet", max_entries=1024)

        info = self.manager.get_info(self.test_set_name)
        assert info is not None
        assert self.test_set_name in info


class TestEndToEnd:
    """End-to-end integration tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = IPSetManager()
        self.test_set_name = "test_e2e_dynamic_ipset"
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config.d")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_manager = ConfigManager(config_d_dir=self.config_dir)

    def teardown_method(self):
        """Clean up."""
        import shutil

        try:
            self.manager.destroy(self.test_set_name)
        except Exception:
            pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_workflow(self):
        """Test the complete workflow: config -> fetch -> update ipset."""
        config = ListConfig(
            name=self.test_set_name,
            source_url="https://example.com/ips.txt",
            family="inet",
        )
        self.config_manager.save(config)

        self.manager.create(self.test_set_name, family="inet")

        entries = ["192.168.1.0/24", "10.0.0.0/8", "172.16.0.0/12"]

        self.manager.update(self.test_set_name, entries, family="inet")

        listed = self.manager.list_entries(self.test_set_name)
        assert len(listed) == 3
        for entry in entries:
            assert entry in listed
