from __future__ import annotations

import shutil
import sys
from collections.abc import Sequence

WIDTH = 28

class LiveDisplay:
	"""Small dependency-free terminal status/progress renderer."""

	def __init__(self) -> None:
		self.interactive = sys.stdout.isatty()
		"""Whether the display is running in an interactive terminal."""
		self.lines = 0
		"""Number of lines currently displayed."""
		self.last_text = ""
		"""Last text that was displayed."""

	def status(self, text: str) -> None:
		"""
		Display a status message.
		
		In interactive mode, the line is redrawn in-place.
		In non-interactive mode, the line is printed only when it changes and on a new line.
		"""
		if not self.interactive:
			if text != self.last_text:
				print(text, flush=True)
				self.last_text = text
			return
		self._render([text])

	def progress(self, bars: Sequence[tuple[str, int, int, str]]) -> None:
		"""
		Displays one or more progress bars.

		In interactive mode, the progress bars are redrawn in-place.
		In non-interactive mode, the progress bars are not displayed.
		"""
		if not self.interactive: return # Non-interactive mode does not display progress

		lines: list[str] = []
		for title, current, total, unit in bars:
			lines.append(title)
			lines.append(self._bar(current, total, unit))
		self._render(lines)

	def finish(self) -> None:
		"""Finish the progress display."""
		if self.lines:
			sys.stdout.write("\n")
			sys.stdout.flush()
			self.lines = 0

	def _render(self, lines: Sequence[str]) -> None:
		"""
		Redraw lines in-place.
		"""
		previous = self.lines
		if previous:
			sys.stdout.write(f"\x1b[{previous}F")
		for line in lines:
			sys.stdout.write(f"\r\x1b[2K{self._fit(line)}\n")
		for _ in range(previous - len(lines)):
			sys.stdout.write("\r\x1b[2K\n")
		sys.stdout.flush()
		self.lines = max(previous, len(lines))

	def _bar(self, current: int, total: int, unit: str) -> str:
		"""Render a progress bar."""
		width = WIDTH
		filled = int(width * current / total) if total else width
		return f"[{'#' * filled}{'-' * (width - filled)}] {current}/{total} {unit}"

	def _fit(self, text: str) -> str:
		"""
		Truncate text to fit in the terminal.
		
		This prevents the text from overflowing the terminal width which would cause the display to become corrupted.
		"""
		columns = shutil.get_terminal_size(fallback=(80, 24)).columns
		if len(text) <= columns: return text
		return text[: max(columns - 3, 0)] + "..."
