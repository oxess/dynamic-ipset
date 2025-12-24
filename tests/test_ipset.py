"""Tests for ipset module."""

import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock

from dynamic_ipset.ipset import IPSetManager
from dynamic_ipset.exceptions import IPSetError, ValidationError


def make_result(returncode=0, stdout="", stderr=""):
    """Create a mock CompletedProcess result."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestIPSetManager:
    """Tests for IPSetManager class."""

    def test_init_default_cmd(self):
        """Test default ipset command."""
        manager = IPSetManager()
        assert manager.ipset_cmd == "ipset"

    def test_init_custom_cmd(self):
        """Test custom ipset command."""
        manager = IPSetManager(ipset_cmd="/usr/sbin/ipset")
        assert manager.ipset_cmd == "/usr/sbin/ipset"

    @patch("subprocess.run")
    def test_exists_true(self, mock_run):
        """Test exists returns True when ipset exists."""
        mock_run.return_value = make_result(returncode=0)

        manager = IPSetManager()
        assert manager.exists("testlist") is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_exists_false(self, mock_run):
        """Test exists returns False when ipset doesn't exist."""
        mock_run.return_value = make_result(returncode=1, stderr="does not exist")

        manager = IPSetManager()
        assert manager.exists("testlist") is False

    @patch("subprocess.run")
    def test_create_success(self, mock_run):
        """Test successful ipset creation."""
        # First call: exists check (not exists)
        # Second call: create
        mock_run.side_effect = [
            make_result(returncode=1),  # exists check
            make_result(returncode=0),  # create
        ]

        manager = IPSetManager()
        result = manager.create("testlist")

        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_create_already_exists(self, mock_run):
        """Test create when ipset already exists."""
        mock_run.return_value = make_result(returncode=0)  # exists

        manager = IPSetManager()
        result = manager.create("testlist")

        assert result is False
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_create_with_options(self, mock_run):
        """Test create with custom options."""
        mock_run.side_effect = [
            make_result(returncode=1),  # exists check
            make_result(returncode=0),  # create
        ]

        manager = IPSetManager()
        manager.create(
            "testlist",
            ipset_type="hash:ip",
            family="inet6",
            max_entries=10000,
        )

        # Check the create command args
        create_call = mock_run.call_args_list[1]
        cmd = create_call[0][0]
        assert "hash:ip" in cmd
        assert "inet6" in cmd
        assert "10000" in cmd

    def test_create_invalid_name(self):
        """Test create with invalid name raises error."""
        manager = IPSetManager()
        with pytest.raises(ValidationError):
            manager.create("1invalid")

    @patch("subprocess.run")
    def test_destroy_success(self, mock_run):
        """Test successful ipset destruction."""
        mock_run.side_effect = [
            make_result(returncode=0),  # exists check
            make_result(returncode=0),  # destroy
        ]

        manager = IPSetManager()
        result = manager.destroy("testlist")

        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_destroy_not_exists(self, mock_run):
        """Test destroy when ipset doesn't exist."""
        mock_run.return_value = make_result(returncode=1)  # doesn't exist

        manager = IPSetManager()
        result = manager.destroy("testlist")

        assert result is False
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_flush(self, mock_run):
        """Test flushing ipset."""
        mock_run.return_value = make_result(returncode=0)

        manager = IPSetManager()
        manager.flush("testlist")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "flush" in cmd
        assert "testlist" in cmd

    @patch("subprocess.run")
    def test_add(self, mock_run):
        """Test adding entry to ipset."""
        mock_run.return_value = make_result(returncode=0)

        manager = IPSetManager()
        manager.add("testlist", "192.168.1.0/24")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "add" in cmd
        assert "192.168.1.0/24" in cmd
        assert "-exist" in cmd

    @patch("subprocess.run")
    def test_add_many(self, mock_run):
        """Test adding multiple entries."""
        mock_run.return_value = make_result(returncode=0)

        manager = IPSetManager()
        entries = ["192.168.1.0/24", "10.0.0.0/8", "8.8.8.8/32"]
        result = manager.add_many("testlist", entries)

        assert result == 3
        # Should use restore command
        cmd = mock_run.call_args[0][0]
        assert "restore" in cmd

    @patch("subprocess.run")
    def test_add_many_empty(self, mock_run):
        """Test add_many with empty list."""
        manager = IPSetManager()
        result = manager.add_many("testlist", [])

        assert result == 0
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_remove(self, mock_run):
        """Test removing entry from ipset."""
        mock_run.return_value = make_result(returncode=0)

        manager = IPSetManager()
        manager.remove("testlist", "192.168.1.0/24")

        cmd = mock_run.call_args[0][0]
        assert "del" in cmd
        assert "192.168.1.0/24" in cmd

    @patch("subprocess.run")
    def test_update(self, mock_run):
        """Test atomic update of ipset."""
        # Mock sequence:
        # 1. exists check for main set (doesn't exist)
        # 2. create main set
        # 3. exists check for temp set (doesn't exist)
        # 4. create temp set
        # 5. restore entries
        # 6. swap
        # 7. exists check for temp set (exists)
        # 8. destroy temp set
        mock_run.side_effect = [
            make_result(returncode=1),  # exists main
            make_result(returncode=0),  # create main
            make_result(returncode=1),  # exists temp
            make_result(returncode=0),  # create temp
            make_result(returncode=0),  # restore
            make_result(returncode=0),  # swap
            make_result(returncode=0),  # exists temp
            make_result(returncode=0),  # destroy temp
        ]

        manager = IPSetManager()
        entries = ["192.168.1.0/24", "10.0.0.0/8"]
        result = manager.update("testlist", entries)

        assert result == 2

    @patch("subprocess.run")
    def test_update_cleans_up_on_failure(self, mock_run):
        """Test update cleans up temp set on failure."""
        mock_run.side_effect = [
            make_result(returncode=1),  # exists main
            make_result(returncode=0),  # create main
            make_result(returncode=1),  # exists temp
            make_result(returncode=0),  # create temp
            make_result(returncode=1, stderr="restore failed"),  # restore fails
            make_result(returncode=0),  # exists temp (cleanup check)
            make_result(returncode=0),  # destroy temp (cleanup)
        ]

        manager = IPSetManager()
        with pytest.raises(IPSetError, match="restore failed"):
            manager.update("testlist", ["192.168.1.0/24"])

    @patch("subprocess.run")
    def test_list_entries(self, mock_run):
        """Test listing ipset entries."""
        mock_run.return_value = make_result(
            returncode=0,
            stdout="""Name: testlist
Type: hash:net
Header: family inet hashsize 1024 maxelem 65536
Size in memory: 1024
Members:
192.168.1.0/24
10.0.0.0/8
"""
        )

        manager = IPSetManager()
        entries = manager.list_entries("testlist")

        assert len(entries) == 2
        assert "192.168.1.0/24" in entries
        assert "10.0.0.0/8" in entries

    @patch("subprocess.run")
    def test_list_entries_empty(self, mock_run):
        """Test listing empty ipset."""
        mock_run.return_value = make_result(
            returncode=0,
            stdout="""Name: testlist
Type: hash:net
Header: family inet hashsize 1024 maxelem 65536
Size in memory: 1024
Members:
"""
        )

        manager = IPSetManager()
        entries = manager.list_entries("testlist")

        assert entries == []

    @patch("subprocess.run")
    def test_list_all(self, mock_run):
        """Test listing all ipsets."""
        mock_run.return_value = make_result(
            returncode=0,
            stdout="blocklist\nwhitelist\ntestlist\n"
        )

        manager = IPSetManager()
        sets = manager.list_all()

        assert len(sets) == 3
        assert "blocklist" in sets
        assert "whitelist" in sets
        assert "testlist" in sets

    @patch("subprocess.run")
    def test_get_info(self, mock_run):
        """Test getting ipset info."""
        mock_run.return_value = make_result(
            returncode=0,
            stdout="""Name: testlist
Type: hash:net
Revision: 6
Header: family inet hashsize 1024 maxelem 65536
Size in memory: 2048
References: 0
Number of entries: 42
"""
        )

        manager = IPSetManager()
        info = manager.get_info("testlist")

        assert info["name"] == "testlist"
        assert info["type"] == "hash:net"
        assert info["family"] == "inet"
        assert info["max_entries"] == 65536
        assert info["entries"] == 42

    @patch("subprocess.run")
    def test_count_entries(self, mock_run):
        """Test counting entries."""
        mock_run.return_value = make_result(
            returncode=0,
            stdout="""Name: testlist
Type: hash:net
Header: family inet hashsize 1024 maxelem 65536
Number of entries: 100
"""
        )

        manager = IPSetManager()
        count = manager.count_entries("testlist")

        assert count == 100

    @patch("subprocess.run")
    def test_command_not_found(self, mock_run):
        """Test handling ipset command not found."""
        mock_run.side_effect = FileNotFoundError("ipset not found")

        manager = IPSetManager()
        with pytest.raises(IPSetError, match="not found"):
            manager.exists("testlist")

    @patch("subprocess.run")
    def test_command_failure(self, mock_run):
        """Test handling ipset command failure."""
        mock_run.return_value = make_result(
            returncode=1,
            stderr="Permission denied"
        )

        manager = IPSetManager()
        with pytest.raises(IPSetError, match="Permission denied"):
            manager.create("testlist")
