import pytest

from docket.config.env import AWS_REGIONS
from docket.db.db import _build_aws_config


@pytest.fixture
def no_regions(monkeypatch):
    monkeypatch.delenv(AWS_REGIONS, raising=False)


def test_build_aws_config_empty(no_regions):
    assert _build_aws_config(None) is None


def test_build_aws_config_profile_only(no_regions):
    assert _build_aws_config("admin") == 'profile = "admin"'


def test_build_aws_config_regions_only(monkeypatch):
    monkeypatch.setenv(AWS_REGIONS, "us-east-1")
    assert _build_aws_config(None) == 'regions = ["us-east-1"]'


def test_build_aws_config_profile_and_regions(monkeypatch):
    monkeypatch.setenv(AWS_REGIONS, "us-east-1, us-west-2,")
    assert _build_aws_config("admin") == (
        'profile = "admin"\nregions = ["us-east-1", "us-west-2"]'
    )
