"""Tests for the oversized-blob guard.

The important case is the bypass that defeated the previous working-tree-based
hook: stage a large blob, then truncate the working copy. A size check that
stats the path passes; a check that reads the staged blob does not.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "tools" / "check_large_files.py"


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def run_checker(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git("init", "-b", "main", cwd=tmp_path)
    git("config", "user.email", "test@example.invalid", cwd=tmp_path)
    git("config", "user.name", "Test", cwd=tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    git("add", "seed.txt", cwd=tmp_path)
    git("commit", "-m", "seed", cwd=tmp_path)
    return tmp_path


def test_small_file_passes(repo: Path):
    (repo / "small.txt").write_text("tiny\n")
    git("add", "small.txt", cwd=repo)
    assert run_checker(repo).returncode == 0


def test_large_file_blocked(repo: Path):
    (repo / "big.bin").write_bytes(b"\0" * (11 * 1024 * 1024))
    git("add", "big.bin", cwd=repo)
    result = run_checker(repo)
    assert result.returncode == 1
    assert "big.bin" in result.stderr


def test_staged_large_blob_with_truncated_working_copy_is_blocked(repo: Path):
    """The bypass case. This is why the check reads blobs, not the filesystem."""
    target = repo / "sneaky.bin"
    target.write_bytes(b"\0" * (11 * 1024 * 1024))
    git("add", "sneaky.bin", cwd=repo)
    target.write_bytes(b"x")  # working copy now 1 byte; blob is still 11 MiB

    result = run_checker(repo)
    assert result.returncode == 1, "large staged blob escaped the check"
    assert "sneaky.bin" in result.stderr


def test_filename_with_spaces_is_reported(repo: Path):
    (repo / "a big file.bin").write_bytes(b"\0" * (11 * 1024 * 1024))
    git("add", "a big file.bin", cwd=repo)
    result = run_checker(repo)
    assert result.returncode == 1
    assert "a big file.bin" in result.stderr


def test_deletion_does_not_crash(repo: Path):
    git("rm", "seed.txt", cwd=repo)
    assert run_checker(repo).returncode == 0


def test_rename_is_handled(repo: Path):
    git("mv", "seed.txt", "renamed.txt", cwd=repo)
    assert run_checker(repo).returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlink_target_is_not_followed(repo: Path):
    huge = repo / "huge_target.bin"
    huge.write_bytes(b"\0" * (11 * 1024 * 1024))
    link = repo / "link.bin"
    link.symlink_to(huge)
    git("add", "link.bin", cwd=repo)  # huge_target.bin itself stays unstaged
    assert run_checker(repo).returncode == 0, "symlink was followed to its target"


def test_tree_mode_scans_committed_blobs(repo: Path):
    (repo / "committed_big.bin").write_bytes(b"\0" * (11 * 1024 * 1024))
    git("add", "committed_big.bin", cwd=repo)
    git("commit", "--no-verify", "-m", "sneak past the hook", cwd=repo)

    # --staged is clean now, but the blob is in history: this is the --no-verify
    # case that CI must catch.
    assert run_checker(repo, "--staged").returncode == 0
    assert run_checker(repo, "--tree").returncode == 1
