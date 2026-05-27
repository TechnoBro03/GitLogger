from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

class GitLoggerError(RuntimeError):
	"""Raised for expected CLI failures that should print without a traceback."""

@dataclass(frozen=True)
class Commit:
	"""A source commit."""

	id: str
	"""The stable, unique identifier for this commit."""
	source: str
	"""The source repository for this commit."""
	sourcePath: str
	"""The path to the source repository for this commit."""
	hash: str
	"""The hash of the commit."""
	authored_at: str
	"""The date and time the commit was authored."""
	author_name: str
	"""The name of the author of the commit."""
	author_email: str
	"""The email of the author of the commit."""
	subject: str
	"""The subject of the commit."""
	message: str | None
	"""The message of the commit."""

@dataclass(frozen=True)
class ExportFilters:
	"""Filters used to create the commits file."""

	source: list[str]
	"""The source repositories."""
	name: str | None
	"""The name to override for a source repository"""
	author: str | None
	"""Case-insensitive regex filter for author name."""
	email: str | None
	"""Case-insensitive regex filter for author email."""
	message: str | None
	"""Case-insensitive regex filter for commit message."""
	since: str | None
	"""Only include commits after this Git date expression."""
	until: str | None
	"""Only include commits before this Git date expression."""
	all_refs: bool
	"""Include all references in the commits file."""

@dataclass(frozen=True)
class SourceInfo:
	"""A source repository matched during export."""

	name: str
	"""The name of the source repository."""
	path: str
	"""The path to the source repository."""

@dataclass(frozen=True)
class CommitFile:
	"""The JSON file used to generate contribution history."""

	generated_at: str
	"""The date and time the commits file was generated."""
	filters: ExportFilters
	"""The filters used to create the commits file."""
	commits: list[Commit]
	"""The commits included in the commits file."""
	sources: list[SourceInfo]
	"""The source repositories matched during export."""
	schema: str = "https://raw.githubusercontent.com/TechnoBro03/GitLogger/refs/heads/main/gitlogger.schema.json"
	"""The schema file used to validate the commits file."""

@dataclass(frozen=True)
class ExportOptions:
	"""Options for reading private Git repositories into a commits file."""

	output: Path
	"""The commits file to write."""
	filters: ExportFilters
	"""The filters used to create the commits file."""

@dataclass(frozen=True)
class GenerateOptions:
	"""Options for replacing the target branch from a commits file."""

	repo: Path
	"""The repository to generate the target branch in."""
	input: Path
	"""The commits file to read."""
	branch: str | None
	"""The branch to generate in the repository."""
	remote: str
	"""The remote to push the target branch to."""
	committer_email: str
	"""The email to use as the committer."""
	push: bool
	"""Whether to push the target branch to the remote."""
	replace: bool
	"""Whether to replace the existing branch instead of appending new commits."""
	excluded: set[str]
	"""The metadata to exclude from the target branch."""
	message_format: str
	"""The format string to use for the commit message."""

@dataclass(frozen=True)
class GenerateResult:
	backup: str
	"""The backup branch created before generating the target branch."""
	branch_ref: str
	"""The reference to the target branch in the repository."""
	commit_count: int
	"""The number of commits added to the target branch."""
	skipped_count: int = 0
	"""The number of commits skipped because they were already generated."""
