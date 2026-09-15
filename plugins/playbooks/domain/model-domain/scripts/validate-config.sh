#!/usr/bin/env bash
set -euo pipefail
file="$1"
# Deterministic validation declaration:
# source=the public playbook JSON; input=model-domain orchestration fields;
# normalization=none beyond jq structural comparison; predicate=the exact public
# inputs and YAML-declared step order expose the source index before grill and
# preserve the typed write-doc boundary; diagnostic=the single error below;
# positive=current playbook; negative=missing/reordered steps or legacy output_target;
# boundary=empty grill arrays and domain-model quality remain semantic review.
jq -e '
  .document_type=="domain-model" and .output_format=="markdown" and .inputs==["domain_rule_path","user_input","existing_document_path","output_directory","name"] and
  (has("out_dir")|not) and
  .requirements.input_grounded==true and .requirements.clarify_with_grill==true and .requirements.exclude_implementation==true and
  [.requires[].plugin]==["grill","domain-model","write-doc"] and
  (.contract.source_sections|keys|sort)==["actors","bdd","concepts","events","invariants","open_questions","rejections","rules","states","terms"] and
  .contract.model_sections==["目的と範囲","要素一覧","モデル図","各要素の詳細","集約の境界","状態と型の分割","ドメインイベント","BDDとの対応","捨てた割り当て","未決","この資料に書かないもの"] and
  .contract.element_kinds==["値オブジェクト","エンティティ","集約ルート","ドメインイベント","ドメインサービス"] and
  .contract.cleanup.delete_after_document==["source_index","candidate_model_path"] and .contract.cleanup.preserve==["domain_model_document_path"] and
  [.steps[].id]==["prepare-work-directory","index-source","settle","assign","verify","document","cleanup"] and
  [.steps[] | (.agent_work // .script // .playbook)]==["invoking_agent","scripts/source.py","grill","invoking_agent","scripts/verify.py","write-doc","scripts/cleanup.py"] and
  ([.steps[] | select(has("agent_work")) | .agent_work]==["invoking_agent","invoking_agent"]) and
  ([.steps[] | select(has("playbook")) | .playbook]==["grill","write-doc"]) and
  ([.steps[] | select(has("skill") or has("plugin"))]|length)==0 and
  .steps[0].provides==["work_directory"] and
  .steps[1].needs==["domain_rule_path","work_directory"] and .steps[1].provides==["source_index"] and
  .steps[2].needs==["domain_rule_path","user_input","source_index"] and .steps[2].provides==["decisions","open_questions"] and
  .steps[3].needs==["domain_rule_path","source_index","decisions","open_questions"] and .steps[3].provides==["final_markdown","candidate_model_path"] and
  .steps[4].needs==["candidate_model_path","source_index"] and .steps[4].provides==["validation_report"] and
  .steps[5].needs==["final_markdown","validation_report"] and
  .steps[5].conditional_needs==[{"when":"existing_document_path","needs":["existing_document_path"]},{"when":"not existing_document_path","needs":["output_directory","name"]}] and
  .steps[5].provides==["domain_model_document_path"] and .steps[5].input=={"document_type":"${.document_type}"} and
  .steps[6].needs==["work_directory","source_index","candidate_model_path","domain_model_document_path"] and .steps[6].provides==["cleanup_report"]
' "$file" >/dev/null || {
  echo "[error] model-domainはYAML順の正本索引→grill→同一agentの割当→構造検査→text資料化→安全な後片付けで構成する" >&2
  exit 2
}
