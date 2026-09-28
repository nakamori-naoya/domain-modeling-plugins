#!/usr/bin/env python3
"""ドメインモデル資料の決定可能な構造だけを検査する。

基準資料: business-knowledge 型資料の `### [BDD-<番号>]` 見出し（source.py）。
入力: 標準入力の Markdown 本文と --source で指定する業務知識資料。
合格述語: classDiagram があり、Mermaid の対象行を読め、書いた種別が template の許す一つの印で、関係の両端が図内で宣言済みで、本文中の BDD 参照が業務知識資料に存在する。
失敗時の診断: 標準エラーへ違反を1行ずつ出し、終了コード2。
正例: tests/fixtures/library-lending/domain-model.md、設計候補の仮名や業務知識に未記載のクラスを含む資料。
反例: classDiagram 欠落・不正な宣言/関係/種別・未宣言要素への関係・未知の BDD 参照。
意味評価として残す範囲: 仮説が明示されているか、境界や責務、型の選択、業務上の妥当性と十分性。

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
CLASS_DECL = re.compile(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*\["([^"\n]+)"\])?\s*(\{)?\s*$')
MEMBER = re.compile(r"^(?:[+\-#~]?\s*)?(?:[A-Za-z_][A-Za-z0-9_]*|[ぁ-んァ-ヶ一-龠々ー][^(){}:]*)(?:\s*\([^()]*\))?(?:\s*:\s*[A-Za-z_][A-Za-z0-9_<>, .\[\]]*)?$")
STEREOTYPES = {"集約ルート", "エンティティ", "値オブジェクト", "ドメインイベント", "ドメインサービス", "値オブジェクト・文脈共有"}


def references(line: str) -> list[str]:
    refs: list[str] = []
    for start, end in BDD_REF.findall(line):
        width = len(start)
        last = int(end) if end else int(start)
        refs.extend(f"BDD-{number:0{width}d}" for number in range(int(start), max(int(start), last) + 1))
    return refs


def diagrams(body: str) -> tuple[list[list[str]], list[str]]:
    classes: list[list[str]] = []
    prose: list[str] = []
    fence: list[str] | None = None
    language = ""
    for line in body.splitlines():
        if fence is not None:
            if line.startswith("```"):
                content = [entry.strip() for entry in fence if entry.strip() and not entry.strip().startswith("%%")]
                if language == "mermaid" and content and content[0] == "classDiagram":
                    classes.append(content[1:])
                fence = None
            else:
                fence.append(line)
            continue
        if line.startswith("```"):
            fence, language = [], line[3:].strip()
        else:
            prose.append(line)
    return classes, prose


def validate_class_diagram(lines: list[str]) -> list[str]:
    errors: list[str] = []
    declared: set[str] = set()
    relations: list[tuple[str, str]] = []
    current: str | None = None
    has_stereotype = False
    for line in lines:
        if current is not None:
            if line == "}":
                current = None
                has_stereotype = False
            elif line.startswith("<<") and line.endswith(">>") and len(line) > 4:
                stereotype = line[2:-2]
                if stereotype not in STEREOTYPES:
                    errors.append(f"classDiagram の種別が契約に無い: {stereotype}")
                if has_stereotype:
                    errors.append(f"classDiagram の種別が一つの要素に二つある: {current}")
                has_stereotype = True
            elif MEMBER.fullmatch(line):
                continue
            else:
                errors.append(f"classDiagram のクラス本文を読めない: {line}")
            continue
        declaration = CLASS_DECL.fullmatch(line)
        if declaration:
            identifier, _label, opens = declaration.groups()
            if identifier in declared:
                errors.append(f"classDiagram で同じ要素を重複宣言している: {identifier}")
            declared.add(identifier)
            current = identifier if opens else None
            has_stereotype = False
            continue
        relation = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s+(?:"[^"]*"\s*)?(<\|--|\*--|o--|-->|<--|\.\.>|<\.\.|--\*|--o|--\|>|\.\.\|>|--|\.\.)\s*(?:"[^"]*"\s*)?([A-Za-z_][A-Za-z0-9_]*)(?:\s*:\s*.+)?$', line)
        if relation:
            relations.append((relation.group(1), relation.group(3)))
            continue
        if line in {"direction TB", "direction BT", "direction LR", "direction RL"}:
            continue
        errors.append(f"classDiagram の行を読めない: {line}")
    if current is not None:
        errors.append(f"classDiagram のクラス本文が閉じていない: {current}")
    if not declared:
        errors.append("classDiagram に要素宣言が無い")
    for left, right in relations:
        for identifier in (left, right):
            if identifier not in declared:
                errors.append(f"classDiagram の関係が未宣言要素を参照している: {identifier}")
    return errors


def check(body: str, source_path: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    class_diagrams, prose = diagrams(body)
    if not class_diagrams:
        errors.append("Mermaid classDiagram が無い")
    for lines in class_diagrams:
        errors.extend(validate_class_diagram(lines))
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
