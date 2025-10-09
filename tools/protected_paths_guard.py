#!/usr/bin/env python3
"""
Pre-commit guard that enforces protected path rules defined in
`docs/protocol/PROTECTED_PATHS.yaml`.

The script reads the configured glob patterns, inspects staged changes, and
blocks commits that attempt to modify protected files unless an explicit Owner
override is present.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "docs/protocol/PROTECTED_PATHS.yaml"
DECISIONS_PATH = REPO_ROOT / "docs/protocol/DECISIONS.md"
OWNER_STAMP_TOKEN = "APPROVED BY OWNER —"


@dataclass(frozen=True)
class ProtectedPathsConfig:
    globs: Sequence[str]
    policy: Dict[str, str]


def _strip_comment(line: str) -> str:
    """Remove YAML-style comments from a line (naive but sufficient here)."""
    if "#" in line:
        index = line.index("#")
        return line[:index]
    return line


def _parse_value(raw: str) -> str:
    """Strip surrounding whitespace and quotes from a scalar value."""
    value = raw.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return value.strip()


def load_config(path: Path) -> ProtectedPathsConfig:
    """
    Parse the minimal YAML structure used for PROTECTED_PATHS.yaml without
    relying on third-party dependencies.
    """
    if not path.exists():
        raise FileNotFoundError(f"Protected paths config not found: {path}")

    globs: List[str] = []
    policy: Dict[str, str] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line:
            continue

        if not line.startswith(("-", " ")):
            # Section header (e.g., "globs:", "policy:")
            if line.endswith(":"):
                current_section = line[:-1].strip()
            else:
                current_section = None
            continue

        if current_section == "globs":
            if line.lstrip().startswith("-"):
                value = _parse_value(line.split("-", 1)[1])
                if value:
                    globs.append(value)
            continue

        if current_section == "policy":
            stripped = line.strip()
            if ":" in stripped:
                key, val = stripped.split(":", 1)
                policy[key.strip()] = _parse_value(val)

    return ProtectedPathsConfig(globs=tuple(globs), policy=policy)


def _run_git_diff_cached() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - git error
        print(exc.stderr or "Failed to inspect staged changes.", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def _iter_staged_changes(diff_output: str):
    for line in diff_output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        code = status[0]

        if code == "R" and len(parts) >= 3:
            yield code, parts[1], parts[2]
        elif code in {"M", "A", "D"} and len(parts) >= 2:
            yield code, parts[1], None
        else:
            # Other statuses are ignored for now.
            continue


def _matches_any_glob(path: str, patterns: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def _git_dir() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        check=True,
        capture_output=True,
        text=True,
    )
    return (Path(result.stdout.strip()) if result.stdout.strip() else Path(".git")).resolve()


def _commit_message_has_owner_stamp() -> bool:
    try:
        git_dir = _git_dir()
    except subprocess.CalledProcessError:
        return False

    for candidate in ["COMMIT_EDITMSG", "MERGE_MSG"]:
        path = git_dir / candidate
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if OWNER_STAMP_TOKEN in content:
                return True
    return False


def _decisions_has_owner_stamp() -> bool:
    if not DECISIONS_PATH.exists():
        return False
    try:
        return OWNER_STAMP_TOKEN in DECISIONS_PATH.read_text(encoding="utf-8")
    except OSError:
        return False


def owner_override_available() -> bool:
    return _commit_message_has_owner_stamp() or _decisions_has_owner_stamp()


def main() -> None:
    try:
        config = load_config(CONFIG_PATH)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    diff_output = _run_git_diff_cached()
    if not diff_output.strip():
        return

    blocked_files: List[str] = []
    warned_files: List[str] = []

    policy_modify = config.policy.get("on_modify", "block").lower()
    policy_delete = config.policy.get("on_delete", "block").lower()
    policy_rename = config.policy.get("on_rename", "block").lower()
    requires_owner = config.policy.get("override_requires_owner_stamp", "false").lower() == "true"

    for status, path1, path2 in _iter_staged_changes(diff_output):
        target_path = path2 if path2 else path1

        if not target_path:
            continue

        if not _matches_any_glob(target_path, config.globs):
            # For renames we should also check the original path.
            if status == "R" and path1 and _matches_any_glob(path1, config.globs):
                target_path = path1
            else:
                continue

        if status in {"M", "A"} and policy_modify == "block":
            blocked_files.append(target_path)
        elif status == "D" and policy_delete == "block":
            blocked_files.append(target_path)
        elif status == "R":
            if policy_rename == "block":
                blocked_files.append(target_path)
            elif policy_rename == "warn":
                warned_files.append(f"{path1} -> {path2}")

    for warning in warned_files:
        print(f"[protected-paths] rename warning: {warning}", file=sys.stderr)

    if not blocked_files:
        return

    if requires_owner and owner_override_available():
        print(
            "[protected-paths] Owner approval detected; bypassing guard for protected files.",
            file=sys.stderr,
        )
        return

    files_list = "\n  - ".join(sorted(blocked_files))
    message = (
        "[protected-paths] Staged changes include protected files. "
        "Commit blocked.\n"
        f"  - {files_list}"
    )
    if requires_owner:
        message += (
            "\nAdd an Owner approval line to the commit message or DECISIONS.md to override."
        )
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - interactive cancel
        sys.exit(130)
