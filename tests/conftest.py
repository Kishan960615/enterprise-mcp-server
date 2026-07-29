from collections.abc import Iterator
from pathlib import Path

import pytest

from enterprise_mcp.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    root = tmp_path / "files"
    root.mkdir()
    (root / "policy.md").write_text("Least privilege and audit evidence.", encoding="utf-8")
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        auth_mode="development",
        file_roots={"demo": root},
        development_tenant="tenant-a",
        development_subject="user-a",
    )


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    from enterprise_mcp.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
