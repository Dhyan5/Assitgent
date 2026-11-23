"""Retain small test fixtures: no automated deletion, including pytest temp cleanup."""
from pathlib import Path
from uuid import uuid4
import pytest


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[1] / '.test-artifacts' / uuid4().hex
    path.mkdir(parents=True)
    return path
