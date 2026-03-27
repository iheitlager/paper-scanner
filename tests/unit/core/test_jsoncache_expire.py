"""
Unit tests for JSONFileCache expiration functionality.

Tests various TTL (time-to-live) scenarios including:
- Default TTL behavior
- Custom TTL values (int days and timedelta)
- Expired cache entries
- Non-expired cache entries
- TTL = 0 (never expire)
- TTL = -1 (never expire)
- TTL = None (use default)
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from paper_scanner.core.cache import JSONFileCache


def set_file_mtime(file_path: Path, days_old: int = 0, hours_old: int = 0, minutes_old: int = 0, seconds_old: int = 0):
    """
    Helper function to set file modification time to a past date.

    Args:
        file_path: Path to the file
        days_old: Number of days in the past
        hours_old: Number of hours in the past
        minutes_old: Number of minutes in the past
        seconds_old: Number of seconds in the past
    """
    past_time = datetime.now() - timedelta(days=days_old, hours=hours_old, minutes=minutes_old, seconds=seconds_old)
    timestamp = past_time.timestamp()
    os.utime(file_path, (timestamp, timestamp))


class TestCacheExpirationDefaults:
    """Tests for default TTL behavior."""

    def test_default_ttl_is_30_days(self, tmp_path):
        """Test that default TTL is 30 days."""
        cache = JSONFileCache(cache_dir=tmp_path)
        assert cache.default_ttl == timedelta(days=30)

    def test_custom_default_ttl_as_int(self, tmp_path):
        """Test setting custom default TTL as integer (days)."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=7)
        assert cache.default_ttl == timedelta(days=7)

    def test_custom_default_ttl_as_timedelta(self, tmp_path):
        """Test setting custom default TTL as timedelta."""
        custom_ttl = timedelta(hours=12)
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=custom_ttl)
        assert cache.default_ttl == custom_ttl


class TestCacheExpirationLogic:
    """Tests for cache expiration logic."""

    def test_get_returns_fresh_cache_within_default_ttl(self, tmp_path):
        """Test that get returns data when file is within default TTL."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        # Set cache
        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file modification time to be 1 day old (within 30 day TTL)
        set_file_mtime(cache_path, days_old=1)

        result = cache.get(key)
        assert result == test_data

    def test_get_returns_none_for_expired_cache_default_ttl(self, tmp_path):
        """Test that get returns None when cache exceeds default TTL."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        # Set cache
        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file modification time to be 31 days old (exceeds 30 day TTL)
        set_file_mtime(cache_path, days_old=31)

        # Call with ttl=None to use default TTL
        result = cache.get(key, ttl=None)
        assert result is None
        # Verify file was deleted
        assert not cache_path.exists()

    def test_get_with_custom_ttl_int_days(self, tmp_path):
        """Test get with custom TTL specified as integer (days)."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 6 days old
        set_file_mtime(cache_path, days_old=6)

        # Should return None with TTL=5 days (file is 6 days old)
        result = cache.get(key, ttl=5)
        assert result is None
        assert not cache_path.exists()

    def test_get_with_custom_ttl_timedelta(self, tmp_path):
        """Test get with custom TTL specified as timedelta."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 2 hours old
        set_file_mtime(cache_path, hours_old=2)

        # Should return data with TTL=3 hours (file is 2 hours old)
        result = cache.get(key, ttl=timedelta(hours=3))
        assert result == test_data

    def test_get_with_custom_ttl_expired_timedelta(self, tmp_path):
        """Test get with custom TTL expired when specified as timedelta."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 2 hours old
        set_file_mtime(cache_path, hours_old=2)

        # Should return None with TTL=1 hour (file is 2 hours old)
        result = cache.get(key, ttl=timedelta(hours=1))
        assert result is None
        assert not cache_path.exists()


class TestCacheNeverExpire:
    """Tests for cache entries that never expire."""

    def test_get_with_ttl_minus_one_never_expires(self, tmp_path):
        """Test that TTL=-1 means cache never expires."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be very old (365 days)
        set_file_mtime(cache_path, days_old=365)

        result = cache.get(key, ttl=-1)
        assert result == test_data

    def test_get_with_ttl_zero_never_expires(self, tmp_path):
        """Test that TTL=0 means cache never expires (zero timedelta)."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be very old (365 days)
        set_file_mtime(cache_path, days_old=365)

        result = cache.get(key, ttl=0)
        assert result == test_data

    def test_get_with_ttl_zero_timedelta_never_expires(self, tmp_path):
        """Test that TTL=timedelta(0) means cache never expires."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be very old (365 days)
        set_file_mtime(cache_path, days_old=365)

        result = cache.get(key, ttl=timedelta(0))
        assert result == test_data


class TestCacheExpirationEdgeCases:
    """Tests for edge cases in cache expiration."""

    def test_get_with_ttl_none_uses_default(self, tmp_path):
        """Test that TTL=None uses the default TTL."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=10)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 11 days old (exceeds 10 day default TTL)
        set_file_mtime(cache_path, days_old=11)

        result = cache.get(key, ttl=None)
        assert result is None
        assert not cache_path.exists()

    def test_get_exactly_at_ttl_boundary(self, tmp_path):
        """Test cache behavior exactly at TTL boundary."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=5)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be exactly 5 days old
        set_file_mtime(cache_path, days_old=5)

        result = cache.get(key, ttl=5)
        # At exact boundary, file_age >= ttl_delta will be True (equal), so it expires
        assert result is None

    def test_get_just_after_ttl_boundary(self, tmp_path):
        """Test cache behavior just after TTL boundary."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=5)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 5 days and 1 second old
        set_file_mtime(cache_path, days_old=5, seconds_old=1)

        result = cache.get(key, ttl=5)
        assert result is None
        assert not cache_path.exists()

    def test_get_with_very_short_ttl_minutes(self, tmp_path):
        """Test cache with very short TTL in minutes."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 5 minutes old
        set_file_mtime(cache_path, minutes_old=5)

        # TTL of 3 minutes - should be expired
        result = cache.get(key, ttl=timedelta(minutes=3))
        assert result is None
        assert not cache_path.exists()

    def test_get_with_very_long_ttl(self, tmp_path):
        """Test cache with very long TTL (years)."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 100 days old
        set_file_mtime(cache_path, days_old=100)

        # TTL of 5 years - should still be valid
        result = cache.get(key, ttl=timedelta(days=365*5))
        assert result == test_data


class TestCacheExpirationMultipleAccess:
    """Tests for cache expiration across multiple access patterns."""

    def test_expired_cache_is_deleted_and_not_accessible(self, tmp_path):
        """Test that expired cache is deleted and subsequent get returns None."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=5)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Verify file exists
        assert cache_path.exists()

        # Set file to be 6 days old
        set_file_mtime(cache_path, days_old=6)

        # First access - should delete expired file (use default TTL)
        result1 = cache.get(key, ttl=None)
        assert result1 is None

        # Verify file was actually deleted
        assert not cache_path.exists()

        # Second access - should still return None (file doesn't exist)
        result2 = cache.get(key)
        assert result2 is None

    def test_different_ttl_values_for_same_key(self, tmp_path):
        """Test accessing same key with different TTL values."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=30)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 10 days old
        set_file_mtime(cache_path, days_old=10)

        # Should be valid with TTL=15 days
        result1 = cache.get(key, ttl=15)
        assert result1 == test_data

        # Should be expired with TTL=5 days
        result2 = cache.get(key, ttl=5)
        assert result2 is None

    def test_set_resets_modification_time(self, tmp_path):
        """Test that setting cache again resets the modification time."""
        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=5)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        # Initial set
        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Get initial modification time
        initial_mtime = cache_path.stat().st_mtime

        # Wait and set again (in real scenario this would be later)
        cache.set(key, {"title": "Updated Paper"})

        # Modification time should be updated (or at least not older)
        new_mtime = cache_path.stat().st_mtime
        assert new_mtime >= initial_mtime


class TestCacheExpirationNegativeTimedelta:
    """Tests for negative timedelta values."""

    def test_negative_timedelta_is_treated_as_never_expire(self, tmp_path):
        """Test that negative timedelta values don't cause expiration."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper"}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Set file to be 100 days old
        set_file_mtime(cache_path, days_old=100)

        # Negative timedelta should not cause expiration
        result = cache.get(key, ttl=timedelta(days=-10))
        assert result == test_data
