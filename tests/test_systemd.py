"""Tests for systemd module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from dynamic_ipset.config import ListConfig
from dynamic_ipset.exceptions import SystemdError
from dynamic_ipset.systemd import SERVICE_TEMPLATE, TIMER_TEMPLATE, SystemdManager


def make_result(returncode=0, stdout="", stderr=""):
    """Create a mock CompletedProcess result."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestSystemdManager:
    """Tests for SystemdManager class."""

    def test_init_default_paths(self):
        """Test default paths are set."""
        manager = SystemdManager()
        assert manager.unit_dir.name == "system"
        assert manager.systemctl_cmd == "systemctl"

    def test_init_custom_paths(self, temp_dir):
        """Test custom paths can be set."""
        manager = SystemdManager(
            unit_dir=temp_dir,
            systemctl_cmd="/bin/systemctl",
        )
        assert manager.unit_dir == temp_dir
        assert manager.systemctl_cmd == "/bin/systemctl"

    def test_service_name(self):
        """Test service name generation."""
        manager = SystemdManager()
        assert manager._service_name("blocklist") == "dynamic-ipset-blocklist.service"

    def test_timer_name(self):
        """Test timer name generation."""
        manager = SystemdManager()
        assert manager._timer_name("blocklist") == "dynamic-ipset-blocklist.timer"

    @patch("subprocess.run")
    def test_create_units(self, mock_run, temp_dir):
        """Test creating systemd units."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager(unit_dir=temp_dir)
        config = ListConfig(
            name="testlist",
            source_url="http://example.com/list.txt",
            periodic="daily",
        )

        service_path, timer_path = manager.create_units(config)

        # Check files were created
        assert service_path.exists()
        assert timer_path.exists()

        # Check service content
        service_content = service_path.read_text()
        assert "testlist" in service_content
        assert "http://example.com/list.txt" in service_content
        assert "ExecStart" in service_content

        # Check timer content
        timer_content = timer_path.read_text()
        assert "testlist" in timer_content
        assert "daily" in timer_content
        assert "OnCalendar" in timer_content

        # Check daemon-reload was called
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_delete_units(self, mock_run, temp_dir):
        """Test deleting systemd units."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager(unit_dir=temp_dir)
        config = ListConfig(
            name="testlist",
            source_url="http://example.com",
        )

        # Create units first
        service_path, timer_path = manager.create_units(config)
        assert service_path.exists()
        assert timer_path.exists()

        # Delete units
        manager.delete_units("testlist")

        # Check files were deleted
        assert not service_path.exists()
        assert not timer_path.exists()

    @patch("subprocess.run")
    def test_enable(self, mock_run):
        """Test enabling timer."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager()
        manager.enable("testlist")

        # Check enable and start were called
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("enable" in c for c in calls)
        assert any("start" in c for c in calls)

    @patch("subprocess.run")
    def test_disable(self, mock_run):
        """Test disabling timer."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager()
        manager.disable("testlist")

        # Check stop and disable were called
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("stop" in c for c in calls)
        assert any("disable" in c for c in calls)

    @patch("subprocess.run")
    def test_is_enabled_true(self, mock_run):
        """Test is_enabled returns True when enabled."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager()
        assert manager.is_enabled("testlist") is True

    @patch("subprocess.run")
    def test_is_enabled_false(self, mock_run):
        """Test is_enabled returns False when not enabled."""
        mock_run.return_value = make_result(returncode=1)

        manager = SystemdManager()
        assert manager.is_enabled("testlist") is False

    @patch("subprocess.run")
    def test_is_active_true(self, mock_run):
        """Test is_active returns True when active."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager()
        assert manager.is_active("testlist") is True

    @patch("subprocess.run")
    def test_is_active_false(self, mock_run):
        """Test is_active returns False when not active."""
        mock_run.return_value = make_result(returncode=1)

        manager = SystemdManager()
        assert manager.is_active("testlist") is False

    @patch("subprocess.run")
    def test_get_status(self, mock_run):
        """Test getting status."""
        mock_run.side_effect = [
            make_result(returncode=0),  # is_enabled
            make_result(returncode=0),  # is_active
            make_result(returncode=0, stdout="NextElapseUSecRealtime=Mon 2024-01-01 03:00:00 UTC"),
            make_result(returncode=0, stdout="ExecMainStartTimestamp=Sun 2024-01-01 00:00:00 UTC"),
            make_result(returncode=0, stdout="ExecMainStatus=0"),
        ]

        manager = SystemdManager()
        status = manager.get_status("testlist")

        assert status["timer_enabled"] is True
        assert status["timer_active"] is True
        assert status["next_run"] is not None
        assert status["last_run"] is not None
        assert status["last_result"] == "0"

    @patch("subprocess.run")
    def test_run_now(self, mock_run):
        """Test triggering immediate run."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager()
        manager.run_now("testlist")

        cmd = mock_run.call_args[0][0]
        assert "start" in cmd
        assert "dynamic-ipset-testlist.service" in cmd

    def test_unit_exists(self, temp_dir):
        """Test checking if units exist."""
        manager = SystemdManager(unit_dir=temp_dir)

        # Units don't exist yet
        assert manager.unit_exists("testlist") is False

        # Create unit files manually
        service_path = temp_dir / "dynamic-ipset-testlist.service"
        timer_path = temp_dir / "dynamic-ipset-testlist.timer"
        service_path.write_text("test")
        timer_path.write_text("test")

        # Now they exist
        assert manager.unit_exists("testlist") is True

        # Only service exists
        timer_path.unlink()
        assert manager.unit_exists("testlist") is False

    def test_get_service_content(self, temp_dir):
        """Test getting service content."""
        manager = SystemdManager(unit_dir=temp_dir)

        # File doesn't exist
        assert manager.get_service_content("testlist") is None

        # Create file
        service_path = temp_dir / "dynamic-ipset-testlist.service"
        service_path.write_text("service content here")

        assert manager.get_service_content("testlist") == "service content here"

    def test_get_timer_content(self, temp_dir):
        """Test getting timer content."""
        manager = SystemdManager(unit_dir=temp_dir)

        # File doesn't exist
        assert manager.get_timer_content("testlist") is None

        # Create file
        timer_path = temp_dir / "dynamic-ipset-testlist.timer"
        timer_path.write_text("timer content here")

        assert manager.get_timer_content("testlist") == "timer content here"

    @patch("subprocess.run")
    def test_daemon_reload(self, mock_run):
        """Test daemon reload."""
        mock_run.return_value = make_result(returncode=0)

        manager = SystemdManager()
        manager.daemon_reload()

        cmd = mock_run.call_args[0][0]
        assert "daemon-reload" in cmd

    @patch("subprocess.run")
    def test_systemctl_error(self, mock_run):
        """Test handling systemctl errors."""
        mock_run.return_value = make_result(
            returncode=1,
            stderr="Permission denied",
        )

        manager = SystemdManager()
        with pytest.raises(SystemdError, match="Permission denied"):
            manager.daemon_reload()

    @patch("subprocess.run")
    def test_systemctl_not_found(self, mock_run):
        """Test handling systemctl not found."""
        mock_run.side_effect = FileNotFoundError()

        manager = SystemdManager()
        with pytest.raises(SystemdError, match="not found"):
            manager.daemon_reload()


class TestTemplates:
    """Tests for systemd unit templates."""

    def test_service_template_contains_required_sections(self):
        """Test service template has required sections."""
        assert "[Unit]" in SERVICE_TEMPLATE
        assert "[Service]" in SERVICE_TEMPLATE
        assert "[Install]" in SERVICE_TEMPLATE

    def test_service_template_has_placeholders(self):
        """Test service template has placeholders."""
        assert "{name}" in SERVICE_TEMPLATE
        assert "{source_url}" in SERVICE_TEMPLATE

    def test_timer_template_contains_required_sections(self):
        """Test timer template has required sections."""
        assert "[Unit]" in TIMER_TEMPLATE
        assert "[Timer]" in TIMER_TEMPLATE
        assert "[Install]" in TIMER_TEMPLATE

    def test_timer_template_has_placeholders(self):
        """Test timer template has placeholders."""
        assert "{name}" in TIMER_TEMPLATE
        assert "{periodic}" in TIMER_TEMPLATE

    def test_service_template_formatting(self):
        """Test service template can be formatted."""
        content = SERVICE_TEMPLATE.format(
            name="testlist",
            source_url="http://example.com",
        )
        assert "testlist" in content
        assert "http://example.com" in content
        assert "{name}" not in content

    def test_timer_template_formatting(self):
        """Test timer template can be formatted."""
        content = TIMER_TEMPLATE.format(
            name="testlist",
            periodic="daily",
        )
        assert "testlist" in content
        assert "daily" in content
        assert "{periodic}" not in content
