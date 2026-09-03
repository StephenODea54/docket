import pytest

from docket.config.env import AWS_REGIONS
from docket.db.db import _build_aws_config


def test_build_aws_config_empty(monkeypatch):
    monkeypatch.delenv(AWS_REGIONS, raising=False)
    assert _build_aws_config() is None


def test_build_aws_config_single_region(monkeypatch):
    monkeypatch.setenv(AWS_REGIONS, "us-east-1")
    assert _build_aws_config() == 'regions = ["us-east-1"]'


def test_build_aws_config_multiple_regions(monkeypatch):
    monkeypatch.setenv(AWS_REGIONS, "us-east-1, us-west-2,")
    assert _build_aws_config() == 'regions = ["us-east-1", "us-west-2"]'
