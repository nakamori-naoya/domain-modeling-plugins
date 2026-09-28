#!/usr/bin/env python3
"""業務知識資料から、参照先として存在する BDD 見出しを読む。"""

from __future__ import annotations

from pathlib import Path
import re

HEADING = re.compile(r"^(#{1,6})[ ]+(.+?)[ ]*$")
BDD_ID = re.compile(r"\[(BDD-\d{3,})\]")


def regular_file(raw: str, label: str) -> Path:
    """絶対 path で指定された通常ファイルを返す。"""
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"{label}が絶対pathではない: {raw}")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label}が通常ファイルではない: {raw}")
    return path.resolve()


def bdd_ids(source: Path) -> set[str]:
    """コードフェンス外の H3 `### [BDD-<番号>]` 見出しの識別子を返す。"""
    ids: set[str] = set()
    in_fence = False
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match and len(match.group(1)) == 3:
            ids.update(BDD_ID.findall(match.group(2)))
    return ids
