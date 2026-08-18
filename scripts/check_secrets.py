#!/usr/bin/env python3
"""Scan the repository for accidental secret literals (stdlib only).

Prints only masked values. Exit 1 when a finding is reported.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ── Patterns ────────────────────────────────────────────────────────────────

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub PAT", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("GitHub fine-grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("GitLab PAT", re.compile(r"glpat-[A-Za-z0-9\-_]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("OpenAI-like key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z\-_]{20,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("Private key header", re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----")),
    ("URL userinfo", re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:'\"]+:[^@\s'\"]+@")),
    (
        "Literal secret assignment",
        re.compile(
            r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|apikey|secret|password|passwd|token|authorization)"
            r"(?![A-Za-z0-9])[ \t]*[:=][ \t]*"
            r"""(?:['"]([^'"$`{]{12,})['"]|([^'"$\s`()\[\]{};,]{12,}))"""
        ),
    ),
)

_PLACEHOLDER = re.compile(
    r"(?i)^(x+|x{3,}|[.*•…]{3,}|your[_-].+|changeme|dummy|none|null|"
    r"example|placeholder|test-key|sample|todo|fixme|<\w+>)$"
)

_DANGEROUS_NAMES = re.compile(
    r"(?i)(^|/)("
    r"\.env(?!\.example)($|\..+)|"
    r"\.secrets$|"
    r"auth\.json$|"
    r"credentials\.json$|"
    r"service-account.*\.json$|"
    r"\.netrc$|"
    r"id_rsa$|id_ed25519$|id_ecdsa$|id_dsa$|"
    r".+\.(pem|p12|pfx|key)$"
    r")$"
)

_SKIP_DIR = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".slim",
}

_MAX_FILE_BYTES = 2 * 1024 * 1024


class GitUnavailable(RuntimeError):
    """git is required but missing or returned a non-zero status."""


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mask(value: str) -> str:
    compact = value.replace("\n", " ").strip()
    if len(compact) <= 8:
        return compact[:2] + "****"
    return compact[:6] + "...****" + compact[-4:]


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.match(value.strip().strip("'\"")))


def _captured_value(match: re.Match[str]) -> str:
    if match.lastindex:
        for idx in range(1, match.lastindex + 1):
            group = match.group(idx)
            if group:
                return group
    return match.group(0)


def _repo_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parents[1]


def _git_z(args: list[str], cwd: Path, *, required: bool) -> list[str]:
    try:
        raw = subprocess.check_output(args, cwd=cwd, stderr=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        if required:
            raise GitUnavailable("git is required for --staged") from exc
        return []
    except subprocess.CalledProcessError as exc:
        if required:
            raise GitUnavailable("git command failed: " + " ".join(args)) from exc
        return []
    if not raw:
        return []
    return [p.decode("utf-8", errors="replace") for p in raw.split(b"\0") if p]


def _listed_files(root: Path, staged: bool) -> list[Path]:
    if staged:
        names = _git_z(
            ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
            root,
            required=True,
        )
        return [root / name for name in names]
    names = _git_z(
        ["git", "ls-files", "-z", "-c", "-o", "--exclude-standard"],
        root,
        required=False,
    )
    if names:
        return [root / name for name in names]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR]
        for name in filenames:
            found.append(Path(dirpath) / name)
    return found


def _read_file(path: Path, root: Path, staged: bool) -> bytes | None:
    if staged:
        rel = path.relative_to(root).as_posix()
        try:
            return subprocess.check_output(
                ["git", "show", f":{rel}"],
                cwd=root,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise GitUnavailable("git is required for --staged") from exc
        except subprocess.CalledProcessError as exc:
            raise GitUnavailable(f"git show failed for staged path: {rel}") from exc
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
        return path.read_bytes()
    except OSError:
        return None


def _scan_text(rel: str, text: str) -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    if _DANGEROUS_NAMES.search(rel.replace("\\", "/")):
        hits.append(("Sensitive filename", 0, rel, "filename"))
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            raw = _captured_value(match)
            if _is_placeholder(raw):
                continue
            line = text.count("\n", 0, match.start()) + 1
            hits.append((kind, line, _mask(match.group(0)), "literal"))
    return hits


# ── Self-test ───────────────────────────────────────────────────────────────

def _self_test() -> int:
    fake_gh = "ghp_" + ("A" * 36)
    fake_gh_example = "ghp_" + ("A" * 10) + "example" + ("B" * 20)
    fake_pem = "-----BEGIN " + "RSA PRIVATE KEY-----"
    unquoted = "COMMANDCODE" + "_API_KEY=" + "not-a-placeholder-value"
    placeholder = 'COMMANDCODE_API_KEY="..."'
    code_assign = "api_key = _api_key(self.headers)\nif not api_key:\n    self._error(401, 'x')\n"
    model_id = '"nvidia/nemotron-3-ultra-550b-a55b"'
    interpolated = 'COMMANDCODE_API_KEY="$detected_key"'
    test_key = 'api_key = "test-key"'

    gh_hits = _scan_text("tmp.txt", f"token={fake_gh}\n")
    gh_ex_hits = _scan_text("tmp.txt", fake_gh_example + "\n")
    pem_hits = _scan_text("tmp.txt", fake_pem + "\n")
    name_hits = _scan_text(".env", "FOO=1\n")
    key_name_hits = _scan_text("server.key", "not-a-pem-blob\n")
    unquoted_hits = _scan_text("notes.sh", unquoted + "\n")
    empty = (
        _scan_text("README.md", placeholder + "\n")
        + _scan_text("models.json", model_id + "\n")
        + _scan_text("bin/hermes-commandcode", interpolated + "\n")
        + _scan_text("scripts/test_reasoning_mapping.py", test_key + "\n")
        + _scan_text("commandcode_bridge.py", code_assign)
    )
    git_fail_closed = False
    try:
        _git_z(["git", "rev-parse", "--verify", "not-a-real-git-ref"], Path("."), required=True)
    except GitUnavailable:
        git_fail_closed = True
    ok = (
        any(h[0] == "GitHub PAT" for h in gh_hits)
        and any(h[0] == "GitHub PAT" for h in gh_ex_hits)
        and any(h[0] == "Private key header" for h in pem_hits)
        and any(h[0] == "Sensitive filename" for h in name_hits)
        and any(h[0] == "Sensitive filename" for h in key_name_hits)
        and any(h[0] == "Literal secret assignment" for h in unquoted_hits)
        and git_fail_closed
        and not empty
    )
    if not ok:
        print("self-test failed", file=sys.stderr)
        return 1
    print("secret scanner self-test ok")
    return 0


# ── Main ────────────────────────────────────────────────────────────────────

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="scan only staged files")
    parser.add_argument("--self-test", action="store_true", help="run built-in pattern checks")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.self_test:
        return _self_test()

    root = _repo_root()
    findings = 0
    try:
        paths = _listed_files(root, staged=args.staged)
    except GitUnavailable as exc:
        print(f"secret scan failed: {exc}", file=sys.stderr)
        return 1
    for path in paths:
        if not path.is_file() and not args.staged:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = str(path)
        try:
            data = _read_file(path, root, staged=args.staged)
        except GitUnavailable as exc:
            print(f"secret scan failed: {exc}", file=sys.stderr)
            return 1
        if data is None:
            continue
        if b"\0" in data[:8192]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")
        for kind, line, masked, _how in _scan_text(rel, text):
            findings += 1
            where = f"{rel}:{line}" if line else rel
            print(f"{where}: {kind} ({masked})", file=sys.stderr)

    if findings:
        print(
            f"secret scan failed: {findings} finding(s). "
            "Remove the credential and rotate it if it was real.",
            file=sys.stderr,
        )
        return 1
    print("secret scan ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
