"""Tests for CLI module."""

from unittest.mock import MagicMock, patch

import pytest

from dynamic_ipset.cli import CLI, main
from dynamic_ipset.config import ListConfig
from dynamic_ipset.exceptions import ConfigError


class TestCLI:
    """Tests for CLI class."""

    @pytest.fixture
    def mock_managers(self):
        """Create mock managers for CLI."""
        config = MagicMock()
        ipset = MagicMock()
        fetcher = MagicMock()
        systemd = MagicMock()
        return config, ipset, fetcher, systemd

    @pytest.fixture
    def cli(self, mock_managers):
        """Create CLI instance with mocked managers."""
        config, ipset, fetcher, systemd = mock_managers
        return CLI(
            config_manager=config,
            ipset_manager=ipset,
            fetcher=fetcher,
            systemd_manager=systemd,
        )

    def test_create_parser(self, cli):
        """Test parser creation."""
        parser = cli.create_parser()
        assert parser is not None

    def test_parse_create_command(self, cli):
        """Test parsing create command."""
        parser = cli.create_parser()
        args = parser.parse_args(["create", "mylist", "http://example.com/list.txt"])
        assert args.command == "create"
        assert args.name == "mylist"
        assert args.url == "http://example.com/list.txt"

    def test_parse_create_with_periodic(self, cli):
        """Test parsing create with periodic."""
        parser = cli.create_parser()
        args = parser.parse_args(["create", "mylist", "http://example.com/list.txt", "daily"])
        assert args.periodic == "daily"

    def test_parse_delete_command(self, cli):
        """Test parsing delete command."""
        parser = cli.create_parser()
        args = parser.parse_args(["delete", "mylist"])
        assert args.command == "delete"
        assert args.name == "mylist"

    def test_parse_show_command(self, cli):
        """Test parsing show command."""
        parser = cli.create_parser()
        args = parser.parse_args(["show"])
        assert args.command == "show"
        assert args.name is None

    def test_parse_show_with_name(self, cli):
        """Test parsing show with name."""
        parser = cli.create_parser()
        args = parser.parse_args(["show", "mylist"])
        assert args.name == "mylist"

    def test_cmd_create_success(self, cli, mock_managers):
        """Test create command success."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = False
        fetcher.fetch.return_value = (["192.168.1.0/24"], [])

        parser = cli.create_parser()
        args = parser.parse_args(["create", "mylist", "http://example.com"])

        result = cli.cmd_create(args)

        assert result == 0
        config.save.assert_called_once()
        systemd.create_units.assert_called_once()
        systemd.enable.assert_called_once()

    def test_cmd_create_already_exists(self, cli, mock_managers, capsys):
        """Test create command when list already exists."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = True

        parser = cli.create_parser()
        args = parser.parse_args(["create", "mylist", "http://example.com"])

        result = cli.cmd_create(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_cmd_create_no_enable(self, cli, mock_managers):
        """Test create with --no-enable."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = False
        fetcher.fetch.return_value = (["192.168.1.0/24"], [])

        parser = cli.create_parser()
        args = parser.parse_args(["create", "mylist", "http://example.com", "--no-enable"])

        cli.cmd_create(args)

        systemd.enable.assert_not_called()

    def test_cmd_create_no_fetch(self, cli, mock_managers):
        """Test create with --no-fetch."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = False

        parser = cli.create_parser()
        args = parser.parse_args(["create", "mylist", "http://example.com", "--no-fetch"])

        cli.cmd_create(args)

        fetcher.fetch.assert_not_called()

    def test_cmd_delete_success(self, cli, mock_managers):
        """Test delete command success."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = True
        ipset.exists.return_value = True

        parser = cli.create_parser()
        args = parser.parse_args(["delete", "mylist"])

        result = cli.cmd_delete(args)

        assert result == 0
        systemd.delete_units.assert_called_once()
        config.delete.assert_called_once()
        ipset.destroy.assert_called_once()

    def test_cmd_delete_not_found(self, cli, mock_managers, capsys):
        """Test delete command when list not found."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = False

        parser = cli.create_parser()
        args = parser.parse_args(["delete", "mylist"])

        result = cli.cmd_delete(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_cmd_delete_keep_ipset(self, cli, mock_managers):
        """Test delete with --keep-ipset."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = True

        parser = cli.create_parser()
        args = parser.parse_args(["delete", "mylist", "--keep-ipset"])

        cli.cmd_delete(args)

        ipset.destroy.assert_not_called()

    def test_cmd_show_all(self, cli, mock_managers, capsys):
        """Test show all lists."""
        config, ipset, fetcher, systemd = mock_managers
        config.load_all.return_value = {
            "list1": ListConfig(name="list1", source_url="http://example.com/1"),
            "list2": ListConfig(name="list2", source_url="http://example.com/2"),
        }

        parser = cli.create_parser()
        args = parser.parse_args(["show"])

        result = cli.cmd_show(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "list1" in captured.out
        assert "list2" in captured.out

    def test_cmd_show_empty(self, cli, mock_managers, capsys):
        """Test show when no lists configured."""
        config, ipset, fetcher, systemd = mock_managers
        config.load_all.return_value = {}

        parser = cli.create_parser()
        args = parser.parse_args(["show"])

        result = cli.cmd_show(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No ipset lists configured" in captured.out

    def test_cmd_show_one(self, cli, mock_managers, capsys):
        """Test show single list."""
        config, ipset, fetcher, systemd = mock_managers
        config.load.return_value = ListConfig(
            name="mylist",
            source_url="http://example.com",
        )
        systemd.get_status.return_value = {
            "timer_enabled": True,
            "timer_active": True,
            "next_run": "tomorrow",
            "last_run": "yesterday",
            "last_result": "0",
        }
        ipset.exists.return_value = True
        ipset.count_entries.return_value = 100

        parser = cli.create_parser()
        args = parser.parse_args(["show", "mylist"])

        result = cli.cmd_show(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "mylist" in captured.out
        assert "http://example.com" in captured.out
        assert "Entry count: 100" in captured.out

    def test_cmd_show_not_found(self, cli, mock_managers, capsys):
        """Test show when list not found."""
        config, ipset, fetcher, systemd = mock_managers
        config.load.side_effect = ConfigError("List 'mylist' not found")

        parser = cli.create_parser()
        args = parser.parse_args(["show", "mylist"])

        result = cli.cmd_show(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_cmd_update(self, cli, mock_managers, capsys):
        """Test update command."""
        config, ipset, fetcher, systemd = mock_managers
        config.load.return_value = ListConfig(
            name="mylist",
            source_url="http://example.com",
        )
        fetcher.fetch.return_value = (
            ["192.168.1.0/24", "10.0.0.0/8"],
            [],
        )

        parser = cli.create_parser()
        args = parser.parse_args(["update", "mylist"])

        result = cli.cmd_update(args)

        assert result == 0
        fetcher.fetch.assert_called_once()
        ipset.update.assert_called_once()
        captured = capsys.readouterr()
        assert "Fetched 2 valid entries" in captured.out

    def test_cmd_update_with_errors(self, cli, mock_managers, capsys):
        """Test update command with parse errors."""
        config, ipset, fetcher, systemd = mock_managers
        config.load.return_value = ListConfig(
            name="mylist",
            source_url="http://example.com",
        )
        fetcher.fetch.return_value = (
            ["192.168.1.0/24"],
            ["Line 2: Invalid entry", "Line 5: Invalid entry"],
        )

        parser = cli.create_parser()
        args = parser.parse_args(["update", "mylist"])

        result = cli.cmd_update(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Warning:" in captured.err

    def test_cmd_enable(self, cli, mock_managers, capsys):
        """Test enable command."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = True

        parser = cli.create_parser()
        args = parser.parse_args(["enable", "mylist"])

        result = cli.cmd_enable(args)

        assert result == 0
        systemd.enable.assert_called_once_with("mylist")
        captured = capsys.readouterr()
        assert "enabled" in captured.out

    def test_cmd_disable(self, cli, mock_managers, capsys):
        """Test disable command."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = True

        parser = cli.create_parser()
        args = parser.parse_args(["disable", "mylist"])

        result = cli.cmd_disable(args)

        assert result == 0
        systemd.disable.assert_called_once_with("mylist")
        captured = capsys.readouterr()
        assert "disabled" in captured.out

    def test_cmd_run(self, cli, mock_managers, capsys):
        """Test run command."""
        config, ipset, fetcher, systemd = mock_managers
        config.exists.return_value = True

        parser = cli.create_parser()
        args = parser.parse_args(["run", "mylist"])

        result = cli.cmd_run(args)

        assert result == 0
        systemd.run_now.assert_called_once_with("mylist")
        captured = capsys.readouterr()
        assert "triggered" in captured.out

    def test_cmd_reload(self, cli, mock_managers, capsys):
        """Test reload command."""
        config, ipset, fetcher, systemd = mock_managers
        config.load_all.return_value = {
            "list1": ListConfig(name="list1", source_url="http://example.com/1"),
        }

        parser = cli.create_parser()
        args = parser.parse_args(["reload"])

        result = cli.cmd_reload(args)

        assert result == 0
        systemd.create_units.assert_called_once()
        captured = capsys.readouterr()
        assert "Reload complete" in captured.out

    def test_cmd_reload_dry_run(self, cli, mock_managers, capsys):
        """Test reload with --dry-run."""
        config, ipset, fetcher, systemd = mock_managers
        config.load_all.return_value = {
            "list1": ListConfig(name="list1", source_url="http://example.com/1"),
        }

        parser = cli.create_parser()
        args = parser.parse_args(["reload", "--dry-run"])

        result = cli.cmd_reload(args)

        assert result == 0
        systemd.create_units.assert_not_called()
        captured = capsys.readouterr()
        assert "Would process" in captured.out

    def test_run_no_command(self, cli, capsys):
        """Test run without command prints help."""
        result = cli.run([])

        assert result == 1

    def test_run_unknown_command(self, cli, capsys):
        """Test run with unknown command."""
        # argparse exits with SystemExit for invalid commands
        with pytest.raises(SystemExit):
            cli.run(["unknown"])


class TestMain:
    """Tests for main function."""

    def test_main_returns_int(self):
        """Test main returns integer exit code."""
        with patch.object(CLI, "run", return_value=0):
            result = main([])
            assert isinstance(result, int)

    def test_main_passes_argv(self):
        """Test main passes argv to CLI."""
        with patch.object(CLI, "run") as mock_run:
            mock_run.return_value = 0
            main(["show"])
            mock_run.assert_called_once_with(["show"])
