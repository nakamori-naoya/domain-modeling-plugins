#!/usr/bin/env bash
jq -e '.version==1 and (.output_dir|type=="string" and length>0) and
  (.artifact.kind=="domain-model-candidate") and
  (.artifact.required_sections|type=="array" and length==11) and
  (.artifact.required_nonempty_sections|type=="array" and length>0) and
  (.instructions.assignment.directive|type=="string" and length>0)' >/dev/null <<<"$merged" \
  || { echo "[error] domain-model contractが不正" >&2; exit 2; }
output_dir=$(jq -r '.output_dir' <<<"$merged"); output_dir="${output_dir/#\~/$HOME}"
case "$output_dir" in /*) ;; *) output_dir="${root}/${output_dir}" ;; esac
out=$(jq -cn --arg kind "$(jq -r '.artifact.kind' <<<"$merged")" --arg output "$output_dir" \
  --arg mapping "$PLUGIN_ROOT/references/mapping.md" \
  --arg disciplines "$PLUGIN_ROOT/references/disciplines.md" \
  --arg questions "$PLUGIN_ROOT/references/element-questions.md" \
  --arg root "$root" --arg pr "$PLUGIN_ROOT" \
  --argjson required "$(jq -c '.artifact.required_sections' <<<"$merged")" \
  --argjson nonempty "$(jq -c '.artifact.required_nonempty_sections' <<<"$merged")" \
  --argjson instructions "$(jq -c '.instructions' <<<"$merged")" \
  '{contract:1, artifact_kind:$kind, output_dir:$output, required_sections:$required,
    required_nonempty_sections:$nonempty, mapping:$mapping, disciplines:$disciplines,
    element_questions:$questions, instructions:$instructions, repo_root:$root, plugin_root:$pr}')
