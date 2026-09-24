#!/usr/bin/env python3
"""domain-ruleの正式な定義から、図に使ってよい語の索引を機械的に抜き出し、標準出力へJSONで返す。

正式な定義の見出し名は同じdirectoryの playbook.yml の contract.source_sections が持つ。ここは見出しの名前を知らず、
その見出しの下にある表のセル・小見出し・BDD番号を拾うだけで、意味の判断はしない。
索引はfileへ書かない。verify.py は同じ build_index を呼び、正式な定義のpathから毎回同じ索引を導く。

  source.py --playbook <同じdirectoryのplaybook.yml> --source <domain-ruleの正式な定義の絶対path>

exit 0 = 索引を標準出力へ返した / 2 = 正式な定義が契約の節を持たない、または読めない（診断は標準エラー）。
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


def outline(body: str) -> list[dict]:
    """見出しごとに level, title, lines を並べる。コードブロックの中は見出しに数えない。"""
    nodes: list[dict] = []
    in_code = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        match = None if in_code else HEADING.match(line)
        if match:
            nodes.append({"level": len(match.group(1)), "title": strip_markup(match.group(2)), "lines": []})
        elif nodes:
            nodes[-1]["lines"].append(line)
    return nodes


def section(nodes: list[dict], title: str) -> tuple[dict, list[dict]] | None:
    """title と一致する見出しと、その配下（同じ深さ以上の次の見出しまで）を返す。"""
    for index, node in enumerate(nodes):
        if node["title"] == title:
            children = []
            for child in nodes[index + 1:]:
                if child["level"] <= node["level"]:
                    break
                children.append(child)
            return node, children
    return None


def table_rows(lines: list[str]) -> list[list[str]]:
    """Markdown表の本文行をセルの列で返す。見出し行と区切り行は除く。"""
    rows: list[list[str]] = []
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            header_seen = False
            continue
        cells = [strip_markup(cell) for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            header_seen = True
            continue
        if header_seen and cells and cells[0]:
            rows.append(cells)
    return rows


def unique(words: list[str]) -> list[str]:
    seen: list[str] = []
    for word in words:
        if word and word not in seen:
            seen.append(word)
    return seen


def build_index(playbook_path: Path, source_raw: str) -> dict:
    """playbook.yml の contract と正式な定義のpathから索引を組み立てる。正式な定義が契約の節を持たなければ ValueError。"""
    contract = load_yaml(playbook_path)["contract"]
    sections = contract["source_sections"]
    source = regular_file(source_raw, "正式な定義")
    nodes = outline(source.read_text(encoding="utf-8"))

    def own_and_children(role: str) -> tuple[dict, list[dict]] | None:
        return section(nodes, sections[role])

    index: dict = {"terms": [], "events": [], "commands": [], "concepts": [],
                   "state_holders": [], "states": [], "bdd": []}
    found = own_and_children("terms")
    if found:
        index["terms"] = unique([row[0] for row in table_rows(found[0]["lines"])])
    found = own_and_children("events")
    if found:
        index["events"] = unique([row[0] for row in table_rows(found[0]["lines"])])
    found = own_and_children("commands")
    if found:
        index["commands"] = unique([row[0] for row in table_rows(found[0]["lines"])
                                    if len(row) > 1 and row[1] == contract["command_kind"]])
    found = own_and_children("concepts")
    if found:
        node, children = found
        index["concepts"] = unique([c["title"] for c in children if c["level"] == node["level"] + 1])
    found = own_and_children("states")
    if found:
        node, children = found
        holders = [c for c in children if c["level"] == node["level"] + 1]
        index["state_holders"] = unique([c["title"] for c in holders])
        index["states"] = unique([row[0] for c in holders for row in table_rows(c["lines"])])
    found = own_and_children("bdd")
    if found:
        node, children = found
        ids: list[str] = []
        for text in node["lines"] + [c["title"] for c in children] + [l for c in children for l in c["lines"]]:
            ids.extend(BDD_ID.findall(text))
        index["bdd"] = unique(ids)

    missing = [sections[role] for role in REQUIRED_ROLES if not index[role]]
    if missing:
        raise ValueError("正式な定義に契約の節が無いか空である: " + ", ".join(missing))
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
