from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Sequence

from .models import GitLoggerError

@dataclass(frozen=True)
class GitResult:
	"""The result of a Git command."""

	returncode: int
	"""The Git process exit code."""
	stdout: str
	"""The standard output of a Git command."""
	stderr: str
	"""The error output of a Git command."""

def _run(args: Sequence[str], cwd: Path | None = None, env: dict[str, str] | None = None, input_text: str | None = None) -> GitResult:
	"""Run Git with provided arguments and return the result."""

	completed = subprocess.run(
		["git", *args],
		cwd=str(cwd) if cwd else None,
		env=env,
		input=input_text,
		text=True,
		encoding="utf-8",
		errors="replace",
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE)

	return GitResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)

def run_git(args: Sequence[str], cwd: Path | None = None, env: dict[str, str] | None = None, input_text: str | None = None, throw: bool = True) -> GitResult:
	"""Run Git and raise when Git returns a non-zero exit code."""

	result = _run(args, cwd=cwd, env=env, input_text=input_text)

	if throw and result.returncode != 0:
		location = f" in {cwd}" if cwd else ""
		raise GitLoggerError(
			f"git {' '.join(args)} failed{location} with exit code {result.returncode}:\n"
			f"{result.stderr.strip()}")

	return result