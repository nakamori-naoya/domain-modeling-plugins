#!/usr/bin/env python3
"""候補のドメインモデル本文が、図の構造契約を満たすかを検査する。

基準資料: 同じdirectoryの playbook.yml の contract と、domain-ruleの正式な定義（source.py の build_index が索引を導く）。
入力: 標準入力の候補本文（Markdown）、--playbook、--source。索引fileも候補fileも受け取らない。
正規化: コードフェンスの外の行だけを見出しと本文として読む。```mermaid の中は、先頭の行（classDiagram / stateDiagram-v2）で図の種類を決め、
  空行と %% の注釈行を除く。見出しの `*` `_` と backtick は外して比べる。
合格述語:
  - 「クラス図」の節がちょうど一つあり、その中に classDiagram がある。「未決」の節があり空でない
  - クラスのラベルが索引の語である。種別がちょうど一つで、契約の種別（値オブジェクトなどに「・文脈共有」を添えてよい）である。
    同じラベルの種別が図ごとに食い違わない。関係の線が宣言済みのクラスだけを結ぶ
  - コマンド（+名前(引数)）は集約ルートとエンティティにだけあり、名前が正式な定義でコマンドとした行い、引数が同じ図のクラスのラベルである。
    集約ルートとエンティティはコマンド以外の行を持たない。値オブジェクトは括弧を含まない行（取り得る値か、判断に使う業務の語）だけを持つ。
    ドメインイベントは何も持たない
  - 正式な定義で状態を持つ集約ルートには同じ語の H2 節と、その中の stateDiagram-v2 がある。状態は索引の状態、矢印のラベルはその集約のコマンドで、
    終端への矢印だけラベルを省ける。状態遷移図は集約ルートの節の外に無い
  - 集約ルートの H2 節の中の H3 は、契約の決まった節か、クラス図に描いたコマンドである。状態遷移図で矢印の出ていない状態があるコマンド
    （生成のコマンドを除く）は、その集約の節の中に同じ語の H3 を持つ（拒む理由の置き場）
  - 本文が引くBDD番号（「BDD-001〜006」の範囲を含む）が正式な定義にある
  - 「業務知識への提案」の節があれば提案ごとの H3 があり、その語が図のラベルに無い
失敗時の診断: 標準エラーへ「[error] <どの要素が、どの述語に反したか>」を1行ずつ。終了code 2。
正例: tests/fixtures/library-lending（集約一つ、状態あり、提案あり）と tests/fixtures/member-directory（業務の決まりが薄く、クラス図と未決だけ）。
反例と境界例: tests/test-domain-modeling.sh が正例を1か所ずつ変えて作る（索引外の語、契約外の種別、値オブジェクトの操作、集約ルートのフィールド、
  クエリをコマンドにする、図に無い引数、状態遷移図の欠落と索引外の状態、業務イベントを矢印に使う、未知のBDD番号、表だけの提案、空の未決、
  集約の節の中の余計な見出し、受け付けない状態があるのに拒む理由の節の無いコマンド。境界例: 空の標準入力、コマンドの節の無いコマンド、提案の節の無い資料、取り得る値の行、BDDの範囲表記）。
意味評価として残す範囲: 境界の引き方と集約の数、拒む理由の節が受け付けない状態のすべてを一文ずつ書いているか、文章が図の言い直しになっていないか、
  値オブジェクトの行が業務の語か、warnings の本文が引いていないBDDが本当に集約の外で成立するか。

  verify.py --playbook <同じdirectoryのplaybook.yml> --source <domain-ruleの正式な定義の絶対path>  < <候補本文（Markdown）>

exit 0 = 通った（stdoutに verified, source_path, warnings） / 2 = 標準入力が空、正式な定義が契約の節を持たない、または述語が成り立たない。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source import HEADING, build_index, load_yaml, strip_markup  # noqa: E402

BDD_REF = re.compile(r"BDD-(\d{3,})(?:〜(?:BDD-)?(\d{3,}))?")
CLASS_DECL = re.compile(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\["([^"]+)"\])?\s*(\{)?\s*$')
RELATION = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:"[^"]*"\s*)?(<\|--|\*--|o--|-->|<--|\.\.>|<\.\.|--\*|--o|--\|>|\.\.\|>|--|\.\.)\s*(?:"[^"]*"\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*(?::.*)?$')
STEREOTYPE = re.compile(r"^<<(.+)>>$")
COMMAND = re.compile(r"^\+\s*([^()]+?)\s*\((.*)\)\s*$")
TRANSITION = re.compile(r"^(\[\*\]|[^\s:]+)\s*-->\s*(\[\*\]|[^\s:]+)\s*(?::\s*(.*))?$")


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
        labels_in_diagram = {cls["label"] for cls in classes.values()}
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
                        errors.append(f"クラス「{label}」のコマンド「{name}」は、正式な定義の業務の行いのコマンドに無い")
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

    # ── 集約ごとの節と状態遷移図 ──
    h2_by_title = {h2["title"]: h2 for h2 in h2s}
    roots = [label for label, kind in kind_of.items() if kind == "集約ルート"]
    fixed_subsections = set(contract["aggregate_subsections"])
    all_commands = {name for names in commands_of.values() for name in names}
    for label in roots:
        h2 = h2_by_title.get(label)
        if label in index["state_holders"] and h2 is None:
            errors.append(f"正式な定義で状態を持つ「{label}」の「## {label}」節が無い（状態遷移図を置く）")
            continue
        if h2 is None:
            continue
        for title in h2["h3"]:
            if title not in fixed_subsections and title not in all_commands:
                errors.append(f"「## {label}」の中の「### {title}」は、{'・'.join(sorted(fixed_subsections))}でも、クラス図に描いたコマンドでもない")
        state_diagrams = [d for d in diagrams if d["kind"] == "stateDiagram-v2" and d["h2"] == label]
        if label in index["state_holders"] and not state_diagrams:
            errors.append(f"正式な定義で状態を持つ「{label}」の節に stateDiagram-v2 が無い")
        outgoing: dict[str, set[str]] = {}
        diagram_states: set[str] = set()
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
                    continue
                diagram_states.update(state for state in (source_state, target_state) if state != "[*]")
                outgoing.setdefault(command.strip(), set()).add(source_state)
        for name in commands_of.get(label, []):
            sources = outgoing.get(name, set())
            if sources and sources <= {"[*]"}:
                continue
            refused = sorted(diagram_states - sources)
            if refused and name not in h2["h3"]:
                errors.append(f"「{label}」のコマンド「{name}」は状態 {'・'.join(refused)} から矢印が無いのに、拒む理由を書く「### {name}」節が「## {label}」の中に無い")
    stray = [d for d in diagrams if d["kind"] == "stateDiagram-v2" and d["h2"] not in roots]
    for diagram in stray:
        errors.append(f"状態遷移図が集約ルートの節の外（「## {diagram['h2']}」）にある")

    # ── BDD番号 ──
    cited = []
    for line in prose:
        for ref in cited_bdd(line):
            if ref not in cited:
                cited.append(ref)
    unknown = [ref for ref in cited if ref not in index["bdd"]]
    if unknown:
        errors.append("本文が引くBDD番号が正式な定義に無い: " + ", ".join(unknown))
    uncited = [ref for ref in index["bdd"] if ref not in cited]
    if uncited and any(root in h2_by_title for root in roots):
        warnings.append("本文が引いていない正式な定義のBDD（集約の外で成立するものか、要素の不足かを読み返す）: " + ", ".join(uncited))

    # ── 業務知識への提案 ──
    proposal = h2_by_title.get(contract["proposal_section"])
    if proposal is not None:
        proposed = proposal["h3"]
        if not proposed:
            errors.append(f"「## {contract['proposal_section']}」に提案ごとの ### 見出しが無い。提案が無ければ見出しごと置かない")
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
