"""Tests for config module."""

import pytest

from dynamic_ipset.config import ConfigManager, ListConfig
from dynamic_ipset.constants import DEFAULT_IPSET_TYPE, DEFAULT_PERIODIC
from dynamic_ipset.exceptions import ConfigError, ValidationError


class TestListConfig:
    """Tests for ListConfig dataclass."""

    def test_create_with_defaults(self):
        """Test creating config with default values."""
        config = ListConfig(name="test", source_url="http://example.com/list.txt")
        assert config.name == "test"
        assert config.source_url == "http://example.com/list.txt"
        assert config.enabled is True
        assert config.periodic == DEFAULT_PERIODIC
        assert config.ipset_type == DEFAULT_IPSET_TYPE

    def test_create_with_custom_values(self):
        """Test creating config with custom values."""
        config = ListConfig(
            name="custom",
            source_url="https://example.com/ips.txt",
            periodic="daily",
            enabled=False,
            max_entries=1000,
        )
        assert config.name == "custom"
        assert config.periodic == "daily"
        assert config.enabled is False
        assert config.max_entries == 1000

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = ListConfig(name="test", source_url="http://example.com")
        d = config.to_dict()
        assert "source_url" in d
        assert d["enabled"] == "yes"
        assert d["source_url"] == "http://example.com"

    def test_to_dict_disabled(self):
        """Test to_dict with disabled config."""
        config = ListConfig(name="test", source_url="http://example.com", enabled=False)
        d = config.to_dict()
        assert d["enabled"] == "no"

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "source_url": "http://example.com",
            "periodic": "daily",
            "enabled": "no",
        }
        config = ListConfig.from_dict("test", data)
        assert config.source_url == "http://example.com"
        assert config.periodic == "daily"
        assert config.enabled is False

    def test_from_dict_missing_url(self):
        """Test from_dict with missing source_url."""
        with pytest.raises(ConfigError, match="Missing source_url"):
            ListConfig.from_dict("test", {})

    def test_from_dict_enabled_variations(self):
        """Test from_dict handles different enabled values."""
        # Test 'yes'
        config = ListConfig.from_dict("t", {"source_url": "http://x", "enabled": "yes"})
        assert config.enabled is True

        # Test 'true'
        config = ListConfig.from_dict("t", {"source_url": "http://x", "enabled": "true"})
        assert config.enabled is True

        # Test '1'
        config = ListConfig.from_dict("t", {"source_url": "http://x", "enabled": "1"})
        assert config.enabled is True

        # Test 'no'
        config = ListConfig.from_dict("t", {"source_url": "http://x", "enabled": "no"})
        assert config.enabled is False


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_init_default_paths(self):
        """Test default paths are set."""
        manager = ConfigManager()
        assert manager.config_file.name == "config"
        assert manager.config_d_dir.name == "config.d"

    def test_init_custom_paths(self, config_dir):
        """Test custom paths can be set."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )
        assert manager.config_file == config_dir / "config"
        assert manager.config_d_dir == config_dir / "config.d"

    def test_save_and_load(self, config_dir):
        """Test saving and loading a config."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        config = ListConfig(name="testlist", source_url="http://example.com/ips.txt")
        manager.save(config)

        loaded = manager.load("testlist")
        assert loaded.name == "testlist"
        assert loaded.source_url == "http://example.com/ips.txt"
        assert loaded.enabled is True

    def test_save_creates_directory(self, temp_dir):
        """Test save creates config.d directory if missing."""
        config_d = temp_dir / "new_config.d"
        manager = ConfigManager(
            config_file=temp_dir / "config",
            config_d_dir=config_d,
        )

        assert not config_d.exists()
        config = ListConfig(name="test", source_url="http://example.com")
        manager.save(config)
        assert config_d.exists()

    def test_save_returns_path(self, config_dir):
        """Test save returns the config file path."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        config = ListConfig(name="mylist", source_url="http://example.com")
        path = manager.save(config)

        assert path.exists()
        assert path.name == "mylist.conf"

    def test_load_nonexistent(self, config_dir):
        """Test loading non-existent list raises error."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        with pytest.raises(ConfigError, match="not found"):
            manager.load("nonexistent")

    def test_load_invalid_name(self, config_dir):
        """Test loading with invalid name raises error."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        with pytest.raises(ValidationError):
            manager.load("1invalid")

    def test_delete(self, config_dir):
        """Test deleting a config."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        config = ListConfig(name="todelete", source_url="http://example.com")
        manager.save(config)
        assert manager.exists("todelete")

        manager.delete("todelete")
        assert not manager.exists("todelete")

    def test_delete_nonexistent(self, config_dir):
        """Test deleting non-existent list raises error."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        with pytest.raises(ConfigError, match="not found"):
            manager.delete("nonexistent")

    def test_exists(self, config_dir):
        """Test exists method."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        assert not manager.exists("testlist")

        config = ListConfig(name="testlist", source_url="http://example.com")
        manager.save(config)

        assert manager.exists("testlist")

    def test_load_all_empty(self, config_dir):
        """Test load_all with empty config.d."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        lists = manager.load_all()
        assert lists == {}

    def test_load_all_multiple(self, config_dir):
        """Test load_all with multiple configs."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        # Save multiple configs
        manager.save(ListConfig(name="list1", source_url="http://example.com/1"))
        manager.save(ListConfig(name="list2", source_url="http://example.com/2"))
        manager.save(ListConfig(name="list3", source_url="http://example.com/3"))

        lists = manager.load_all()
        assert len(lists) == 3
        assert "list1" in lists
        assert "list2" in lists
        assert "list3" in lists

    def test_load_all_nonexistent_dir(self, temp_dir):
        """Test load_all when config.d doesn't exist."""
        manager = ConfigManager(
            config_file=temp_dir / "config",
            config_d_dir=temp_dir / "nonexistent_config.d",
        )

        lists = manager.load_all()
        assert lists == {}

    def test_get_config_path(self, config_dir):
        """Test get_config_path method."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        path = manager.get_config_path("mylist")
        assert path == config_dir / "config.d" / "mylist.conf"

    def test_save_validates_url(self, config_dir):
        """Test save validates URL."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        config = ListConfig(name="test", source_url="invalid_url")
        with pytest.raises(ValidationError, match="http"):
            manager.save(config)

    def test_save_validates_name(self, config_dir):
        """Test save validates list name."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        config = ListConfig(name="1invalid", source_url="http://example.com")
        with pytest.raises(ValidationError, match="start with letter"):
            manager.save(config)

    def test_save_validates_periodic(self, config_dir):
        """Test save validates periodic schedule."""
        manager = ConfigManager(
            config_file=config_dir / "config",
            config_d_dir=config_dir / "config.d",
        )

        config = ListConfig(
            name="test",
            source_url="http://example.com",
            periodic="invalid_schedule",
        )
        with pytest.raises(ValidationError, match="OnCalendar"):
            manager.save(config)
