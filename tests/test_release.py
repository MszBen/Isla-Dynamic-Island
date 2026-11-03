import importlib.util
from pathlib import Path

import pytest

import isla

_spec = importlib.util.spec_from_file_location(
    "release", Path(__file__).resolve().parent.parent / "packaging" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


def test_app_version_is_semver():
    assert release.SEMVER.match(isla.__version__)


@pytest.mark.parametrize("spec,expected", [
    ("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0"), ("3.0.0-beta.1", "3.0.0-beta.1"),
])
def test_next_version(spec, expected):
    assert release.next_version("1.2.3", spec) == expected


def test_next_version_rejects_garbage():
    with pytest.raises(ValueError):
        release.next_version("1.2.3", "bigger")
