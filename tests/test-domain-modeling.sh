#!/usr/bin/env bash
# verify.py は図の構造とBDD参照の実在だけを判定し、設計の意味は判定しない。
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

expect_ok "$FIX/domain-model.md" "existing domain-model fixture passes"
python3 - "$FIX/domain-model.md" "$TMP/provisional.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
text = text.replace('class Loan["貸出"]', 'class Loan["貸出候補"]')
text = text.replace('class UserNumber["利用者番号"]', 'class DraftNumber["仮の貸出番号"]')
text = text.replace('Loan --> UserNumber : 誰の貸出か', 'Loan --> DraftNumber : 仮説上の参照先')
text = text.replace('(BDD-007)', '(BDD-007、業務資料未記載の条件を仮置き)')
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
expect_ok "$TMP/provisional.md" "hypothetical and source-absent element labels remain discussable"

python3 - "$FIX/domain-model.md" "$TMP/no-stereotype.md" "$TMP/bad-stereotype.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write(text.replace('<<値オブジェクト・文脈共有>>', '', 1))
open(sys.argv[3], "w", encoding="utf-8").write(text.replace('<<値オブジェクト・文脈共有>>', '<<文脈共有>>', 1))
PY
expect_ok "$TMP/no-stereotype.md" "element kind may be left undecided in a draft"
expect_error "種別が契約に無い: 文脈共有" "$TMP/bad-stereotype.md"

python3 - "$FIX/domain-model.md" "$TMP/no-classdiagram.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().replace("classDiagram", "flowchart LR", 1)
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
expect_error "Mermaid classDiagram が無い" "$TMP/no-classdiagram.md"

python3 - "$FIX/domain-model.md" "$TMP/bad-relation.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().replace("Loan --> UserNumber", "Loan --> MissingNumber", 1)
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
expect_error "関係が未宣言要素を参照している: MissingNumber" "$TMP/bad-relation.md"

python3 - "$FIX/domain-model.md" "$TMP/bad-syntax.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().replace("Loan --> UserNumber : 誰の貸出か", "Loan => UserNumber", 1)
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
expect_error "classDiagram の行を読めない" "$TMP/bad-syntax.md"

python3 - "$FIX/domain-model.md" "$TMP/unknown-bdd.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().replace("BDD-007", "BDD-999", 1)
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
expect_error "業務知識の資料に無いBDD参照: BDD-999" "$TMP/unknown-bdd.md"

: > "$TMP/empty.md"
expect_error "標準入力が空" "$TMP/empty.md"

echo "domain modeling structure checks: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
