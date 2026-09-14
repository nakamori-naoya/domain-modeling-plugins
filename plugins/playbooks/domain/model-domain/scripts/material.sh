#!/usr/bin/env bash
# 検査済みモデル、正本のpath、決定と未決、索引の要約を、write-docへ渡す1つの素材へ束ねる。
#
#   material.sh --config <解決済みYAML> --model <検査済みモデルの絶対path> \
#               --grounded-input <ground.pyの出力> --source-index <索引> --output <素材の書き込み先>
#
# 束ねるだけで、内容の判断はしない。どれかが欠けていれば束ねずに exit 2。
set -euo pipefail

config=""; model=""; grounded=""; index=""; output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --config) config="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --grounded-input) grounded="$2"; shift 2 ;;
    --source-index) index="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    *) echo "[error] 未知の引数: $1" >&2; exit 2 ;;
  esac
done
for pair in "config:$config" "model:$model" "grounded-input:$grounded" "source-index:$index" "output:$output"; do
  name="${pair%%:*}"; value="${pair#*:}"
  [ -n "$value" ] || { echo "[error] --${name} が要る" >&2; exit 2; }
done
for f in "$config" "$model" "$grounded" "$index"; do
  case "$f" in /*) ;; *) echo "[error] 絶対pathではない: $f" >&2; exit 2 ;; esac
  [ ! -L "$f" ] && [ -f "$f" ] || { echo "[error] 通常ファイルではない: $f" >&2; exit 2; }
done
case "$output" in /*) ;; *) echo "[error] 書き込み先が絶対pathではない: $output" >&2; exit 2 ;; esac
[ -d "$(dirname "$output")" ] || { echo "[error] 書き込み先の親directoryが無い: $output" >&2; exit 2; }

document_type=$(yq -er '.playbook.document_type' "$config")
source_path=$(jq -er '.source_path' "$grounded")
existing=$(jq -r '.existing_document_path // ""' "$grounded")
{
  echo "# 素材: ${document_type}"
  echo
  echo "## 正本"
  echo
  echo "- 業務知識の正本: ${source_path}"
  [ -z "$existing" ] || echo "- 更新する既存資料: ${existing}"
  echo
  echo "## 確かめた決定"
  echo
  jq -r '.decisions[] | "- \(.question) → \(.answer)（理由: \(.rationale)）"' "$grounded"
  [ "$(jq '.decisions|length' "$grounded")" != "0" ] || echo "- なし"
  echo
  echo "## 未決"
  echo
  jq -r '.open_questions[] | "- [\(.state)] \(.question)（\(.reason // "理由未記載")）"' "$grounded"
  [ "$(jq '.open_questions|length' "$grounded")" != "0" ] || echo "- なし"
  echo
  echo "## 正本の索引（要約）"
  echo
  jq -r '"- 業務用語: \(.terms|length)件 / 業務イベント: \(.events|length)件 / 概念: \(.concepts|length)件 / 常に守られること: \(.invariants|length)件 / BDD: \(.bdd|length)件"' "$index"
  jq -r '"- 正本の未決: " + (if (.open_questions|length)==0 then "なし" else (.open_questions|join(" ／ ")) end)' "$index"
  echo
  echo "## 検査済みモデル"
  echo
  cat "$model"
} > "$output"
printf '{"material_path":"%s"}\n' "$output"
