"""Issue #58: the visual editor's keyword search scans the repo with its own
parser. It must follow the same header rules as the Explorer (BOM, translated
headers), or resource keywords silently vanish from the step dropdown."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ai import rf_knowledge


@pytest.fixture
def scan(tmp_path: Path):
    @contextmanager
    def fake_session():
        s = MagicMock()
        s.execute.return_value.scalar_one_or_none.return_value = MagicMock(local_path=str(tmp_path))
        yield s

    rf_knowledge._imported_repos.discard(9999)
    rf_knowledge._repo_keywords_cache.pop(9999, None)
    with patch("src.database.get_sync_session", fake_session):
        yield lambda: {k["name"] for k in rf_knowledge._scan_repo_files(9999)[0]}
    rf_knowledge._imported_repos.discard(9999)
    rf_knowledge._repo_keywords_cache.pop(9999, None)


def test_bom_before_keywords_header(tmp_path: Path, scan):
    (tmp_path / "公共.resource").write_text("﻿*** Keywords ***\n当前的日期增减天数\n    No Operation\n", encoding="utf-8")
    assert "当前的日期增减天数" in scan()


def test_translated_headers(tmp_path: Path, scan):
    (tmp_path / "common.resource").write_text(
        "Language: Chinese Simplified\n\n*** 关键字 ***\n关闭浏览器\n    No Operation\n", encoding="utf-8"
    )
    assert "关闭浏览器" in scan()
