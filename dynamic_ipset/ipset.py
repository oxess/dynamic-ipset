"""IPset operations for dynamic-ipset."""

import logging
import subprocess
from typing import List, Optional

from .constants import DEFAULT_IPSET_FAMILY, DEFAULT_IPSET_TYPE, DEFAULT_MAX_ENTRIES
from .exceptions import IPSetError
from .validator import validate_list_name

logger = logging.getLogger(__name__)


class IPSetManager:
    """Manages Linux ipset operations."""

    def __init__(self, ipset_cmd: str = "ipset"):
        """
        Initialize the IPset manager.

        Args:
            ipset_cmd: Path to the ipset command
        """
        self.ipset_cmd = ipset_cmd

    def _run(
        self,
        args: List[str],
        check: bool = True,
        input_data: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        """
        Execute ipset command.

        Args:
            args: Command arguments
            check: Whether to raise on non-zero exit
            input_data: Optional input to pass to stdin

        Returns:
            CompletedProcess result

        Raises:
            IPSetError: If the command fails and check=True
        """
        cmd = [self.ipset_cmd] + args
        logger.debug("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=input_data,
            )
        except FileNotFoundError:
            raise IPSetError(f"ipset command not found: {self.ipset_cmd}")
        except Exception as e:
            raise IPSetError(f"Failed to run ipset: {e}")

        if check and result.returncode != 0:
            stderr = result.stderr.strip()
            raise IPSetError(f"ipset command failed: {stderr}")

        return result

    def exists(self, name: str) -> bool:
        """
        Check if ipset exists.

        Args:
            name: The ipset name

        Returns:
            True if the ipset exists
        """
        result = self._run(["list", name, "-n"], check=False)
        return result.returncode == 0

    def create(
        self,
        name: str,
        ipset_type: str = DEFAULT_IPSET_TYPE,
        family: str = DEFAULT_IPSET_FAMILY,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> bool:
        """
        Create a new ipset.

        Args:
            name: The ipset name
            ipset_type: Type of ipset (e.g., hash:net)
            family: IP family (inet or inet6)
            max_entries: Maximum number of entries

        Returns:
            True if created, False if already exists

        Raises:
            IPSetError: If creation fails
        """
        validate_list_name(name)

        if self.exists(name):
            return False

        args = [
            "create",
            name,
            ipset_type,
            "family",
            family,
            "maxelem",
            str(max_entries),
        ]
        self._run(args)
        logger.info("Created ipset: %s", name)
        return True

    def destroy(self, name: str) -> bool:
        """
        Destroy an ipset.

        Args:
            name: The ipset name

        Returns:
            True if destroyed, False if didn't exist

        Raises:
            IPSetError: If destruction fails
        """
        validate_list_name(name)

        if not self.exists(name):
            return False

        self._run(["destroy", name])
        logger.info("Destroyed ipset: %s", name)
        return True

    def flush(self, name: str) -> None:
        """
        Flush all entries from an ipset.

        Args:
            name: The ipset name

        Raises:
            IPSetError: If flush fails
        """
        validate_list_name(name)
        self._run(["flush", name])
        logger.debug("Flushed ipset: %s", name)

    def add(self, name: str, entry: str) -> None:
        """
        Add an entry to the ipset.

        Args:
            name: The ipset name
            entry: The IP/CIDR to add

        Raises:
            IPSetError: If add fails
        """
        # Use -exist to avoid errors on duplicates
        self._run(["add", name, entry, "-exist"])

    def add_many(self, name: str, entries: List[str]) -> int:
        """
        Add multiple entries efficiently using restore.

        Args:
            name: The ipset name
            entries: List of IP/CIDR entries

        Returns:
            Number of entries added

        Raises:
            IPSetError: If restore fails
        """
        if not entries:
            return 0

        # Build restore format
        lines = []
        for entry in entries:
            lines.append(f"add {name} {entry} -exist")

        restore_input = "\n".join(lines) + "\n"

        self._run(["restore"], input_data=restore_input)
        logger.debug("Added %d entries to %s", len(entries), name)
        return len(entries)

    def remove(self, name: str, entry: str) -> None:
        """
        Remove an entry from the ipset.

        Args:
            name: The ipset name
            entry: The IP/CIDR to remove

        Raises:
            IPSetError: If remove fails
        """
        self._run(["del", name, entry, "-exist"])

    def update(
        self,
        name: str,
        entries: List[str],
        ipset_type: str = DEFAULT_IPSET_TYPE,
        family: str = DEFAULT_IPSET_FAMILY,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> int:
        """
        Atomic update of ipset contents.

        Creates temp set, populates it, then swaps with the main set.
        This ensures no traffic interruption during update.

        Args:
            name: The ipset name
            entries: List of IP/CIDR entries
            ipset_type: Type of ipset
            family: IP family
            max_entries: Maximum entries

        Returns:
            Number of entries in the updated set

        Raises:
            IPSetError: If update fails
        """
        validate_list_name(name)

        # Generate temp name (keep under 31 chars)
        temp_name = f"{name[:26]}_tmp"

        try:
            # Create main set if not exists
            self.create(name, ipset_type, family, max_entries)

            # Destroy temp set if exists (from previous failed update)
            if self.exists(temp_name):
                self.destroy(temp_name)

            # Create temp set with same properties
            self.create(temp_name, ipset_type, family, max_entries)

            # Populate temp set
            if entries:
                self.add_many(temp_name, entries)

            # Atomic swap
            self._run(["swap", temp_name, name])
            logger.info("Updated ipset %s with %d entries", name, len(entries))

            # Destroy temp set
            self.destroy(temp_name)

            return len(entries)

        except Exception:
            # Cleanup on failure
            if self.exists(temp_name):
                try:
                    self.destroy(temp_name)
                except IPSetError:
                    pass
            raise

    def list_entries(self, name: str) -> List[str]:
        """
        List all entries in an ipset.

        Args:
            name: The ipset name

        Returns:
            List of entries

        Raises:
            IPSetError: If list fails
        """
        validate_list_name(name)
        result = self._run(["list", name])

        # Parse output - entries are after "Members:" line
        entries = []
        in_members = False

        for line in result.stdout.splitlines():
            if line.startswith("Members:"):
                in_members = True
                continue
            if in_members and line.strip():
                entries.append(line.strip())

        return entries

    def list_all(self) -> List[str]:
        """
        List all ipset names.

        Returns:
            List of ipset names
        """
        result = self._run(["list", "-n"])
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def get_info(self, name: str) -> dict:
        """
        Get information about an ipset.

        Args:
            name: The ipset name

        Returns:
            Dictionary with ipset information

        Raises:
            IPSetError: If the ipset doesn't exist
        """
        validate_list_name(name)
        result = self._run(["list", name, "-t"])

        info = {
            "name": name,
            "type": None,
            "family": None,
            "size": 0,
            "max_entries": 0,
        }

        for line in result.stdout.splitlines():
            if line.startswith("Type:"):
                info["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("Header:"):
                header = line.split(":", 1)[1].strip()
                # Parse header like: family inet hashsize 1024 maxelem 65536
                parts = header.split()
                for i, part in enumerate(parts):
                    if part == "family" and i + 1 < len(parts):
                        info["family"] = parts[i + 1]
                    elif part == "maxelem" and i + 1 < len(parts):
                        try:
                            info["max_entries"] = int(parts[i + 1])
                        except ValueError:
                            pass
            elif line.startswith("Size in memory:"):
                try:
                    size_str = line.split(":", 1)[1].strip()
                    info["size"] = int(size_str)
                except ValueError:
                    pass
            elif line.startswith("Number of entries:"):
                try:
                    count_str = line.split(":", 1)[1].strip()
                    info["entries"] = int(count_str)
                except ValueError:
                    pass

        return info

    def count_entries(self, name: str) -> int:
        """
        Count entries in an ipset.

        Args:
            name: The ipset name

        Returns:
            Number of entries
        """
        info = self.get_info(name)
        return info.get("entries", 0)
