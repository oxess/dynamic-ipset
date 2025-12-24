"""Configuration management for dynamic-ipset."""

import configparser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .constants import (
    CONFIG_D_DIR,
    CONFIG_FILE,
    DEFAULT_IPSET_FAMILY,
    DEFAULT_IPSET_TYPE,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_PERIODIC,
)
from .exceptions import ConfigError
from .validator import validate_list_name, validate_oncalendar, validate_url


@dataclass
class ListConfig:
    """Represents configuration for a single IP list."""

    name: str
    source_url: str
    periodic: str = DEFAULT_PERIODIC
    ipset_type: str = DEFAULT_IPSET_TYPE
    family: str = DEFAULT_IPSET_FAMILY
    max_entries: int = DEFAULT_MAX_ENTRIES
    enabled: bool = True

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for serialization."""
        return {
            "source_url": self.source_url,
            "periodic": self.periodic,
            "ipset_type": self.ipset_type,
            "family": self.family,
            "max_entries": str(self.max_entries),
            "enabled": "yes" if self.enabled else "no",
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, str]) -> "ListConfig":
        """Create from dictionary."""
        source_url = data.get("source_url")
        if not source_url:
            raise ConfigError(f"Missing source_url for list '{name}'")

        return cls(
            name=name,
            source_url=source_url,
            periodic=data.get("periodic", DEFAULT_PERIODIC),
            ipset_type=data.get("ipset_type", DEFAULT_IPSET_TYPE),
            family=data.get("family", DEFAULT_IPSET_FAMILY),
            max_entries=int(data.get("max_entries", DEFAULT_MAX_ENTRIES)),
            enabled=data.get("enabled", "yes").lower() in ("yes", "true", "1"),
        )


class ConfigManager:
    """Manages dynamic-ipset configuration files."""

    def __init__(
        self,
        config_file: Optional[Path] = None,
        config_d_dir: Optional[Path] = None,
    ):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to main config file (default: /etc/dynamic-ipset/config)
            config_d_dir: Path to config.d directory (default: /etc/dynamic-ipset/config.d)
        """
        self.config_file = Path(config_file) if config_file else CONFIG_FILE
        self.config_d_dir = Path(config_d_dir) if config_d_dir else CONFIG_D_DIR

    def _get_list_config_path(self, name: str) -> Path:
        """Get config file path for a specific list."""
        return self.config_d_dir / f"{name}.conf"

    def load_all(self) -> dict[str, ListConfig]:
        """
        Load all list configurations from config.d directory.

        Returns:
            Dictionary mapping list names to their configurations
        """
        lists: dict[str, ListConfig] = {}

        if not self.config_d_dir.exists():
            return lists

        # Load from config.d directory
        for conf_file in sorted(self.config_d_dir.glob("*.conf")):
            parser = configparser.ConfigParser()
            try:
                parser.read(conf_file)
            except configparser.Error as e:
                raise ConfigError(f"Error reading {conf_file}: {e}") from e

            for section in parser.sections():
                if section.startswith("list:"):
                    name = section[5:]  # Remove 'list:' prefix
                    data = dict(parser.items(section))
                    try:
                        lists[name] = ListConfig.from_dict(name, data)
                    except (ValueError, ConfigError) as e:
                        raise ConfigError(f"Error in {conf_file}: {e}") from e

        return lists

    def load(self, name: str) -> ListConfig:
        """
        Load a specific list configuration.

        Args:
            name: The list name

        Returns:
            The list configuration

        Raises:
            ConfigError: If the list is not found or config is invalid
        """
        validate_list_name(name)
        conf_path = self._get_list_config_path(name)

        if not conf_path.exists():
            raise ConfigError(f"List '{name}' not found")

        parser = configparser.ConfigParser()
        try:
            parser.read(conf_path)
        except configparser.Error as e:
            raise ConfigError(f"Error reading config for '{name}': {e}") from e

        section = f"list:{name}"
        if not parser.has_section(section):
            raise ConfigError(f"Invalid config file for '{name}'")

        data = dict(parser.items(section))
        return ListConfig.from_dict(name, data)

    def save(self, list_config: ListConfig) -> Path:
        """
        Save a list configuration.

        Args:
            list_config: The list configuration to save

        Returns:
            Path to the saved config file

        Raises:
            ValidationError: If the configuration is invalid
            ConfigError: If the file cannot be written
        """
        # Validate configuration
        validate_list_name(list_config.name)
        validate_url(list_config.source_url)
        validate_oncalendar(list_config.periodic)

        conf_path = self._get_list_config_path(list_config.name)

        parser = configparser.ConfigParser()
        section = f"list:{list_config.name}"
        parser.add_section(section)

        for key, value in list_config.to_dict().items():
            parser.set(section, key, value)

        # Ensure directory exists
        self.config_d_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(conf_path, "w") as f:
                parser.write(f)
        except OSError as e:
            raise ConfigError(f"Cannot write config for '{list_config.name}': {e}") from e

        return conf_path

    def delete(self, name: str) -> None:
        """
        Delete a list configuration.

        Args:
            name: The list name

        Raises:
            ConfigError: If the list is not found
        """
        validate_list_name(name)
        conf_path = self._get_list_config_path(name)

        if not conf_path.exists():
            raise ConfigError(f"List '{name}' not found")

        try:
            conf_path.unlink()
        except OSError as e:
            raise ConfigError(f"Cannot delete config for '{name}': {e}") from e

    def exists(self, name: str) -> bool:
        """
        Check if a list configuration exists.

        Args:
            name: The list name

        Returns:
            True if the configuration exists
        """
        conf_path = self._get_list_config_path(name)
        return conf_path.exists()

    def get_config_path(self, name: str) -> Path:
        """
        Get the path to a list's configuration file.

        Args:
            name: The list name

        Returns:
            Path to the configuration file
        """
        return self._get_list_config_path(name)
