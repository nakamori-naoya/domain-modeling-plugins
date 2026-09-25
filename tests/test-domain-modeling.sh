#!/usr/bin/env bash
# model-domain が所有する script（source.py / verify.py）を、正例・反例・境界例で実行する。
# 基準資料: playbook.yml の contract と、domain-rule資料（fixtures/library-lending/domain-rule.md）。
# 入力: domain-rule資料のpath（source.py）、domain-rule資料のpath＋標準入力の候補本文（verify.py）。
# 正例: fixtures/library-lending/domain-model.md。業務の決まりが薄い境界例: fixtures/member-directory。反例と境界例は正例を1か所ずつ変えて作る。
# 検査するのは構造の述語であって、モデルの良し悪しではない。
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/domain-modeling-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PB="$ROOT/plugins/domain-modeling/skills/model-domain"
FIX="$ROOT/tests/fixtures/library-lending"
PASS=0
FAIL=0

ok() { echo "  ok: $1"; PASS=$((PASS + 1)); }
ng() { echo "  NG: $1"; FAIL=$((FAIL + 1)); }
source_index() { python3 "$PB/scripts/source.py" --playbook "$PB/playbook.yml" --source "$1"; }
verify() { python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$TMP/rule.md" < "$1"; }
expect_ok() {
  verify "$1" >"$TMP/out" 2>"$TMP/err" && { ok "$2"; return; }
  ng "$2: $(head -3 "$TMP/err")"
}
expect_error() {
  local want="$1" candidate="$2"
  if verify "$candidate" >/dev/null 2>"$TMP/err"; then ng "should fail: $want"; return; fi
  if grep -qF "$want" "$TMP/err"; then ok "$want"; else ng "expected: $want / got: $(head -3 "$TMP/err")"; fi
}
# 正例を1か所だけ置き換えた候補を作る。置き換え前の文字列が無ければ試験自体の誤りとして落とす。
mutate() {
  local out="$1" old="$2" new="$3"
  python3 - "$FIX/domain-model.md" "$out" "$old" "$new" <<'PY'
import sys
src, out, old, new = sys.argv[1:5]
text = open(src, encoding="utf-8").read()
if old not in text:
    sys.exit(f"mutate: 置き換え前の文字列が正例に無い: {old!r}")
open(out, "w", encoding="utf-8").write(text.replace(old, new, 1))
PY
  [ $? -eq 0 ] || ng "mutate failed for $out"
}

cp "$FIX/domain-rule.md" "$TMP/rule.md"

# ── 索引（source.py） ──────────────────────────────────────────────
source_index "$TMP/rule.md" > "$TMP/index.json" 2>"$TMP/err" && ok "source.py prints the index" || ng "source.py: $(head -3 "$TMP/err")"
jq -e '(.vocabulary|index("貸出")) and (.vocabulary|index("本が貸し出された")) and (.commands==["本を借りる","本を返す","延滞にする"]) and (.state_holders==["貸出"]) and (.states==["貸出中","延滞","返却済み"]) and (.bdd|length)==13' "$TMP/index.json" >/dev/null \
  && ok "index holds vocabulary, commands (not queries), states, BDD ids" || ng "index content: $(cat "$TMP/index.json")"
# 反例: ユビキタス言語の表にコマンドの行が無いdomain-rule資料
python3 - "$TMP/rule.md" "$TMP/rule-nocommands.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"^\|[^\n]*\| コマンド \|\n", "", t, flags=re.M)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
source_index "$TMP/rule-nocommands.md" >/dev/null 2>"$TMP/err" && ng "missing command rows should fail" || { grep -qF "種類が「コマンド」の行" "$TMP/err" && ok "missing command rows are rejected" || ng "diagnostic: $(head -2 "$TMP/err")"; }
# 反例: ユビキタス言語の表が無い
python3 - "$TMP/rule.md" "$TMP/rule-notable.md" <<'PY'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write(t.replace("| 業務の言葉 | 英名 | 種類 |", "| 語 | 英名 | 種類 |"))
PY
source_index "$TMP/rule-notable.md" >/dev/null 2>"$TMP/err" && ng "missing vocabulary table should fail" || { grep -qF "ユビキタス言語の表が0個" "$TMP/err" && ok "missing vocabulary table is rejected" || ng "diagnostic: $(head -2 "$TMP/err")"; }
# 境界例: 見出しの名前を変えても（結論を入れても）索引は同じ
python3 - "$TMP/rule.md" "$TMP/rule-headings.md" <<'PY'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
t = t.replace("# 業務の行い\n", "# 利用者と図書館が行うこと\n").replace("# 状態と、その移り変わり\n", "# 貸出は返却で終わる\n").replace("# BDD\n", "# 場面で確かめる\n")
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
source_index "$TMP/rule-headings.md" > "$TMP/index-headings.json" 2>"$TMP/err" && cmp -s <(jq -S 'del(.source_path)' "$TMP/index.json") <(jq -S 'del(.source_path)' "$TMP/index-headings.json") \
  && ok "renamed headings give the same index" || ng "renamed headings: $(head -2 "$TMP/err")"
# 境界例: title の無い状態遷移図は状態を持つものとして数えない
python3 - "$TMP/rule.md" "$TMP/rule-untitled.md" <<'PY'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[2], "w", encoding="utf-8").write(t.replace("---\ntitle: 貸出\n---\n", ""))
PY
source_index "$TMP/rule-untitled.md" 2>/dev/null | jq -e '.state_holders==[] and .states==[]' >/dev/null && ok "untitled state diagram is not a state holder" || ng "untitled state diagram"
# 境界例: domain-rule資料のpathが相対、存在しない
source_index "fixtures/rule.md" >/dev/null 2>&1 && ng "relative source should fail" || ok "relative source path is rejected"
source_index "$TMP/missing.md" >/dev/null 2>&1 && ng "missing source should fail" || ok "missing source is rejected"

# ── 検査（verify.py） ─────────────────────────────────────────────
# 検査が読む目印は write-doc の公開契約が domain-model 型について宣言する。目印と verify.py の一致は、
# 兄弟 checkout の write-doc の見本（その目印で書いた記載例）を verify.py に通して確かめる。見本が無ければ失敗させる。
EXAMPLE="$ROOT/../write-doc-plugins/plugins/write-doc/skills/write-doc/assets/examples/domain-model.example.md"
if [ -f "$EXAMPLE" ] && python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$TMP/rule.md" < "$EXAMPLE" >/dev/null 2>"$TMP/err"; then
  ok "write-doc domain-model example passes verify.py"
else
  ng "write-doc domain-model example does not pass verify.py: $EXAMPLE $(head -3 "$TMP/err" 2>/dev/null)"
fi
expect_ok "$FIX/domain-model.md" "library example passes"
jq -e '.verified==true and (.source_path|endswith("rule.md")) and (.warnings|type=="array")' "$TMP/out" >/dev/null && ok "verify returns verified, source_path, warnings" || ng "verify output shape"

# 境界例: 空の標準入力
: > "$TMP/empty.md"
expect_error "標準入力が空" "$TMP/empty.md"
# 反例: 索引に無い語をクラスにする（業務知識の文中にだけ現れる語も同じ）
mutate "$TMP/m1.md" 'class BorrowerStanding["貸出状況"]' 'class BorrowerStanding["利用者カード"]'
expect_error "クラス「利用者カード」はdomain-rule資料の索引に無い語" "$TMP/m1.md"
# 反例: 種別が契約に無い
mutate "$TMP/m2.md" '<<値オブジェクト・文脈共有>>' '<<外部の集約>>'
expect_error "種別「外部の集約」は契約に無い" "$TMP/m2.md"
# 反例: 印が文脈共有以外
mutate "$TMP/m3.md" '<<値オブジェクト・文脈共有>>' '<<値オブジェクト・共通>>'
expect_error "種別「値オブジェクト・共通」は契約に無い" "$TMP/m3.md"
# 反例: 種別が無い
mutate "$TMP/m4.md" $'        <<値オブジェクト>>\n    }\n    class DueDate' $'    }\n    class DueDate'
expect_error "種別（<<…>>）をちょうど1つ持たない" "$TMP/m4.md"
# 反例: 値オブジェクトに判定だけの操作
mutate "$TMP/m5.md" $'<<値オブジェクト>>\n    }\n    class BorrowerStanding' $'<<値オブジェクト>>\n        +過ぎているか(日付)\n    }\n    class BorrowerStanding'
expect_error "に操作がある" "$TMP/m5.md"
# 反例: 集約ルートにフィールド
mutate "$TMP/m6.md" '        +本を返す()' $'        +本を返す()\n        -返却期限'
expect_error "コマンド以外の行がある" "$TMP/m6.md"
# 反例: コマンドがクエリか、domain-rule資料に無い
mutate "$TMP/m7.md" '        +本を返す()' $'        +本を返す()\n        +借りている本を確かめる()'
expect_error "コマンド「借りている本を確かめる」は、domain-rule資料の業務の行いのコマンドに無い" "$TMP/m7.md"
# 反例: ドメインイベントに中身がある
mutate "$TMP/m8.md" $'<<ドメインイベント>>\n    }\n    class LoanReturned' $'<<ドメインイベント>>\n        貸出日\n    }\n    class LoanReturned'
expect_error "ドメインイベント「本が貸し出された」に中身の行がある" "$TMP/m8.md"
# 境界例: 取り得る値が限られる値オブジェクトは値の行を持ってよい
mutate "$TMP/b1.md" $'<<値オブジェクト>>\n    }\n    class BorrowerStanding' $'<<値オブジェクト>>\n        14日後\n    }\n    class BorrowerStanding'
expect_ok "$TMP/b1.md" "value object may list its possible values"
# 反例: コマンドの引数が図のクラスに無い（業務知識の語でない「日付」）
mutate "$TMP/m21.md" '+延滞にする(判定日時)' '+延滞にする(日付)'
expect_error "引数「日付」が、同じ図のクラスのラベルに無い" "$TMP/m21.md"
# 反例: 関係の線が宣言の無いクラスを結ぶ
mutate "$TMP/m9.md" '    Loan *-- DueDate' $'    Loan *-- DueDate\n    Loan *-- Ghost'
expect_error "宣言の無いクラスを結んでいる: Ghost" "$TMP/m9.md"
# 境界例: 見出しの文言は読まない。集約の節の見出しにも小見出しにも結論を入れてよい
mutate "$TMP/b5.md" $'\n## 貸出\n' $'\n## 貸出の境界は一冊の本に引いた\n'
expect_ok "$TMP/b5.md" "a concluding H2 for the aggregate section passes"
mutate "$TMP/b6.md" '### 守ること' '### 同時に借りられたときの上限は、貸出を記録する側が守る'
expect_ok "$TMP/b6.md" "a concluding H3 inside the aggregate section passes"
# 境界例: 拒む理由の節は、見出しの最初の「:」より前がコマンド名なら、後ろに結論を書いてよい
mutate "$TMP/b7.md" '### 本を返す' '### 本を返す: 返却済みの貸出だけを拒む'
expect_ok "$TMP/b7.md" "a rejection section named before the colon passes"
# 反例: 拒む理由の節の見出しがコマンド名で始まらない
mutate "$TMP/m10.md" '### 本を返す' '### 返却済みの貸出は拒む'
expect_error "拒む理由を書く「### 本を返す」節" "$TMP/m10.md"
# 反例: 拒む理由の節が、状態遷移図を含む節の外にある
python3 - "$FIX/domain-model.md" "$TMP/m11.md" <<'PY2'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
section = re.search(r"### 本を返す\n.*?(?=### 延滞にする)", t, flags=re.S).group(0)
t = t.replace(section, "", 1).replace("## 未決\n", "## 未決\n\n" + section, 1)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY2
expect_error "拒む理由を書く「### 本を返す」節" "$TMP/m11.md"
# 境界例: コマンドの節は求めない（書くことが無いコマンドの節を消しても通る）
python3 - "$FIX/domain-model.md" "$TMP/b4.md" <<'PY2'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"### 本を借りる\n.*?(?=### 本を返す)", "", t, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY2
expect_ok "$TMP/b4.md" "a creation command without its own section passes"
# 反例: 受け付けない状態（返却済み）があるのに、拒む理由の節が無い
python3 - "$FIX/domain-model.md" "$TMP/m22.md" <<'PY2'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"### 本を返す\n.*?(?=### 延滞にする)", "", t, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY2
expect_error "状態 返却済み から矢印が無いのに、拒む理由を書く「### 本を返す」節" "$TMP/m22.md"
# 反例: 状態を持つ集約に状態遷移図が無い
python3 - "$FIX/domain-model.md" "$TMP/m12.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"```mermaid\nstateDiagram-v2\n.*?```\n", "", t, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_error "domain-rule資料で状態を持つ「貸出」の状態遷移図が無い" "$TMP/m12.md"
# 反例: 状態遷移図の状態がdomain-rule資料に無い
mutate "$TMP/m13.md" '    貸出中 --> 延滞: 延滞にする' '    貸出中 --> 督促中: 延滞にする'
expect_error "状態「督促中」はdomain-rule資料の状態に無い" "$TMP/m13.md"
# 反例: 矢印のラベルが業務イベント（コマンドではない）
mutate "$TMP/m14.md" '    貸出中 --> 延滞: 延滞にする' '    貸出中 --> 延滞: 貸出が延滞になった'
expect_error "ラベル 貸出が延滞になった が、クラス図で集約ルートに描いたコマンドではない" "$TMP/m14.md"
# 境界例: 終端への矢印はラベル無しでよい
expect_ok "$FIX/domain-model.md" "unlabeled transition to [*] passes"
# 反例: domain-rule資料に無いBDD番号
mutate "$TMP/m15.md" '（BDD-010〜012）' '（BDD-099）'
expect_error "本文が引くBDD番号がdomain-rule資料に無い: BDD-099" "$TMP/m15.md"
# 境界例: 「BDD-001〜006」は範囲として引いたことになる
verify "$FIX/domain-model.md" 2>/dev/null | jq -e '.warnings == []' >/dev/null && ok "BDD ranges count as cited" || ng "BDD range citation"
# 境界例: 引かないBDDは失敗ではなく warning
mutate "$TMP/b2.md" '（BDD-005、BDD-013）' '（BDD-005）'
verify "$TMP/b2.md" 2>/dev/null | jq -e '.warnings | any(contains("BDD-013"))' >/dev/null && ok "uncited BDD is a warning" || ng "uncited BDD warning"
# 境界例: 提案が無ければ節ごと置かない
python3 - "$FIX/domain-model.md" "$TMP/b3.md" <<'PY'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
t = re.sub(r"## 業務知識への提案\n.*?(?=## 未決)", "", t, flags=re.S)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY
expect_ok "$TMP/b3.md" "no proposal section passes"
# 境界例: 業務の決まりが薄い文脈（会員の住所録）は、クラス図と未決だけで通る
python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$ROOT/tests/fixtures/member-directory/domain-rule.md" < "$ROOT/tests/fixtures/member-directory/domain-model.md" >/dev/null 2>"$TMP/err" \
  && ok "thin CRUD context passes with only a class diagram and open questions" || ng "thin CRUD context: $(head -3 "$TMP/err")"
python3 "$PB/scripts/verify.py" --playbook "$PB/playbook.yml" --source "$ROOT/tests/fixtures/member-directory/domain-rule.md" < "$ROOT/tests/fixtures/member-directory/domain-model.md" 2>/dev/null | jq -e '.warnings == []' >/dev/null \
  && ok "thin context without aggregate sections gets no uncited-BDD warning" || ng "thin context warnings"
# 反例: classDiagram が無い
mutate "$TMP/m18.md" $'```mermaid\nclassDiagram' $'```mermaid\nflowchart LR'
expect_error "Mermaid classDiagram が無い" "$TMP/m18.md"
# 境界例: クラス図の節の見出しに結論を入れてよい
mutate "$TMP/b8.md" '## クラス図' '## 集約は貸出一つで、利用者と本は番号で指す'
expect_ok "$TMP/b8.md" "a concluding H2 for the class diagram passes"
# 反例: 二つの H2 節に同じ集約の状態遷移図を分ける
python3 - "$FIX/domain-model.md" "$TMP/m19.md" <<'PY2'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
diagram = re.search(r"```mermaid\nstateDiagram-v2\n.*?```\n", t, flags=re.S).group(0)
t = t.replace("## 未決\n", "## 未決\n\n" + diagram, 1)
open(sys.argv[2], "w", encoding="utf-8").write(t)
PY2
expect_error "「貸出」の状態遷移図が二つ以上の H2 節に分かれている" "$TMP/m19.md"
# 反例: 状態遷移図に、ラベルの無い途中の矢印がある
mutate "$TMP/m20.md" '    貸出中 --> 延滞: 延滞にする' '    貸出中 --> 延滞'
expect_error "にコマンドのラベルが無い" "$TMP/m20.md"

# ── 一時file配管を持たない ─────────────────────────────────────────
yq -o=json -I=0 '.' "$PB/playbook.yml" | jq -e '([.steps[].id]==["index-source","settle","assign","verify","document"]) and ([.steps[]|.provides[]?]|index("work_directory")|not)' >/dev/null \
  && ok "playbook has the five steps and no work directory" || ng "playbook steps"

echo "domain modeling scripts: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
