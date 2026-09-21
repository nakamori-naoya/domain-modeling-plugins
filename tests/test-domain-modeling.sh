#!/usr/bin/env bash
# model-domain が所有する script（source.py / verify.py）を、典型例・負例・境界例で実行する。
# 基準資料: playbook.yml の contract と domain-ruleの正式な定義。入力: 正式な定義のpath（source.py）、正式な定義のpath＋標準入力の候補本文（verify.py）。
# 正規化: 見出し・表・箇条書きの機械抽出。合格述語: verify.py 冒頭の一覧。診断: 標準エラー。
# 正例: fixtures/domain-model.md（業務知識へ提案する概念を2件持つ）。反例: 索引外の語、空欄、節の順序、未宣言BDD、提案した語が要素一覧に混ざる、提案の表の欠落・不正なBDD番号・不正な足す先。境界例: 空stdin、正式な定義のpath欠落、旧形の --candidate 引数、提案0件の「なし」、索引に既にある語の提案。
# 検査するのは述語であって、モデルの良し悪しではない。
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/domain-modeling-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PB="$ROOT/plugins/domain-modeling/skills/model-domain"
FIX="$ROOT/tests/fixtures"
WRITE_DOC_TEMPLATE="$ROOT/../write-doc-plugins/plugins/write-doc/skills/write-doc/assets/templates/domain-model.md"
PASS=0
FAIL=0

ok() { echo "  ok: $1"; PASS=$((PASS + 1)); }
ng() { echo "  NG: $1"; FAIL=$((FAIL + 1)); }
expect_fail() { "$@" >/dev/null 2>&1 && { ng "$* should fail"; return; }; ok "$* is rejected"; }
expect_ok() { "$@" >/dev/null 2>"$TMP/err" && { ok "$*"; return; }; ng "$* failed: $(head -3 "$TMP/err")"; }
expect_stderr() {
  local want="$1"; shift
  "$@" >/dev/null 2>"$TMP/err"
  if grep -qF "$want" "$TMP/err"; then ok "$want"; else ng "expected stderr to contain: $want / got: $(head -3 "$TMP/err")"; fi
}
# verify.py は候補本文を標準入力で受ける。
verify() { local candidate="$1"; shift; python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$TMP/order.md" "$@" < "$candidate"; }
expect_verify_ok() { verify "$1" >/dev/null 2>"$TMP/err" && { ok "verify < $(basename "$1")"; return; }; ng "verify < $(basename "$1") failed: $(head -3 "$TMP/err")"; }
expect_verify_stderr() {
  local want="$1" candidate="$2"
  verify "$candidate" >/dev/null 2>"$TMP/err"
  if grep -qF "$want" "$TMP/err"; then ok "$want"; else ng "expected stderr to contain: $want / got: $(head -3 "$TMP/err")"; fi
}

cp "$FIX/domain-rule.md" "$TMP/order.md"

# ── 正式な定義の索引（source.py） ───────────────────────────────────────────────
python3 "$PB/scripts/source.py" --playbook "$PB/playbook.yml" --source "$TMP/order.md" > "$TMP/index.json" 2>"$TMP/err" && ok "source.py prints the index to stdout" || ng "source.py: $(head -3 "$TMP/err")"
jq -e '(.terms|index("利用枠")) and (.concepts|index("予約")) and (.events|length)>0 and (.invariants|length)>0 and (.bdd|index("BDD-001")) and (.vocabulary|index("仮押さえ予約")) and (.states.holders|index("予約")) and (.counts.vocabulary>0)' "$TMP/index.json" >/dev/null && ok "index picks terms, concepts, events, invariants, states, BDD ids" || ng "index content"
[ -z "$(find "$TMP" -name 'source-index*' -o -name '*.index' 2>/dev/null)" ] && ok "index is not written to a file" || ng "index file was written"
# 負例: 契約の節（常に守られること）が無い正式な定義
grep -v '^# 常に守られること' "$TMP/order.md" | sed '/^| # | 常に守られること/,/^$/d' > "$TMP/order-noinv.md"
expect_stderr "正式な定義に契約の節が無いか空である" python3 "$PB/scripts/source.py" --playbook "$PB/playbook.yml" --source "$TMP/order-noinv.md"
# 境界例: 旧形の --output、正式な定義のpath欠落、正式な定義が無い
expect_fail python3 "$PB/scripts/source.py" --playbook "$PB/playbook.yml" --source "$TMP/order.md" --output "$TMP/index-old.json"
expect_fail python3 "$PB/scripts/source.py" --playbook "$PB/playbook.yml"
expect_stderr "通常ファイルではない" python3 "$PB/scripts/source.py" --playbook "$PB/playbook.yml" --source "$TMP/missing.md"

# ── 割り当ての検査（verify.py） ───────────────────────────────────────────
[ -f "$WRITE_DOC_TEMPLATE" ] \
  && rg -F '## 業務知識へ提案する概念' "$WRITE_DOC_TEMPLATE" >/dev/null \
  && rg -F '| 要素 | 種別 | 業務知識の語 | 目的（一文） |' "$WRITE_DOC_TEMPLATE" >/dev/null \
  && rg -F '| 概念 | なぜ要るか | 導いた業務ルール・BDD | 業務知識のどの節へ足すか |' "$WRITE_DOC_TEMPLATE" >/dev/null \
  && ok "write-docのdomain-model templateと検査契約の節・列名が一致" \
  || ng "write-docのdomain-model templateを検査契約の根拠として読めない"
expect_verify_ok "$FIX/domain-model.md"
verify "$FIX/domain-model.md" 2>/dev/null | jq -e '.verified==true and (.source_path|endswith("order.md")) and (.warnings|type=="array")' >/dev/null && ok "verify returns verified, source_path, warnings" || ng "verify output shape"
legacy_term=$(printf '\u6b63\u672c')
sed "s/業務知識の語/${legacy_term}の語/" "$FIX/domain-model.md" > "$TMP/model-legacy-element-column.md"
expect_verify_stderr "要素一覧に「要素 | 種別 | 業務知識の語 | 目的（一文）」の表が無いか空である" "$TMP/model-legacy-element-column.md"
# 境界例: 空の標準入力、正式な定義のpath欠落、旧形の --candidate / --source-index 引数、正式な定義が契約の節を持たない
: > "$TMP/empty.md"
expect_verify_stderr "標準入力が空" "$TMP/empty.md"
expect_fail_stdin() { local input="$1"; shift; "$@" < "$input" >/dev/null 2>&1 && { ng "$* < $(basename "$input") should fail"; return; }; ok "$* < $(basename "$input") is rejected"; }
expect_fail_stdin "$FIX/domain-model.md" python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml"
expect_fail_stdin "$FIX/domain-model.md" python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$TMP/order.md" --candidate "$FIX/domain-model.md"
expect_fail_stdin "$FIX/domain-model.md" python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$TMP/order.md" --source-index "$TMP/index.json"
expect_fail_stdin "$FIX/domain-model.md" python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$TMP/order-noinv.md"

# 境界例: 正式な定義本文には現れるが、明示索引に無い「予約者」を要素名にしても拒否する。
sed 's/^| 利用枠 | 値オブジェクト | 利用枠 |/| 予約者 | 値オブジェクト | 予約者 |/; s/^### 利用枠$/### 予約者/' "$FIX/domain-model.md" > "$TMP/model-prose-only.md"
expect_verify_stderr "索引に無い" "$TMP/model-prose-only.md"

# ── 業務知識へ提案する概念（D2）: 正例は fixture（会議室・繰上げの不成立を提案し、要素一覧には無い） ──
# 負例: 提案した語（会議室）を要素一覧にも載せる → 索引外より先に「混ざっている」で拒否
sed 's/^| 利用枠 | 値オブジェクト | 利用枠 |/| 会議室 | 値オブジェクト | 会議室 |/; s/^### 利用枠$/### 会議室/' "$FIX/domain-model.md" > "$TMP/model-proposal-mixed.md"
expect_verify_stderr "業務知識へ提案する概念の語が要素一覧に混ざっている" "$TMP/model-proposal-mixed.md"
# 負例: 提案の節に表も「なし」も無い
python3 - "$FIX/domain-model.md" "$TMP/model-proposal-empty.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"(## 業務知識へ提案する概念\n\n)(?:\|.*\n)+", r"\1提案は本文のどこかに書いた。\n", t)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_verify_stderr "業務知識へ提案する概念に「概念 | なぜ要るか | 導いた業務ルール・BDD | 業務知識のどの節へ足すか」の表が無い" "$TMP/model-proposal-empty.md"
# 境界例: 提案が0件なら「なし」とだけ書けば通る
python3 - "$FIX/domain-model.md" "$TMP/model-proposal-none.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"(## 業務知識へ提案する概念\n\n)(?:\|.*\n)+", r"\1なし\n", t)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_verify_ok "$TMP/model-proposal-none.md"
# 負例: 提案が引くBDD番号が正式な定義に無い
sed 's/業務ルール「予約待ち」の繰上げ、BDD-007/業務ルール「予約待ち」の繰上げ、BDD-099/' "$FIX/domain-model.md" > "$TMP/model-proposal-badbdd.md"
expect_verify_stderr "引くBDD番号が正式な定義に無い: BDD-099" "$TMP/model-proposal-badbdd.md"
# 負例: 足す先が正式な定義の節名ではない（実装の節）
sed 's/^\(| 繰上げの不成立 | .* | \)業務イベント、BDD |$/\1テーブル定義 |/' "$FIX/domain-model.md" > "$TMP/model-proposal-badtarget.md"
grep -q 'テーブル定義 |$' "$TMP/model-proposal-badtarget.md" || ng "fixture edit for bad target did not apply"
expect_verify_stderr "足す先が正式な定義の節名ではない: テーブル定義" "$TMP/model-proposal-badtarget.md"
# 境界例: 提案した語が既に索引にある（無断不利用。要素ではない）→ 通るが warning に出る
sed 's/^| 繰上げの不成立 | /| 無断不利用 | /' "$FIX/domain-model.md" > "$TMP/model-proposal-indexed.md"
verify "$TMP/model-proposal-indexed.md" 2>"$TMP/err" \
  | jq -e '.warnings | any(contains("業務知識へ提案する概念「無断不利用」は正式な定義の索引に既にある"))' >/dev/null && ok "indexed proposal passes with neutral warning" || ng "indexed proposal: $(head -2 "$TMP/err")"

# 負例1: 正式な定義に無い語を要素にする
sed 's/^| 利用枠 | 値オブジェクト | 利用枠 |/| 用紙ロット | 値オブジェクト | 用紙ロット |/; s/^### 利用枠$/### 用紙ロット/' "$FIX/domain-model.md" > "$TMP/model-unknown.md"
expect_verify_stderr "索引に無い" "$TMP/model-unknown.md"
# 負例2: 操作の契約に空欄がある
sed 's/^- 拒む理由: なし（判定だけで、拒まない）$/- 拒む理由: /' "$FIX/domain-model.md" > "$TMP/model-blank.md"
grep -q '^- 拒む理由: $' "$TMP/model-blank.md" || ng "fixture edit for blank field did not apply"
expect_verify_stderr "空欄がある" "$TMP/model-blank.md"
# 負例2b: モデル図にフィールドがある
sed 's/^        <<値オブジェクト>>$/        <<値オブジェクト>>\n        -会議室/' "$FIX/domain-model.md" > "$TMP/model-field.md"
expect_verify_stderr "フィールドかゲッター" "$TMP/model-field.md"
# 負例2c: モデル図に要素一覧に無いクラスがある
python3 - "$FIX/domain-model.md" "$TMP/model-extra-class.md" <<'PY'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
t = t.replace("classDiagram\n", "classDiagram\n    class Room[\"会議室\"] {\n        <<エンティティ>>\n    }\n", 1)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_verify_stderr "要素一覧に無いクラス" "$TMP/model-extra-class.md"
# 負例2e: 集約の図に責務が無い
python3 - "$FIX/domain-model.md" "$TMP/model-noboundary.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"^- 境界: .*$", "- 境界: ", t, count=1, flags=re.M)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_verify_stderr "「- 境界:」が無いか空" "$TMP/model-noboundary.md"
# 負例2f: 集約が2つ以上なのに「集約どうしの関係」が無い
python3 - "$FIX/domain-model.md" "$TMP/model-norel.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"### 集約どうしの関係\n\n```mermaid\n.*?```\n\n", "", t, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_verify_stderr "「### 集約どうしの関係」が無い" "$TMP/model-norel.md"
# 負例2d: 必須項目（####）が無い
sed '/^#### 協働相手$/,/^$/d' "$FIX/domain-model.md" > "$TMP/model-noitem.md"
expect_verify_stderr "必須項目（####）が無いか空" "$TMP/model-noitem.md"
# 語の存在だけでは責務境界を判定しない。同じ語が業務上の固有語か実装詳細かは意味評価へ残す。
sed 's/^会議室、利用開始、利用終了$/会議室、利用開始、利用終了のレコード/' "$FIX/domain-model.md" > "$TMP/model-dbword.md"
expect_verify_ok "$TMP/model-dbword.md"
# 負例3: 節の順序を入れ替える（未決を先頭へ）
python3 - "$FIX/domain-model.md" "$TMP/model-order.md" <<'PY'
import sys, re
text = open(sys.argv[1], encoding="utf-8").read()
parts = re.split(r"(?m)^(?=## )", text)
head, sections = parts[0], parts[1:]
mikketsu = [s for s in sections if s.startswith("## 未決")]
rest = [s for s in sections if not s.startswith("## 未決")]
open(sys.argv[2], "w", encoding="utf-8").write(head + "".join(mikketsu + rest))
PY
expect_verify_stderr "節と順序が契約に一致しない" "$TMP/model-order.md"
# 負例4: 正式な定義のBDDが対応表にも「対応しないBDD」にも無い
grep -v '^| BDD-013 |' "$FIX/domain-model.md" > "$TMP/model-nobdd.md"
expect_verify_stderr "BDD-013" "$TMP/model-nobdd.md"
# 境界例: 対応しないBDDを宣言すれば通り、warning に出る
sed 's/^- 対応しないBDD: なし$/- 対応しないBDD: BDD-013（利用枠の隣接を扱う要素が足りない）/' "$TMP/model-nobdd.md" > "$TMP/model-declared.md"
verify "$TMP/model-declared.md" 2>"$TMP/err" \
  | jq -e '.warnings | any(contains("対応しないと明示されたBDDがある"))' >/dev/null && ok "declared unmapped BDD passes with neutral warning" || ng "declared unmapped BDD: $(head -2 "$TMP/err")"
# 負例5: 実装の節が混入
printf '\n## テーブル定義\n\n| 列 | 型 |\n|---|---|\n| id | uuid |\n' >> "$TMP/model-declared.md"
expect_verify_stderr "実装の節が混入" "$TMP/model-declared.md"
# 負例6: 詳細にあって一覧に無い要素
printf '\n### 会議室\n\n| 項目 | 内容 |\n|---|---|\n| 目的 | x |\n' > "$TMP/extra.md"
python3 - "$FIX/domain-model.md" "$TMP/extra.md" "$TMP/model-extra.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read(); extra = open(sys.argv[2], encoding="utf-8").read()
marker = "## 集約の境界"
open(sys.argv[3], "w", encoding="utf-8").write(text.replace(marker, extra + "\n" + marker, 1))
PY
expect_verify_stderr "詳細にあって要素一覧に無い要素" "$TMP/model-extra.md"

# ── 一時file配管を持たない ───────────────────────────────────────────────
yq -o=json -I=0 '.' "$PB/playbook.yml" | jq -e '(.contract|has("cleanup")|not) and ([.steps[].id]|index("cleanup")|not) and ([.steps[].id]|index("prepare-work-directory")|not) and ([.steps[]|.provides[]?]|index("work_directory")|not) and ([.steps[]|.provides[]?]|index("candidate_model_path")|not)' >/dev/null \
  && [ ! -e "$PB/scripts/cleanup.py" ] && ok "playbook has no work directory, candidate file, or cleanup step" || ng "temporary-file plumbing remains"

echo "domain modeling scripts: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
