"""
Unit tests for OpenAccessStatus model

Tests for paper_scanner.core.models.OpenAccessStatus
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from paper_scanner.core.models import OpenAccessStatus


class TestOpenAccessStatus:
    """Test OpenAccessStatus model"""

    def test_oa_status_minimal_creation(self):
        """Verify OpenAccessStatus can be created with required is_oa field"""
        oa = OpenAccessStatus(is_oa=True)
        assert oa.is_oa is True
        assert oa.oa_status is None
        assert oa.oa_url is None
        assert oa.version is None
        assert oa.license is None
        assert oa.host_type is None
        assert oa.source is None
        assert oa.verified_at is None

    def test_oa_status_gold_access(self):
        """Verify gold open access configuration"""
        oa = OpenAccessStatus(
            is_oa=True,
            oa_status="gold",
            oa_url="https://example.com/paper.pdf",
            version="publishedVersion",
            license="CC-BY-4.0",
            host_type="publisher",
            source="unpaywall"
        )
        assert oa.is_oa is True
        assert oa.oa_status == "gold"
        assert oa.oa_url == "https://example.com/paper.pdf"
        assert oa.version == "publishedVersion"
        assert oa.license == "CC-BY-4.0"
        assert oa.host_type == "publisher"
        assert oa.source == "unpaywall"

    def test_oa_status_green_access(self):
        """Verify green (repository) open access configuration"""
        oa = OpenAccessStatus(
            is_oa=True,
            oa_status="green",
            oa_url="https://arxiv.org/pdf/2301.00001.pdf",
            version="acceptedVersion",
            host_type="repository",
            source="openalex"
        )
        assert oa.is_oa is True
        assert oa.oa_status == "green"
        assert oa.host_type == "repository"

    def test_oa_status_bronze_access(self):
        """Verify bronze (free but no license) open access"""
        oa = OpenAccessStatus(
            is_oa=True,
            oa_status="bronze",
            oa_url="https://example.com/paper.pdf"
        )
        assert oa.is_oa is True
        assert oa.oa_status == "bronze"
        assert oa.license is None  # Bronze has no explicit license

    def test_oa_status_closed_access(self):
        """Verify closed access configuration"""
        oa = OpenAccessStatus(is_oa=False)
        assert oa.is_oa is False
        assert oa.oa_url is None

    def test_oa_status_with_verified_timestamp(self):
        """Verify OpenAccessStatus can store verification timestamp"""
        verified_time = datetime.now(timezone.utc)
        oa = OpenAccessStatus(
            is_oa=True,
            oa_status="gold",
            verified_at=verified_time
        )
        assert oa.verified_at == verified_time

    def test_oa_status_is_oa_required(self):
        """Verify is_oa field is required"""
        with pytest.raises(ValidationError) as exc_info:
            OpenAccessStatus()
        
        assert "is_oa" in str(exc_info.value)

    def test_oa_status_various_licenses(self):
        """Verify OpenAccessStatus accepts various license types"""
        licenses = [
            "CC-BY",
            "CC-BY-SA",
            "CC-BY-NC",
            "CC-0",
            "ODbL"
        ]
        
        for license_type in licenses:
            oa = OpenAccessStatus(
                is_oa=True,
                oa_status="gold",
                license=license_type
            )
            assert oa.license == license_type

    def test_oa_status_various_sources(self):
        """Verify OpenAccessStatus accepts various source identifiers"""
        sources = [
            "unpaywall",
            "openalex",
            "core",
            "crossref",
            "scienceopen"
        ]
        
        for source in sources:
            oa = OpenAccessStatus(
                is_oa=True,
                source=source
            )
            assert oa.source == source

    def test_oa_status_serialization(self):
        """Verify OpenAccessStatus can be serialized to dict"""
        oa = OpenAccessStatus(
            is_oa=True,
            oa_status="gold",
            oa_url="https://example.com/paper.pdf",
            license="CC-BY"
        )
        
        data = oa.model_dump()
        assert data["is_oa"] is True
        assert data["oa_status"] == "gold"
        assert data["oa_url"] == "https://example.com/paper.pdf"
        assert data["license"] == "CC-BY"

    def test_oa_status_model_validation(self):
        """Verify OpenAccessStatus validates correctly from dict"""
        data = {
            "is_oa": True,
            "oa_status": "gold",
            "oa_url": "https://example.com/paper.pdf",
            "version": "publishedVersion"
        }
        
        oa = OpenAccessStatus(**data)
        assert oa.is_oa is True
        assert oa.oa_status == "gold"
