"""Tests for fetcher module."""

from unittest.mock import Mock, patch

import pytest

from dynamic_ipset.exceptions import FetchError
from dynamic_ipset.fetcher import IPListFetcher, fetch_ip_list


class TestIPListFetcher:
    """Tests for IPListFetcher class."""

    def test_init_default_timeout(self):
        """Test default timeout is set."""
        fetcher = IPListFetcher()
        assert fetcher.timeout == 30

    def test_init_custom_timeout(self):
        """Test custom timeout can be set."""
        fetcher = IPListFetcher(timeout=60)
        assert fetcher.timeout == 60

    def test_parse_simple_list(self):
        """Test parsing a simple IP list."""
        fetcher = IPListFetcher()
        content = """192.168.1.0/24
10.0.0.0/8
8.8.8.8"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 3
        assert len(errors) == 0
        assert "192.168.1.0/24" in entries
        assert "10.0.0.0/8" in entries
        assert "8.8.8.8/32" in entries

    def test_parse_with_comments(self):
        """Test parsing list with comment lines."""
        fetcher = IPListFetcher()
        content = """# This is a comment
192.168.1.0/24
; Another comment
10.0.0.0/8"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 2
        assert len(errors) == 0

    def test_parse_with_inline_comments(self):
        """Test parsing list with inline comments."""
        fetcher = IPListFetcher()
        content = """192.168.1.0/24 # network block
10.0.0.0/8 ; private range"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 2
        assert "192.168.1.0/24" in entries
        assert "10.0.0.0/8" in entries

    def test_parse_with_blank_lines(self):
        """Test parsing list with blank lines."""
        fetcher = IPListFetcher()
        content = """192.168.1.0/24

10.0.0.0/8

8.8.8.8
"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 3
        assert len(errors) == 0

    def test_parse_with_invalid_entries(self):
        """Test parsing list with some invalid entries."""
        fetcher = IPListFetcher()
        content = """192.168.1.0/24
invalid_entry
10.0.0.0/8
not_an_ip
256.256.256.256"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 2
        assert len(errors) == 3
        assert "192.168.1.0/24" in entries
        assert "10.0.0.0/8" in entries

    def test_parse_ipv6_entries(self):
        """Test parsing IPv6 entries."""
        fetcher = IPListFetcher()
        content = """2001:db8::/32
::1
fe80::1"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 3
        assert len(errors) == 0
        assert "2001:db8::/32" in entries
        assert "::1/128" in entries
        assert "fe80::1/128" in entries

    def test_parse_mixed_ipv4_ipv6(self):
        """Test parsing mixed IPv4 and IPv6 entries."""
        fetcher = IPListFetcher()
        content = """192.168.1.0/24
2001:db8::/32
8.8.8.8
::1"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 4
        assert len(errors) == 0

    def test_parse_multiple_entries_per_line(self):
        """Test parsing multiple entries on a single line."""
        fetcher = IPListFetcher()
        content = """192.168.1.0/24 10.0.0.0/8
8.8.8.8, 1.1.1.1"""
        entries, errors = fetcher._parse_ip_list(content)
        assert len(entries) == 4
        assert len(errors) == 0

    def test_split_entries_single(self):
        """Test splitting single entry."""
        fetcher = IPListFetcher()
        parts = fetcher._split_entries("192.168.1.0/24")
        assert parts == ["192.168.1.0/24"]

    def test_split_entries_with_comment(self):
        """Test splitting entry with inline comment."""
        fetcher = IPListFetcher()
        parts = fetcher._split_entries("192.168.1.0/24 # comment")
        assert parts == ["192.168.1.0/24"]

    def test_split_entries_space_separated(self):
        """Test splitting space-separated entries."""
        fetcher = IPListFetcher()
        parts = fetcher._split_entries("192.168.1.0/24 10.0.0.0/8")
        assert len(parts) == 2
        assert "192.168.1.0/24" in parts
        assert "10.0.0.0/8" in parts

    def test_split_entries_comma_separated(self):
        """Test splitting comma-separated entries."""
        fetcher = IPListFetcher()
        parts = fetcher._split_entries("192.168.1.0/24,10.0.0.0/8")
        assert len(parts) == 2

    def test_split_entries_empty(self):
        """Test splitting empty line."""
        fetcher = IPListFetcher()
        parts = fetcher._split_entries("")
        assert parts == []

    def test_split_entries_only_comment(self):
        """Test splitting line that becomes empty after comment removal."""
        fetcher = IPListFetcher()
        parts = fetcher._split_entries("# just a comment")
        assert parts == []

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_success(self, mock_urlopen):
        """Test successful fetch."""
        mock_response = Mock()
        mock_response.read.return_value = b"192.168.1.0/24\n10.0.0.0/8"
        mock_urlopen.return_value = mock_response

        fetcher = IPListFetcher()
        entries, errors = fetcher.fetch("http://example.com/list.txt")

        assert len(entries) == 2
        assert len(errors) == 0
        mock_urlopen.assert_called_once()

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_http_error(self, mock_urlopen):
        """Test fetch with HTTP error."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError("http://example.com", 404, "Not Found", {}, None)

        fetcher = IPListFetcher()
        with pytest.raises(FetchError, match="HTTP error 404"):
            fetcher.fetch("http://example.com/list.txt")

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_url_error(self, mock_urlopen):
        """Test fetch with URL error."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        fetcher = IPListFetcher()
        with pytest.raises(FetchError, match="URL error"):
            fetcher.fetch("http://example.com/list.txt")

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_timeout(self, mock_urlopen):
        """Test fetch with timeout."""
        mock_urlopen.side_effect = TimeoutError()

        fetcher = IPListFetcher()
        with pytest.raises(FetchError, match="Timeout"):
            fetcher.fetch("http://example.com/list.txt")

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_raw_success(self, mock_urlopen):
        """Test raw fetch success."""
        mock_response = Mock()
        mock_response.read.return_value = b"raw content here"
        mock_urlopen.return_value = mock_response

        fetcher = IPListFetcher()
        content = fetcher.fetch_raw("http://example.com/list.txt")

        assert content == "raw content here"

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_raw_error(self, mock_urlopen):
        """Test raw fetch with error."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError("http://example.com", 500, "Server Error", {}, None)

        fetcher = IPListFetcher()
        with pytest.raises(FetchError, match="HTTP error 500"):
            fetcher.fetch_raw("http://example.com/list.txt")


class TestFetchIPListFunction:
    """Tests for fetch_ip_list convenience function."""

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_ip_list(self, mock_urlopen):
        """Test fetch_ip_list function."""
        mock_response = Mock()
        mock_response.read.return_value = b"192.168.1.0/24"
        mock_urlopen.return_value = mock_response

        entries, errors = fetch_ip_list("http://example.com/list.txt")

        assert len(entries) == 1
        assert entries[0] == "192.168.1.0/24"

    @patch("dynamic_ipset.fetcher.urlopen")
    def test_fetch_ip_list_with_timeout(self, mock_urlopen):
        """Test fetch_ip_list with custom timeout."""
        mock_response = Mock()
        mock_response.read.return_value = b"192.168.1.0/24"
        mock_urlopen.return_value = mock_response

        fetch_ip_list("http://example.com/list.txt", timeout=60)

        # Verify urlopen was called with correct timeout
        call_args = mock_urlopen.call_args
        assert call_args.kwargs.get("timeout") == 60
