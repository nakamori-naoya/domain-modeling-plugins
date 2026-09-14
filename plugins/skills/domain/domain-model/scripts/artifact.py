#!/usr/bin/env python3
"""候補モデル（型付きMarkdown成果物）の検査と保存。

必須節の有無と空欄だけを見る。割り当ての妥当性は見ない（それはplaybookのverify.pyと人の仕事）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def die(message: str, code: int = 2) -> None:
    print(f"[error] {message}", file=sys.stderr)
    raise SystemExit(code)


def load_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"設定を読めない: {exc}")
    required = ("artifact_kind", "output_dir", "required_sections", "required_nonempty_sections")
    if any(not data.get(key) for key in required):
        die("成果物の契約が不完全")
    return data


def safe_topic(raw: str) -> str:
    topic = raw.strip()
    if not topic or topic in {".", ".."} or "/" in topic or "\\" in topic:
        die("topicは空でない単一のファイル名にする")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", topic):
        die("topicは英数字、点、ハイフン、アンダースコアだけを使う")
    return topic


def sections(body: str) -> dict[str, str]:
    matches = list(re.finditer(r"^## (.+?)\s*$", body, re.MULTILINE))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        if name in result:
            die(f"節が重複している: {name}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[name] = body[match.end():end].strip()
    return result


def validate_body(body: str, config: dict) -> str | None:
    if not body.strip():
        die("空の成果物は保存できない")
    found = sections(body)
    missing = [name for name in config["required_sections"] if name not in found]
    if missing:
        die("必須節が無い: " + ", ".join(missing))
    empty = [name for name in config["required_nonempty_sections"]
             if not found.get(name, "").strip() or found[name].strip() in {"なし", "未定"}]
    if empty:
        die("必須節が空または未定: " + ", ".join(empty))
    for name in config.get("evidence_sections", []):
        for line in found.get(name, "").splitlines():
            if line.lstrip().startswith("-") and ("出典：" not in line or "観測時点：" not in line):
                die(f"{name}の各箇条書きには出典：と観測時点：が必要")
    verdict = None
    if config.get("verdict_section"):
        verdict = found[config["verdict_section"]].strip()
        if verdict not in config.get("allowed_verdicts", []):
            die("判定は許可された値を1つだけ書く")
    return verdict


def contained_target(output_dir: Path, topic: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    root = output_dir.resolve()
    target = output_dir / f"{topic}.md"
    if target.is_symlink():
        die("symlinkの出力先には書き込まない")
    parent = target.parent.resolve()
    if os.path.commonpath((str(root), str(parent))) != str(root):
        die("出力先がoutput_dirの外に出ている")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "write"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--body-file", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    try:
        body = args.body_file.read_text(encoding="utf-8")
    except OSError as exc:
        die(f"本文を読めない: {exc}")
    verdict = validate_body(body, config)
    topic = safe_topic(args.topic)
    target = contained_target(Path(config["output_dir"]), topic)
    if args.command == "write":
        if target.exists() and not args.force:
            die("既存成果物を上書きしない。更新を明示する場合だけ--forceを使う", 3)
        target.write_text(body.rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"kind": config["artifact_kind"], "path": str(target), "verdict": verdict}, ensure_ascii=False))


if __name__ == "__main__":
    main()
