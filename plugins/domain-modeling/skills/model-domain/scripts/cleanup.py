#!/usr/bin/env python3
"""このplaybookが所有する中間成果物だけを、最終資料の保存を確認してから削除する。

後片付けは呼び出し元の仕事である。外部packageのscriptへ委ねない。
削除してよいのは contract.cleanup.delete_after_document に宣言した論理名の成果物だけで、
preserve の成果物、repository の外、追跡済みファイルには手を触れない。

  cleanup.py --playbook <同じdirectoryのplaybook.yml> --work-dir <run専用directory> --artifact <論理名>=<絶対path> ...

exit 0 = 後片付けした / 2 = 契約を満たさないので何も削除していない。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


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


def has_git_marker(directory: Path) -> bool:
    for ancestor in (directory, *directory.parents):
        try:
            (ancestor / ".git").lstat()
        except FileNotFoundError:
            continue
        return True
    return False


def tracked(path: Path) -> bool:
    root_result = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True,
                                 env={**os.environ, "LC_ALL": "C"})
    if root_result.returncode != 0:
        if (root_result.returncode == 128
                and "not a git repository" in root_result.stderr
                and not has_git_marker(path.parent)):
            return False
        detail = root_result.stderr.strip() or f"exit {root_result.returncode}"
        raise ValueError(f"Git repository境界を確認できない: {detail}")
    raw_root = root_result.stdout.strip()
    if not raw_root:
        raise ValueError("Git repository境界を確認できない: rootが空")
    repo_root = Path(raw_root)
    if not repo_root.is_absolute() or not repo_root.is_dir():
        raise ValueError("Git repository境界を確認できない: rootが不正")
    repo_root = repo_root.resolve()
    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        raise ValueError("Git repository境界と削除候補が一致しない")
    result = subprocess.run(["git", "-C", str(repo_root), "ls-files", "--error-unmatch", str(relative)],
                            capture_output=True, text=True,
                            env={**os.environ, "LC_ALL": "C"})
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.strip() or f"exit {result.returncode}"
    raise ValueError(f"Gitの追跡状態を確認できない: {detail}")


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
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()
    try:
        playbook = load_resolved(Path(args.playbook))
        cleanup = playbook["contract"]["cleanup"]
        deletable = list(cleanup["delete_after_document"])
        preserved = list(cleanup["preserve"])
        work_dir_raw = Path(args.work_dir)
        if not work_dir_raw.is_absolute() or work_dir_raw.is_symlink():
            raise ValueError("work-dirはsymlinkでない絶対pathで渡す")
        work_dir = work_dir_raw.resolve(strict=True)
        if not work_dir.is_dir():
            raise ValueError("work-dirがdirectoryではない")
        system_temp = Path(tempfile.gettempdir()).resolve(strict=True)
        if not contained(system_temp, work_dir) or work_dir == system_temp:
            raise ValueError("work-dirはsystem temporary directory内のrun専用directoryにする")
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
            if not contained(work_dir, resolved_path):
                raise ValueError(f"削除候補がrun専用directoryの外にある: {name}")
            if str(resolved_path) in kept:
                raise ValueError(f"保持する成果物と同じpathを削除候補にしている: {name}")
            if tracked(resolved_path):
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
