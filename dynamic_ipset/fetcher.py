"""URL fetching and IP list parsing for dynamic-ipset."""

import logging
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .constants import COMMENT_CHARS, DEFAULT_TIMEOUT
from .exceptions import FetchError, ValidationError
from .validator import parse_ip_entry

logger = logging.getLogger(__name__)


class IPListFetcher:
    """Fetches and parses IP lists from URLs."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize the fetcher.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout

    def fetch(self, url: str) -> tuple[list[str], list[str]]:
        """
        Fetch IP list from URL.

        Args:
            url: The URL to fetch from

        Returns:
            Tuple of (valid_entries, parse_errors)
            - valid_entries: List of validated CIDR entries
            - parse_errors: List of error messages for invalid entries

        Raises:
            FetchError: If the URL cannot be fetched
        """
        try:
            # Create SSL context that verifies certificates
            context = ssl.create_default_context()
            response = urlopen(url, timeout=self.timeout, context=context)
            content = response.read().decode("utf-8", errors="replace")
            return self._parse_ip_list(content)
        except HTTPError as e:
            raise FetchError(f"HTTP error {e.code}: {url}") from e
        except URLError as e:
            raise FetchError(f"URL error: {e.reason} - {url}") from e
        except TimeoutError as e:
            raise FetchError(f"Timeout fetching {url}") from e
        except Exception as e:
            raise FetchError(f"Failed to fetch {url}: {e}") from e

    def _parse_ip_list(self, content: str) -> tuple[list[str], list[str]]:
        """
        Parse IP list content.

        Supports formats:
        - One IP/CIDR per line
        - Lines starting with # or ; are comments
        - Inline comments after IP
        - Blank lines ignored
        - IPv4 and IPv6 entries

        Args:
            content: The raw content from the URL

        Returns:
            Tuple of (valid_entries, parse_errors)
        """
        entries: list[str] = []
        errors: list[str] = []

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip comment lines
            if line.startswith(COMMENT_CHARS):
                continue

            # Handle potential multiple entries per line (space or comma separated)
            # But first check if it's a single entry with inline comment
            parts = self._split_entries(line)

            for part in parts:
                if not part:
                    continue

                try:
                    entry, family = parse_ip_entry(part)
                    entries.append(entry)
                except ValidationError as e:
                    errors.append(f"Line {line_num}: {e}")

        return entries, errors

    def _split_entries(self, line: str) -> list[str]:
        """
        Split a line into individual entries.

        Handles:
        - Single entry per line
        - Multiple entries separated by whitespace or comma
        - Inline comments

        Args:
            line: The line to split

        Returns:
            List of entry strings
        """
        # First, remove any inline comment
        for comment_char in COMMENT_CHARS:
            if comment_char in line:
                line = line.split(comment_char)[0].strip()

        if not line:
            return []

        # Check if line contains separator characters
        # (space, comma, tab)
        if " " in line or "," in line or "\t" in line:
            # Split by whitespace and comma
            import re

            parts = re.split(r"[\s,]+", line)
            return [p.strip() for p in parts if p.strip()]
        else:
            return [line]

    def fetch_raw(self, url: str) -> str:
        """
        Fetch raw content from URL without parsing.

        Args:
            url: The URL to fetch from

        Returns:
            The raw content as string

        Raises:
            FetchError: If the URL cannot be fetched
        """
        try:
            context = ssl.create_default_context()
            response = urlopen(url, timeout=self.timeout, context=context)
            return response.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            raise FetchError(f"HTTP error {e.code}: {url}") from e
        except URLError as e:
            raise FetchError(f"URL error: {e.reason} - {url}") from e
        except TimeoutError as e:
            raise FetchError(f"Timeout fetching {url}") from e
        except Exception as e:
            raise FetchError(f"Failed to fetch {url}: {e}") from e


def fetch_ip_list(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[list[str], list[str]]:
    """
    Convenience function to fetch an IP list.

    Args:
        url: The URL to fetch from
        timeout: HTTP request timeout in seconds

    Returns:
        Tuple of (valid_entries, parse_errors)

    Raises:
        FetchError: If the URL cannot be fetched
    """
    fetcher = IPListFetcher(timeout=timeout)
    return fetcher.fetch(url)
