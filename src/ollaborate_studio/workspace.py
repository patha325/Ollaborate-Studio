from __future__ import annotations

from pathlib import Path


class Workspace:
    """A path-confined workspace exposed to agents and the UI."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace does not exist: {self.root}")

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("Path escapes the workspace")
        return path

    def list_files(self, path: str = ".") -> list[str]:
        """List files below a workspace-relative directory."""
        base = self.resolve(path)
        if not base.is_dir():
            raise ValueError(f"Not a directory: {path}")
        ignored = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
        return sorted(
            str(item.relative_to(self.root))
            for item in base.rglob("*")
            if item.is_file() and not any(part in ignored for part in item.parts)
        )[:2000]

    def read_file(self, path: str) -> str:
        """Read a UTF-8 text file from the workspace."""
        target = self.resolve(path)
        if target.stat().st_size > 1_000_000:
            raise ValueError("Agent file reads are limited to 1 MB")
        return target.read_text(encoding="utf-8")

    def search_files(self, query: str) -> list[str]:
        """Return matching line locations for a literal text query."""
        if not query or len(query) > 500:
            raise ValueError("Search query must contain 1-500 characters")
        matches: list[str] = []
        for relative in self.list_files():
            try:
                lines = self.resolve(relative).read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(lines, 1):
                if query.casefold() in line.casefold():
                    matches.append(f"{relative}:{number}: {line[:240]}")
                    if len(matches) >= 200:
                        return matches
        return matches

    def write_file(self, path: str, content: str) -> str:
        """Write UTF-8 text inside the workspace."""
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content.encode('utf-8'))} bytes to {path}"

