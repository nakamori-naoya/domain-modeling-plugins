#!/usr/bin/env python3
"""ドメインモデル資料の決定可能な構造だけを検査する。

基準資料: write-doc の domain-model 型 template の表の目印と、business-knowledge 型資料の `### [BDD-<番号>]` 見出し（source.py）。
入力: 標準入力の Markdown 本文と --source で指定する業務知識資料。
合格述語: 要素・関係の表が契約の列で一つずつあり、要素の識別子と名前が空でなく識別子が一意で所定の形を満たし、種別と関係の種類が許容値で、関係の両端が宣言済みで、本文中の BDD 参照が業務知識資料に存在し、Mermaid ブロックが無い。
失敗時の診断: 標準エラーへ違反を1行ずつ出し、終了コード2。
正例: tests/fixtures/library-lending/domain-model.md、設計候補の仮名や業務知識に未記載のクラスを含む資料。
反例: 表の欠落・不正な列/識別子/種別/関係の種類・未宣言要素への関係・未知の BDD 参照・Mermaid ブロック。
意味評価として残す範囲: 図と表の一致、仮説が明示されているか、境界や責務、型の選択、業務上の妥当性と十分性。

これは構造検査であり、ドメインモデルの設計品質を判定しない。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source import bdd_ids, regular_file  # noqa: E402

BDD_REF = re.compile(r"BDD-(\d{3,})(?:〜(?:BDD-)?(\d{3,}))?")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STEREOTYPES = {"", "集約ルート", "エンティティ", "値オブジェクト", "ドメインイベント", "ドメインサービス", "値オブジェクト・文脈共有"}
RELATION_KINDS = {"参照", "依存", "構成", "集約", "継承", "実現", "関連"}


def references(line: str) -> list[str]:
    refs: list[str] = []
    for start, end in BDD_REF.findall(line):
        width = len(start)
        last = int(end) if end else int(start)
        refs.extend(f"BDD-{number:0{width}d}" for number in range(int(start), max(int(start), last) + 1))
    return refs


def prose_lines(body: str) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    errors: list[str] = []
    fence: str | None = None
    for line in body.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            continue
        if match:
            fence = match[1]
            if match[2].strip() == "mermaid":
                errors.append("Mermaid のブロックは置けない")
        else:
            lines.append(line)
    return lines, errors


def table(lines: list[str], marker: str, headers: list[str], errors: list[str]) -> list[list[str]]:
    positions = [i for i, line in enumerate(lines) if line.strip() == f"<!-- domain-model:{marker} -->"]
    if len(positions) != 1:
        errors.append(f"表の目印は一つ必要: domain-model:{marker}")
        return []
    index = positions[0] + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].strip().startswith("|"):
        line = lines[index].strip()
        if not line.endswith("|"):
            errors.append(f"表の行の末尾に縦棒が無い: {line}")
        rows.append([cell.strip() for cell in line[1:-1].split("|")])
        index += 1
    if len(rows) < 2 or rows[0] != headers or len(rows[1]) != len(headers) or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        errors.append(f"表の見出しまたは区切り行が不正: domain-model:{marker}")
        return []
    valid: list[list[str]] = []
    for row in rows[2:]:
        if len(row) != len(headers):
            errors.append(f"表の列数が不正: domain-model:{marker}: {row}")
        else:
            valid.append(row)
    return valid


def check(body: str, source_path: str) -> tuple[list[str], list[str]]:
    prose, errors = prose_lines(body)
    elements = table(prose, "elements", ["識別子", "名前", "種別"], errors)
    relations = table(prose, "relations", ["関係元", "関係先", "種類", "関係"], errors)
    declared: set[str] = set()
    if not elements:
        errors.append("要素の表に要素宣言が無い")
    for identifier, label, stereotype in elements:
        if not IDENTIFIER.fullmatch(identifier):
            errors.append(f"要素の識別子が不正: {identifier}")
        if identifier in declared:
            errors.append(f"要素を重複宣言している: {identifier}")
        declared.add(identifier)
        if not label:
            errors.append(f"要素の名前が空: {identifier}")
        if stereotype not in STEREOTYPES:
            errors.append(f"種別が契約に無い: {stereotype}")
    for left, right, kind, _label in relations:
        if kind not in RELATION_KINDS:
            errors.append(f"関係の種類が契約に無い: {kind}")
        for identifier in (left, right):
            if identifier not in declared:
                errors.append(f"関係が未宣言要素を参照している: {identifier}")
    known_bdd = bdd_ids(regular_file(source_path, "業務知識の資料"))
    for line in prose:
        for reference in references(line):
            if reference not in known_bdd:
                errors.append(f"業務知識の資料に無いBDD参照: {reference}")
    return errors, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    if sys.stdin.isatty():
        print("[error] 候補本文を標準入力で渡す", file=sys.stderr)
        return 2
    body = sys.stdin.read()
    if not body.strip():
        print("[error] 標準入力が空。候補本文を標準入力で渡す", file=sys.stderr)
        return 2
    try:
        source = regular_file(args.source, "業務知識の資料")
        errors, warnings = check(body, str(source))
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        return 2
    print(json.dumps({"verified": True, "source_path": str(source), "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
