from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .git import *
from .models import *
from .progress import LiveDisplay

DEFAULT_COMMITS_FILE = "commits.json"
DEFAULT_MESSAGE_FORMAT = "{source} | {subject}\n\n{message}"
DEFAULT_AUTHOR_NAME = "Unknown"
DEFAULT_AUTHOR_EMAIL = "unknown@unknown.email"
BACKUP_BRANCH_PREFIX = "backup-before-generate"
GITLOGGER_COMMITTER_PREFIX = "gitlogger:"

def cli_path(value: str) -> Path:
	"""Convert a string to an expanded Path."""

	return Path(value).expanduser().resolve()

def repo_path(value: str) -> Path:
	"""Convert a string to an expanded Path and verify that it is a Git repository."""

	path = cli_path(value)
	if not path.is_dir():
		raise GitLoggerError(f"Repository path does not exist: {path}")
	run_git(["rev-parse", "--git-dir"], cwd=path)
	return path

def export_options_from_args(args: argparse.Namespace) -> ExportOptions:
	return ExportOptions(
		output=cli_path(args.output),
		filters=ExportFilters(
			source=args.source,
			name=args.name,
			author=args.author,
			email=args.email,
			message=args.message,
			since=args.since,
			until=args.until,
			all_refs=args.all_refs))

def generate_options_from_args(args: argparse.Namespace) -> GenerateOptions:
	excluded = {item for group in args.exclude for item in group}
	return GenerateOptions(
		repo=repo_path(args.repo),
		input=cli_path(args.input),
		branch=args.branch,
		remote=args.remote,
		committer_email=args.committer_email,
		push=args.push,
		replace=args.replace,
		excluded=excluded,
		message_format=args.format)

def current_branch(repo: Path) -> str:
	"""Determine the current branch in a Git repository."""

	branch = run_git(["branch", "--show-current"], cwd=repo).stdout.strip()
	if not branch:
		raise GitLoggerError("Could not determine current branch. Pass --branch explicitly.")
	return branch

def full_ref(branch: str) -> str:
	"""Convert a branch name to a full Git reference."""

	return branch if branch.startswith("refs/") else f"refs/heads/{branch}"

def load_commit_file(path: Path) -> CommitFile:
	"""Load commits JSON into DTOs using constructor unpacking."""

	if not path.exists():
		raise GitLoggerError(f"Input file does not exist: {path}")
	with path.open("r", encoding="utf-8") as handle:
		data = json.load(handle)

	if not isinstance(data.get("commits"), list):
		raise GitLoggerError("Input file is missing a commits array.")

	filters = data["filters"]
	return CommitFile(
		generated_at=data["generated_at"],
		filters=ExportFilters(
			source=filters["source"],
			name=filters["name"],
			author=filters["author"],
			email=filters["email"],
			message=filters["message"],
			since=filters["since"],
			until=filters["until"],
			all_refs=filters["all_refs"],
		),
		commits=[Commit(**commit) for commit in data["commits"]],
		sources=[SourceInfo(**source) for source in data["sources"]],
		schema=data["$schema"],
	)


def write_commit_file(path: Path, commit_file: CommitFile) -> None:
	"""Write a CommitFile to a JSON file."""

	path.parent.mkdir(parents=True, exist_ok=True)
	data = asdict(commit_file)
	data = {
		"$schema": data.pop("schema"),
		"generated_at": data["generated_at"],
		"filters": data["filters"],
		"commits": data["commits"],
		"sources": data["sources"],
	}
	with path.open("w", encoding="utf-8", newline="\n") as handle:
		json.dump(data, handle, indent=2)
		handle.write("\n")


def expand_source_patterns(patterns: Sequence[str]) -> list[Path]:
	"""Expand literal paths/globs and return unique Git repository roots."""

	repos: dict[str, Path] = {}
	for pattern in patterns:
		pattern_text = str(Path(pattern).expanduser())
		candidates = glob.glob(pattern_text, recursive=True) or [pattern_text]
		for candidate in candidates:
			path = cli_path(candidate)
			if not path.is_dir():
				continue
			try:
				root = cli_path(run_git(["rev-parse", "--show-toplevel"], cwd=path).stdout.strip())
			except GitLoggerError:
				continue
			repos[str(root).casefold()] = root
	return sorted(repos.values(), key=lambda item: str(item).casefold())


def compile_regex(value: str | None, label: str) -> re.Pattern[str] | None:
	"""Compile a regex pattern for filtering commits."""

	if not value:
		return None
	try:
		return re.compile(value, re.IGNORECASE)
	except re.error as exc:
		raise GitLoggerError(f"Invalid {label} regex: {exc}") from exc

def stable_record_id(source_name: str, commit_hash: str) -> str:
	"""Generate a stable record ID for a commit from a source."""

	return hashlib.sha256(f"{source_name}\0{commit_hash}".encode("utf-8")).hexdigest()[:40]

def source_log_rows(repo: Path, options: ExportOptions) -> list[str]:
	"""Get the log rows for a source repository."""

	command = [
		"log",
		"--all" if options.filters.all_refs else "HEAD",
		"--date-order",
		"--format=%H%x1f%aI%x1f%an%x1f%ae%x1f%B%x1e",
	]
	if options.filters.since:
		command.append(f"--since={options.filters.since}")
	if options.filters.until:
		command.append(f"--until={options.filters.until}")
	return [record.strip() for record in run_git(command, cwd=repo).stdout.split("\x1e") if record.strip()]

def split_commit_message(value: str) -> tuple[str, str | None]:
	"""Split Git's full commit message into subject and trimmed body."""

	normalized = value.strip()
	if not normalized: return "", None

	subject, _, body = normalized.partition("\n")
	body = body.strip()
	return subject.strip(), body or None

def collect_commits(repos: Sequence[Path], options: ExportOptions, display: LiveDisplay | None = None) -> list[Commit]:
	"""Collect source commits, apply filters, and de-duplicate records."""

	author_re = compile_regex(options.filters.author, "author")
	email_re = compile_regex(options.filters.email, "email")
	message_re = compile_regex(options.filters.message, "message")
	commits_by_id: dict[str, Commit] = {}

	for repo_index, repo in enumerate(repos, start=1):
		source_name = options.filters.name or repo.name
		rows = source_log_rows(repo, options)
		if display:
				display.progress([
					("Processing repositories", repo_index - 1, len(repos), "repos"),
					(f"Processing {source_name}", 0, len(rows), "commits")])
		if not rows: continue

		for commit_index, row in enumerate(rows, start=1):
			commit_hash, authored_at, author_name, author_email, full_message = row.split("\x1f", 4)
			subject, message = split_commit_message(full_message)

			if not ((author_re and not author_re.search(author_name)) or (email_re and not email_re.search(author_email)) or (message_re and not message_re.search(full_message))):
				record_id = stable_record_id(source_name, commit_hash)
				commits_by_id[record_id] = Commit(
					id=record_id,
					source=source_name,
					sourcePath=str(repo),
					hash=commit_hash,
					authored_at=authored_at,
					author_name=author_name,
					author_email=author_email,
					subject=subject,
					message=message)

			if display:
				display.progress([
					("Processing repositories", repo_index - 1, len(repos), "repos"),
					(f"Processing {source_name}", commit_index, len(rows), "commits")])

		if display:
			display.progress([
				("Processing repositories", repo_index, len(repos), "repos"),
				(f"Processing {source_name}", len(rows), len(rows), "commits")])

	return sorted(commits_by_id.values(), key=lambda commit: (commit.authored_at, commit.source.casefold(), commit.id))

def source_infos(repos: Sequence[Path], options: ExportOptions) -> list[SourceInfo]:
	"""Get the source information for a list of repositories."""

	return [SourceInfo(name=options.filters.name or repo.name, path=str(repo)) for repo in repos]

def build_commit_message(commit: Commit, options: GenerateOptions) -> str:
	"""Build a commit message from a Commit object and GenerateOptions."""

	values = {
		# Format values
		"source": commit.source,
		"sourcePath": commit.sourcePath,
		"hash": commit.hash,
		"hash12": commit.hash[:12],
		"authoredAt": commit.authored_at,
		"subject": commit.subject,
		"message": commit.message or "",
		# Metadata (can be excluded by --exclude)
		"author": commit.author_name if "author" not in options.excluded else DEFAULT_AUTHOR_NAME,
		"email": commit.author_email if "email" not in options.excluded else DEFAULT_AUTHOR_EMAIL,
	}

	try:
		message = options.message_format.format(**values)
	except KeyError as exc:
		raise GitLoggerError(f"Unknown message format field: {exc.args[0]}") from exc
	return message.strip() or commit.id # Default to internal commit ID if message is empty

def commit_env(commit: Commit, options: GenerateOptions) -> dict[str, str]:
	"""Build the environment for a generated commit.

	The GitLogger id is stored as the committer name (prefixed with GITLOGGER_COMMITTER_PREFIX)
	so dedupe across runs can read all ids with a single `git log --format=%cn`.
	"""

	# Hide author and email if they are excluded
	author_name = DEFAULT_AUTHOR_NAME if "author" in options.excluded else commit.author_name
	author_email = DEFAULT_AUTHOR_EMAIL if "email" in options.excluded else commit.author_email

	env = os.environ.copy()
	env.update(
		{
			"GIT_AUTHOR_DATE": commit.authored_at,
			"GIT_COMMITTER_DATE": commit.authored_at,
			"GIT_AUTHOR_NAME": author_name,
			"GIT_AUTHOR_EMAIL": author_email,
			"GIT_COMMITTER_NAME": f"{GITLOGGER_COMMITTER_PREFIX}{commit.id}", # Store id for deduplication
			"GIT_COMMITTER_EMAIL": options.committer_email or author_email, # Use committer email or author email if committer email is not set
		}
	)
	return env

def empty_tree(repo: Path) -> str:
	"""Create an empty tree in a Git repository."""

	return run_git(["mktree"], cwd=repo, input_text="").stdout.strip()

def create_generated_commit(repo: Path, tree: str, parent: str | None, message: str, env: dict[str, str]) -> str:
	"""Create a generated commit in a Git repository."""

	args = ["commit-tree", tree]
	if parent:
		args.extend(["-p", parent])
	return run_git(args, cwd=repo, env=env, input_text=f"{message}\n").stdout.strip()

def backup_branch(repo: Path, branch_head: str) -> str:
	"""Create a backup branch in a Git repository."""

	timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
	backup = f"{BACKUP_BRANCH_PREFIX}/{timestamp}"
	run_git(["update-ref", full_ref(backup), branch_head], cwd=repo)
	return backup

def existing_ids(repo: Path, branch_ref: str) -> set[str]:
	"""Return the set of GitLogger ids already recorded on commits in branch_ref.

	The id is encoded in the committer name as "gitlogger:<id>".
	"""

	if run_git(["rev-parse", "--verify", branch_ref], cwd=repo, throw=False).returncode != 0:
		return set()

	result = run_git(["log", branch_ref, "--format=%cn"], cwd=repo, throw=False)
	if result.returncode != 0: return set()

	prefix_len = len(GITLOGGER_COMMITTER_PREFIX)
	ids: set[str] = set()

	for line in result.stdout.splitlines():
		if line.startswith(GITLOGGER_COMMITTER_PREFIX):
			ids.add(line[prefix_len:])
	return ids

def export_commits(options: ExportOptions, display: LiveDisplay | None = None) -> CommitFile:
	"""Export commits from a list of Git repositories."""

	if display: display.status("Finding Git repositories...")
	repos = expand_source_patterns(options.filters.source)
	if not repos:
		raise GitLoggerError("No Git repositories matched --source.")
	if options.filters.name and len(repos) > 1:
		raise GitLoggerError("--name can only be used when --source resolves to one repository.")

	if display: display.status(f"Found {len(repos)} source repo(s).")
	commits = collect_commits(repos, options, display)
	commit_file = CommitFile(
		generated_at=datetime.now(timezone.utc).isoformat(),
		filters=options.filters,
		commits=commits,
		sources=source_infos(repos, options),
	)
	write_commit_file(options.output, commit_file)
	return commit_file

def generate_history(options: GenerateOptions, display: LiveDisplay | None = None) -> GenerateResult:
	"""Append generated commits to the target branch, or replace it when --replace is set."""

	if display: display.status("Resolving target branch...")
	branch = options.branch or current_branch(options.repo)
	branch_ref = full_ref(branch)

	if display: display.status(f"Reading current {branch_ref}...")
	head_result = run_git(["rev-parse", branch_ref], cwd=options.repo, throw=False)
	old_head = head_result.stdout.strip() if head_result.returncode == 0 else None

	if display: display.status("Creating backup branch...")
	backup = backup_branch(options.repo, old_head) if old_head else ""

	if display: display.status(f"Loading commits from {options.input}...")
	commit_file = load_commit_file(options.input)

	if display: display.status("Reading existing GitLogger ids...")
	known_ids: set[str] = set() if options.replace else existing_ids(options.repo, branch_ref)

	pending = [commit for commit in commit_file.commits if commit.id not in known_ids]
	skipped = len(commit_file.commits) - len(pending)
	total = len(pending)

	if options.replace or old_head is None:
		if display: display.status("Creating empty tree...")
		base_tree = empty_tree(options.repo)
		new_head: str | None = None if options.replace else old_head
	else:
		if display: display.status("Reading current branch tree...")
		base_tree = run_git(["rev-parse", f"{old_head}^{{tree}}"], cwd=options.repo).stdout.strip()
		new_head = old_head

	for index, commit in enumerate(pending, start=1):
		message = build_commit_message(commit, options)
		new_head = create_generated_commit(options.repo, base_tree, new_head, message, commit_env(commit, options))
		if display: display.progress([("Generating commits", index, total, "commits")])

	if new_head is None or (options.replace and total == 0):
		raise GitLoggerError("Nothing to generate; commits file is empty.")

	reason = "replace GitLogger branch" if options.replace else "append GitLogger commits"
	if old_head:
		run_git(["update-ref", "-m", reason, branch_ref, new_head, old_head], cwd=options.repo)
	else:
		run_git(["update-ref", "-m", reason, branch_ref, new_head], cwd=options.repo)

	if options.push:
		run_git(["push", options.remote, f"{branch_ref}:{branch_ref}"], cwd=options.repo)

	return GenerateResult(backup, branch_ref, total, skipped)

def cmd_export(args: argparse.Namespace) -> int:
	"""Handle the 'export' command."""

	options = export_options_from_args(args)
	display = LiveDisplay()

	try: commit_file = export_commits(options, display)
	finally: display.finish()

	print(f"\033[92mWrote {len(commit_file.commits)} unique commits to {options.output}\033[0m")
	return 0

def cmd_generate(args: argparse.Namespace) -> int:
	"""Handle the 'generate' command."""

	options = generate_options_from_args(args)
	display = LiveDisplay()

	try: result = generate_history(options, display)
	finally: display.finish()

	action = "Replaced branch with" if options.replace else "Added"
	print(f"\033[92m{action} {result.commit_count} commits from {options.input}.\033[0m")

	if result.skipped_count: print(f"  Skipped {result.skipped_count} commits already present on the branch.")
	if result.backup: print(f"  Backup branch created: {result.backup}")

	if options.push:
		print(f"  Pushed generated commits to {options.remote}/{options.branch}.")
	else:
		print(f"  Review with: \033[96mgit -C {options.repo} log --oneline\033[0m")
		print(f"  Push with:   \033[96mgit -C {options.repo} push {options.remote} {result.branch_ref}:{result.branch_ref}\033[0m")
	return 0

def add_export_args(parser: argparse.ArgumentParser) -> None:
	"""Add arguments for the 'export' command."""

	parser.add_argument("-s", "--source", action="append", required=True, help="Source Git repo path or glob. Can be repeated.")
	parser.add_argument("-o", "--output", default=DEFAULT_COMMITS_FILE, help="JSON commits file to write.")
	parser.add_argument("-n", "--name", help="Override source repo name. Only valid for one source repo.")
	parser.add_argument("-a", "--author", help="Case-insensitive regex filter for author name.")
	parser.add_argument("-e", "--email", help="Case-insensitive regex filter for author email.")
	parser.add_argument("-m", "--message", help="Case-insensitive regex filter for full commit message.")
	parser.add_argument("-S", "--since", help="Only include commits after this Git date expression.")
	parser.add_argument("-U", "--until", help="Only include commits before this Git date expression.")
	parser.add_argument("--all-refs", action="store_true", help="Export commits reachable from all refs instead of HEAD only.")

def add_generate_args(parser: argparse.ArgumentParser) -> None:
	"""Add arguments for the 'generate' command."""

	parser.add_argument("-r", "--repo", default=".", help="Target repository to update.")
	parser.add_argument("-i", "--input", default=DEFAULT_COMMITS_FILE, help="JSON commits file to read.")
	parser.add_argument("-b", "--branch", help="Target branch. Defaults to current branch.")
	parser.add_argument("--remote", default="origin", help="Remote used when --push is set.")
	parser.add_argument("-c", "--committer-email", default="", help="Override committer email. This allows GitHub to attribute the commits to the correct user.")
	parser.add_argument("-p", "--push", action="store_true", help="Push after generating commits.")
	parser.add_argument("--replace", action="store_true", help="Replace the target branch instead of appending new commits.")
	parser.add_argument(
		"-x",
		"--exclude",
		action="append",
		choices=("author", "email"),
		default=[],
		nargs="+",
		help="Generated Git metadata to omit. Example: --exclude author email. Can be repeated.",
	)
	parser.add_argument(
		"-f",
		"--format",
		default=DEFAULT_MESSAGE_FORMAT,
		help="Generated commit message format. Available fields: {source}, {sourcePath}, {subject}, {message}, {hash}, {hash12}, {author}, {email}, {authoredAt}.",
	)

def build_parser() -> argparse.ArgumentParser:
	"""Build the command-line parser."""

	parser = argparse.ArgumentParser(prog="gitlogger", description="Generate public contribution history from private Git repos.")
	subparsers = parser.add_subparsers(dest="command", required=True)

	export_parser = subparsers.add_parser("export", help="Export private repo history into a JSON commits file.")
	add_export_args(export_parser)
	export_parser.set_defaults(func=cmd_export)

	generate_parser = subparsers.add_parser("generate", help="Generate commits from a JSON commits file.")
	add_generate_args(generate_parser)
	generate_parser.set_defaults(func=cmd_generate)

	return parser

def main(argv: Sequence[str] | None = None) -> int:
	"""Main entry point for the gitlogger command-line tool."""

	try:
		parser = build_parser()
		args = parser.parse_args(argv)
		return args.func(args)

	except KeyboardInterrupt:
		print("\033[91mInterrupted\033[0m", file=sys.stderr)
		return 130

	except Exception as exc:
		print(f"\033[91mUnexpected error: {exc}\033[0m", file=sys.stderr)
		return 1

if __name__ == "__main__":
	raise SystemExit(main())
