"""Command-line interface for dynamic-ipset."""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import ConfigManager, ListConfig
from .constants import DEFAULT_PERIODIC
from .exceptions import DynamicIPSetError, ConfigError
from .fetcher import IPListFetcher
from .ipset import IPSetManager
from .systemd import SystemdManager

logger = logging.getLogger(__name__)


class CLI:
    """Main CLI application."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        ipset_manager: Optional[IPSetManager] = None,
        fetcher: Optional[IPListFetcher] = None,
        systemd_manager: Optional[SystemdManager] = None,
    ):
        """
        Initialize CLI with optional dependency injection for testing.

        Args:
            config_manager: Configuration manager instance
            ipset_manager: IPset manager instance
            fetcher: IP list fetcher instance
            systemd_manager: Systemd manager instance
        """
        self.config = config_manager or ConfigManager()
        self.ipset = ipset_manager or IPSetManager()
        self.fetcher = fetcher or IPListFetcher()
        self.systemd = systemd_manager or SystemdManager()

    def create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            prog="dynamic-ipset",
            description="Manage dynamic ipset rules from URL sources",
        )
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Enable verbose output",
        )

        subparsers = parser.add_subparsers(dest="command", help="Commands")

        # create command
        create_parser = subparsers.add_parser(
            "create",
            help="Create new ipset configuration",
        )
        create_parser.add_argument("name", help="Name of the ipset list")
        create_parser.add_argument("url", help="Source URL for IP list")
        create_parser.add_argument(
            "periodic",
            nargs="?",
            default=DEFAULT_PERIODIC,
            help=f"Update schedule (OnCalendar format, default: {DEFAULT_PERIODIC})",
        )
        create_parser.add_argument(
            "--no-enable",
            action="store_true",
            help="Do not enable the timer after creation",
        )
        create_parser.add_argument(
            "--no-fetch",
            action="store_true",
            help="Do not perform initial fetch",
        )

        # delete command
        delete_parser = subparsers.add_parser(
            "delete",
            help="Delete ipset configuration",
        )
        delete_parser.add_argument("name", help="Name of the ipset list")
        delete_parser.add_argument(
            "--keep-ipset",
            action="store_true",
            help="Keep the ipset (only remove config and timer)",
        )

        # show command
        show_parser = subparsers.add_parser(
            "show",
            help="Show ipset configuration and status",
        )
        show_parser.add_argument(
            "name",
            nargs="?",
            help="Name of the ipset list (omit to list all)",
        )

        # edit command
        edit_parser = subparsers.add_parser(
            "edit",
            help="Edit ipset configuration",
        )
        edit_parser.add_argument("name", help="Name of the ipset list")

        # reload command
        reload_parser = subparsers.add_parser(
            "reload",
            help="Reload configuration and update environment",
        )
        reload_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

        # update command (internal, used by systemd service)
        update_parser = subparsers.add_parser(
            "update",
            help="Update a specific ipset from its source",
        )
        update_parser.add_argument("name", help="Name of the ipset list")

        # enable/disable commands
        enable_parser = subparsers.add_parser(
            "enable",
            help="Enable timer for an ipset",
        )
        enable_parser.add_argument("name", help="Name of the ipset list")

        disable_parser = subparsers.add_parser(
            "disable",
            help="Disable timer for an ipset",
        )
        disable_parser.add_argument("name", help="Name of the ipset list")

        # run command
        run_parser = subparsers.add_parser(
            "run",
            help="Manually trigger update for an ipset",
        )
        run_parser.add_argument("name", help="Name of the ipset list")

        return parser

    def cmd_create(self, args: argparse.Namespace) -> int:
        """Handle create command."""
        if self.config.exists(args.name):
            print(f"Error: List '{args.name}' already exists", file=sys.stderr)
            return 1

        # Create configuration
        list_config = ListConfig(
            name=args.name,
            source_url=args.url,
            periodic=args.periodic,
        )

        # Save configuration
        self.config.save(list_config)
        print(f"Created configuration for '{args.name}'")

        # Create systemd units
        self.systemd.create_units(list_config)
        print("Created systemd units")

        # Initial update
        if not args.no_fetch:
            print("Performing initial update...")
            try:
                self._do_update(list_config)
            except DynamicIPSetError as e:
                print(f"Warning: Initial fetch failed: {e}", file=sys.stderr)

        # Enable timer
        if not args.no_enable:
            self.systemd.enable(args.name)
            print("Timer enabled")

        return 0

    def cmd_delete(self, args: argparse.Namespace) -> int:
        """Handle delete command."""
        if not self.config.exists(args.name):
            print(f"Error: List '{args.name}' not found", file=sys.stderr)
            return 1

        # Delete systemd units
        self.systemd.delete_units(args.name)
        print("Removed systemd units")

        # Delete configuration
        self.config.delete(args.name)
        print("Removed configuration")

        # Delete ipset
        if not args.keep_ipset:
            if self.ipset.exists(args.name):
                self.ipset.destroy(args.name)
                print("Removed ipset")

        return 0

    def cmd_show(self, args: argparse.Namespace) -> int:
        """Handle show command."""
        if args.name:
            return self._show_one(args.name)
        else:
            return self._show_all()

    def _show_one(self, name: str) -> int:
        """Show details for a single list."""
        try:
            list_config = self.config.load(name)
        except ConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        status = self.systemd.get_status(name)
        ipset_exists = self.ipset.exists(name)

        print(f"List: {name}")
        print(f"  Source URL: {list_config.source_url}")
        print(f"  Schedule: {list_config.periodic}")
        print(f"  Type: {list_config.ipset_type}")
        print(f"  Family: {list_config.family}")
        print(f"  Max entries: {list_config.max_entries}")
        print(f"  Enabled: {'yes' if list_config.enabled else 'no'}")
        print("")
        print("Status:")
        print(f"  Timer enabled: {'yes' if status.get('timer_enabled') else 'no'}")
        print(f"  Timer active: {'yes' if status.get('timer_active') else 'no'}")
        print(f"  Next run: {status.get('next_run') or 'N/A'}")
        print(f"  Last run: {status.get('last_run') or 'N/A'}")
        print(f"  Last result: {status.get('last_result') or 'N/A'}")
        print(f"  IPset exists: {'yes' if ipset_exists else 'no'}")

        if ipset_exists:
            try:
                count = self.ipset.count_entries(name)
                print(f"  Entry count: {count}")
            except DynamicIPSetError:
                pass

        return 0

    def _show_all(self) -> int:
        """List all configured ipsets."""
        lists = self.config.load_all()

        if not lists:
            print("No ipset lists configured")
            return 0

        print(f"{'NAME':<20} {'ENABLED':<10} {'SCHEDULE':<20} URL")
        print("-" * 80)

        for name, list_config in sorted(lists.items()):
            status = "yes" if list_config.enabled else "no"
            url_short = (
                list_config.source_url[:40] + "..."
                if len(list_config.source_url) > 40
                else list_config.source_url
            )
            print(f"{name:<20} {status:<10} {list_config.periodic:<20} {url_short}")

        return 0

    def cmd_edit(self, args: argparse.Namespace) -> int:
        """Handle edit command."""
        if not self.config.exists(args.name):
            print(f"Error: List '{args.name}' not found", file=sys.stderr)
            return 1

        # Get editor from environment
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
        conf_path = self.config.get_config_path(args.name)

        # Launch editor
        os.system(f"{editor} {conf_path}")

        print("Configuration edited. Run 'dynamic-ipset reload' to apply changes.")
        return 0

    def cmd_reload(self, args: argparse.Namespace) -> int:
        """Handle reload command."""
        lists = self.config.load_all()

        if not lists:
            print("No configurations to reload")
            return 0

        for name, list_config in lists.items():
            if args.dry_run:
                print(f"Would process: {name}")
                continue

            print(f"Processing '{name}'...")

            # Recreate systemd units (in case schedule changed)
            self.systemd.create_units(list_config)

            # Enable/disable based on config
            if list_config.enabled:
                self.systemd.enable(name)
            else:
                self.systemd.disable(name)

        if not args.dry_run:
            print("Reload complete")

        return 0

    def cmd_update(self, args: argparse.Namespace) -> int:
        """Handle update command (used by systemd service)."""
        try:
            list_config = self.config.load(args.name)
        except ConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        return self._do_update(list_config)

    def _do_update(self, list_config: ListConfig) -> int:
        """Perform the actual update for a list."""
        print(f"Fetching IP list from {list_config.source_url}...")

        entries, errors = self.fetcher.fetch(list_config.source_url)

        if errors:
            for err in errors[:10]:  # Limit error output
                print(f"Warning: {err}", file=sys.stderr)
            if len(errors) > 10:
                print(f"... and {len(errors) - 10} more warnings", file=sys.stderr)

        print(f"Fetched {len(entries)} valid entries")

        if not entries:
            print("Warning: No valid entries found", file=sys.stderr)
            return 0

        # Update ipset
        print(f"Updating ipset '{list_config.name}'...")
        self.ipset.update(
            list_config.name,
            entries,
            ipset_type=list_config.ipset_type,
            family=list_config.family,
            max_entries=list_config.max_entries,
        )

        print("Update complete")
        return 0

    def cmd_enable(self, args: argparse.Namespace) -> int:
        """Handle enable command."""
        if not self.config.exists(args.name):
            print(f"Error: List '{args.name}' not found", file=sys.stderr)
            return 1

        self.systemd.enable(args.name)
        print(f"Timer enabled for '{args.name}'")
        return 0

    def cmd_disable(self, args: argparse.Namespace) -> int:
        """Handle disable command."""
        if not self.config.exists(args.name):
            print(f"Error: List '{args.name}' not found", file=sys.stderr)
            return 1

        self.systemd.disable(args.name)
        print(f"Timer disabled for '{args.name}'")
        return 0

    def cmd_run(self, args: argparse.Namespace) -> int:
        """Handle run command."""
        if not self.config.exists(args.name):
            print(f"Error: List '{args.name}' not found", file=sys.stderr)
            return 1

        self.systemd.run_now(args.name)
        print(f"Update triggered for '{args.name}'")
        return 0

    def run(self, argv: Optional[List[str]] = None) -> int:
        """
        Main entry point.

        Args:
            argv: Command line arguments (defaults to sys.argv[1:])

        Returns:
            Exit code
        """
        parser = self.create_parser()
        args = parser.parse_args(argv)

        # Configure logging
        if args.verbose:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(levelname)s: %(message)s",
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
            )

        if not args.command:
            parser.print_help()
            return 1

        # Dispatch to command handler
        handler_name = f"cmd_{args.command.replace('-', '_')}"
        handler = getattr(self, handler_name, None)

        if handler:
            try:
                return handler(args)
            except DynamicIPSetError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the CLI."""
    cli = CLI()
    return cli.run(argv)


if __name__ == "__main__":
    sys.exit(main())
