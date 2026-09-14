#!/usr/bin/env python3
"""確かめた決定と未決を、このplaybookが所有する「根拠づけられた入力」へ束ねる。

対話工程は決めたことと未決だけを返す。素材へ束ね直すのは呼び出し元の仕事なので、
この工程はこのpackageが持つ。読むのは対話工程の公開出力ファイルだけで、
相手の決定ログや内部の記録形式には触れない。

  ground.py --config <解決済みYAML> --dialogue-output <対話工程の出力YAML>
            --source <domain-rule正本の絶対path> --output <束ねた入力の書き込み先>
            [--request <path>] [--existing <既存のドメインモデル資料の絶対path>]

--source は正本の domain-rule 資料で、必ず1本である。--existing は同じパスへ更新する既存資料で、
渡されたときだけ更新扱いになる。

exit 0 = 束ねた / 2 = 入力が契約を満たさない。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

DIALOGUE_DEPENDENCY = "grill"


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


def expected_contract(playbook: dict) -> str:
    for requirement in playbook.get("requires") or []:
        if isinstance(requirement, dict) and requirement.get("plugin") == DIALOGUE_DEPENDENCY:
            return f"{requirement['marketplace']}/{requirement['plugin']}"
    raise ValueError(f"requiresに{DIALOGUE_DEPENDENCY}が無い")


def checked_entries(output: dict, key: str, fields: tuple[str, ...]) -> list[dict]:
    entries = output.get(key) or []
    if not isinstance(entries, list):
        raise ValueError(f"{key}が配列ではない")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{key}の要素がobjectではない")
        missing = [field for field in fields if not isinstance(entry.get(field), str) or not entry[field]]
        if missing:
            raise ValueError(f"{key}に{'・'.join(missing)}が無い要素がある")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--dialogue-output", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--request", action="append", default=[])
    parser.add_argument("--existing")
    args = parser.parse_args()
    try:
        resolved = load_yaml(Path(args.config))
        playbook = resolved["playbook"]
        contract = expected_contract(playbook)
        output = load_yaml(regular_file(args.dialogue_output, "対話工程の出力"))
        if not isinstance(output, dict):
            raise ValueError("対話工程の出力がmappingではない")
        if output.get("contract") != contract or output.get("version") != 1:
            raise ValueError(f"対話工程の出力が契約{contract} 版1ではない")
        if output.get("status") != "completed":
            raise ValueError("対話工程が完了していない。劣化した入力で先へ進まない")
        decisions = checked_entries(output, "decisions", ("id", "question", "answer", "rationale"))
        open_questions = checked_entries(output, "open_questions", ("id", "question", "state"))
        for entry in open_questions:
            if entry["state"] not in {"open", "withdrawn"}:
                raise ValueError("未決の状態がopen/withdrawnではない: " + entry["state"])
        if not decisions and not open_questions:
            raise ValueError("決定も未決も無い。確かめていない入力で先へ進まない")
        source = regular_file(args.source, "正本")
        if source.suffix.lower() != ".md":
            raise ValueError("正本はMarkdownの domain-rule 資料に限る: " + args.source)
        requests = [str(regular_file(raw, "依頼")) for raw in args.request]
        existing = str(regular_file(args.existing, "既存資料")) if args.existing else None
        destination = Path(args.output)
        if not destination.is_absolute() or not destination.parent.is_dir():
            raise ValueError("束ねた入力の書き込み先が不正: " + args.output)
        grounded = {
            "playbook": playbook["name"],
            "document_type": playbook.get("document_type"),
            "source_path": str(source),
            "requests": requests,
            "existing_document_path": existing,
            "decisions": decisions,
            "open_questions": open_questions,
        }
        destination.write_text(json.dumps(grounded, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps({"grounded_input_path": str(destination.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
