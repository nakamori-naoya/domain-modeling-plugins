---
name: model-domain
description: 業務知識・コアドメイン（domain-rule）の正本を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存する。正本だけでは決まらない割り当てはgrillで1問ずつ確かめる。「ドメインモデルを作って」「この業務資料を集約とVOに落として」「BDDから戦術DDDのモデルを設計して」と言われたとき、実装やデータモデルへ進む前に使う。業務知識の発見・反証、永続化、実装コード、層構成は扱わない。
---

# model-domain（正本の概念を、契約つきの要素へ写す）

**正本に無い語を要素にしない。** 要素の名前は正本のユビキタス言語から取る。必要に思えた語は、要素にせず「捨てた割り当て」か「未決」へ理由付きで残す。

**割り当ては写像であって、発見ではない。** 新しい業務の事実が要ると分かったら、それはこの段取りの外（domain-ruleの発見・反証）へ戻す。ここで業務知識を足さない。

## 0. プラグイン root を決める

<!-- BEGIN shared:skill-entry/root-block -->
```bash
BUNDLE_ROOT="${CLAUDE_PLUGIN_ROOT:-/absolute/path/to/this/plugin}"
if [ -d "${BUNDLE_ROOT}/playbooks/domain/model-domain" ]; then
  PLUGIN_ROOT="${BUNDLE_ROOT}/playbooks/domain/model-domain"
else
  PLUGIN_ROOT="${BUNDLE_ROOT}"
fi
```

`PLUGIN_ROOT`は配布物rootの絶対パスである。単一skill pluginではこの`SKILL.md`があるdirectory、複数skill pluginでは`skills/<skill>/`の2つ上に当たる。Claude Codeでは`${CLAUDE_PLUGIN_ROOT}`が自動展開される。
<!-- END shared:skill-entry/root-block -->

## 1. 工程を解決する

<!-- BEGIN shared:skill-entry/config-load -->
```bash
CFG_FILE=$(bash "${PLUGIN_ROOT}/scripts/prepare.sh" "$(pwd)") || exit 2
printf '%s\n' "$CFG_FILE"
```

**このコマンドは説明例ではない。必ず実行する。** 解決済みYAMLが空なら先へ進まない。設定ファイルを直接読んで代用しない。

本文中の `${...}` は解決済みYAMLのプロパティである。使用時に `yq -er` で読み、欠落または `null` なら停止する。
<!-- END shared:skill-entry/config-load -->

`${.instructions.execution.directive}`と`${.instructions.interaction.directive}`に従い、`${.playbook.steps}`を上から実行する。自分のpackageのskillへは`--scope=${.resolution.scope_root}`と`${.playbook.contract}`と前工程の成果物を渡す。外部packageは`playbook:`の工程でだけ呼び、§3の手順に従う。

一時ファイルは解決済みYAMLと同じdirectory（`$(dirname "$CFG_FILE")`）へ置く。

[実行指示書](references/execution-guidance.md)を必ず読む。`playbook.yml`は工程順・依存・入出力を決定し、実行指示書は各工程で意識することと、grillへ渡す題材固有の文脈を補う。

## 2. 入力を確かめてから始める

**開始条件は、domain-ruleの正本が1本、絶対pathで指されていることである。** 次のどれかなら、推測せず、その1問を返して停止する。

| 観察 | 返す問い |
|---|---|
| 正本のpathが依頼に無い | 「どのdomain-rule資料を正本にしますか（絶対path）」 |
| pathが複数ある | 「どれを正本にしますか。モデルは正本1本につき1本です」 |
| 指されたファイルが業務知識・コアドメインの型でない（`# 概要`〜`# BDD`の見出しを持たない） | 「この資料はdomain-rule型ではありません。先にdiscover-domainで正本を作りますか」 |

既存のドメインモデル資料が同じ正本から作られていて、依頼が「更新」なら、その資料の絶対pathを`--existing`として`ground`工程へ渡す。依頼に無い既存資料を探して更新扱いにしない。

## 3. 外部playbookの呼び方

`playbook:`の工程（`settle`と`document`）は、相手の公開契約だけを使って呼ぶ。相手のskill名、工程id、references、config、保存モード名、scriptの引数は使わない。**呼び方は2段だけである。**

### 第1段 — こちらが解決する

相手の`CONTRACT.md`が定める入力schemaで入力YAMLを書く。`contract`・`version`・`output_to`は必ず入れ、`output_to`は自分が用意する絶対pathにする。そのうえで相手の`prepare.sh`を通す。

```bash
DEP_CFG=$(bash "${.deps.<論理名>.root}/scripts/prepare.sh" "$(pwd)" \
  --input="<入力YAMLの絶対path>" \
  --scope="${.resolution.scope_root}" \
  --bindings="${.resolution.bindings_lock}") || exit 2
```

標準出力に返る絶対pathが、相手の解決済みYAMLである。空なら工程を実行せず停止する。

### 第2段 — 入口のSKILL.mdへ渡して実行させる

`${.deps.<論理名>.entry}`が相手の入口SKILL.mdである。**第1段で得た`$DEP_CFG`を`CFG_FILE`として渡し**、そのSKILL.mdに従って実行する。入口は相手の契約が選ぶので、相手の公開skill名を知る必要はない。

**相手に`prepare.sh`を再実行させない。** 解決は第1段で終わっている。二度解決すると、こちらが渡した`--input`と、入口playbookが決めた`--scope`・束縛lockが捨てられ、後始末の持ち主も分からなくなる。

相手のrootから他のpath（`scripts/`のそれ以外、`skills/`、`references/`、`config/`）を組み立てない。相手の実行設定の後始末は相手が自分で行う。完了したら`output_to`の絶対pathに書かれた出力YAMLを読む。**相手の内部の記録やログは読まない。**

### settle（`grill`）

入力に`topic`（正本の題材名）、`context`（`purpose`・`audience`・`boundary`）、`questions`（`{id, question, recommendation}`。推奨は必ず添える）、`grounding`（正本の絶対path）、`output_to`を渡す。**正本と索引から読み取れることは問わない。** 問うのは、正本だけでは一つに決まらない割り当てだけである。何を問うかは[実行指示書](references/execution-guidance.md)の「settleで確かめること」に従い、題材固有の観点は`context`で渡して相手に持ち込ませない。

第1段は `bash "${.deps.grill.root}/scripts/prepare.sh"`、第2段は `${.deps.grill.entry}` のSKILL.mdである。

出力は`decisions`と`open_questions`の2つだけである。「根拠づけられた入力」は相手の出力ではないので、次の`ground`工程がこちらの側で束ねる。

```bash
python3 "${PLUGIN_ROOT}/scripts/ground.py" --config "$CFG_FILE" \
  --dialogue-output "<output_toのpath>" \
  --source "<domain-rule正本の絶対path>" \
  --request "<依頼のpath>" [--existing "<既存資料の絶対path>"] \
  --output "<束ねた入力の書き込み先>"
```

契約を満たさない出力（契約IDや版の不一致、`status`が`completed`でない、`rationale`の無い決定、`open`/`withdrawn`以外の状態）では束ねずに停止する。

### document（`write-doc`）

入力の必須は`contract: write-doc/write-doc`、`version: 1`、`material`（**絶対pathの配列**。`assemble`が束ねた素材1つ）、`output_to`である。`document_type`に`${.playbook.document_type}`、`output_format`に`${.playbook.output_format}`を渡す。`references`には[成果物の形](references/deliverable.md)の絶対pathを渡す（こちらが書いた文書だけを渡せる）。

保存先は、新規作成なら`name`（正本のファイル名から`-model`を付けた名前。例: `order.md` → `order-model.md`）、既存資料の更新なら`update_target`（`ground`へ渡した`existing_document_path`）を渡す。この2つは**排他**で、両方を渡しても、どちらも渡さなくても止まる。`output_directory`は、依頼で保存先が明示されたときだけ`name`と一緒に渡す。**依頼に無い保存先を推測して渡さない。**

第1段は `bash "${.deps.write-doc.root}/scripts/prepare.sh"`、第2段は `${.deps.write-doc.entry}` のSKILL.mdである。

出力YAMLは`status`（`completed` | `failed`）、`path`、`document_type`、`output_format`（失敗時は`reason`）を持つ。1回の呼び出しで作る資料は1本だけである。`status: completed`と`path`を確かめてから、次へ進む。

## 4. 正本を索引にし、割り当てて、検査する

```bash
python3 "${PLUGIN_ROOT}/scripts/source.py" --config "$CFG_FILE" \
  --grounded-input "<ground.pyの出力>" --output "<索引の書き込み先>"
```

索引は、正本の業務用語・業務イベント・概念・常に守られること・状態・誰が行えるか・業務ルール・拒む理由・BDD番号・未決を機械的に抜き出したものである。**索引の語だけが要素の名前になれる。** 正本が契約の節を持たなければここで止まる。正本を直してから再実行する。

`assign`工程は自分のpackageの`assign-domain-model`skillに、`--scope=${.resolution.scope_root}`、束ねた入力、索引、`${.playbook.contract}`を渡して実行する。候補モデルの絶対pathが返る。

```bash
python3 "${PLUGIN_ROOT}/scripts/verify.py" --config "$CFG_FILE" \
  --candidate "<候補モデルの絶対path>" --source-index "<索引の絶対path>"
```

検査は述語だけを見る（節と順序、実装の節の混入、正本に無い語、要素ごとの必須項目と操作の契約、BDDの対応の過不足、未決の有無）。**通らなければ`assign`へ戻って候補を直す。検査を緩めない。** 通ったら`warnings`を報告に写す。`warnings`は合否ではなく、人が読み返す箇所の索引である。

```bash
bash "${PLUGIN_ROOT}/scripts/material.sh" --config "$CFG_FILE" \
  --model "<検査済みモデル>" --grounded-input "<ground.pyの出力>" \
  --source-index "<索引>" --output "<素材の書き込み先>"
```

## 5. 後片付けして報告する

最終資料の保存を確認したら、`scripts/cleanup.py`へ`--config "$CFG_FILE"`と`--artifact <論理名>=<絶対path>`を渡し、`${.playbook.contract.cleanup}`で削除候補にした自分の作業用成果物だけを後片付けする。保持対象・repositoryの外・追跡済みファイルは削除しない。後片付けを外部packageへ委ねない。

報告する内容:

- 保存した資料の絶対pathと、元にした正本の絶対path
- 要素一覧（要素名・種別）と、集約の境界
- **状態と型の分割** — どの状態で何ができ、何ができないか
- 捨てた割り当てと、その理由
- 未決と、何が分かれば確定するか
- 検査の`warnings`（索引外だが本文に現れる語、例外扱いの種別、対応しないBDD、対応のない要素）
- **機械検査が通ったときに言えるのは、判定した述語が成り立ったことだけである。** 「モデルは正しい」と書かない

資料が保存されるまで完了にしない。データモデル・実装コード・層構成は作らない。

## 実行設定の寿命

prepareが返した絶対pathを実行記録へ保持する。別shellではそのpathを`CFG_FILE`へ明示して読み、shell変数の継承を前提にしない。完了時と失敗停止時のどちらも、最後の設定利用後に`python3 "${PLUGIN_ROOT}/scripts/run-config.py" cleanup --config "$CFG_FILE"`を実行する。他runの設定やdirectoryを削除しない。**外部packageの実行設定には触れない。**

条件付き工程を含め、各工程を呼ぶ直前に`yq -o=json '.' "$CFG_FILE" | python3 "${PLUGIN_ROOT}/scripts/resolve-dependency.py" --check-steps <工程id>`を実行する。失敗時は工程を実行せず停止する。
