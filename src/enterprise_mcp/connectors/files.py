"""Root-confined file-system connector."""

import os
from pathlib import Path

from enterprise_mcp.domain import Provenance, ResultLimitError, ToolResult, ValidationError


class FileConnector:
    def __init__(self, roots: dict[str, Path], max_result_bytes: int) -> None:
        self._roots = {name: path.resolve() for name, path in roots.items()}
        self._max_result_bytes = max_result_bytes

    def _resolve(self, root_name: str, relative_path: str) -> Path:
        try:
            root = self._roots[root_name]
        except KeyError as exc:
            raise ValidationError("unknown file root") from exc
        candidate = (root / relative_path).resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path escapes configured root") from exc
        if candidate.is_symlink() or not candidate.is_file():
            raise ValidationError("path is not a readable regular file")
        return candidate

    async def read(
        self, root: str, path: str, start_line: int = 1, end_line: int = 200
    ) -> ToolResult:
        candidate = self._resolve(root, path)
        if candidate.stat().st_size > self._max_result_bytes:
            raise ResultLimitError("file exceeds configured size limit")
        if end_line < start_line or end_line - start_line > 500:
            raise ValidationError("invalid line range")
        text = candidate.read_text(encoding="utf-8")
        lines = text.splitlines()
        content = "\n".join(lines[max(0, start_line - 1) : end_line])
        if len(content.encode()) > self._max_result_bytes:
            raise ResultLimitError("result exceeds configured size limit")
        stat = os.stat(candidate)
        return ToolResult(
            data={
                "content": content,
                "path": path,
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
            },
            provenance=[
                Provenance(
                    uri=f"enterprise://files/{root}/{path}",
                    title=candidate.name,
                    revision=f"mtime:{stat.st_mtime_ns}",
                )
            ],
        )

    async def search(self, root: str, query: str, limit: int = 20) -> ToolResult:
        try:
            base = self._roots[root]
        except KeyError as exc:
            raise ValidationError("unknown file root") from exc
        query_lower = query.lower()
        matches: list[dict[str, str]] = []
        for candidate in base.rglob("*"):
            if len(matches) >= min(limit, 100):
                break
            if candidate.is_file() and not candidate.is_symlink():
                relative = candidate.relative_to(base)
                if query_lower in str(relative).lower():
                    matches.append({"path": str(relative), "name": candidate.name})
        return ToolResult(data={"matches": matches})
