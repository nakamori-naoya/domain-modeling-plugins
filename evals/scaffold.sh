#!/usr/bin/env bash
# ケースが共有する準備。空の作業場所へ、お題の業務知識の資料と、skill が読む別 package のファイルを置く。
# 各ケースの scaffold.sh が、お題のディレクトリを渡して呼ぶ。要件（materials/input/）は採点役だけが読み、作業場所へは置かない。
# 別 package（write-doc、grill）は隔離環境に入らないので、兄弟 checkout の最新のファイルを写す。
# 兄弟 checkout が無ければ、写しで代用せずに止まる。
set -euo pipefail

[ $# -eq 1 ] || { echo "使い方: bash scaffold.sh <お題のディレクトリ>" >&2; exit 2; }
TOPIC_DIR=$(cd "$1" && pwd)
EVALS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPOSITORY=$(cd "$EVALS_DIR/.." && pwd)
WORKSPACE=$(cd "$(dirname "$REPOSITORY")" && pwd)
WRITE_DOC="$WORKSPACE/write-doc-plugins/plugins/write-doc/skills/write-doc"
GRILL="$WORKSPACE/grill-plugins/plugins/grill/skills/grill"

for skill in "$WRITE_DOC" "$GRILL"; do
  [ -f "$skill/SKILL.md" ] || { echo "兄弟 checkout の skill が無い: $skill" >&2; exit 2; }
done

mkdir -p harness out grill-log
cp -R "$TOPIC_DIR/materials/business-knowledge" business-knowledge
cp -R "$WRITE_DOC" harness/write-doc
cp -R "$GRILL" harness/grill
