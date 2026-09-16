#!/usr/bin/env bash
# Scenario: repositoryのpackage、manifest、marketplace、公開入口のscript契約、構文が一致する
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# 継承したenvで検査が変わらないようにする。開発用mapやtest cacheが外から入っていると、
# 「解決できないこと」を見る負の試験が黙って解決してしまい、緑になる。
unset HARNESS_PLUGIN_DEV_ROOTS HARNESS_PLUGIN_CACHE_ROOT HARNESS_PLUGIN_ALLOW_PRERELEASE
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/plugin-repository-validation.XXXXXX") || exit 2
export TMPDIR="$TMP_ROOT"
trap 'rm -rf "$TMP_ROOT"' EXIT
failed=0
PACKAGE="$ROOT/plugins/domain-modeling"
ENTRY="$PACKAGE/skills/model-domain"

# 保守用の共有tool（正本はproduct-planning-plugins/shared/runtime-source）。
python3 "$ROOT/scripts/test-hardening.py" || failed=1
bash "$ROOT/scripts/validate-marketplace.sh" "$ROOT" || failed=1
bash "$ROOT/scripts/test-marketplace-validation.sh" || failed=1

# 公開入口の隣接playbook.yml: version 2、requiresは外部packageだけ、stepsのscriptは入口scripts/配下に実在する。
pb="$ENTRY/playbook.yml"
yq -o=json -I=0 '.' "$pb" | jq -e '.version==2 and .name=="model-domain" and (.requires|length>0) and all(.requires[]; type=="object" and ((keys|sort)==["marketplace","plugin"]) and .marketplace!="domain-modeling")' >/dev/null || { echo "[fail] playbook.yml の version / name / requires"; failed=1; }
while IFS= read -r script; do
  [ -f "$ENTRY/$script" ] || { echo "[fail] steps が指す script が無い: $script"; failed=1; }
done < <(yq -o=json -I=0 '.' "$pb" | jq -r '.steps[] | select(.script) | .script')
# 禁止参照形（root validatorと同じ4 token）が配布物に無い。
if rg -n -e '\$\{\.' -e '<!-- BEGIN shared:' -e 'CLAUDE_PLUGIN_ROOT' -e 'BUNDLE_ROOT' "$PACKAGE" >/dev/null; then
  echo "[fail] 禁止参照形が配布物に残っている"; failed=1
fi
# package配下のSKILL.mdは公開入口だけ（内部skillは無い）。
skill_count=$(find "$PACKAGE" -name SKILL.md -type f | wc -l | tr -d ' ')
[ "$skill_count" = "1" ] || { echo "[fail] SKILL.md が $skill_count 本（公開入口1本のはず）"; failed=1; }

while IFS= read -r script; do bash -n "$script" || failed=1; done < <(find "$ROOT" -type f -name '*.sh' | sort)
while IFS= read -r script; do PYTHONPYCACHEPREFIX="$TMP_ROOT/pycache" python3 -m py_compile "$script" || failed=1; done < <(find "$ROOT" -type f -name '*.py' | sort)

# ── 消費側の契約lint — 実際の配布物から検出語を作る ─────────────────────
# lintはSKILL.md・README・references・scripts・.harness-plugins配下の設定を含む全行を見る。
# 検出語は手書きせず、外部依存として実在するproviderのmanifestから作るので、依存先の実配布物が要る。
lint_consumer_contract() {
  local map="$TMP_ROOT/lint-dev-map.json"
  local grill write_doc parent
  grill= write_doc=
  parent="${GITHUB_WORKSPACE:-$ROOT}"
  [ -d "$parent/grill-plugins/plugins/grill" ] && grill="$parent/grill-plugins/plugins/grill"
  [ -d "$parent/write-doc-plugins/plugins/write-doc" ] && write_doc="$parent/write-doc-plugins/plugins/write-doc"
  parent="$ROOT"
  for _ in 1 2 3 4; do
    [ -z "$grill" ] && [ -d "$parent/grill-plugins/plugins/grill" ] && grill="$parent/grill-plugins/plugins/grill"
    [ -z "$write_doc" ] && [ -d "$parent/write-doc-plugins/plugins/write-doc" ] && write_doc="$parent/write-doc-plugins/plugins/write-doc"
    parent="$(dirname "$parent")"
  done
  if [ ! -d "$grill" ] || [ ! -d "$write_doc" ]; then
    echo "[error] 依存先の配布物checkout（grill-plugins / write-doc-plugins）が無い。fixtureだけで緑にしない" >&2
    return 1
  fi
  grill=$(cd "$grill" && pwd -P)
  write_doc=$(cd "$write_doc" && pwd -P)
  jq -n --arg g "$grill" --arg w "$write_doc" \
    '{schema:1,dependencies:{"grill/grill":$g,"write-doc/write-doc":$w}}' > "$map" || return 1
  local status=0 runtime
  for runtime in claude codex; do
    HARNESS_PLUGIN_DEV_ROOTS="$map" python3 "$ROOT/scripts/lint-consumer-contract.py" \
      --repo "$ROOT" --runtime "$runtime" || status=1
  done
  return "$status"
}

lint_consumer_contract || failed=1
bash "$ROOT/tests/test-domain-modeling.sh" || failed=1
if [ "$failed" -eq 0 ]; then echo 'Validation: passed'; else echo 'Validation: failed'; fi
[ "$failed" -eq 0 ]
