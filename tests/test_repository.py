"""Unit tests for control/repository.py against local fixture repos."""

from __future__ import annotations

from pathlib import Path

from control import repository
from tests.helpers.git_fixture import make_template_repo


def test_checkout_clones_and_returns_baseline(tmp_path: Path) -> None:
    template = make_template_repo(tmp_path / "template")
    target = tmp_path / "repo"
    sha = repository.checkout("wo-1", str(template), None, repo_dir=target)
    assert len(sha) == 40
    assert (target / "pyproject.toml").exists()
    assert repository._git(target, "rev-parse", "HEAD").stdout.strip() == sha


def test_checkout_at_pinned_baseline(tmp_path: Path) -> None:
    template = make_template_repo(tmp_path / "template")
    baseline = repository._git(template, "rev-parse", "HEAD").stdout.strip()
    # advance the template past the baseline
    (template / "extra.txt").write_text("later work\n")
    repository._git(template, "add", "-A")
    repository._git(template, "commit", "-m", "later")

    target = tmp_path / "repo"
    sha = repository.checkout("wo-1", str(template), baseline, repo_dir=target)
    assert sha == baseline
    assert not (target / "extra.txt").exists()


def test_checkout_refuses_populated_workspace(tmp_path: Path) -> None:
    import pytest

    template = make_template_repo(tmp_path / "template")
    target = tmp_path / "repo"
    target.mkdir()
    (target / "stale.txt").write_text("leftover\n")

    with pytest.raises(FileExistsError):
        repository.checkout("wo-1", str(template), None, repo_dir=target)


def test_commit_candidate_creates_branch_and_commits(tmp_path: Path) -> None:
    template = make_template_repo(tmp_path / "template")
    target = tmp_path / "repo"
    baseline = repository.checkout("wo-1", str(template), None, repo_dir=target)

    (target / "app" / "feature.txt").write_text("new work\n")
    sha = repository.commit_candidate("wo-1", "feat: new work", repo_dir=target)

    assert sha != baseline
    branch = repository._git(target, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    assert branch == "eds/wo-1"
    committed = repository._git(target, "show", "--stat", "--oneline", "HEAD").stdout
    assert "feature.txt" in committed


def test_commit_candidate_idempotent_without_changes(tmp_path: Path) -> None:
    template = make_template_repo(tmp_path / "template")
    target = tmp_path / "repo"
    repository.checkout("wo-1", str(template), None, repo_dir=target)
    first = repository.commit_candidate("wo-1", "feat: baseline only", repo_dir=target)
    second = repository.commit_candidate("wo-1", "feat: nothing new", repo_dir=target)
    assert first == second


def test_ensure_bare_repo_is_cloneable_and_idempotent(tmp_path: Path) -> None:
    source = make_template_repo(tmp_path / "src")
    bare = repository.ensure_bare_repo(source, tmp_path / "template.git")
    assert (bare / "HEAD").exists()

    clone = tmp_path / "clone"
    import subprocess

    subprocess.run(
        ["git", "clone", str(bare), str(clone)], check=True, capture_output=True, text=True
    )
    assert (clone / "pyproject.toml").exists()

    # second call must not fail or rewrite history
    again = repository.ensure_bare_repo(source, tmp_path / "template.git")
    assert again == bare


def test_worker_repo_dir_layout(tmp_path: Path) -> None:
    path = repository.worker_repo_dir("wo-9", base_dir=tmp_path)
    assert path == tmp_path / "wo-9" / "worker" / "repo"
