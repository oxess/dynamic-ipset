"""Tests for validator module."""

import pytest

from dynamic_ipset.validator import (
    parse_ip_entry,
    validate_cidr,
    validate_ip,
    validate_ipv4,
    validate_ipv6,
    validate_list_name,
    validate_oncalendar,
    validate_url,
)
from dynamic_ipset.exceptions import ValidationError


class TestValidateListName:
    """Tests for validate_list_name function."""

    def test_valid_simple_name(self):
        """Test simple valid names."""
        assert validate_list_name("blocklist")
        assert validate_list_name("whitelist")
        assert validate_list_name("test")

    def test_valid_name_with_underscore(self):
        """Test names with underscores."""
        assert validate_list_name("my_list")
        assert validate_list_name("block_list_v2")

    def test_valid_name_with_hyphen(self):
        """Test names with hyphens."""
        assert validate_list_name("test-list")
        assert validate_list_name("my-block-list")

    def test_valid_name_with_numbers(self):
        """Test names with numbers."""
        assert validate_list_name("list1")
        assert validate_list_name("blocklist2024")

    def test_valid_single_char(self):
        """Test single character name."""
        assert validate_list_name("A")
        assert validate_list_name("z")

    def test_invalid_empty(self):
        """Test empty name."""
        with pytest.raises(ValidationError):
            validate_list_name("")

    def test_invalid_starts_with_number(self):
        """Test name starting with number."""
        with pytest.raises(ValidationError, match="start with letter"):
            validate_list_name("1blocklist")

    def test_invalid_starts_with_underscore(self):
        """Test name starting with underscore."""
        with pytest.raises(ValidationError):
            validate_list_name("_blocklist")

    def test_invalid_too_long(self):
        """Test name exceeding 31 characters."""
        with pytest.raises(ValidationError, match="max 31"):
            validate_list_name("a" * 32)

    def test_valid_max_length(self):
        """Test name at exactly 31 characters."""
        assert validate_list_name("a" * 31)

    def test_invalid_special_chars(self):
        """Test names with invalid special characters."""
        with pytest.raises(ValidationError):
            validate_list_name("block.list")
        with pytest.raises(ValidationError):
            validate_list_name("block list")
        with pytest.raises(ValidationError):
            validate_list_name("block@list")


class TestValidateIPv4:
    """Tests for validate_ipv4 function."""

    def test_valid_ipv4(self):
        """Test valid IPv4 addresses."""
        assert validate_ipv4("192.168.1.1")
        assert validate_ipv4("0.0.0.0")
        assert validate_ipv4("255.255.255.255")
        assert validate_ipv4("8.8.8.8")
        assert validate_ipv4("10.0.0.1")

    def test_invalid_ipv4(self):
        """Test invalid IPv4 addresses."""
        assert not validate_ipv4("256.1.1.1")
        assert not validate_ipv4("192.168.1")
        assert not validate_ipv4("not_an_ip")
        assert not validate_ipv4("")
        assert not validate_ipv4("192.168.1.1.1")

    def test_ipv6_returns_false(self):
        """Test that IPv6 addresses return False."""
        assert not validate_ipv4("::1")
        assert not validate_ipv4("2001:db8::1")


class TestValidateIPv6:
    """Tests for validate_ipv6 function."""

    def test_valid_ipv6(self):
        """Test valid IPv6 addresses."""
        assert validate_ipv6("::1")
        assert validate_ipv6("2001:db8::1")
        assert validate_ipv6("fe80::1")
        assert validate_ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:7334")

    def test_invalid_ipv6(self):
        """Test invalid IPv6 addresses."""
        assert not validate_ipv6("not_an_ip")
        assert not validate_ipv6("")
        assert not validate_ipv6("2001:db8:::1")

    def test_ipv4_returns_false(self):
        """Test that IPv4 addresses return False."""
        assert not validate_ipv6("192.168.1.1")
        assert not validate_ipv6("8.8.8.8")


class TestValidateIP:
    """Tests for validate_ip function."""

    def test_valid_ipv4(self):
        """Test valid IPv4 addresses."""
        valid, version = validate_ip("192.168.1.1")
        assert valid
        assert version == 4

    def test_valid_ipv6(self):
        """Test valid IPv6 addresses."""
        valid, version = validate_ip("2001:db8::1")
        assert valid
        assert version == 6

    def test_invalid_ip(self):
        """Test invalid IP addresses."""
        valid, version = validate_ip("not_an_ip")
        assert not valid
        assert version == 0


class TestValidateCIDR:
    """Tests for validate_cidr function."""

    def test_valid_ipv4_cidr(self):
        """Test valid IPv4 CIDR notation."""
        addr, prefix, family = validate_cidr("192.168.1.0/24")
        assert addr == "192.168.1.0"
        assert prefix == 24
        assert family == "inet"

    def test_valid_ipv4_cidr_with_host(self):
        """Test IPv4 CIDR that gets normalized."""
        addr, prefix, family = validate_cidr("192.168.1.100/24")
        assert addr == "192.168.1.0"  # Normalized to network address
        assert prefix == 24
        assert family == "inet"

    def test_valid_ipv6_cidr(self):
        """Test valid IPv6 CIDR notation."""
        addr, prefix, family = validate_cidr("2001:db8::/32")
        assert addr == "2001:db8::"
        assert prefix == 32
        assert family == "inet6"

    def test_plain_ipv4(self):
        """Test plain IPv4 address (no prefix)."""
        addr, prefix, family = validate_cidr("8.8.8.8")
        assert addr == "8.8.8.8"
        assert prefix == 32
        assert family == "inet"

    def test_plain_ipv6(self):
        """Test plain IPv6 address (no prefix)."""
        addr, prefix, family = validate_cidr("::1")
        assert addr == "::1"
        assert prefix == 128
        assert family == "inet6"

    def test_invalid_prefix_too_large_ipv4(self):
        """Test IPv4 with prefix > 32."""
        with pytest.raises(ValidationError, match="Invalid CIDR"):
            validate_cidr("192.168.1.0/33")

    def test_invalid_prefix_too_large_ipv6(self):
        """Test IPv6 with prefix > 128."""
        with pytest.raises(ValidationError, match="Invalid CIDR"):
            validate_cidr("2001:db8::/129")

    def test_invalid_ip(self):
        """Test invalid IP in CIDR."""
        with pytest.raises(ValidationError):
            validate_cidr("999.999.999.999/24")

    def test_invalid_format(self):
        """Test completely invalid format."""
        with pytest.raises(ValidationError):
            validate_cidr("not_a_cidr")


class TestValidateURL:
    """Tests for validate_url function."""

    def test_valid_http(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com/list.txt")

    def test_valid_https(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com/list.txt")

    def test_valid_with_path(self):
        """Test URL with path components."""
        assert validate_url("https://example.com/path/to/list.txt")

    def test_valid_with_query(self):
        """Test URL with query string."""
        assert validate_url("https://example.com/list?format=txt")

    def test_invalid_empty(self):
        """Test empty URL."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_url("")

    def test_invalid_no_scheme(self):
        """Test URL without scheme."""
        with pytest.raises(ValidationError, match="http:// or https://"):
            validate_url("example.com/list.txt")

    def test_invalid_ftp_scheme(self):
        """Test URL with unsupported scheme."""
        with pytest.raises(ValidationError, match="http:// or https://"):
            validate_url("ftp://example.com/list.txt")

    def test_invalid_no_host(self):
        """Test URL without host."""
        with pytest.raises(ValidationError, match="valid hostname"):
            validate_url("http:///list.txt")


class TestValidateOnCalendar:
    """Tests for validate_oncalendar function."""

    def test_valid_keywords(self):
        """Test valid OnCalendar keywords."""
        assert validate_oncalendar("daily")
        assert validate_oncalendar("hourly")
        assert validate_oncalendar("weekly")
        assert validate_oncalendar("monthly")
        assert validate_oncalendar("yearly")
        assert validate_oncalendar("annually")

    def test_valid_keywords_case_insensitive(self):
        """Test keywords are case insensitive."""
        assert validate_oncalendar("DAILY")
        assert validate_oncalendar("Hourly")

    def test_valid_time_spec(self):
        """Test valid time specifications."""
        assert validate_oncalendar("*-*-* 0/3:00:00")
        assert validate_oncalendar("*-*-* 06:00:00")
        assert validate_oncalendar("*:0/15")

    def test_valid_date_spec(self):
        """Test valid date specifications."""
        assert validate_oncalendar("*-*-01")
        assert validate_oncalendar("2024-01-01")

    def test_invalid_empty(self):
        """Test empty specification."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_oncalendar("")

    def test_invalid_unknown_keyword(self):
        """Test unknown keyword."""
        with pytest.raises(ValidationError):
            validate_oncalendar("biweekly")


class TestParseIPEntry:
    """Tests for parse_ip_entry function."""

    def test_plain_ipv4(self):
        """Test parsing plain IPv4."""
        entry, family = parse_ip_entry("192.168.1.1")
        assert entry == "192.168.1.1/32"
        assert family == "inet"

    def test_cidr_ipv4(self):
        """Test parsing IPv4 CIDR."""
        entry, family = parse_ip_entry("192.168.1.0/24")
        assert entry == "192.168.1.0/24"
        assert family == "inet"

    def test_ipv6(self):
        """Test parsing IPv6."""
        entry, family = parse_ip_entry("2001:db8::/32")
        assert entry == "2001:db8::/32"
        assert family == "inet6"

    def test_with_inline_comment_hash(self):
        """Test parsing entry with # inline comment."""
        entry, family = parse_ip_entry("192.168.1.0/24 # some comment")
        assert entry == "192.168.1.0/24"

    def test_with_inline_comment_semicolon(self):
        """Test parsing entry with ; inline comment."""
        entry, family = parse_ip_entry("192.168.1.0/24 ; some comment")
        assert entry == "192.168.1.0/24"

    def test_with_whitespace(self):
        """Test parsing entry with extra whitespace."""
        entry, family = parse_ip_entry("  192.168.1.0/24  ")
        assert entry == "192.168.1.0/24"

    def test_empty_entry(self):
        """Test empty entry raises error."""
        with pytest.raises(ValidationError, match="Empty entry"):
            parse_ip_entry("")

    def test_only_comment(self):
        """Test entry that is only a comment."""
        with pytest.raises(ValidationError, match="Empty entry"):
            parse_ip_entry("# just a comment")
