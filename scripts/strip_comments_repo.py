from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "pip_packages",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "logs",
    "run",
}

EXCLUDED_PREFIXES = {
    "core/saturday-core/third_party",
}

TARGET_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".scss",
    ".html",
    ".htm",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".ino",
}

TARGET_FILENAMES = {
    "CMakeLists.txt",
    "Dockerfile",
}

C_STYLE_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".scss",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".ino",
}

HASH_COMMENT_EXTENSIONS = {
    ".ps1",
    ".sh",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
}

BATCH_EXTENSIONS = {".bat", ".cmd"}


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: str


def is_excluded(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return True
    return any(rel.startswith(prefix + "/") or rel == prefix for prefix in EXCLUDED_PREFIXES)


def target_file(path: Path) -> bool:
    if path.name in TARGET_FILENAMES:
        return True
    return path.suffix.lower() in TARGET_EXTENSIONS


def decode_text(data: bytes) -> tuple[str, str] | None:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return None


def pos_to_offset(lines: list[str], line: int, col: int) -> int:
    return sum(len(lines[i]) for i in range(line - 1)) + col


def collect_python_docstring_edits(tree: ast.AST, lines: list[str]) -> list[Edit]:
    edits: list[Edit] = []

    def maybe_add_docstring(body: list[ast.stmt], add_pass_when_only: bool) -> None:
        if not body:
            return
        first = body[0]
        if not isinstance(first, ast.Expr):
            return
        value = first.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return
        if not hasattr(first, "lineno") or not hasattr(first, "end_lineno"):
            return
        start = pos_to_offset(lines, first.lineno, first.col_offset)
        end = pos_to_offset(lines, first.end_lineno, first.end_col_offset)
        replacement = ""
        if add_pass_when_only and len(body) == 1:
            indent = " " * first.col_offset
            replacement = f"{indent}pass\n"
        edits.append(Edit(start=start, end=end, replacement=replacement))

    if isinstance(tree, ast.Module):
        maybe_add_docstring(tree.body, add_pass_when_only=False)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            maybe_add_docstring(node.body, add_pass_when_only=True)

    return edits


def apply_edits(text: str, edits: list[Edit]) -> str:
    if not edits:
        return text
    out = text
    for e in sorted(edits, key=lambda x: x.start, reverse=True):
        out = out[: e.start] + e.replacement + out[e.end :]
    return out


def strip_python_comments(text: str) -> str:
    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None

    if tree is not None:
        text = apply_edits(text, collect_python_docstring_edits(tree, lines))

    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        cleaned: list[tokenize.TokenInfo] = []
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                if tok.start[0] == 1 and tok.string.startswith("#!"):
                    cleaned.append(tok)
                continue
            cleaned.append(tok)
        result = tokenize.untokenize(cleaned)
        return compact_blank_lines(result)
    except Exception:
        return strip_python_line_comments(text)


def strip_python_line_comments(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if idx == 1 and stripped.startswith("#!"):
            out.append(line)
            continue
        if stripped.startswith("#"):
            continue
        out.append(line)
    return compact_blank_lines("".join(out))


def strip_c_style_full_line_comments(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_block = False

    for line in lines:
        stripped = line.lstrip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("//"):
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block = True
            continue
        if stripped.startswith("*") and out and out[-1].strip().endswith("/*"):
            continue
        out.append(line)

    return compact_blank_lines("".join(out))


def strip_hash_comments(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if idx == 1 and stripped.startswith("#!"):
            out.append(line)
            continue
        if stripped.startswith("#"):
            continue
        out.append(line)
    return compact_blank_lines("".join(out))


def strip_batch_comments(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        lowered = stripped.lower()
        if lowered.startswith("rem ") or lowered == "rem\r\n" or lowered == "rem\n" or stripped.startswith("::"):
            continue
        out.append(line)
    return compact_blank_lines("".join(out))


def strip_html_comments(text: str) -> str:
    out = text
    while True:
        start = out.find("<!--")
        if start == -1:
            break
        end = out.find("-->", start + 4)
        if end == -1:
            out = out[:start]
            break
        out = out[:start] + out[end + 3 :]
    return compact_blank_lines(out)


def compact_blank_lines(text: str) -> str:
    lines = text.splitlines(keepends=True)
    compacted: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count > 2:
                continue
        else:
            blank_count = 0
        compacted.append(line)
    return "".join(compacted)


def strip_comments_for_file(path: Path, text: str) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return strip_python_comments(text)
    if ext in C_STYLE_EXTENSIONS or path.name == "CMakeLists.txt":
        return strip_c_style_full_line_comments(text)
    if ext in HASH_COMMENT_EXTENSIONS:
        return strip_hash_comments(text)
    if ext in BATCH_EXTENSIONS:
        return strip_batch_comments(text)
    if ext in {".html", ".htm"}:
        return strip_html_comments(text)
    return text


def main() -> None:
    scanned = 0
    modified = 0
    skipped_decode = 0
    skipped_binary_like = 0
    skipped_errors = 0

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded(path):
            continue
        if not target_file(path):
            continue
        scanned += 1
        raw = path.read_bytes()
        if b"\x00" in raw:
            skipped_binary_like += 1
            continue
        decoded = decode_text(raw)
        if decoded is None:
            skipped_decode += 1
            continue
        text, encoding = decoded
        newline = "\r\n" if b"\r\n" in raw else "\n"
        normalized = re.sub(r"\r+\n", "\n", text).replace("\r", "\n")
        try:
            cleaned = strip_comments_for_file(path, normalized)
        except Exception:
            skipped_errors += 1
            continue
        if newline == "\r\n":
            cleaned = cleaned.replace("\n", "\r\n")
        if cleaned != text:
            out = cleaned.encode("utf-8-sig" if encoding == "utf-8-sig" else "utf-8")
            path.write_bytes(out)
            modified += 1

    print(f"scanned={scanned}")
    print(f"modified={modified}")
    print(f"skipped_decode={skipped_decode}")
    print(f"skipped_binary_like={skipped_binary_like}")
    print(f"skipped_errors={skipped_errors}")


if __name__ == "__main__":
    main()
