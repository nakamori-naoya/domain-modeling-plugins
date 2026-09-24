#!/usr/bin/env python3
"""候補のドメインモデル本文が、図の構造契約を満たすかを検査する。

検査するのは述語であって、モデルの良し悪しではない。通ったときに言えるのは次だけである。

  - 「クラス図」の節に Mermaid classDiagram があり、「未決」の節が空でない
  - クラス図の各クラスのラベルが、正式な定義から機械抽出した索引の語である
  - 各クラスが契約の種別を一つだけ持つ（値オブジェクトなどに「・文脈共有」を添えてよい）。同じラベルの種別が図ごとに食い違わない
  - コマンド（+名前(引数)）は集約ルートかエンティティにだけあり、その名前が正式な定義でコマンドとした行いである
  - 集約ルートとエンティティはコマンド以外の行を持たない。値オブジェクトは取り得る値の行を持ってよいが、コマンドを持たない。ドメインイベントは何も持たない
  - 関係の線が宣言済みのクラスだけを結ぶ
  - 集約ルートごとに同じ語の H2 節があり、その集約のコマンドごとに同じ語の H3 節がその中にある
  - 正式な定義で状態を持つとされた集約ルートの節に stateDiagram-v2 があり、状態が索引の状態で、矢印のラベルがその集約のコマンドである
  - 本文が引くBDD番号が正式な定義にある
  - 「業務知識への提案」の節があれば、提案した語が図のラベルに無い

  verify.py --playbook <同じdirectoryのplaybook.yml> --source <domain-ruleの正式な定義の絶対path>  < <候補本文（Markdown）>

exit 0 = 通った（stdoutに verified, source_path, warnings） / 2 = 標準入力が空、正式な定義が契約の節を持たない、または述語が成り立たない（診断は標準エラー）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source import HEADING, build_index, load_yaml, strip_markup, table_rows  # noqa: E402

BDD_REF = re.compile(r"BDD-\d{3,}")
CLASS_DECL = re.compile(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\["([^"]+)"\])?\s*(\{)?\s*$')
RELATION = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:"[^"]*"\s*)?(<\|--|\*--|o--|-->|<--|\.\.>|<\.\.|--\*|--o|--\|>|\.\.\|>|--|\.\.)\s*(?:"[^"]*"\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*(?::.*)?$')
STEREOTYPE = re.compile(r"^<<(.+)>>$")
COMMAND = re.compile(r"^\+\s*([^()]+?)\s*\((.*)\)\s*$")
TRANSITION = re.compile(r"^(\[\*\]|[^\s:]+)\s*-->\s*(\[\*\]|[^\s:]+)\s*(?::\s*(.*))?$")


class Invalid(Exception):
    pass


def read_stdin() -> str:
    if sys.stdin.isatty():
        raise Invalid("候補本文を標準入力で渡す")
    body = sys.stdin.read()
    if not body.strip():
        raise Invalid("標準入力が空。候補本文を標準入力で渡す")
    return body


def parse(body: str) -> tuple[list[dict], list[dict], list[str]]:
    """H2節の並び、Mermaid図、コードブロック外の行を返す。各図とH3はどのH2の中にあるかを持つ。"""
    h2s: list[dict] = []
    diagrams: list[dict] = []
    prose: list[str] = []
    fence: list[str] | None = None
    fence_lang = ""
    for line in body.splitlines():
        if fence is not None:
            if line.startswith("```"):
                if fence_lang == "mermaid":
                    content = [l.strip() for l in fence if l.strip() and not l.strip().startswith("%%")]
                    kind = content[0] if content else ""
                    diagrams.append({"kind": kind, "lines": content[1:], "h2": h2s[-1]["title"] if h2s else None})
                fence = None
            else:
                fence.append(line)
            continue
        if line.startswith("```"):
            fence, fence_lang = [], line[3:].strip()
            continue
        prose.append(line)
        match = HEADING.match(line)
        if not match:
            if h2s:
                h2s[-1]["lines"].append(line)
            continue
        level, title = len(match.group(1)), strip_markup(match.group(2))
        if level == 2:
            h2s.append({"title": title, "h3": [], "lines": []})
        elif level == 3 and h2s:
            h2s[-1]["h3"].append(title)
    return h2s, diagrams, prose


def parse_class_diagram(lines: list[str], errors: list[str]) -> tuple[dict, list[tuple[str, str]]]:
    """classDiagram から {id: {label, body}} と関係の組を取り出す。"""
    classes: dict[str, dict] = {}
    relations: list[tuple[str, str]] = []
    current: str | None = None
    for line in lines:
        if current is not None:
            if line == "}":
                current = None
            else:
                classes[current]["body"].append(line)
            continue
        declared = CLASS_DECL.match(line)
        if declared:
            class_id, label, opens = declared.groups()
            if class_id in classes:
                errors.append(f"クラス図で同じidのクラスを2度宣言している: {class_id}")
            classes[class_id] = {"label": label or class_id, "body": []}
            current = class_id if opens else None
            continue
        related = RELATION.match(line)
        if related:
            relations.append((related.group(1), related.group(3)))
            continue
        errors.append(f"クラス図の行を読めない（class 宣言、関係の線、クラスの中身のどれでもない）: {line}")
    if current is not None:
        errors.append(f"クラス図のクラスが閉じていない: {current}")
    return classes, relations


def check(body: str, index: dict, contract: dict) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    h2s, diagrams, prose = parse(body)
    titles = [h2["title"] for h2 in h2s]
    vocabulary = set(index["vocabulary"])
    commands_in_source = set(index["commands"])
    kinds = contract["element_kinds"]
    holders = set(contract["command_holders"])
    shared = contract["shared_mark"]

    class_section = contract["class_diagram_section"]
    if not any(d["kind"] == "classDiagram" and d["h2"] == class_section for d in diagrams):
        errors.append(f"「## {class_section}」の節に Mermaid classDiagram が無い")
    open_section = contract["open_questions_section"]
    open_h2 = next((h2 for h2 in h2s if h2["title"] == open_section), None)
    if open_h2 is None or not any(line.strip() for line in open_h2["lines"]):
        errors.append(f"「## {open_section}」の節が無いか空である（0件なら「なし」と書く）")

    # ── クラス図 ──
    kind_of: dict[str, str] = {}
    commands_of: dict[str, list[str]] = {}
    for diagram in (d for d in diagrams if d["kind"] == "classDiagram"):
        classes, relations = parse_class_diagram(diagram["lines"], errors)
        for source_id, target_id in relations:
            for end in (source_id, target_id):
                if end not in classes:
                    errors.append(f"クラス図の関係の線が宣言の無いクラスを結んでいる: {end}")
        for class_id, cls in classes.items():
            label = cls["label"]
            if label not in vocabulary:
                errors.append(f"クラス「{label}」は正式な定義の索引に無い語である。要素にせず「{contract['proposal_section']}」へ移す")
            stereotypes = [m.group(1) for m in (STEREOTYPE.match(l) for l in cls["body"]) if m]
            if len(stereotypes) != 1:
                errors.append(f"クラス「{label}」は種別（<<…>>）をちょうど1つ持たない")
                continue
            kind, _, mark = stereotypes[0].partition("・")
            if kind not in kinds or (mark and mark != shared):
                errors.append(f"クラス「{label}」の種別「{stereotypes[0]}」は契約に無い（{'／'.join(kinds)}、印は「・{shared}」だけ）")
                continue
            if label in kind_of and kind_of[label] != kind:
                errors.append(f"クラス「{label}」の種別が図によって違う: {kind_of[label]} と {kind}")
            kind_of[label] = kind
            own_commands = commands_of.setdefault(label, [])
            for line in cls["body"]:
                if STEREOTYPE.match(line):
                    continue
                command = COMMAND.match(line)
                if kind in holders:
                    if not command:
                        errors.append(f"クラス「{label}」（{kind}）にコマンド以外の行がある: {line}。フィールドや判定だけの操作は描かない")
                        continue
                    name = command.group(1).strip()
                    if name not in commands_in_source:
                        errors.append(f"クラス「{label}」のコマンド「{name}」は、正式な定義の「コマンドとクエリ」でコマンドとした行いに無い")
                    if name not in own_commands:
                        own_commands.append(name)
                elif kind == "値オブジェクト":
                    if "(" in line or ")" in line:
                        errors.append(f"値オブジェクト「{label}」に操作がある: {line}。コマンドは集約ルートかエンティティにだけ描く")
                else:
                    errors.append(f"ドメインイベント「{label}」に中身の行がある: {line}")

    # ── 集約ごとの節、コマンドの節、状態遷移図 ──
    h2_by_title = {h2["title"]: h2 for h2 in h2s}
    aggregate_sections = set()
    for label, kind in kind_of.items():
        if kind != "集約ルート":
            continue
        aggregate_sections.add(label)
        h2 = h2_by_title.get(label)
        if h2 is None:
            errors.append(f"集約ルート「{label}」の「## {label}」節が無い")
            continue
        for name in commands_of.get(label, []):
            if name not in h2["h3"]:
                errors.append(f"集約「{label}」のコマンド「{name}」の「### {name}」節が「## {label}」の中に無い")
        state_diagrams = [d for d in diagrams if d["kind"] == "stateDiagram-v2" and d["h2"] == label]
        if label in index["state_holders"] and not state_diagrams:
            errors.append(f"正式な定義で状態を持つ「{label}」の節に stateDiagram-v2 が無い")
        for diagram in state_diagrams:
            for line in diagram["lines"]:
                transition = TRANSITION.match(line)
                if not transition:
                    errors.append(f"「{label}」の状態遷移図の行を読めない（「状態 --> 状態: コマンド」の形だけを書く）: {line}")
                    continue
                source_state, target_state, command = transition.groups()
                for state in (source_state, target_state):
                    if state != "[*]" and state not in index["states"]:
                        errors.append(f"「{label}」の状態遷移図の状態「{state}」は正式な定義の状態に無い")
                if target_state == "[*]" and not command:
                    continue
                if not command or command.strip() not in commands_of.get(label, []):
                    errors.append(f"「{label}」の状態遷移図の矢印「{line}」のラベルが、クラス図でこの集約に描いたコマンドではない")
    entity_commands = [(label, name) for label, kind in kind_of.items() if kind == "エンティティ" for name in commands_of.get(label, [])]
    for label, name in entity_commands:
        if not any(name in h2_by_title[t]["h3"] for t in aggregate_sections if t in h2_by_title):
            errors.append(f"エンティティ「{label}」のコマンド「{name}」の「### {name}」節が、どの集約の節にも無い")
    stray = [d for d in diagrams if d["kind"] == "stateDiagram-v2" and d["h2"] not in aggregate_sections]
    for diagram in stray:
        errors.append(f"状態遷移図が集約ルートの節の外（「## {diagram['h2']}」）にある")

    # ── BDD番号 ──
    cited = []
    for line in prose:
        for ref in BDD_REF.findall(line):
            if ref not in cited:
                cited.append(ref)
    unknown = [ref for ref in cited if ref not in index["bdd"]]
    if unknown:
        errors.append("本文が引くBDD番号が正式な定義に無い: " + ", ".join(unknown))
    uncited = [ref for ref in index["bdd"] if ref not in cited]
    if uncited:
        warnings.append("本文が引いていない正式な定義のBDD（集約の外で成立するものか、要素の不足かを読み返す）: " + ", ".join(uncited))

    # ── 業務知識への提案 ──
    proposal = h2_by_title.get(contract["proposal_section"])
    if proposal is not None:
        proposed = [row[0] for row in table_rows(proposal["lines"])]
        if not proposed:
            errors.append(f"「## {contract['proposal_section']}」に表が無い。提案が無ければ見出しごと置かない")
        for word in proposed:
            if word in kind_of:
                errors.append(f"業務知識への提案の語「{word}」が図のクラスにある。提案した語は図に使わない")
            if word in vocabulary:
                warnings.append(f"業務知識への提案「{word}」は正式な定義の索引に既にある")

    if titles.count(class_section) != 1:
        errors.append(f"「## {class_section}」の節がちょうど1つではない")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        body = read_stdin()
        contract = load_yaml(Path(args.playbook))["contract"]
        index = build_index(Path(args.playbook), args.source)
    except (Invalid, KeyError, OSError, UnicodeDecodeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    errors, warnings = check(body, index, contract)
    if errors:
        for message in errors:
            print(f"[error] {message}", file=sys.stderr)
        return 2
    print(json.dumps({"verified": True, "source_path": index["source_path"], "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
