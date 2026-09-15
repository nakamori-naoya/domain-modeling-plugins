#!/usr/bin/env bash
set -euo pipefail
file="$1"
jq -e '
  .document_type=="domain-model" and
  .output_format=="markdown" and
  .requirements.input_grounded==true and
  .requirements.clarify_with_grill==true and
  .requirements.exclude_implementation==true and
  [.requires[].plugin]==["grill","domain-model","write-doc"] and
  [.requires[].marketplace]==["grill","domain-modeling","write-doc"] and
  (.contract.source_sections|keys|sort)==["actors","bdd","concepts","events","invariants","open_questions","rejections","rules","states","terms"] and
  .contract.model_sections==["目的と範囲","要素一覧","モデル図","各要素の詳細","集約の境界","状態と型の分割","ドメインイベント","BDDとの対応","捨てた割り当て","未決","この資料に書かないもの"] and
  .contract.element_kinds==["値オブジェクト","エンティティ","集約ルート","ドメインイベント","ドメインサービス"] and
  .contract.exceptional_kinds==["ドメインサービス"] and
  .contract.element_items==["目的","何でないか","持つもの","不変条件","生成の条件","協働相手"] and
  .contract.operation_fields==["事前条件","事後条件","拒む理由","発するイベント"] and
  .contract.collaboration_means==["識別子で参照","値として渡す","ドメインイベント","呼び手が両方を操作"] and
  (.contract.forbidden_sections|length)>0 and
  .contract.cleanup.delete_after_document==["grounded_input","source_index","candidate_model_path","verified_model_path","material"] and
  .contract.cleanup.preserve==["domain_model_document_path"] and
  [.steps[].id]==["settle","ground","index-source","assign","verify","assemble","document","cleanup"] and
  [.steps[] | (.skill // .script // .playbook)]==["grill","scripts/ground.py","scripts/source.py","assign-domain-model","scripts/verify.py","scripts/material.sh","write-doc","scripts/cleanup.py"] and
  ([.steps[] | select(has("skill")) | .skill]==["assign-domain-model"]) and
  ([.steps[] | select(has("playbook")) | .playbook]==["grill","write-doc"]) and
  ([.steps[] | select(has("plugin"))]|length)==0 and
  .steps[0].provides==["decisions","open_questions"] and
  (.steps[0]|has("input")|not) and
  .steps[1].needs==["decisions","open_questions"] and .steps[1].provides==["grounded_input"] and
  .steps[2].needs==["grounded_input"] and .steps[2].provides==["source_index"] and
  .steps[3].needs==["grounded_input","source_index"] and .steps[3].provides==["candidate_model_path"] and
  .steps[4].needs==["candidate_model_path","source_index"] and .steps[4].provides==["verified_model_path"] and
  .steps[5].needs==["verified_model_path","grounded_input","source_index"] and .steps[5].provides==["material"] and
  .steps[6].needs==["material"] and .steps[6].provides==["domain_model_document_path"] and
  .steps[6].input=={"document_type":"${.document_type}"} and
  .steps[7].needs==["grounded_input","source_index","candidate_model_path","verified_model_path","material","domain_model_document_path"] and
  .steps[7].provides==["cleanup_report"]
' "$file" >/dev/null || {
  echo "[error] model-domainはgrill→根拠づけ→正本の索引→割り当て→verify→束ね→write-doc→自分の中間生成物の後片付けという契約を変えられない" >&2
  exit 2
}
