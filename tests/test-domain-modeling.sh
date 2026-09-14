#!/usr/bin/env bash
# model-domain が所有する script を、典型例・負例・境界例で実行する。
# 検査するのは述語であって、モデルの良し悪しではない。
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/domain-modeling-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PB="$ROOT/plugins/playbooks/domain/model-domain"
SK="$ROOT/plugins/skills/domain/domain-model"
FIX="$ROOT/tests/fixtures"
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

yq -o=json '.' "$PB/playbook.yml" | jq --arg root "$TMP" '{playbook:., repo_root:$root}' | yq -P > "$TMP/resolved.yml"

# ── 契約の固定（validate-config.sh） ────────────────────────────────────
yq -o=json '.' "$PB/playbook.yml" > "$TMP/pb.json"
expect_ok bash "$PB/scripts/validate-config.sh" "$TMP/pb.json"
jq '.steps |= map(select(.id != "verify"))' "$TMP/pb.json" > "$TMP/pb-noverify.json"
expect_fail bash "$PB/scripts/validate-config.sh" "$TMP/pb-noverify.json"
jq '.contract.element_kinds += ["リポジトリ"]' "$TMP/pb.json" > "$TMP/pb-kind.json"
expect_fail bash "$PB/scripts/validate-config.sh" "$TMP/pb-kind.json"

# ── 根拠づけ（ground.py） ────────────────────────────────────────────────
cat > "$TMP/dialogue.yml" <<'YAML'
contract: grill/grill
version: 1
status: completed
decisions:
  - id: q1
    question: 予約と予約待ちは別の集約にするか
    answer: 別にする
    rationale: 予約待ちは予約より長く生きるため
open_questions:
  - id: q2
    question: 同時仮押さえの排他をどこで保証するか
    state: open
    reason: 設計資料で決める
YAML
cp "$FIX/domain-rule.md" "$TMP/order.md"
expect_ok python3 "$PB/scripts/ground.py" --config "$TMP/resolved.yml" --dialogue-output "$TMP/dialogue.yml" --source "$TMP/order.md" --output "$TMP/grounded.json"
jq -e '.source_path and (.decisions|length==1) and (.open_questions|length==1) and .existing_document_path==null' "$TMP/grounded.json" >/dev/null && ok "grounded input carries source, decisions, open questions" || ng "grounded input shape"
expect_fail python3 "$PB/scripts/ground.py" --config "$TMP/resolved.yml" --dialogue-output "$TMP/dialogue.yml" --source "relative/order.md" --output "$TMP/g2.json"
cp "$TMP/order.md" "$TMP/order.txt"
expect_fail python3 "$PB/scripts/ground.py" --config "$TMP/resolved.yml" --dialogue-output "$TMP/dialogue.yml" --source "$TMP/order.txt" --output "$TMP/g3.json"
sed 's/status: completed/status: failed/' "$TMP/dialogue.yml" > "$TMP/dialogue-failed.yml"
expect_fail python3 "$PB/scripts/ground.py" --config "$TMP/resolved.yml" --dialogue-output "$TMP/dialogue-failed.yml" --source "$TMP/order.md" --output "$TMP/g4.json"

# ── 正本の索引（source.py） ───────────────────────────────────────────────
expect_ok python3 "$PB/scripts/source.py" --config "$TMP/resolved.yml" --grounded-input "$TMP/grounded.json" --output "$TMP/index.json"
jq -e '(.terms|index("利用枠")) and (.concepts|index("予約")) and (.events|length)>0 and (.invariants|length)>0 and (.bdd|index("BDD-001")) and (.vocabulary|index("仮押さえ予約")) and (.states.holders|index("予約"))' "$TMP/index.json" >/dev/null && ok "index picks terms, concepts, events, invariants, states, BDD ids" || ng "index content"
# 負例: 契約の節（常に守られること）が無い正本
grep -v '^# 常に守られること' "$TMP/order.md" | sed '/^| # | 常に守られること/,/^$/d' > "$TMP/order-noinv.md"
jq --arg s "$TMP/order-noinv.md" '.source_path=$s' "$TMP/grounded.json" > "$TMP/grounded-noinv.json"
expect_stderr "正本に契約の節が無いか空である" python3 "$PB/scripts/source.py" --config "$TMP/resolved.yml" --grounded-input "$TMP/grounded-noinv.json" --output "$TMP/index-noinv.json"

# ── 割り当ての検査（verify.py） ───────────────────────────────────────────
expect_ok python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$FIX/domain-model.md" --source-index "$TMP/index.json"
python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$FIX/domain-model.md" --source-index "$TMP/index.json" 2>/dev/null \
  | jq -e '.warnings | any(contains("仮押さえ期限"))' >/dev/null && ok "index-外の語は warning として報告される" || ng "expected warning for out-of-index term"

# 負例1: 正本に無い語を要素にする
sed 's/^| 利用枠 | 値オブジェクト | 利用枠 |/| 用紙ロット | 値オブジェクト | 用紙ロット |/; s/^### 利用枠$/### 用紙ロット/' "$FIX/domain-model.md" > "$TMP/model-unknown.md"
expect_stderr "正本に無い" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-unknown.md" --source-index "$TMP/index.json"
# 負例2: 操作の契約に空欄がある
sed 's/^- 拒む理由: なし（判定だけで、拒まない）$/- 拒む理由: /' "$FIX/domain-model.md" > "$TMP/model-blank.md"
grep -q '^- 拒む理由: $' "$TMP/model-blank.md" || ng "fixture edit for blank field did not apply"
expect_stderr "空欄がある" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-blank.md" --source-index "$TMP/index.json"
# 負例2b: モデル図にフィールドがある
sed 's/^        <<値オブジェクト>>$/        <<値オブジェクト>>\n        -会議室/' "$FIX/domain-model.md" > "$TMP/model-field.md"
expect_stderr "フィールドかゲッター" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-field.md" --source-index "$TMP/index.json"
# 負例2c: モデル図に要素一覧に無いクラスがある
python3 - "$FIX/domain-model.md" "$TMP/model-extra-class.md" <<'PY'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
t = t.replace("classDiagram\n", "classDiagram\n    class Room[\"会議室\"] {\n        <<エンティティ>>\n    }\n", 1)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_stderr "要素一覧に無いクラス" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-extra-class.md" --source-index "$TMP/index.json"
# 負例2e: 集約の図に責務が無い
python3 - "$FIX/domain-model.md" "$TMP/model-noboundary.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"^- 境界: .*$", "- 境界: ", t, count=1, flags=re.M)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_stderr "「- 境界:」が無いか空" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-noboundary.md" --source-index "$TMP/index.json"
# 負例2f: 集約が2つ以上なのに「集約どうしの関係」が無い
python3 - "$FIX/domain-model.md" "$TMP/model-norel.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"### 集約どうしの関係\n\n```mermaid\n.*?```\n\n", "", t, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_stderr "「### 集約どうしの関係」が無い" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-norel.md" --source-index "$TMP/index.json"
# 負例2d: 必須項目（####）が無い
sed '/^#### 協働相手$/,/^$/d' "$FIX/domain-model.md" > "$TMP/model-noitem.md"
expect_stderr "必須項目（####）が無いか空" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-noitem.md" --source-index "$TMP/index.json"
# 負例2g: データの持ち方の語
sed 's/^会議室、利用開始、利用終了$/会議室、利用開始、利用終了のレコード/' "$FIX/domain-model.md" > "$TMP/model-dbword.md"
expect_stderr "データの持ち方の語がある" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-dbword.md" --source-index "$TMP/index.json"
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
expect_stderr "節と順序が契約に一致しない" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-order.md" --source-index "$TMP/index.json"
# 負例4: 正本のBDDが対応表にも「対応しないBDD」にも無い
grep -v '^| BDD-013 |' "$FIX/domain-model.md" > "$TMP/model-nobdd.md"
expect_stderr "BDD-013" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-nobdd.md" --source-index "$TMP/index.json"
# 境界例: 対応しないBDDを宣言すれば通り、warning に出る
sed 's/^- 対応しないBDD: なし$/- 対応しないBDD: BDD-013（利用枠の隣接を扱う要素が足りない）/' "$TMP/model-nobdd.md" > "$TMP/model-declared.md"
python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-declared.md" --source-index "$TMP/index.json" 2>"$TMP/err" \
  | jq -e '.warnings | any(contains("対応しないBDDがある"))' >/dev/null && ok "declared unmapped BDD passes with warning" || ng "declared unmapped BDD: $(head -2 "$TMP/err")"
# 負例5: 実装の節が混入
printf '\n## テーブル定義\n\n| 列 | 型 |\n|---|---|\n| id | uuid |\n' >> "$TMP/model-declared.md"
expect_stderr "実装の節が混入" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-declared.md" --source-index "$TMP/index.json"
# 負例6: 詳細にあって一覧に無い要素
printf '\n### 会議室\n\n| 項目 | 内容 |\n|---|---|\n| 目的 | x |\n' > "$TMP/extra.md"
python3 - "$FIX/domain-model.md" "$TMP/extra.md" "$TMP/model-extra.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read(); extra = open(sys.argv[2], encoding="utf-8").read()
marker = "## 集約の境界"
open(sys.argv[3], "w", encoding="utf-8").write(text.replace(marker, extra + "\n" + marker, 1))
PY
expect_stderr "詳細にあって要素一覧に無い要素" python3 "$PB/scripts/verify.py" --config "$TMP/resolved.yml" --candidate "$TMP/model-extra.md" --source-index "$TMP/index.json"

# ── 素材の束ね（material.sh） ────────────────────────────────────────────
expect_ok bash "$PB/scripts/material.sh" --config "$TMP/resolved.yml" --model "$FIX/domain-model.md" --grounded-input "$TMP/grounded.json" --source-index "$TMP/index.json" --output "$TMP/material.md"
grep -q '^## 検査済みモデル' "$TMP/material.md" && grep -q '別にする' "$TMP/material.md" && grep -q '同時仮押さえの排他' "$TMP/material.md" && ok "material bundles model, decisions, open questions" || ng "material content"
expect_fail bash "$PB/scripts/material.sh" --config "$TMP/resolved.yml" --model "$FIX/domain-model.md" --grounded-input "$TMP/grounded.json" --output "$TMP/m2.md"

# ── 候補の保存（artifact.py） ────────────────────────────────────────────
mkdir -p "$TMP/out/candidates"
cat > "$TMP/skill.json" <<JSON
{"artifact_kind":"domain-model-candidate","output_dir":"$TMP/out/candidates","required_sections":["目的と範囲","要素一覧","各要素の詳細","集約の境界","状態と型の分割","ドメインイベント","BDDとの対応","捨てた割り当て","未決","この資料に書かないもの"],"required_nonempty_sections":["目的と範囲","要素一覧","各要素の詳細","集約の境界","状態と型の分割","ドメインイベント","BDDとの対応","捨てた割り当て","未決","この資料に書かないもの"]}
JSON
expect_ok python3 "$SK/scripts/artifact.py" write --config "$TMP/skill.json" --topic order --body-file "$FIX/domain-model.md"
[ -f "$TMP/out/candidates/order.md" ] && ok "candidate saved" || ng "candidate not saved"
expect_status() { local want="$1"; shift; "$@" >/dev/null 2>&1; local got=$?; [ "$got" = "$want" ] && ok "$* exits $want" || ng "$* exits $got, expected $want"; }
expect_status 3 python3 "$SK/scripts/artifact.py" write --config "$TMP/skill.json" --topic order --body-file "$FIX/domain-model.md"
printf '## 目的と範囲\n\nx\n' > "$TMP/partial.md"
expect_fail python3 "$SK/scripts/artifact.py" check --config "$TMP/skill.json" --topic partial --body-file "$TMP/partial.md"

# ── 後片付け（cleanup.py） ───────────────────────────────────────────────
git -C "$TMP" init -q
mkdir -p "$TMP/domain-model"
cp "$FIX/domain-model.md" "$TMP/domain-model/order-model.md"
cp "$TMP/index.json" "$TMP/index-copy.json"
expect_ok python3 "$PB/scripts/cleanup.py" --config "$TMP/resolved.yml" --artifact "source_index=$TMP/index-copy.json" --artifact "domain_model_document_path=$TMP/domain-model/order-model.md"
[ ! -e "$TMP/index-copy.json" ] && [ -f "$TMP/domain-model/order-model.md" ] && ok "cleanup removes index and keeps document" || ng "cleanup outcome"
expect_fail python3 "$PB/scripts/cleanup.py" --config "$TMP/resolved.yml" --artifact "source_index=$TMP/index.json"
expect_fail python3 "$PB/scripts/cleanup.py" --config "$TMP/resolved.yml" --artifact "unknown=$TMP/index.json" --artifact "domain_model_document_path=$TMP/domain-model/order-model.md"

echo "domain modeling scripts: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
