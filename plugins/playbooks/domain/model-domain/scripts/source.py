#!/usr/bin/env python3
"""domain-rule正本から、割り当ての候補と検査の正解になる索引を機械的に抜き出す。

正本の見出し名は解決済みYAMLの contract.source_sections が持つ。ここは見出しの名前を知らず、
「その見出しの下にある表の第1列・小見出し・箇条書き・BDD番号」を拾うだけである。
意味の判断はしない。索引に無い語を要素にできない、という検査の材料を作る。

  source.py --config <公開playbook.yml> --source <domain-rule正本> --output <索引の書き込み先>

exit 0 = 索引を書いた / 2 = 正本が契約の節を持たない、または読めない。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

HEADING = re.compile(r"^(#{1,4})[ ]+(.+?)[ ]*$")
BDD_ID = re.compile(r"\[(BDD-\d{3,})\]")
REQUIRED_ROLES = ("terms", "events", "concepts", "invariants", "bdd")


def fail(message: str) -> int:
    print(f"[error] {message}", file=sys.stderr)
    return 2


def load_yaml(path: Path) -> object:
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


def outline(body: str) -> list[dict]:
    """見出しごとに (level, title, lines) を並べる。コードブロックの中は見出しに数えない。"""
    nodes: list[dict] = []
    in_code = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if in_code:
            if nodes:
                nodes[-1]["lines"].append(line)
            continue
        match = HEADING.match(line)
        if match:
            nodes.append({"level": len(match.group(1)), "title": match.group(2).strip(), "lines": []})
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


def table_cells(lines: list[str], column: int) -> list[str]:
    """Markdown表の本文行から、指定した列のセルを拾う。見出し行と区切り行は除く。"""
    cells: list[str] = []
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            header_seen = False
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if all(set(part) <= set("-: ") for part in parts):
            header_seen = True
            continue
        if not header_seen:
            continue
        if column < len(parts) and parts[column] and parts[column] != "&nbsp;":
            cells.append(strip_markup(parts[column]))
    return cells


def strip_markup(text: str) -> str:
    text = re.sub(r"[*`_]", "", text)
    return text.strip()


def bullets(lines: list[str]) -> list[str]:
    return [strip_markup(line.strip()[2:]) for line in lines if line.strip().startswith(("- ", "* "))]


def collect(nodes: list[dict], sections: dict[str, str]) -> dict:
    index: dict = {}
    for role, title in sections.items():
        found = section(nodes, title)
        if found is None:
            index[role] = None
            continue
        node, children = found
        own = node["lines"]
        all_lines = own + [line for child in children for line in child["lines"]]
        if role == "terms":
            index[role] = table_cells(all_lines, 0)
        elif role == "events":
            index[role] = table_cells(all_lines, 0)
        elif role == "concepts":
            index[role] = [child["title"] for child in children if child["level"] == node["level"] + 1]
        elif role == "invariants":
            # 第1列が番号なら第2列、そうでなければ第1列を本文にする
            rows = table_cells(all_lines, 0)
            index[role] = table_cells(all_lines, 1) if rows and all(row.isdigit() for row in rows) else rows
        elif role == "states":
            holders = [child["title"] for child in children if child["level"] == node["level"] + 1]
            names = []
            for child in children:
                names.extend(table_cells(child["lines"], 0))
            index[role] = {"holders": holders, "names": names, "triggers": table_cells(own, 0)}
        elif role == "actors":
            index[role] = table_cells(all_lines, 1)
        elif role == "rules":
            index[role] = [child["title"] for child in children if child["level"] == node["level"] + 1]
        elif role == "rejections":
            index[role] = table_cells(all_lines, 0)
        elif role == "open_questions":
            items = bullets(all_lines)
            index[role] = [] if items == ["なし"] or "なし" in [line.strip() for line in own] else items
        elif role == "bdd":
            ids = []
            for line in all_lines + [child["title"] for child in children]:
                for found_id in BDD_ID.findall(line):
                    if found_id not in ids:
                        ids.append(found_id)
            index[role] = ids
        else:
            index[role] = all_lines
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        resolved = load_yaml(Path(args.config))
        playbook = resolved.get("playbook", resolved)
        sections = playbook["contract"]["source_sections"]
        source = regular_file(args.source, "正本")
        nodes = outline(source.read_text(encoding="utf-8"))
        index = collect(nodes, sections)
        missing = [sections[role] for role in REQUIRED_ROLES if not index.get(role)]
        if missing:
            raise ValueError("正本に契約の節が無いか空である: " + ", ".join(missing))
        states = index.get("states") or {"holders": [], "names": [], "triggers": []}
        vocabulary: list[str] = []
        for word in (index["terms"] + index["events"] + index["concepts"]
                     + states["holders"] + states["names"]):
            if word and word not in vocabulary:
                vocabulary.append(word)
        destination = Path(args.output)
        if not destination.is_absolute() or not destination.parent.is_dir():
            raise ValueError("索引の書き込み先が不正: " + args.output)
        payload = {
            "source_path": str(source),
            "sections": sections,
            "terms": index["terms"],
            "events": index["events"],
            "concepts": index["concepts"],
            "invariants": index["invariants"],
            "states": states,
            "actors": index.get("actors") or [],
            "rules": index.get("rules") or [],
            "rejections": index.get("rejections") or [],
            "open_questions": index.get("open_questions") or [],
            "bdd": index["bdd"],
            "vocabulary": vocabulary,
        }
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps({"source_index_path": str(destination.resolve()),
                      "counts": {key: len(value) for key, value in payload.items()
                                 if isinstance(value, list)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
