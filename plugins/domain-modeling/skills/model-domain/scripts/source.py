#!/usr/bin/env python3
"""domain-ruleの正式な定義から、図に使ってよい語の索引を機械的に抜き出し、標準出力へJSONで返す。

基準資料: write-doc の公開契約が domain-rule について宣言した目印と、同じdirectoryの playbook.yml の contract。
  読むのは、ユビキタス言語の表（見出し行が contract.vocabulary_table の表）、title を付けた stateDiagram-v2 の Mermaid ブロック、
  `### [BDD-<番号>]` の見出しだけで、見出しの名前は読まない。意味の判断はしない。
索引はfileへ書かない。verify.py は同じ build_index を呼び、正式な定義のpathから毎回同じ索引を導く。

  source.py --playbook <同じdirectoryのplaybook.yml> --source <domain-ruleの正式な定義の絶対path>

exit 0 = 索引を標準出力へ返した / 2 = 正式な定義が目印を持たない、または読めない（診断は標準エラー）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

HEADING = re.compile(r"^(#{1,6})[ ]+(.+?)[ ]*$")
BDD_ID = re.compile(r"\[(BDD-\d{3,})\]")
TRANSITION = re.compile(r"^(\[\*\]|[^\s:]+)\s*-->\s*(\[\*\]|[^\s:]+)\s*(?::\s*(.*))?$")
REQUIRED_ROLES = ("terms", "commands", "bdd")


def fail(message: str) -> int:
    print(f"[error] {message}", file=sys.stderr)
    return 2


def load_yaml(path: Path) -> dict:
    result = subprocess.run(["yq", "-o=json", "-I=0", ".", str(path)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def regular_file(raw: str, label: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"{label}が絶対pathではない: {raw}")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label}が通常ファイルではない: {raw}")
    return path.resolve()


def strip_markup(text: str) -> str:
    return re.sub(r"[*`_]", "", text).strip()


def split_row(line: str) -> list[str]:
    return [strip_markup(cell) for cell in line.strip().strip("|").split("|")]


def scan(body: str) -> tuple[list[str], list[list[str]]]:
    """コードブロックの外の行と、Mermaid ブロックごとの中身の行を返す。"""
    prose: list[str] = []
    blocks: list[list[str]] = []
    fence: list[str] | None = None
    language = ""
    for line in body.splitlines():
        stripped = line.strip()
        if fence is not None:
            if stripped.startswith("```"):
                if language == "mermaid":
                    blocks.append(fence)
                fence = None
            else:
                fence.append(stripped)
            continue
        if stripped.startswith("```"):
            fence, language = [], stripped[3:].strip()
            continue
        prose.append(line)
    return prose, blocks


def vocabulary_rows(prose: list[str], header: list[str]) -> list[dict[str, str]]:
    """見出し行が header の表を一つだけ探し、行を返す。無い、二つ以上なら ValueError。"""
    found: list[list[dict[str, str]]] = []
    index = 0
    while index < len(prose):
        if prose[index].lstrip().startswith("|") and split_row(prose[index]) == header:
            rows: list[dict[str, str]] = []
            cursor = index + 2
            while cursor < len(prose) and prose[cursor].lstrip().startswith("|"):
                rows.append(dict(zip(header, split_row(prose[cursor]))))
                cursor += 1
            found.append(rows)
            index = cursor
            continue
        index += 1
    if len(found) != 1:
        raise ValueError(f"正式な定義に、見出し行が「| {' | '.join(header)} |」のユビキタス言語の表が{len(found)}個ある（1個必要）")
    return found[0]


def titled_state_diagram(block: list[str]) -> tuple[str, list[str]] | None:
    """`---` `title: <名前>` `---` で始まり stateDiagram-v2 が続くブロックなら (名前, 遷移の状態) を返す。"""
    content = [line for line in block if line and not line.startswith("%%")]
    if len(content) < 4 or content[0] != "---" or content[2] != "---" or content[3] != "stateDiagram-v2":
        return None
    if not content[1].startswith("title:"):
        return None
    holder = content[1][len("title:"):].strip()
    states: list[str] = []
    for line in content[4:]:
        match = TRANSITION.match(line)
        if match:
            states.extend(state for state in match.groups()[:2] if state != "[*]")
    return holder, states


def unique(words: list[str]) -> list[str]:
    seen: list[str] = []
    for word in words:
        if word and word not in seen:
            seen.append(word)
    return seen


def build_index(playbook_path: Path, source_raw: str) -> dict:
    """playbook.yml の contract と正式な定義のpathから索引を組み立てる。正式な定義が目印を持たなければ ValueError。"""
    contract = load_yaml(playbook_path)["contract"]
    header = contract["vocabulary_table"]
    kinds = contract["vocabulary_kinds"]
    source = regular_file(source_raw, "正式な定義")
    prose, blocks = scan(source.read_text(encoding="utf-8"))

    index: dict = {role: [] for role in kinds}
    index.update({"state_holders": [], "states": [], "bdd": []})
    rows = vocabulary_rows(prose, header)
    word_column, kind_column = header[0], header[2]
    for row in rows:
        for role, kind in kinds.items():
            if row.get(kind_column) == kind:
                index[role].append(row.get(word_column, ""))
    for role in kinds:
        index[role] = unique(index[role])
    for block in blocks:
        found = titled_state_diagram(block)
        if found:
            holder, states = found
            index["state_holders"].append(holder)
            index["states"].extend(states)
    index["state_holders"] = unique(index["state_holders"])
    index["states"] = unique(index["states"])
    ids: list[str] = []
    for line in prose:
        match = HEADING.match(line)
        if match and len(match.group(1)) == 3:
            ids.extend(BDD_ID.findall(match.group(2)))
    index["bdd"] = unique(ids)

    labels = {"terms": f"種類が「{kinds['terms']}」の行", "commands": f"種類が「{kinds['commands']}」の行", "bdd": "### [BDD-<番号>] の見出し"}
    missing = [labels[role] for role in REQUIRED_ROLES if not index[role]]
    if missing:
        raise ValueError("正式な定義に目印が無い: " + ", ".join(missing))
    vocabulary = unique(index["terms"] + index["events"] + index["concepts"]
                        + index["state_holders"] + index["states"])
    return {"source_path": str(source), **index, "vocabulary": vocabulary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        payload = build_index(Path(args.playbook), args.source)
    except (KeyError, OSError, UnicodeDecodeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
