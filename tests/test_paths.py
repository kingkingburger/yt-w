"""Tests for the shared root-boundary path resolver."""

from pathlib import Path

import pytest

from src.yt_monitor.paths import PathOutsideRootError, resolve_within_root


def test_resolves_relative_path_under_root(tmp_path: Path):
    target = tmp_path / "live" / "clip.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"clip")

    assert resolve_within_root(tmp_path, "live/clip.mp4") == target.resolve()


def test_resolves_absolute_path_under_root(tmp_path: Path):
    target = tmp_path / "merged" / "clip.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"clip")

    assert resolve_within_root(tmp_path, target) == target.resolve()


def test_resolves_missing_path_because_existence_is_not_checked(tmp_path: Path):
    resolved = resolve_within_root(tmp_path, "merged/absent.mp4")

    assert resolved == (tmp_path / "merged" / "absent.mp4").resolve()
    assert not resolved.exists()


@pytest.mark.parametrize(
    "candidate",
    [
        "../escape.mp4",
        "live/../../escape.mp4",
        "..",
    ],
)
def test_rejects_traversal_out_of_root(tmp_path: Path, candidate: str):
    root = tmp_path / "root"
    (root / "live").mkdir(parents=True)

    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, candidate)


def test_rejects_absolute_path_outside_root(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")

    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, outside)


def test_rejects_symlink_escape_when_supported(tmp_path: Path):
    root = tmp_path / "root"
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    link = root / "merged" / "link.mp4"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"file symlinks are unavailable: {error}")

    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, "merged/link.mp4")


def test_error_is_a_value_error_so_callers_can_keep_domain_handling(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError):
        resolve_within_root(root, "../escape.mp4")
