#!/usr/bin/env bash
# Scenario: repositoryのpackage、manifest、marketplace、公開入口のscript契約、構文が一致する
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/plugin-repository-validation.XXXXXX") || exit 2
export TMPDIR="$TMP_ROOT"
trap 'rm -rf "$TMP_ROOT"' EXIT
failed=0
PACKAGE="$ROOT/plugins/domain-modeling"
ENTRY="$PACKAGE/skills/model-domain"

# 保守toolの参照元は兄弟checkout harness-tools だけ。複製を持たず、無ければ止まる（fixtureで代用しない）。
TOOLS="$ROOT/../harness-tools/tools"
[ -d "$TOOLS" ] || { echo "[error] 兄弟 checkout harness-tools が無い: $TOOLS" >&2; exit 2; }
python3 "$TOOLS/validate-plugin-repository.py" "$ROOT" || failed=1
python3 "$TOOLS/validate-plugin-repository.py" --self-test || failed=1
python3 "$TOOLS/test-hardening.py" --repository "$ROOT" || failed=1

# 禁止参照形（root validatorと同じ4 token）が配布物に無い。
if rg -n -e '\$\{\.' -e '<!-- BEGIN shared:' -e 'CLAUDE_PLUGIN_ROOT' -e 'BUNDLE_ROOT' "$PACKAGE" >/dev/null; then
  echo "[fail] 禁止参照形が配布物に残っている"; failed=1
fi
# package配下のSKILL.mdは公開入口だけ（内部skillは無い）。
skill_count=$(find "$PACKAGE" -name SKILL.md -type f | wc -l | tr -d ' ')
[ "$skill_count" = "1" ] || { echo "[fail] SKILL.md が $skill_count 本（公開入口1本のはず）"; failed=1; }

while IFS= read -r script; do bash -n "$script" || failed=1; done < <(find "$ROOT" -type f -name '*.sh' | sort)
while IFS= read -r script; do PYTHONPYCACHEPREFIX="$TMP_ROOT/pycache" python3 -m py_compile "$script" || failed=1; done < <(find "$ROOT" -type f -name '*.py' | sort)

bash "$ROOT/tests/test-domain-modeling.sh" || failed=1
if [ "$failed" -eq 0 ]; then echo 'Validation: passed'; else echo 'Validation: failed'; fi
[ "$failed" -eq 0 ]
