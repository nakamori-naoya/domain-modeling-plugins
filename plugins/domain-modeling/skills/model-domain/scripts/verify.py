#!/usr/bin/env python3
"""候補のドメインモデル本文が、図の構造契約を満たすかを検査する。

目印: write-doc の domain-model 型の template が「検査が読む目印」に書いた形（クラス図と状態遷移図の Mermaid 記法、
  拒む理由の節の見出し、BDD番号）と、domain-rule資料（source.py の build_index が索引を導く）。
  見出しの文言は読まない。節は、その中にある図と、見出しの先頭のコマンド名で見つける。
入力: 標準入力の資料本文（Markdown）と --source。
正規化: コードフェンスの外の行だけを見出しと本文として読む。```mermaid の中は、先頭の行（classDiagram / stateDiagram-v2）で図の種類を決め、
  空行と %% の注釈行を除く。見出しの `*` `_` と backtick は外して比べる。H3 見出しは、最初の半角 `:` より前を名前として読む。
合格述語:
  - classDiagram が1つ以上ある
  - クラスのラベルが索引の語である。種別がちょうど一つで、契約の種別（値オブジェクトなどに「・文脈共有」を添えてよい）である。
    同じラベルの種別が図ごとに食い違わない。関係の線が宣言済みのクラスだけを結ぶ
  - コマンド（+名前(引数)）は集約ルートとエンティティにだけあり、名前がdomain-rule資料でコマンドとした行い、引数が同じ図のクラスのラベルである。
    集約ルートとエンティティはコマンド以外の行を持たない。値オブジェクトは括弧を含まない行（取り得る値か、判断に使う業務の語）だけを持つ。
    ドメインイベントは何も持たない
  - stateDiagram-v2 は、矢印のラベルがすべて一つの集約ルートのコマンドであり、その図を含む H2 節がその集約の節になる。
    一つの集約の状態遷移図は一つの H2 節にだけあり、一つの H2 節は一つの集約の状態遷移図だけを持つ。状態は索引の状態で、終端への矢印だけラベルを省ける
  - domain-rule資料で状態を持つ集約ルートには、その集約の状態遷移図がある
  - 状態遷移図で矢印の出ていない状態があるコマンド（生成のコマンドを除く）は、その集約の節の中に、名前がそのコマンドの H3 を持つ（拒む理由の置き場）
  - 本文が引くBDD番号（「BDD-001〜006」の範囲を含む）がdomain-rule資料にある
失敗時の診断: 標準エラーへ「[error] <どの要素が、どの述語に反したか>」を1行ずつ。終了code 2。
正例: tests/fixtures/library-lending（集約一つ、状態あり、提案あり）と tests/fixtures/member-directory（業務の決まりが薄く、クラス図と未決だけ）。
反例と境界例: tests/test-domain-modeling.sh が正例を1か所ずつ変えて作る（索引外の語、契約外の種別、値オブジェクトの操作、集約ルートのフィールド、
  クエリをコマンドにする、図に無い引数、状態遷移図の欠落と索引外の状態、業務イベントを矢印に使う、二つの集約のコマンドを混ぜた状態遷移図、未知のBDD番号、
  受け付けない状態があるのに拒む理由の節の無いコマンド。境界例: 空の標準入力、結論を入れた見出し、見出しの `:` の後に結論を書いた拒む理由の節、
  コマンドの節の無い生成のコマンド、提案の節の無い資料、取り得る値の行、BDDの範囲表記）。
意味評価として残す範囲: 境界の引き方と集約の数、拒む理由の節が受け付けない状態のすべてを一文ずつ書いているか、文章が図の言い直しになっていないか、
  値オブジェクトの行が業務の語か、未決と業務知識への提案が要るものを漏らしていないか、warnings の本文が引いていないBDDが本当に集約の外で成立するか。

  verify.py --source <domain-rule資料の絶対path>  < <保存したドメインモデル資料>

exit 0 = 通った（stdoutに verified, source_path, warnings） / 2 = 標準入力が空、domain-rule資料が契約の節を持たない、または述語が成り立たない。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source import HEADING, build_index, strip_markup  # noqa: E402

BDD_REF = re.compile(r"BDD-(\d{3,})(?:〜(?:BDD-)?(\d{3,}))?")
CLASS_DECL = re.compile(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\["([^"]+)"\])?\s*(\{)?\s*$')
RELATION = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:"[^"]*"\s*)?(<\|--|\*--|o--|-->|<--|\.\.>|<\.\.|--\*|--o|--\|>|\.\.\|>|--|\.\.)\s*(?:"[^"]*"\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*(?::.*)?$')
STEREOTYPE = re.compile(r"^<<(.+)>>$")
COMMAND = re.compile(r"^\+\s*([^()]+?)\s*\((.*)\)\s*$")
TRANSITION = re.compile(r"^(\[\*\]|[^\s:]+)\s*-->\s*(\[\*\]|[^\s:]+)\s*(?::\s*(.*))?$")
ELEMENT_KINDS = ["集約ルート", "エンティティ", "値オブジェクト", "ドメインイベント"]
# コマンドを書けるのはこの種別だけ。
COMMAND_HOLDERS = {"集約ルート", "エンティティ"}
# 複数の文脈で使う値に種別へ添える印。
SHARED_MARK = "文脈共有"


def cited_bdd(line: str) -> list[str]:
    """行が引くBDD番号を返す。「BDD-001〜006」「BDD-001〜BDD-006」は範囲として展開する。"""
    refs: list[str] = []
    for start, end in BDD_REF.findall(line):
        width = len(start)
        last = int(end) if end else int(start)
        for number in range(int(start), max(int(start), last) + 1):
            refs.append(f"BDD-{number:0{width}d}")
    return refs


class Invalid(Exception):
    pass


def read_stdin() -> str:
    if sys.stdin.isatty():
        raise Invalid("候補本文を標準入力で渡す")
    body = sys.stdin.read()
    if not body.strip():
        raise Invalid("標準入力が空。候補本文を標準入力で渡す")
    return body


def heading_name(title: str) -> str:
    """見出しの名前。最初の半角 `:` より前を名前とし、後ろは結論として読まない。"""
    return title.split(":", 1)[0].strip()


def parse(body: str) -> tuple[list[dict], list[dict], list[str]]:
    """H2節の並び、Mermaid図、コードブロック外の行を返す。各図は、どのH2節（並びの番号）の中にあるかを持つ。"""
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
                    diagrams.append({"kind": kind, "lines": content[1:], "h2": len(h2s) - 1 if h2s else None})
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
            continue
        level, title = len(match.group(1)), strip_markup(match.group(2))
        if level == 2:
            h2s.append({"title": title, "h3": []})
        elif level == 3 and h2s:
            h2s[-1]["h3"].append(heading_name(title))
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


def check(body: str, index: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    h2s, diagrams, prose = parse(body)
    vocabulary = set(index["vocabulary"])
    commands_in_source = set(index["commands"])
    kinds = ELEMENT_KINDS
    holders = COMMAND_HOLDERS
    shared = SHARED_MARK

    # ── クラス図 ──
    class_diagrams = [d for d in diagrams if d["kind"] == "classDiagram"]
    if not class_diagrams:
        errors.append("Mermaid classDiagram が無い")
    kind_of: dict[str, str] = {}
    commands_of: dict[str, list[str]] = {}
    for diagram in class_diagrams:
        classes, relations = parse_class_diagram(diagram["lines"], errors)
        labels_in_diagram = {cls["label"] for cls in classes.values()}
        for source_id, target_id in relations:
            for end in (source_id, target_id):
                if end not in classes:
                    errors.append(f"クラス図の関係の線が宣言の無いクラスを結んでいる: {end}")
        for class_id, cls in classes.items():
            label = cls["label"]
            if label not in vocabulary:
                errors.append(f"クラス「{label}」はdomain-rule資料の索引に無い語である。要素にせず業務知識への提案へ移す")
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
                        errors.append(f"クラス「{label}」のコマンド「{name}」は、domain-rule資料の業務の行いのコマンドに無い")
                    if name not in own_commands:
                        own_commands.append(name)
                    for argument in (arg.strip() for arg in command.group(2).split(",")):
                        if argument and argument not in labels_in_diagram:
                            errors.append(f"クラス「{label}」のコマンド「{name}」の引数「{argument}」が、同じ図のクラスのラベルに無い。受け取る値をクラスとして描く")
                elif kind == "値オブジェクト":
                    if "(" in line or ")" in line:
                        errors.append(f"値オブジェクト「{label}」に操作がある: {line}。コマンドは集約ルートかエンティティにだけ描く")
                else:
                    errors.append(f"ドメインイベント「{label}」に中身の行がある: {line}")

    # ── 状態遷移図と、それを含む集約の節 ──
    roots = [label for label, kind in kind_of.items() if kind == "集約ルート"]
    owner_of_command = {name: label for label in roots for name in commands_of.get(label, [])}
    section_of: dict[str, int] = {}
    root_of_section: dict[int, str] = {}
    outgoing_of: dict[str, dict[str, set[str]]] = {}
    states_of: dict[str, set[str]] = {}
    for diagram in (d for d in diagrams if d["kind"] == "stateDiagram-v2"):
        transitions: list[tuple[str, str, str | None, str]] = []
        for line in diagram["lines"]:
            transition = TRANSITION.match(line)
            if not transition:
                errors.append(f"状態遷移図の行を読めない（「状態 --> 状態: コマンド」の形だけを書く）: {line}")
                continue
            source_state, target_state, command = transition.groups()
            transitions.append((source_state, target_state, command.strip() if command else None, line))
        owners = {owner_of_command.get(command) for _, _, command, _ in transitions if command}
        if not owners:
            errors.append("状態遷移図の矢印にコマンドのラベルが一つも無く、どの集約の図かが決まらない")
            continue
        if None in owners or len(owners) != 1:
            labels = sorted(command for _, _, command, _ in transitions if command and command not in owner_of_command)
            if labels:
                errors.append(f"状態遷移図の矢印のラベル {'・'.join(labels)} が、クラス図で集約ルートに描いたコマンドではない")
            else:
                errors.append(f"一つの状態遷移図に二つ以上の集約のコマンドがある: {'・'.join(sorted(o for o in owners if o))}")
            continue
        label = owners.pop()
        section = diagram["h2"]
        if section is None:
            errors.append(f"「{label}」の状態遷移図が H2 節の外にある")
            continue
        if section_of.setdefault(label, section) != section:
            errors.append(f"「{label}」の状態遷移図が二つ以上の H2 節に分かれている")
            continue
        if root_of_section.setdefault(section, label) != label:
            errors.append(f"H2 節「{h2s[section]['title']}」に、{root_of_section[section]}と{label}の二つの集約の状態遷移図がある")
            continue
        outgoing = outgoing_of.setdefault(label, {})
        diagram_states = states_of.setdefault(label, set())
        for source_state, target_state, command, line in transitions:
            for state in (source_state, target_state):
                if state != "[*]" and state not in index["states"]:
                    errors.append(f"「{label}」の状態遷移図の状態「{state}」はdomain-rule資料の状態に無い")
            if command is None:
                if target_state != "[*]":
                    errors.append(f"「{label}」の状態遷移図の矢印「{line}」にコマンドのラベルが無い（終端への矢印だけ省ける）")
                continue
            diagram_states.update(state for state in (source_state, target_state) if state != "[*]")
            outgoing.setdefault(command, set()).add(source_state)

    for label in roots:
        if label in index["state_holders"] and label not in section_of:
            errors.append(f"domain-rule資料で状態を持つ「{label}」の状態遷移図が無い")
            continue
        if label not in section_of:
            continue
        section = h2s[section_of[label]]
        for name in commands_of.get(label, []):
            sources = outgoing_of[label].get(name, set())
            if sources and sources <= {"[*]"}:
                continue
            refused = sorted(states_of[label] - sources)
            if refused and name not in section["h3"]:
                errors.append(f"「{label}」のコマンド「{name}」は状態 {'・'.join(refused)} から矢印が無いのに、拒む理由を書く「### {name}」節が、「{label}」の状態遷移図を含む H2 節「{section['title']}」の中に無い")

    # ── BDD番号 ──
    cited = []
    for line in prose:
        for ref in cited_bdd(line):
            if ref not in cited:
                cited.append(ref)
    unknown = [ref for ref in cited if ref not in index["bdd"]]
    if unknown:
        errors.append("本文が引くBDD番号がdomain-rule資料に無い: " + ", ".join(unknown))
    uncited = [ref for ref in index["bdd"] if ref not in cited]
    if uncited and section_of:
        warnings.append("本文が引いていないdomain-rule資料のBDD（集約の外で成立するものか、要素の不足かを読み返す）: " + ", ".join(uncited))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        body = read_stdin()
        index = build_index(args.source)
    except (Invalid, OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    errors, warnings = check(body, index)
    if errors:
        for message in errors:
            print(f"[error] {message}", file=sys.stderr)
        return 2
    print(json.dumps({"verified": True, "source_path": index["source_path"], "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
