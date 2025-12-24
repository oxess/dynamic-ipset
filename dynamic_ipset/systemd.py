"""Systemd service and timer management for dynamic-ipset."""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional

from .config import ListConfig
from .constants import DEFAULT_PERIODIC, SERVICE_PREFIX, SYSTEMD_UNIT_DIR, TIMER_PREFIX
from .exceptions import SystemdError
from .validator import validate_list_name

logger = logging.getLogger(__name__)


# Systemd service template
SERVICE_TEMPLATE = """[Unit]
Description=Update ipset {name} from {source_url}
Documentation=man:dynamic-ipset(8)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/dynamic-ipset update {name}
StandardOutput=journal
StandardError=journal

# Security hardening
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
NoNewPrivileges=yes
CapabilityBoundingSet=CAP_NET_ADMIN
AmbientCapabilities=CAP_NET_ADMIN

[Install]
WantedBy=multi-user.target
"""

# Systemd timer template
TIMER_TEMPLATE = """[Unit]
Description=Periodic update timer for ipset {name}
Documentation=man:dynamic-ipset(8)

[Timer]
OnCalendar={periodic}
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""


class SystemdManager:
    """Manages systemd service and timer units for ipset updates."""

    def __init__(
        self,
        unit_dir: Optional[Path] = None,
        systemctl_cmd: str = "systemctl",
    ):
        """
        Initialize the systemd manager.

        Args:
            unit_dir: Directory for systemd unit files
            systemctl_cmd: Path to systemctl command
        """
        self.unit_dir = Path(unit_dir) if unit_dir else SYSTEMD_UNIT_DIR
        self.systemctl_cmd = systemctl_cmd

    def _run_systemctl(
        self,
        args: list[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Execute systemctl command.

        Args:
            args: Command arguments
            check: Whether to raise on non-zero exit

        Returns:
            CompletedProcess result

        Raises:
            SystemdError: If the command fails and check=True
        """
        cmd = [self.systemctl_cmd] + args
        logger.debug("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise SystemdError(f"systemctl command not found: {self.systemctl_cmd}")
        except Exception as e:
            raise SystemdError(f"Failed to run systemctl: {e}")

        if check and result.returncode != 0:
            stderr = result.stderr.strip()
            raise SystemdError(f"systemctl failed: {stderr}")

        return result

    def _service_name(self, list_name: str) -> str:
        """Get service unit name for a list."""
        return f"{SERVICE_PREFIX}{list_name}.service"

    def _timer_name(self, list_name: str) -> str:
        """Get timer unit name for a list."""
        return f"{TIMER_PREFIX}{list_name}.timer"

    def _service_path(self, list_name: str) -> Path:
        """Get service unit file path."""
        return self.unit_dir / self._service_name(list_name)

    def _timer_path(self, list_name: str) -> Path:
        """Get timer unit file path."""
        return self.unit_dir / self._timer_name(list_name)

    def create_units(self, list_config: ListConfig) -> tuple[Path, Path]:
        """
        Create systemd service and timer units for a list.

        Args:
            list_config: The list configuration

        Returns:
            Tuple of (service_path, timer_path)

        Raises:
            SystemdError: If unit files cannot be created
        """
        validate_list_name(list_config.name)

        # Generate service unit
        service_content = SERVICE_TEMPLATE.format(
            name=list_config.name,
            source_url=list_config.source_url,
        )

        # Generate timer unit
        timer_content = TIMER_TEMPLATE.format(
            name=list_config.name,
            periodic=list_config.periodic,
        )

        # Ensure directory exists
        self.unit_dir.mkdir(parents=True, exist_ok=True)

        service_path = self._service_path(list_config.name)
        timer_path = self._timer_path(list_config.name)

        try:
            with open(service_path, "w") as f:
                f.write(service_content)
            with open(timer_path, "w") as f:
                f.write(timer_content)
        except OSError as e:
            raise SystemdError(f"Cannot write unit files: {e}")

        logger.info("Created systemd units for %s", list_config.name)

        # Reload systemd
        self.daemon_reload()

        return service_path, timer_path

    def delete_units(self, list_name: str) -> None:
        """
        Delete systemd units for a list.

        Args:
            list_name: The list name

        Raises:
            SystemdError: If units cannot be deleted
        """
        validate_list_name(list_name)

        # Stop and disable first
        self.disable(list_name)

        # Remove unit files
        service_path = self._service_path(list_name)
        timer_path = self._timer_path(list_name)

        try:
            if service_path.exists():
                service_path.unlink()
            if timer_path.exists():
                timer_path.unlink()
        except OSError as e:
            raise SystemdError(f"Cannot delete unit files: {e}")

        logger.info("Deleted systemd units for %s", list_name)

        # Reload systemd
        self.daemon_reload()

    def daemon_reload(self) -> None:
        """
        Reload systemd daemon to pick up unit file changes.

        Raises:
            SystemdError: If reload fails
        """
        self._run_systemctl(["daemon-reload"])

    def enable(self, list_name: str) -> None:
        """
        Enable and start timer for a list.

        Args:
            list_name: The list name

        Raises:
            SystemdError: If enable/start fails
        """
        timer = self._timer_name(list_name)
        self._run_systemctl(["enable", timer])
        self._run_systemctl(["start", timer])
        logger.info("Enabled timer for %s", list_name)

    def disable(self, list_name: str) -> None:
        """
        Stop and disable timer for a list.

        Args:
            list_name: The list name
        """
        timer = self._timer_name(list_name)
        # Don't fail if already stopped/disabled
        self._run_systemctl(["stop", timer], check=False)
        self._run_systemctl(["disable", timer], check=False)
        logger.info("Disabled timer for %s", list_name)

    def is_enabled(self, list_name: str) -> bool:
        """
        Check if timer is enabled.

        Args:
            list_name: The list name

        Returns:
            True if timer is enabled
        """
        timer = self._timer_name(list_name)
        result = self._run_systemctl(["is-enabled", timer], check=False)
        return result.returncode == 0

    def is_active(self, list_name: str) -> bool:
        """
        Check if timer is active.

        Args:
            list_name: The list name

        Returns:
            True if timer is active
        """
        timer = self._timer_name(list_name)
        result = self._run_systemctl(["is-active", timer], check=False)
        return result.returncode == 0

    def get_status(self, list_name: str) -> Dict[str, any]:
        """
        Get detailed status of timer and service.

        Args:
            list_name: The list name

        Returns:
            Dictionary with status information
        """
        timer = self._timer_name(list_name)
        service = self._service_name(list_name)

        status = {
            "timer_enabled": self.is_enabled(list_name),
            "timer_active": self.is_active(list_name),
            "next_run": None,
            "last_run": None,
            "last_result": None,
        }

        # Get next run time
        result = self._run_systemctl(
            ["show", timer, "--property=NextElapseUSecRealtime"],
            check=False,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if "=" in output:
                value = output.split("=", 1)[1]
                if value and value != "n/a":
                    status["next_run"] = value

        # Get last run time
        result = self._run_systemctl(
            ["show", service, "--property=ExecMainStartTimestamp"],
            check=False,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if "=" in output:
                value = output.split("=", 1)[1]
                if value and value != "n/a":
                    status["last_run"] = value

        # Get last run result
        result = self._run_systemctl(
            ["show", service, "--property=ExecMainStatus"],
            check=False,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if "=" in output:
                value = output.split("=", 1)[1]
                status["last_result"] = value

        return status

    def run_now(self, list_name: str) -> None:
        """
        Trigger immediate run of the update service.

        Args:
            list_name: The list name

        Raises:
            SystemdError: If start fails
        """
        service = self._service_name(list_name)
        self._run_systemctl(["start", service])
        logger.info("Triggered update for %s", list_name)

    def unit_exists(self, list_name: str) -> bool:
        """
        Check if unit files exist for a list.

        Args:
            list_name: The list name

        Returns:
            True if both service and timer exist
        """
        service_path = self._service_path(list_name)
        timer_path = self._timer_path(list_name)
        return service_path.exists() and timer_path.exists()

    def get_service_content(self, list_name: str) -> Optional[str]:
        """
        Get the content of a service unit file.

        Args:
            list_name: The list name

        Returns:
            Service unit content or None if not found
        """
        service_path = self._service_path(list_name)
        if service_path.exists():
            return service_path.read_text()
        return None

    def get_timer_content(self, list_name: str) -> Optional[str]:
        """
        Get the content of a timer unit file.

        Args:
            list_name: The list name

        Returns:
            Timer unit content or None if not found
        """
        timer_path = self._timer_path(list_name)
        if timer_path.exists():
            return timer_path.read_text()
        return None
