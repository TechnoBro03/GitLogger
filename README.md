# Git Logger

[![Version](https://img.shields.io/pypi/v/gitlogger)](https://pypi.org/project/gitlogger-cli/)
![Python](https://img.shields.io/pypi/pyversions/gitlogger-cli)
![MyPy](https://img.shields.io/badge/mypy-checked-blue)
![License](https://img.shields.io/github/license/TechnoBro03/gitlogger)

The Git Logger CLI is a tool for creating a public contribution history from private Git repositories. It allows you to export commit metadata from private repositories and generate empty commits in another repository, preserving the original authored dates and enabling you to create a transparent contribution history.

## Table of Contents
- [Git Logger CLI](#git-logger)
- [Table of Contents](#table-of-contents)
- [Features](#features)
- [Installation](#installation)
- [Commands](#commands)
  - [gitlogger](#gitlogger)
  - [gitlogger export](#gitlogger-export)
  - [gitlogger generate](#gitlogger-generate)
- [Hiding Private Information](#hiding-private-information)
- [Replace vs Append](#--replace-vs-appending)
- [JSON Commit File](#json-commits-file)
- [Troubleshooting](#troubleshooting)

## Features

- Export commits from one repository, many repositories, or glob-matched repository folders.
- Filter exported commits by author name, author email, commit message, date range, and `HEAD` versus all refs.
- Write a portable JSON commits file that records the original sources and export filters.
- Generate empty commits that preserve authored dates for contribution history.
- Customize generated commit messages with a format string.
- Hide author names and/or emails from generated Git metadata.
- Append only new generated commits by default.
- Replace the generated branch when you want the branch to exactly match the current commits file.
- Create a backup branch before modifying an existing target branch.
- Optionally push the generated branch after generation.

## Installation

1. Make sure `pip` is installed on your system.
2. Run the following command:
	```bash
	pip install gitlogger-cli
	```

> [!TIP]
> See [here](https://packaging.python.org/en/latest/tutorials/installing-packages/) for more details on installing packages.

## Commands

Git Logger has two main commands: `export` and `generate`.

## gitlogger

### Usage

```bash
gitlogger [-h] {export|generate} ...
```

## gitlogger export

Exports commit metadata from one or more Git repositories into a JSON commits file.

### Usage

```bash
gitlogger export -s <source> [options]
```

### Arguments

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `-s`, `--source <path-or-glob>` | Yes | None | Source Git repository path or glob pattern. Can be repeated. |
| `-o`, `--output <file>` | No | `commits.json` | JSON commits file to write. |
| `-n`, `--name <name>` | No | Repository folder name | Override the exported source name. Only valid when `--source` resolves to one repository. |
| `-a`, `--author <regex>` | No | None | Case-insensitive regex filter for author name. |
| `-e`, `--email <regex>` | No | None | Case-insensitive regex filter for author email. |
| `-m`, `--message <regex>` | No | None | Case-insensitive regex filter for the full commit message. |
| `-S`, `--since <date>` | No | None | Only include commits after this Git date expression. |
| `-U`, `--until <date>` | No | None | Only include commits before this Git date expression. |
| `--all-refs` | No | `false` | Export commits reachable from all refs instead of only `HEAD`. |

### Examples

Export a single repository:

```powershell
gitlogger export -s "C:\src\private-repo" -o ".\gitlogger-commits.json"
```

Export every Git repository in a folder:

```powershell
gitlogger export -s "C:\src\private\*" -o ".\gitlogger-commits.json"
```

Export multiple specific sources:

```powershell
gitlogger export -s "C:\src\private-app" -s "C:\src\private-library" -o ".\gitlogger-commits.json"
```

Export only commits from your email:

```powershell
gitlogger export -s "C:\src\private\*" -e "you@example.com"
```

Export only commits from a specific date range:

```powershell
gitlogger export -s "C:\src\private\*" -S "2025-01-01" -U "2025-12-31"
```

Export commits whose messages match certain work types:

```powershell
gitlogger export -s "C:\src\private\*" -m "feature|fix|refactor|test"
```

Export commits from all branches and refs:

```powershell
gitlogger export -s "C:\src\private\*" --all-refs
```

Override the source name for one repository:

```powershell
gitlogger export -s "C:\src\private-client-project" --name "Client Project"
```

## gitlogger generate

Generates empty commits in a target repository from a JSON commits file.

> [!NOTE]
> Before modifying an existing branch, gitlogger creates a backup branch providing a recovery point if the generated commits are incorrect or if the branch is replaced unintentionally.

### Usage

```bash
gitlogger generate [options]
```

### Arguments

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `-r`, `--repo <path>` | No | `.` | Target Git repository to update. |
| `-i`, `--input <file>` | No | `commits.json` | JSON commits file to read. |
| `-b`, `--branch <branch>` | No | Current branch | Target branch to update. |
| `--remote <name>` | No | `origin` | Remote used when `--push` is set. |
| `-c`, `--committer-email <email>` | No | Source author email | Override the committer email. This can help GitHub attribute commits to the correct account. |
| `-p`, `--push` | No | `false` | Push to the remote repository immediately after generating commits. |
| `--replace` | No | `false` | Replace the target branch instead of appending new generated commits. |
| `-x`, `--exclude <author-email>` | No | None | Generated Git metadata to omit. Available values are `author` and `email`. Can accept multiple values and can be repeated. |
| `-f`, `--format <format>` | No | `{source} \| {subject}\n\n{message}` | Format string for generated commit messages. |

### Examples

Generate into the current repository and current branch:

```powershell
gitlogger generate -i ".\gitlogger-commits.json"
```

Generate into a specific repository and branch:

```powershell
gitlogger generate -r "C:\src\public-history" -i ".\gitlogger-commits.json" -b "main"
```

Append new commits only:

```powershell
gitlogger generate -r "C:\src\public-history" -i ".\gitlogger-commits.json" -b "main"
```

Replace the branch from the input file:

```powershell
gitlogger generate -r "C:\src\public-history" -i ".\gitlogger-commits.json" -b "main" --replace
```

Push after generating:

```powershell
gitlogger generate -r "C:\src\public-history" -i ".\gitlogger-commits.json" -b "main" --push
```

Use a specific committer email:

```powershell
gitlogger generate -i ".\gitlogger-commits.json" -c "you@example.com"
```

### Commit Message Format

The default generated commit message format is:

```text
{source} | {subject}

{message}
```

Available fields:

| Field | Description |
| --- | --- |
| `{source}` | Exported source name. Usually the repository folder name, unless overridden with `--name`. |
| `{sourcePath}` | Full path to the source repository. Usually private; avoid in public output. |
| `{hash}` | Full original source commit hash. |
| `{hash12}` | First 12 characters of the original source commit hash. |
| `{authoredAt}` | Original authored timestamp. |
| `{subject}` | Original commit subject line. |
| `{message}` | Original commit body, excluding the subject line. Empty when no body exists. |
| `{author}` | Original author name, unless excluded with `--exclude author`. |
| `{email}` | Original author email, unless excluded with `--exclude email`. |

### Format Examples

Show source and subject:

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --format "{source} | {subject}"
```

Show only the original subject:

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --format "{subject}"
```

Show a short source hash for traceability:

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --format "{subject} [{hash12}]"
```

Show author and subject:

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --format "{author}: {subject}"
```

Avoid exposing local source paths:

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --format "{sourcePath} | {subject}"
```

This is usually not recommended for public branches because it can reveal local folder names, usernames, company names, client names, or internal project paths.

### Multi-line Formats

`--format` is interpreted after your shell parses it. gitlogger does not convert the characters `\n` into a newline by itself.

PowerShell:

```bash
gitlogger generate -i ".\gitlogger-commits.json" --format "{source} | {subject}`n`n{message}"
```

Bash:

```bash
gitlogger generate -i "./gitlogger-commits.json" --format $'{source} | {subject}\n\n{message}'
```

## Hiding Private Information

There are two main tools for privacy during generation:

1. `--exclude` controls generated Git metadata.
2. `--format` controls generated commit message text.

Use both when you want clean public commits.

Hide author metadata by replacing it with a generic fallback.

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --exclude author
```

Hide email metadata by replacing it with a generic fallback.

```powershell
gitlogger generate -i ".\gitlogger-commits.json" --exclude email
```

### Avoid Leaking Data Through `--format`

`{author}`, `email`, `{source}`, `{sourcePath}`, `{hash}`, and `{message}` may reveal information depending on your source history.

For the safest public output, avoid these fields unless you have reviewed them:

```text
{sourcePath}
{email}
{author}
{message}
{hash}
```

A safer public format is:

```powershell
gitlogger generate --exclude author email --format "{subject}"
```

## `--replace` vs Append

By default, gitlogger appends only missing commits. This means it keeps existing generated commits and skips any exported commits already present on the branch.

Use the default append behavior when:

- You already generated a branch before.
- You exported more recent commits and only want to add the new ones.
- You do not want to rewrite public history.
- You are running gitlogger as part of a regular update process.

### Example:

```bash
gitlogger export -s "C:\src\private\*" -o ".\gitlogger-commits.json" -e "you@example.com"
gitlogger generate -r "C:\src\public-history" -i ".\gitlogger-commits.json" -b "main"
```

Use `--replace` when:

- You changed the `--format` and want every generated commit message rebuilt.
- You changed `--exclude` and want old exposed metadata removed.
- You changed export filters and want deleted commits removed from the generated branch.
- You want the target branch to exactly match the current commits file.
- You are intentionally rebuilding a generated branch before publishing it.

### Example:

```bash
gitlogger generate -r "C:\src\public-history" -i ".\gitlogger-commits.json" -b "main" -x author email -f "{subject}" --replace
```

If the branch already exists, gitlogger creates a backup branch before replacing it.

## JSON Commit File

The commits file contains the exported data used by `generate`.

### Example:

```json
{
  "$schema": "gitlogger.schema.json",
  "generated_at": "2026-05-20T00:00:00+00:00",
  "filters": {
    "source": ["C:\\src\\private\\*"],
    "name": null,
    "author": null,
    "email": "you@example.com",
    "message": null,
    "since": "2025-01-01",
    "until": null,
    "all_refs": false
  },
  "commits": [
    {
      "id": "stable-dedupe-id",
      "source": "private-repo",
      "sourcePath": "C:\\src\\private\\private-repo",
      "hash": "0123456789abcdef0123456789abcdef01234567",
      "authored_at": "2026-05-20T12:34:56+00:00",
      "author_name": "Your Name",
      "author_email": "you@example.com",
      "subject": "Original private commit subject",
      "message": "Optional commit body after the first line."
    }
  ],
  "sources": [
    {
      "name": "private-repo",
      "path": "C:\\src\\private\\private-repo"
    }
  ]
}
```

> [!IMPORTANT]
> The JSON file is not automatically sanitized. It records the exported source metadata so generation can be customized later. Do not commit the JSON file to a public repository unless you have reviewed it and are comfortable exposing its contents.

## Troubleshooting

**No Git repositories matched --source.**

The path or glob did not resolve to any Git repositories. Check that the folders exist and contain `.git` directories.

**--name can only be used when --source resolves to one repository.**

`--name` gives one source name to one repository. If your source glob resolves to multiple repositories, remove `--name` or export that repository separately.

**Could not determine current branch. Pass --branch explicitly.**

The target repository is probably in detached HEAD state or has no current branch. Pass `--branch` explicitly:

```bash
gitlogger generate -b "main"
```

**Unknown message format field**

The format string contains a field gitlogger does not recognize. Use only these fields:

```text
{source}, {sourcePath}, {subject}, {message}, {hash}, {hash12}, {author}, {email}, {authoredAt}
```

**Generated commits still reveal private information**

Check both Git metadata and commit message formatting.

Use:

```bash
gitlogger generate --replace --exclude author email --format "{subject}"
```

Then review:

```bash
git log --format=fuller
```

**`--push` pushed to the wrong place**

`--push` uses `--remote`, which defaults to `origin`, and pushes the target branch ref. Use `--remote` and `--branch` explicitly when publishing:

```bash
gitlogger generate -r "C:\src\public-history" -b "main" --remote "origin" --push
```
