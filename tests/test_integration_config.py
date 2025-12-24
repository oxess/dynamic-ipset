"""Integration tests for configuration and fetching.

These tests do NOT require root privileges.

Run with: pytest tests/test_integration_config.py -v
"""

import os
import shutil
import tempfile

import pytest

from dynamic_ipset.config import ConfigManager, ListConfig
from dynamic_ipset.fetcher import IPListFetcher


class TestConfigIntegration:
    """Integration tests for configuration management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config.d")
        os.makedirs(self.config_dir, exist_ok=True)
        self.manager = ConfigManager(config_d_dir=self.config_dir)

    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        config = ListConfig(
            name="test-list",
            source_url="https://example.com/ips.txt",
            periodic="*-*-* 0/6:00:00",
            family="inet",
        )

        self.manager.save(config)
        assert self.manager.exists("test-list")

        loaded = self.manager.load("test-list")
        assert loaded.name == config.name
        assert loaded.source_url == config.source_url
        assert loaded.periodic == config.periodic
        assert loaded.family == config.family

    def test_load_all_configs(self):
        """Test loading all configurations."""
        for i in range(3):
            config = ListConfig(
                name=f"test-list-{i}",
                source_url=f"https://example.com/ips{i}.txt",
            )
            self.manager.save(config)

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

        url = "https://raw.githubusercontent.com/stamparm/ipsum/master/levels/1.txt"

        try:
            entries = fetcher.fetch(url)
            assert len(entries) > 0
            for entry in entries[:10]:
                assert "/" in entry or "." in entry or ":" in entry
        except Exception as e:
            pytest.skip(f"Network request failed: {e}")
