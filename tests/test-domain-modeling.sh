#!/usr/bin/env bash
# 基準資料: write-doc の domain-model 型 template と verify.py の検査宣言。
# 入力: fixture と、その表・BDD参照を変えた候補本文。
# 合格述語: 正例が成功し、各反例が対応する診断で失敗する。
# 失敗時の診断: 期待した診断と実際の標準エラーを表示する。
# 正例: 仮名、未決の種別、関係のないモデル。
# 反例: 表の欠落、不正な行、未宣言要素、未知のBDD、禁止した図の記法。
# 意味評価として残す範囲: 図と表の一致、設計の妥当性。
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PB="$ROOT/plugins/domain-modeling/skills/model-domain"
FIX="$ROOT/tests/fixtures/library-lending"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/domain-modeling-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0
FAIL=0

ok() { echo "  ok: $1"; PASS=$((PASS + 1)); }
ng() { echo "  NG: $1"; FAIL=$((FAIL + 1)); }
verify() { python3 "$PB/scripts/verify.py" --source "$FIX/business-knowledge.md" < "$1"; }
expect_ok() {
  verify "$1" >"$TMP/out" 2>"$TMP/err" && { ok "$2"; return; }
  ng "$2: $(head -3 "$TMP/err")"
}
expect_error() {
  local wanted="$1" candidate="$2"
  if verify "$candidate" >/dev/null 2>"$TMP/err"; then ng "should fail: $wanted"; return; fi
  grep -qF "$wanted" "$TMP/err" && ok "$wanted" || ng "expected $wanted / got: $(head -3 "$TMP/err")"
}

for fixture in "$ROOT"/tests/fixtures/*; do
  if python3 "$PB/scripts/verify.py" --source "$fixture/business-knowledge.md" < "$fixture/domain-model.md" >"$TMP/out" 2>"$TMP/err"; then
    ok "fixture: $(basename "$fixture")"
  else
    ng "fixture: $(cat "$TMP/err")"
  fi
done

python3 - "$FIX/domain-model.md" "$TMP" <<'PYTEST'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])
cases = {
    "provisional": text.replace("| Loan | 貸出 |", "| Loan | 貸出候補 |"),
    "no-stereotype": text.replace("| 値オブジェクト・文脈共有 |", "|  |", 1),
    "bad-stereotype": text.replace("| 値オブジェクト・文脈共有 |", "| 文脈共有 |", 1),
    "no-elements": text.replace("<!-- domain-model:elements -->", ""),
    "no-relations": text.replace("<!-- domain-model:relations -->", ""),
    "bad-relation": text.replace("| Loan | UserNumber |", "| Loan | MissingNumber |", 1),
    "bad-kind": text.replace("| 参照 | 誰の貸出か |", "| 不明 | 誰の貸出か |", 1),
    "bad-columns": text.replace("| Loan | 貸出 | 集約ルート |", "| Loan | 貸出 |"),
    "bad-header": text.replace("| 識別子 | 名前 | 種別 |", "| ID | 名前 | 種別 |"),
    "bad-separator": text.replace("| --- | --- | --- |", "| --- | 壊れた区切り | --- |", 1),
    "bad-identifier": text.replace("| Loan | 貸出 |", "| 1Loan | 貸出 |"),
    "empty-label": text.replace("| Loan | 貸出 |", "| Loan |  |"),
    "duplicate": text.replace("| Loan | 貸出 | 集約ルート |", "| Loan | 貸出 | 集約ルート |\n| Loan | 仮名 |  |"),
    "duplicate-marker": text + "\n<!-- domain-model:elements -->\n",
    "unknown-bdd": text.replace("BDD-007", "BDD-999", 1),
    "mermaid": text + "\n```mermaid\nclassDiagram\n```\n",
    "tilde-mermaid": text + "\n~~~mermaid\nclassDiagram\n~~~\n",
    "fenced-marker": "```text\n" + text + "\n```\n",
}
# 関係が無い叩き台も許す。図の有無と内容はここで判定しない。
cases["no-edges"] = """<!-- domain-model:elements -->

| 識別子 | 名前 | 種別 |
| --- | --- | --- |
| Loan | 仮の貸出 |  |

<!-- domain-model:relations -->

| 関係元 | 関係先 | 種類 | 関係 |
| --- | --- | --- | --- |
"""
for name, body in cases.items():
    (out / (name + ".md")).write_text(body)
PYTEST
expect_ok "$TMP/provisional.md" "設計上の仮名を許す"
expect_ok "$TMP/no-stereotype.md" "種別の未決を許す"
expect_ok "$TMP/no-edges.md" "関係のないモデルを許す"
expect_error "種別が契約に無い: 文脈共有" "$TMP/bad-stereotype.md"
expect_error "表の目印は一つ必要: domain-model:elements" "$TMP/no-elements.md"
expect_error "表の目印は一つ必要: domain-model:relations" "$TMP/no-relations.md"
expect_error "関係が未宣言要素を参照している: MissingNumber" "$TMP/bad-relation.md"
expect_error "関係の種類が契約に無い: 不明" "$TMP/bad-kind.md"
expect_error "表の列数が不正" "$TMP/bad-columns.md"
expect_error "表の見出しまたは区切り行が不正" "$TMP/bad-header.md"
expect_error "表の見出しまたは区切り行が不正" "$TMP/bad-separator.md"
expect_error "要素の識別子が不正: 1Loan" "$TMP/bad-identifier.md"
expect_error "要素の名前が空: Loan" "$TMP/empty-label.md"
expect_error "要素を重複宣言している: Loan" "$TMP/duplicate.md"
expect_error "表の目印は一つ必要: domain-model:elements" "$TMP/duplicate-marker.md"
expect_error "業務知識の資料に無いBDD参照: BDD-999" "$TMP/unknown-bdd.md"
expect_error "Mermaid のブロックは置けない" "$TMP/mermaid.md"
expect_error "Mermaid のブロックは置けない" "$TMP/tilde-mermaid.md"
expect_error "表の目印は一つ必要: domain-model:elements" "$TMP/fenced-marker.md"

: > "$TMP/empty.md"
expect_error "標準入力が空" "$TMP/empty.md"

echo "domain modeling structure checks: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
