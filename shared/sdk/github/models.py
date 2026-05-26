"""Dataclasses for the GitHub SDK return shapes.

These are intentionally minimal — just the fields the platform actually
uses for audit / notification / PR body rendering. We do NOT mirror the
whole GitHub schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GitHubIssue:
    repo: str
    number: int | None
    title: str
    body: str
    url: str
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "dry_run": self.dry_run,
        }


@dataclass
class GitHubBranch:
    repo: str
    name: str
    sha: str
    base_branch: str
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "name": self.name,
            "sha": self.sha,
            "base_branch": self.base_branch,
            "dry_run": self.dry_run,
        }


@dataclass
class GitHubFile:
    repo: str
    branch: str
    path: str
    content_preview: str
    sha: str
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "branch": self.branch,
            "path": self.path,
            "content_preview": self.content_preview,
            "sha": self.sha,
            "dry_run": self.dry_run,
        }


@dataclass
class GitHubPullRequest:
    repo: str
    number: int | None
    title: str
    body: str
    base_branch: str
    head_branch: str
    url: str
    state: str
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
            "url": self.url,
            "state": self.state,
            "dry_run": self.dry_run,
        }


@dataclass
class GitHubChecks:
    repo: str
    ref: str
    checks: list[dict] = field(default_factory=list)
    dry_run: bool = True

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "ref": self.ref,
            "count": len(self.checks),
            "checks": self.checks,
            "dry_run": self.dry_run,
        }
