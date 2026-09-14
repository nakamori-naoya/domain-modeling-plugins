#!/usr/bin/env bash
# Scenario: repositoryのplugin集合、manifest、marketplace、構文が一致する
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# 継承したenvで検査が変わらないようにする。開発用mapやtest cacheが外から入っていると、
# 「解決できないこと」を見る負の試験が黙って解決してしまい、緑になる。
# 必要な検査は、自分の中で明示的に設定する。
unset HARNESS_PLUGIN_DEV_ROOTS HARNESS_PLUGIN_CACHE_ROOT HARNESS_PLUGIN_ALLOW_PRERELEASE
python3 "$ROOT/scripts/test-hardening.py" || exit 1
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/plugin-repository-validation.XXXXXX") || exit 2
export TMPDIR="$TMP_ROOT"
trap 'rm -rf "$TMP_ROOT"' EXIT
failed=0

# owning_bundle は所属package宣言から内外を判定する。合成fixtureの呼び出し元にも
# bundle manifest（marketplace 宣言）が要る。
write_bundle_manifest() {
  # **既定値に波括弧を直接書かない。** bash 3.2（macOS の /bin/bash）は
  # "${4:-{\}}" を {\} へ展開し、jq --argjson が不正なJSONとして落ちる。
  # bash 5 では {} になるため、手元だけ緑になる。既定値は別の行で与える。
  local dir="$1" name="$2" market="$3" internals="${4:-}"
  [ -n "$internals" ] || internals='{}'
  local runtime
  for runtime in codex claude; do
    mkdir -p "$dir/.$runtime-plugin"
    jq -n --arg n "$name" --arg m "$market" --argjson i "$internals" \
      '{name:$n,version:"1.0.0",metadata:{harness:{installationSurface:"playbook-package",marketplace:$m,internalPlugins:$i,contractVersion:1}}}' \
      > "$dir/.$runtime-plugin/plugin.json"
  done
}

validate_dependency_resolution_contract() {
  local resolver="$ROOT/shared/playbook/resolve-dependency.py"
  local repo_resolver="$ROOT/plugins/playbooks/domain/model-domain/scripts/resolve-dependency.py"
  local repo_root="$ROOT/plugins/playbooks/domain/model-domain"
  local fixture="$TMP_ROOT/dependency-resolution"
  local cache="$fixture/empty/.harness-plugin-test-cache"
  local isolated_resolver="$fixture/empty/scripts/resolve-dependency.py"
  local isolated_root
  local status=0
  local out

  mkdir -p "$fixture/empty/scripts" "$cache/fixture-market/fixture-plugin/1.0.0/.codex-plugin" "$cache/fixture-market/fixture-plugin/1.0.0/.claude-plugin"
  cp "$resolver" "$isolated_resolver"
  isolated_root=$(cd "$fixture/empty" && pwd -P)
  write_bundle_manifest "$isolated_root" caller-plugin caller-market
  mkdir -p "$cache/fixture-market/fixture-plugin/9.9.9/.codex-plugin" "$cache/fixture-market/fixture-plugin/9.9.9/.claude-plugin"
  # 外部依存は公開playbookのimplementsを宣言していないと解決できない。
  # cache fixtureも実物と同じ形（marketplace / playbooks / implements と公開入口4点）にする。
  for version in 1.0.0 9.9.9; do
    local versioned="$cache/fixture-market/fixture-plugin/$version"
    mkdir -p "$versioned/pb/scripts"
    printf '%s\n' '---' 'name: fixture-entry' 'description: fixture' '---' > "$versioned/pb/SKILL.md"
    printf '%s\n' 'version: 2' 'name: pb' 'description: fixture' 'instructions: {execution: {directive: fixture}}' 'requires: []' 'steps: [{id: work, skill: fixture-entry, purpose: fixture}]' > "$versioned/pb/playbook.yml"
    printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$versioned/pb/scripts/resolve.sh"
    printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$versioned/pb/scripts/prepare.sh"
    for runtime in codex claude; do
      jq -n --arg v "$version" '{name:"fixture-plugin",version:$v,metadata:{harness:{installationSurface:"playbook-package",marketplace:"fixture-market",playbooks:{pb:"./pb"},internalPlugins:{},contractVersion:1,implements:[{id:"fixture-market/fixture-plugin",version:1,kind:"playbook",playbook:"pb"}]}}}' \
        > "$versioned/.$runtime-plugin/plugin.json"
    done
  done
  printf '%s\n' '---' 'name: wrong-skill' 'description: fixture' '---' > "$cache/fixture-market/fixture-plugin/9.9.9/SKILL.md"

  local marketplace repository_plugin
  marketplace=$(jq -r '.name' "$ROOT/.agents/plugins/marketplace.json")
  repository_plugin=$(jq -r '.plugins[0].name' "$ROOT/.agents/plugins/marketplace.json")
  for runtime in codex claude; do
    out=$(HARNESS_PLUGIN_RUNTIME="$runtime" python3 "$repo_resolver" --plugin-root "$repo_root" --plugin "$repository_plugin" --marketplace "$marketplace" 2> "$fixture/repository-$runtime.err")
    jq -e '.dependency_scope=="internal"' >/dev/null <<<"$out" || status=1
    jq -e --arg runtime "$runtime" --arg plugin "$repository_plugin" '.runtime==$runtime and .plugin==$plugin and .source_kind=="repository"' >/dev/null <<<"$out" || status=1

    out=$(HARNESS_PLUGIN_RUNTIME="$runtime" HARNESS_PLUGIN_CACHE_ROOT="$cache" python3 "$isolated_resolver" --plugin-root "$isolated_root" --plugin fixture-plugin --marketplace fixture-market 2> "$fixture/cache-$runtime.err")
    jq -e --arg runtime "$runtime" '.runtime==$runtime and .version=="9.9.9" and .source_kind=="installed-cache"' >/dev/null <<<"$out" || status=1
  done

  local installed_cache="$fixture/profile/plugins/cache"
  local installed_caller="$installed_cache/caller-market/caller-plugin/1.0.0/playbook"
  mkdir -p "$installed_caller/scripts"
  cp "$resolver" "$installed_caller/scripts/resolve-dependency.py"
  cp -R "$cache/fixture-market" "$installed_cache/"
  local installed_root
  installed_root=$(cd "$installed_caller" && pwd -P)
  write_bundle_manifest "$installed_root" caller-plugin caller-market
  for runtime in codex claude; do
    out=$(HARNESS_PLUGIN_RUNTIME="$runtime" python3 "$installed_caller/scripts/resolve-dependency.py" --plugin-root "$installed_root" --plugin fixture-plugin --marketplace fixture-market 2> "$fixture/installed-$runtime.err")
    jq -e --arg runtime "$runtime" '.runtime==$runtime and .version=="9.9.9" and .source_kind=="installed-cache"' >/dev/null <<<"$out" || status=1
  done

  mkdir -p "$fixture/dev/.codex-plugin" "$fixture/dev/.claude-plugin" "$fixture/dev/pb/scripts"
  printf '%s\n' '---' 'name: fixture-entry' 'description: fixture' '---' > "$fixture/dev/pb/SKILL.md"
  printf '%s\n' 'version: 2' 'name: pb' 'description: fixture' 'instructions: {execution: {directive: fixture}}' 'requires: []' 'steps: [{id: work, skill: fixture-entry, purpose: fixture}]' > "$fixture/dev/pb/playbook.yml"
  printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$fixture/dev/pb/scripts/resolve.sh"
  printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$fixture/dev/pb/scripts/prepare.sh"
  for runtime in codex claude; do
    jq -n '{name:"fixture-plugin",version:"3.4.5",metadata:{harness:{installationSurface:"playbook-package",marketplace:"fixture-market",playbooks:{pb:"./pb"},internalPlugins:{},contractVersion:1,implements:[{id:"fixture-market/fixture-plugin",version:1,kind:"playbook",playbook:"pb"}]}}}' \
      > "$fixture/dev/.$runtime-plugin/plugin.json"
  done
  jq -n --arg root "$fixture/dev" '{schema:1,dependencies:{"fixture-market/fixture-plugin":$root}}' > "$fixture/dev-map.json"
  out=$(HARNESS_PLUGIN_RUNTIME=codex HARNESS_PLUGIN_DEV_ROOTS="$fixture/dev-map.json" HARNESS_PLUGIN_CACHE_ROOT="$cache" python3 "$isolated_resolver" --plugin-root "$isolated_root" --plugin fixture-plugin --marketplace fixture-market 2> "$fixture/dev.err")
  jq -e '.version=="3.4.5" and .source_kind=="dev-map"' >/dev/null <<<"$out" || status=1

  if HARNESS_PLUGIN_RUNTIME=codex HARNESS_PLUGIN_CACHE_ROOT="$cache" python3 "$isolated_resolver" --plugin-root "$isolated_root" --plugin missing-plugin --marketplace fixture-market >/dev/null 2> "$fixture/missing.err"; then
    status=1
  else
    rg '\[error:dependency-missing\].*plugin=missing-plugin.*marketplace=fixture-market' "$fixture/missing.err" >/dev/null || status=1
  fi

  mv "$cache/fixture-market/fixture-plugin/9.9.9/.codex-plugin/plugin.json" "$fixture/correct-manifest.json"
  printf '%s\n' '{"name":"other-plugin","version":"9.9.9"}' > "$cache/fixture-market/fixture-plugin/9.9.9/.codex-plugin/plugin.json"
  if HARNESS_PLUGIN_RUNTIME=codex HARNESS_PLUGIN_CACHE_ROOT="$cache" python3 "$isolated_resolver" --plugin-root "$isolated_root" --plugin fixture-plugin --marketplace fixture-market >/dev/null 2> "$fixture/identity.err"; then
    status=1
  else
    rg 'manifest-identity-mismatch' "$fixture/identity.err" >/dev/null || status=1
  fi
  mv "$fixture/correct-manifest.json" "$cache/fixture-market/fixture-plugin/9.9.9/.codex-plugin/plugin.json"

  mkdir -p "$fixture/ambiguous/.agents/plugins" "$fixture/ambiguous/.claude-plugin" "$fixture/ambiguous/plugins/caller"
  mkdir -p "$fixture/ambiguous/plugins/caller/scripts"
  cp "$resolver" "$fixture/ambiguous/plugins/caller/scripts/resolve-dependency.py"
  local ambiguous_root
  ambiguous_root=$(cd "$fixture/ambiguous/plugins/caller" && pwd -P)
  write_bundle_manifest "$fixture/ambiguous/plugins" caller-plugin caller-market
  jq -n '{name:"fixture-market",plugins:[{name:"fixture-plugin",source:{source:"local",path:"./plugins/a"}},{name:"fixture-plugin",source:{source:"local",path:"./plugins/b"}}]}' > "$fixture/ambiguous/.agents/plugins/marketplace.json"
  if HARNESS_PLUGIN_RUNTIME=codex python3 "$fixture/ambiguous/plugins/caller/scripts/resolve-dependency.py" --plugin-root "$ambiguous_root" --plugin fixture-plugin --marketplace fixture-market >/dev/null 2> "$fixture/ambiguous.err"; then
    status=1
  else
    rg 'source_kind=repository reason=marketplace-entry' "$fixture/ambiguous.err" >/dev/null || status=1
  fi

  mkdir -p "$fixture/playbook/scripts" "$fixture/repo" "$fixture/playbook/internal"
  local playbook_cache="$fixture/playbook/.harness-plugin-test-cache"
  mkdir -p "$playbook_cache"
  cp -R "$cache/." "$playbook_cache/"
  # 内部依存として解決させる。外部依存なら implements 宣言が要るので、
  # steps の skill 検査へ到達する前に external-dependency-no-playbook で落ちる。
  write_bundle_manifest "$fixture/playbook" caller-plugin fixture-market '{"fixture-plugin":"./internal"}'
  for runtime in codex claude; do
    mkdir -p "$fixture/playbook/internal/.$runtime-plugin"
    printf '%s\n' '{"name":"fixture-plugin","version":"1.0.0"}' > "$fixture/playbook/internal/.$runtime-plugin/plugin.json"
  done
  printf '%s\n' '---' 'name: wrong-skill' 'description: fixture' '---' > "$fixture/playbook/internal/SKILL.md"
  cp "$ROOT/shared/playbook/resolve.sh" "$fixture/playbook/scripts/resolve.sh"
  cp "$ROOT/shared/playbook/resolve-dependency.py" "$fixture/playbook/scripts/resolve-dependency.py"
  printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$fixture/playbook/scripts/validate-config.sh"
  chmod +x "$fixture/playbook/scripts/resolve.sh" "$fixture/playbook/scripts/validate-config.sh"
  printf '%s\n' 'version: 2' 'name: fixture-playbook' 'description: fixture' 'instructions:' '  execution: {directive: fixture}' 'requires:' '  - {plugin: fixture-plugin, marketplace: fixture-market}' 'steps:' '  - {id: invoke, skill: expected-skill, purpose: fixture}' > "$fixture/playbook/playbook.yml"
  if XDG_CONFIG_HOME="$fixture/config" HARNESS_PLUGIN_RUNTIME=codex HARNESS_PLUGIN_CACHE_ROOT="$playbook_cache" bash "$fixture/playbook/scripts/resolve.sh" "$fixture/repo" >/dev/null 2> "$fixture/skill.err"; then
    status=1
  else
    rg 'steps が指すスキルが requires のプラグインに無い: expected-skill' "$fixture/skill.err" >/dev/null || status=1
  fi

  cp "$fixture/playbook/playbook.yml" "$fixture/playbook/base.yml"
  yq -o=json -I=0 '.' "$fixture/playbook/base.yml" | jq '.requires[0].version="1.0.0"' | yq -P > "$fixture/playbook/playbook.yml"
  if XDG_CONFIG_HOME="$fixture/config" HARNESS_PLUGIN_RUNTIME=codex HARNESS_PLUGIN_CACHE_ROOT="$playbook_cache" bash "$fixture/playbook/scripts/resolve.sh" "$fixture/repo" >/dev/null 2> "$fixture/pin.err"; then status=1; fi
  yq -o=json -I=0 '.' "$fixture/playbook/base.yml" | jq '.requires[0]=.requires[0].plugin' | yq -P > "$fixture/playbook/playbook.yml"
  if XDG_CONFIG_HOME="$fixture/config" HARNESS_PLUGIN_RUNTIME=codex HARNESS_PLUGIN_CACHE_ROOT="$playbook_cache" bash "$fixture/playbook/scripts/resolve.sh" "$fixture/repo" >/dev/null 2> "$fixture/bare.err"; then status=1; fi

  return "$status"
}
bash "$ROOT/scripts/validate-marketplace.sh" "$ROOT" || failed=1
bash "$ROOT/scripts/test-marketplace-validation.sh" || failed=1
while IFS= read -r pb; do
  yq -o=json -I=0 '.' "$pb" | jq -e '.version==2 and (.requires|length>0) and all(.requires[]; type=="object" and ((keys|sort)==["marketplace","plugin"]))' >/dev/null || failed=1
  yq -o=json -I=0 '.' "$pb" | jq -e 'all(.requires[]; .marketplace=="domain-modeling" or .plugin==.marketplace)' >/dev/null || failed=1
  root=$(dirname "$pb")
  cmp -s "$ROOT/shared/playbook/resolve.sh" "$root/scripts/resolve.sh" || failed=1
  cmp -s "$ROOT/shared/playbook/resolve-dependency.py" "$root/scripts/resolve-dependency.py" || failed=1
done < <(find "$ROOT/plugins/playbooks" -name playbook.yml -type f 2>/dev/null | sort)
while IFS= read -r script; do bash -n "$script" || failed=1; done < <(find "$ROOT" -type f -name '*.sh' | sort)
while IFS= read -r script; do PYTHONPYCACHEPREFIX="$TMP_ROOT/pycache" python3 -m py_compile "$script" || failed=1; done < <(find "$ROOT" -type f -name '*.py' | sort)

# ── 消費側の契約lint — 実際の配布物から検出語を作る ─────────────────────
# resolverはplaybook.ymlしか見ない。lintはSKILL.md・README・references・scripts・
# .harness-plugins配下の設定を含む全行を見る。検出語は手書きせず、外部依存として
# 実在するproviderのmanifestから作るので、依存先の実配布物が要る。
lint_consumer_contract() {
  local map="$TMP_ROOT/lint-dev-map.json"
  local grill="$ROOT/../grill-plugins/plugins"
  local write_doc="$ROOT/../write-doc-plugins/plugins"
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

validate_dependency_resolution_contract || failed=1
lint_consumer_contract || failed=1
bash "$ROOT/tests/test-domain-modeling.sh" || failed=1
if [ "$failed" -eq 0 ]; then echo 'Validation: passed'; else echo 'Validation: failed'; fi
[ "$failed" -eq 0 ]
