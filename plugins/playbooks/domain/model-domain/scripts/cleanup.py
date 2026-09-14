#!/usr/bin/env python3
"""このplaybookが所有する中間成果物だけを、最終資料の保存を確認してから削除する。

後片付けは呼び出し元の仕事である。外部packageのscriptへ委ねない。
削除してよいのは contract.cleanup.delete_after_document に宣言した論理名の成果物だけで、
preserve の成果物、repository の外、追跡済みファイルには手を触れない。

  cleanup.py --config <解決済みYAML> --artifact <論理名>=<絶対path> ...

exit 0 = 後片付けした / 2 = 契約を満たさないので何も削除していない。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def fail(message: str) -> int:
    print(f"[error] {message}", file=sys.stderr)
    return 2


def load_resolved(config_path: Path) -> dict:
    result = subprocess.run(["yq", "-o=json", "-I=0", ".", str(config_path)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def tracked(repo_root: Path, path: Path) -> bool:
    result = subprocess.run(["git", "-C", str(repo_root), "ls-files", "--error-unmatch", str(path)],
                            capture_output=True, text=True)
    return result.returncode == 0


def artifact_map(pairs: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in pairs:
        name, separator, raw = pair.partition("=")
        if not separator or not name or not raw:
            raise ValueError("--artifact は <論理名>=<絶対path> の形で渡す: " + pair)
        if name in mapping:
            raise ValueError("同じ論理名を2度渡している: " + name)
        mapping[name] = raw
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()
    try:
        resolved = load_resolved(Path(args.config))
        cleanup = resolved["playbook"]["contract"]["cleanup"]
        deletable = list(cleanup["delete_after_document"])
        preserved = list(cleanup["preserve"])
        repo_root = Path(resolved["repo_root"]).resolve(strict=True)
        artifacts = artifact_map(args.artifact)

        unknown = sorted(set(artifacts) - set(deletable) - set(preserved))
        if unknown:
            raise ValueError("契約に無い成果物は扱わない: " + ", ".join(unknown))
        missing = [name for name in preserved if name not in artifacts]
        if missing:
            raise ValueError("保持する成果物が渡されていない: " + ", ".join(missing))

        kept: list[str] = []
        for name in preserved:
            path = Path(artifacts[name])
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"保持する成果物が保存されていない: {name}")
            kept.append(str(path.resolve()))

        planned: list[tuple[str, Path]] = []
        for name in deletable:
            raw = artifacts.get(name)
            if raw is None:
                continue
            path = Path(raw)
            if not path.is_absolute():
                raise ValueError(f"削除候補が絶対pathではない: {name}")
            if path.is_symlink():
                raise ValueError(f"削除候補がsymlinkである: {name}")
            if not path.exists():
                continue
            resolved_path = path.resolve()
            if not resolved_path.is_file():
                raise ValueError(f"削除候補が通常ファイルではない: {name}")
            if not contained(repo_root, resolved_path):
                raise ValueError(f"削除候補がrepositoryの外にある: {name}")
            if str(resolved_path) in kept:
                raise ValueError(f"保持する成果物と同じpathを削除候補にしている: {name}")
            if tracked(repo_root, resolved_path):
                raise ValueError(f"追跡済みファイルは削除しない: {name}")
            planned.append((name, resolved_path))

        removed: list[dict[str, str]] = []
        for name, path in planned:
            os.remove(path)
            removed.append({"artifact": name, "path": str(path)})
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps({"cleanup_report": {"removed": removed, "preserved": kept}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
