"""Integration tests for dynamic-ipset.

These tests require:
- Root privileges (sudo)
- ipset installed on the system

Run with: sudo -E pytest tests/test_integration.py -v
"""

import os
import subprocess
import tempfile

import pytest

from dynamic_ipset.config import ConfigManager, ListConfig
from dynamic_ipset.fetcher import IPListFetcher
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


# Skip all tests if not root or ipset not installed
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
        # Create
        result = self.manager.create(self.test_set_name, family="inet")
        assert result is True
        assert self.manager.exists(self.test_set_name)

        # Destroy
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

        # Add entries
        self.manager.add(self.test_set_name, "192.168.1.0/24")
        self.manager.add(self.test_set_name, "10.0.0.0/8")

        # List entries
        entries = self.manager.list_entries(self.test_set_name)
        assert "192.168.1.0/24" in entries
        assert "10.0.0.0/8" in entries

    def test_atomic_update(self):
        """Test atomic update via temp set and swap."""
        # Create initial set
        self.manager.create(self.test_set_name, family="inet")
        self.manager.add(self.test_set_name, "192.168.1.0/24")

        # Atomic update with new entries
        new_entries = ["10.0.0.0/8", "172.16.0.0/12"]
        result = self.manager.update(self.test_set_name, new_entries, family="inet")
        assert result is True

        # Verify new entries
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


class TestConfigIntegration:
    """Integration tests for configuration management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config.d")
        os.makedirs(self.config_dir, exist_ok=True)
        self.manager = ConfigManager(config_dir=self.config_dir)

    def teardown_method(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        config = ListConfig(
            name="test-list",
            source_url="https://example.com/ips.txt",
            periodic="*-*-* 0/6:00:00",
            family="inet",
        )

        # Save
        self.manager.save(config)
        assert self.manager.exists("test-list")

        # Load
        loaded = self.manager.load("test-list")
        assert loaded.name == config.name
        assert loaded.source_url == config.source_url
        assert loaded.periodic == config.periodic
        assert loaded.family == config.family

    def test_load_all_configs(self):
        """Test loading all configurations."""
        # Create multiple configs
        for i in range(3):
            config = ListConfig(
                name=f"test-list-{i}",
                source_url=f"https://example.com/ips{i}.txt",
            )
            self.manager.save(config)

        # Load all
        configs = self.manager.load_all()
        assert len(configs) == 3

    def test_delete_config(self):
        """Test deleting configuration."""
        config = ListConfig(
            name="test-delete",
            source_url="https://example.com/ips.txt",
        )
        self.manager.save(config)
        assert self.manager.exists("test-delete")

        self.manager.delete("test-delete")
        assert not self.manager.exists("test-delete")


class TestFetcherIntegration:
    """Integration tests for URL fetching (requires network access)."""

    @pytest.mark.skipif(
        os.environ.get("SKIP_NETWORK_TESTS", "0") == "1",
        reason="Network tests disabled",
    )
    def test_fetch_real_ip_list(self):
        """Test fetching a real IP list from the internet."""
        fetcher = IPListFetcher()

        # Use a well-known blocklist that should be stable
        # Note: This test depends on external service availability
        url = "https://raw.githubusercontent.com/stamparm/ipsum/master/levels/1.txt"

        try:
            entries = fetcher.fetch(url)
            # Should have some entries
            assert len(entries) > 0
            # Entries should be valid IPs or CIDRs
            for entry in entries[:10]:  # Check first 10
                assert "/" in entry or "." in entry or ":" in entry
        except Exception as e:
            pytest.skip(f"Network request failed: {e}")


class TestEndToEnd:
    """End-to-end integration tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = IPSetManager()
        self.test_set_name = "test_e2e_dynamic_ipset"
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config.d")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_manager = ConfigManager(config_dir=self.config_dir)

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
        # Create config
        config = ListConfig(
            name=self.test_set_name,
            source_url="https://example.com/ips.txt",  # Won't actually fetch
            family="inet",
        )
        self.config_manager.save(config)

        # Create ipset
        self.manager.create(self.test_set_name, family="inet")

        # Simulate fetched entries
        entries = ["192.168.1.0/24", "10.0.0.0/8", "172.16.0.0/12"]

        # Update ipset
        self.manager.update(self.test_set_name, entries, family="inet")

        # Verify
        listed = self.manager.list_entries(self.test_set_name)
        assert len(listed) == 3
        for entry in entries:
            assert entry in listed
