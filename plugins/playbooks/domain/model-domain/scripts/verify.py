#!/usr/bin/env python3
"""候補モデルが契約を満たすかを検査し、通ったものだけを返す。

検査するのは述語であって、モデルの良し悪しではない。通ったときに言えるのは次だけである。

  - 節と順序が契約と一致し、どの節も空でない
  - 実装の節（テーブル定義・API など）が混入せず、要素〜ドメインイベントの節にデータの持ち方の語（記録の列・履歴・レコード・テーブル・DB 等）が無い
  - 要素一覧の全要素が、正本の索引にある語（無ければ正本の本文に現れる語）で名付けられている
  - モデル図が集約ごとに分かれ、各集約に責務・境界の箇条書きと classDiagram があり、全要素がどこかの集約の図に現れ、
    メソッドは公開コマンド（括弧つき）だけで、フィールドが無い。集約が2つ以上なら「集約どうしの関係」の図がある
  - 要素一覧の全要素（ドメインイベントを除く）に詳細があり、必須項目（####）と操作ごとの契約（#### 操作:）が埋まっている
  - 詳細にあって一覧に無い要素が無い
  - 集約が2つ以上なら「集約どうしの協働」の表があり、手段が契約の値（識別子で参照／値として渡す／ドメインイベント／呼び手が両方を操作）に収まる
  - 正本の全BDDが対応表か「対応しないBDD」に現れ、全要素が対応表か「対応のない要素・操作」に現れる
  - 未決の節が空でない（「なし」を含む）

  verify.py --config <解決済みYAML> --candidate <候補モデルの絶対path> --source-index <索引の絶対path>

exit 0 = 通った（stdoutに verified_model_path と warnings） / 2 = 通らない。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

HEADING = re.compile(r"^(#{1,6})[ ]+(.+?)[ ]*$")
BDD_ID = re.compile(r"BDD-\d{3,}")


def fail(message: str) -> int:
    print(f"[error] {message}", file=sys.stderr)
    return 2


def load_playbook(config_path: Path) -> dict:
    result = subprocess.run(["yq", "-o=json", "-I=0", ".", str(config_path)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["playbook"]


def read_regular(raw: str, label: str) -> tuple[Path, str]:
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{label}が絶対pathの通常ファイルではない: {raw}")
    return path.resolve(), path.read_text(encoding="utf-8")


def strip_markup(text: str) -> str:
    return re.sub(r"[*`_]", "", text).strip()


def split_sections(body: str) -> tuple[list[str], dict[str, list[str]], list[tuple[int, str]]]:
    """H2で節を切る。戻り値は (H2の順序, 節→行, 全見出し)。コードブロック内は見出しに数えない。"""
    order: list[str] = []
    content: dict[str, list[str]] = {}
    headings: list[tuple[int, str]] = []
    current: str | None = None
    in_code = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        match = None if in_code else HEADING.match(line)
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            headings.append((level, title))
            if level == 2:
                if title in content:
                    raise ValueError(f"節が重複している: {title}")
                current = title
                order.append(title)
                content[title] = []
                continue
        if current is not None:
            content[current].append(line)
    return order, content, headings


def tables(lines: list[str]) -> list[dict]:
    """節内のMarkdown表を、見出し行と本文行に分けて返す。"""
    found: list[dict] = []
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            current = None
            continue
        cells = [strip_markup(part) for part in stripped.strip("|").split("|")]
        if current is None:
            current = {"header": cells, "rows": []}
            found.append(current)
            continue
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        current["rows"].append(cells)
    return found


def element_parts(lines: list[str]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """要素の詳細（### の下）を、#### 項目 → 本文 と、#### 操作: 名 → {欄: 値} に分ける。"""
    items: dict[str, str] = {}
    operations: dict[str, dict[str, str]] = {}
    current: str | None = None
    current_op: str | None = None
    for line in lines:
        match = HEADING.match(line)
        if match and len(match.group(1)) == 4:
            title = match.group(2).strip()
            if title.startswith("操作:") or title.startswith("操作："):
                current_op = title.split(":", 1)[-1].split("：", 1)[-1].strip()
                if current_op in operations:
                    raise ValueError(f"操作が重複している: {current_op}")
                operations[current_op] = {}
                current = None
            else:
                current = title
                current_op = None
                if current in items:
                    raise ValueError(f"項目が重複している: {current}")
                items[current] = ""
            continue
        if current_op is not None:
            bullet = re.match(r"^\s*[-*]\s*([^:：]+)[:：]\s*(.*)$", line)
            if bullet:
                operations[current_op][bullet.group(1).strip()] = strip_markup(bullet.group(2))
        elif current is not None and line.strip() and not line.strip().startswith("<!--"):
            items[current] = (items[current] + " " + strip_markup(line)).strip()
    return items, operations


CLASS_LABEL = re.compile(r'^\s*class\s+[A-Za-z_][A-Za-z0-9_]*\s*\[\"(.+?)\"\]')


def class_diagram(lines: list[str]) -> tuple[list[str], list[str]]:
    """classDiagram の class ラベル一覧と、フィールド・ゲッターと見なす行を返す。"""
    labels: list[str] = []
    fields: list[str] = []
    in_block = False
    in_class = False
    for line in lines:
        if line.startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            continue
        match = CLASS_LABEL.match(line)
        if match:
            labels.append(match.group(1))
            in_class = line.rstrip().endswith("{")
            continue
        stripped = line.strip()
        if stripped == "}":
            in_class = False
            continue
        if in_class and stripped and not stripped.startswith("<<"):
            if not (stripped.startswith("+") and "(" in stripped):
                fields.append(stripped)
    return labels, fields


def subsections(lines: list[str]) -> dict[str, list[str]]:
    """節内のH3ごとに行を分ける。"""
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        match = HEADING.match(line)
        if match and len(match.group(1)) == 3:
            current = match.group(2).strip()
            if current in result:
                raise ValueError(f"小見出しが重複している: {current}")
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return result


def nonempty(lines: list[str]) -> bool:
    return any(line.strip() and not line.strip().startswith("<!--") for line in lines)


def names_in(cell: str) -> list[str]:
    return [part.strip() for part in re.split(r"[、,／/]", cell) if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--source-index", required=True)
    args = parser.parse_args()
    warnings: list[str] = []
    try:
        playbook = load_playbook(Path(args.config))
        contract = playbook["contract"]
        expected = list(contract["model_sections"])
        kinds = set(contract["element_kinds"])
        exceptional = set(contract["exceptional_kinds"])
        items = list(contract["element_items"])
        op_fields = list(contract["operation_fields"])
        forbidden = set(contract["forbidden_sections"])

        path, body = read_regular(args.candidate, "候補モデル")
        index_path, index_text = read_regular(args.source_index, "索引")
        index = json.loads(index_text)
        source_body = Path(index["source_path"]).read_text(encoding="utf-8")
        vocabulary = set(index["vocabulary"])

        order, content, headings = split_sections(body)
        mixed = [title for _, title in headings if title in forbidden]
        if mixed:
            raise ValueError("実装の節が混入している: " + ", ".join(mixed))
        if order != expected:
            raise ValueError("節と順序が契約に一致しない。期待: " + " / ".join(expected)
                             + " 実際: " + " / ".join(order))
        empty = [title for title in expected if not nonempty(content[title])]
        if empty:
            raise ValueError("空の節がある: " + ", ".join(empty))

        # データの持ち方の語
        forbidden_words = list(contract["forbidden_words"])
        for title in ("要素一覧", "モデル図", "各要素の詳細", "集約の境界", "状態と型の分割", "ドメインイベント"):
            body_text = "\n".join(line for line in content[title] if not line.strip().startswith("<!--"))
            hits = [word for word in forbidden_words if word in body_text]
            if hits:
                raise ValueError(f"「{title}」にデータの持ち方の語がある: " + ", ".join(hits) + "。業務の事実は「起きた」「持つ」「いつ起きたか」で書く")

        # 要素一覧
        listing = [table for table in tables(content["要素一覧"]) if table["header"][:2] == ["要素", "種別"]]
        if not listing or not listing[0]["rows"]:
            raise ValueError("要素一覧に「要素 | 種別 | 正本の語 | 目的」の表が無いか空である")
        elements: dict[str, dict] = {}
        for row in listing[0]["rows"]:
            if len(row) < 4 or not all(row[:4]):
                raise ValueError("要素一覧の行に空欄がある: " + " | ".join(row))
            name, kind, term, purpose = row[0], row[1], row[2], row[3]
            if name in elements:
                raise ValueError("要素一覧に同じ要素が2度ある: " + name)
            if not any(kind.startswith(allowed) for allowed in kinds):
                raise ValueError(f"要素「{name}」の種別が契約の外: {kind}")
            if any(kind.startswith(ex) for ex in exceptional):
                warnings.append(f"例外扱いの種別を使っている: {name}（{kind}）。捨てた割り当てに理由があるか読む")
            for word in {name} | set(names_in(term)):
                if word in vocabulary:
                    continue
                if word in source_body:
                    warnings.append(f"「{word}」は索引（業務用語・業務イベント・概念・状態）に無いが正本の本文には現れる。要素「{name}」")
                else:
                    raise ValueError(f"要素「{name}」の語「{word}」が正本に無い。正本に無い語を要素にしない")
            elements[name] = {"kind": kind, "term": term}

        # 各要素の詳細
        details = subsections(content["各要素の詳細"])
        needs_detail = [name for name, info in elements.items() if not info["kind"].startswith("ドメインイベント")]
        missing_detail = [name for name in needs_detail if name not in details]
        if missing_detail:
            raise ValueError("要素一覧にあって詳細が無い要素: " + ", ".join(missing_detail))
        extra_detail = [name for name in details if name not in elements]
        if extra_detail:
            raise ValueError("詳細にあって要素一覧に無い要素: " + ", ".join(extra_detail))
        for name in needs_detail:
            items_found, operations = element_parts(details[name])
            lacking = [item for item in items if not items_found.get(item)]
            if lacking:
                raise ValueError(f"要素「{name}」の必須項目（####）が無いか空: " + ", ".join(lacking))
            unknown_items = [h for h in items_found if h not in items]
            if unknown_items:
                raise ValueError(f"要素「{name}」に契約に無い項目がある: " + ", ".join(unknown_items))
            if not operations:
                raise ValueError(f"要素「{name}」に「#### 操作: <操作名>」が1つも無い")
            for op_name, fields in operations.items():
                lacking_fields = [f for f in op_fields if not fields.get(f)]
                if lacking_fields:
                    raise ValueError(f"要素「{name}」の操作「{op_name}」に空欄がある: " + ", ".join(lacking_fields) + "。契約の各欄を埋めるか「なし」と書く")

        # モデル図: 集約ごとに1枚。責務・境界の箇条書きと classDiagram。集約が2つ以上なら「集約どうしの関係」
        boundary_tables = [table for table in tables(content["集約の境界"]) if table["header"][:2] == ["集約", "ルート"]]
        if not boundary_tables or not boundary_tables[0]["rows"]:
            raise ValueError("集約の境界に「集約 | ルート | …」の表が無いか空である")
        aggregates = [row[0] for row in boundary_tables[0]["rows"] if row and row[0]]
        diagram_sections = subsections(content["モデル図"])
        aggregate_sections = {title[len("集約:"):].strip(): body for title, body in diagram_sections.items()
                              if title.startswith("集約:") or title.startswith("集約：")}
        aggregate_sections = {(k if not k.startswith("：") else k[1:]).strip(): v for k, v in aggregate_sections.items()}
        missing_diagram = [name for name in aggregates if name not in aggregate_sections]
        if missing_diagram:
            raise ValueError("集約の境界にあってモデル図に「### 集約: <名>」が無い集約: " + ", ".join(missing_diagram))
        extra_diagram = [name for name in aggregate_sections if name not in aggregates]
        if extra_diagram:
            raise ValueError("モデル図にあって集約の境界に無い集約: " + ", ".join(extra_diagram))
        all_labels: set[str] = set()
        for name, body in aggregate_sections.items():
            bullets = {}
            for line in body:
                bullet = re.match(r"^\s*[-*]\s*([^:：]+)[:：]\s*(.*)$", line)
                if bullet:
                    bullets[bullet.group(1).strip()] = bullet.group(2).strip()
            for key in ("責務", "境界"):
                if not bullets.get(key):
                    raise ValueError(f"集約「{name}」のモデル図に「- {key}:」が無いか空")
            labels, fields_found = class_diagram(body)
            if not labels:
                raise ValueError(f"集約「{name}」のモデル図に classDiagram の class が無い")
            if name not in labels:
                raise ValueError(f"集約「{name}」のモデル図にルート「{name}」のクラスが無い")
            if fields_found:
                raise ValueError(f"集約「{name}」のモデル図にフィールドかゲッターがある（メソッドは括弧つきの公開コマンドだけ）: " + ", ".join(fields_found))
            unknown = [label for label in labels if label not in elements]
            if unknown:
                raise ValueError(f"集約「{name}」のモデル図にあって要素一覧に無いクラス: " + ", ".join(unknown))
            all_labels.update(labels)
        missing_class = [name for name in elements if name not in all_labels]
        if missing_class:
            raise ValueError("要素一覧にあってどの集約のモデル図にも無い要素: " + ", ".join(missing_class))
        # 集約どうしの協働（集約の境界の小節）
        boundary_subs = subsections(content["集約の境界"])
        collab = boundary_subs.get("集約どうしの協働")
        if collab is None:
            raise ValueError("集約の境界に「### 集約どうしの協働」が無い")
        collab_tables = [table for table in tables(collab) if len(table["header"]) > 1 and table["header"][1] == "手段"]
        if len(aggregates) >= 2:
            if not collab_tables or not collab_tables[0]["rows"]:
                raise ValueError("集約が2つ以上あるのに「集約どうしの協働」の表が無いか空")
            means = set(contract["collaboration_means"])
            for row in collab_tables[0]["rows"]:
                if len(row) < 4 or not all(row[:4]):
                    raise ValueError("集約どうしの協働の行に空欄がある: " + " | ".join(row))
                if row[1] not in means:
                    raise ValueError(f"集約どうしの協働の手段が契約の外: {row[1]}（許す値: {'／'.join(sorted(means))}）")
        elif not nonempty(collab):
            raise ValueError("集約が1つなら「集約どうしの協働」に「なし」と書く")

        relation = diagram_sections.get("集約どうしの関係")
        if len(aggregates) >= 2:
            if relation is None:
                raise ValueError("集約が2つ以上あるのに「### 集約どうしの関係」が無い")
            rel_labels, _ = class_diagram(relation)
            missing_rel = [name for name in aggregates if name not in rel_labels]
            if missing_rel:
                raise ValueError("「集約どうしの関係」に無い集約: " + ", ".join(missing_rel))
        elif relation is not None:
            raise ValueError("集約が1つなのに「### 集約どうしの関係」がある")

        # BDDとの対応
        mapping_lines = content["BDDとの対応"]
        mapping_tables = [table for table in tables(mapping_lines) if table["header"][:1] == ["BDD"]]
        if not mapping_tables:
            raise ValueError("BDDとの対応に「BDD | 要素 | 操作 | …」の表が無い")
        covered_bdd: set[str] = set()
        covered_elements: set[str] = set()
        for row in mapping_tables[0]["rows"]:
            covered_bdd.update(BDD_ID.findall(row[0]))
            if len(row) > 1:
                covered_elements.update(names_in(row[1]))
        unmapped_line = next((line for line in mapping_lines if line.strip().startswith("- 対応しないBDD:")), None)
        unused_line = next((line for line in mapping_lines if line.strip().startswith("- 対応のない要素・操作:")), None)
        if unmapped_line is None or unused_line is None:
            raise ValueError("BDDとの対応に「- 対応しないBDD:」と「- 対応のない要素・操作:」の行が要る")
        declared_unmapped = set(BDD_ID.findall(unmapped_line))
        missing_bdd = [bdd for bdd in index["bdd"] if bdd not in covered_bdd and bdd not in declared_unmapped]
        if missing_bdd:
            raise ValueError("正本のBDDが対応表にも「対応しないBDD」にも無い: " + ", ".join(missing_bdd))
        unknown_bdd = sorted(bdd for bdd in covered_bdd if bdd not in set(index["bdd"]))
        if unknown_bdd:
            raise ValueError("正本に無いBDD番号が対応表にある: " + ", ".join(unknown_bdd))
        declared_unused = names_in(unused_line.split(":", 1)[1])
        unused = [name for name in needs_detail if name not in covered_elements and name not in declared_unused]
        if unused:
            raise ValueError("対応表にも「対応のない要素・操作」にも無い要素: " + ", ".join(unused)
                             + "。BDDに対応しない要素は余りである")
        if declared_unmapped:
            warnings.append("対応しないBDDがある: " + ", ".join(sorted(declared_unmapped)) + "。要素が足りていない")
        if declared_unused and declared_unused != ["なし"]:
            warnings.append("対応のない要素・操作がある: " + ", ".join(declared_unused) + "。要素が余っている")

        # 未決
        if not nonempty(content["未決"]):
            raise ValueError("未決の節が空。0件なら「なし」と書く")
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps({"verified_model_path": str(path), "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
