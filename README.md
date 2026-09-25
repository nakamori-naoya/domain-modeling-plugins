# Domain Modeling Plugins

業務知識・コアドメイン（domain-rule）の資料を1本受け取り、集約・エンティティ・値オブジェクト・ドメインイベントとその関係をクラス図に、状態とコマンドを状態遷移図に描いたドメインモデル資料を1本保存する、Claude Code/Codex両対応のmarketplaceである。文章は、図だけでは表せないこと（境界の理由、不変条件、コマンドの契約と拒む理由、何でないか）に絞る。

## こんなときに使う

**業務として何が正しいかは確定したが、それを形にするエンジニアが、図を囲んで境界とコマンドを議論したいときに使う。** 実装コードを書く前に、何を集約にし、どの状態でどのコマンドを受け付け、何を拒むかを、少ない図と短い文章で揃える。

同じdomain-rule資料を読んでも人によって集約の境界が違うとき、上限のような集合への規則を誰が守るかが曖昧なとき、domain-rule資料に無い語（「〜ロット」「〜マネージャ」）が要素として増えていくときに効く。業務知識の発見・反証、永続化、実装コード、層構成、画面、APIは扱わない。

## 公開入口

公開入口は`model-domain`の1つである。domain-rule資料の絶対pathを渡すと新しい資料を作り、既存のドメインモデル資料のpathも渡すと、domain-rule資料の変更が及ぶ箇所だけを同じパスで更新する。domain-rule資料に無い語や決まりは図に使わず、domain-rule資料の反証（bddの`formulate-domain`）への提案にする。それでモデルの結論（集約の境界、要素の種別、受け付けるコマンド）が変わるなら止まって提案を返し、変わらないなら提案を資料に残して完成させる。この入口はdomain-rule資料を書き換えない。

## 利用例

```text
docs/domain/library-lending.md を元に、ドメインモデル資料を作って。
```

```text
domain-rule資料が更新されたので、docs/domain-model/library-lending-model.md を同じパスで更新して。
```

## 工程

`index-source`でdomain-rule資料から図に使える語（業務用語、業務イベント、コマンド、状態、BDD番号）を抜き出す。`settle`で、domain-rule資料だけでは決まらず図の形を変える割り当てを`grill`で確かめる。`assign`で図を先に描き、図で表せないことだけを文章にする。`verify`で図の語と記法の構造を検査する。`document`で`write-doc`の`domain-model`型として保存する。判断の本質は[割り当ての判断](plugins/domain-modeling/skills/model-domain/references/modeling.md)にある。

## インストール

インストールするのは`domain-modeling@domain-modeling`です。外部の工程を実行するため、`grill@grill`、`write-doc@write-doc`も必要です。下のコマンドには、それらも含めています。domain-rule資料を作る`bdd-discovery-and-formulation@bdd-discovery-and-formulation`は実行時の依存ではないので含めていません。

### Codex

利用するCodexと同じ設定環境で実行してください。

```bash
codex plugin marketplace add nakamori-naoya/grill-plugins
codex plugin add grill@grill
codex plugin marketplace add nakamori-naoya/write-doc-plugins
codex plugin add write-doc@write-doc
codex plugin marketplace add nakamori-naoya/domain-modeling-plugins
codex plugin add domain-modeling@domain-modeling
codex plugin list
```

一覧で導入先を確認し、新しい会話で利用してください。

### Claude Code

次は自分の全プロジェクトで使う例です。このプロジェクトのチームで共有する場合は`project`、このプロジェクトで自分だけが使う場合は`local`に変更し、利用先のディレクトリで実行してください。

```bash
CLAUDE_PLUGIN_SCOPE=user
claude plugin marketplace add nakamori-naoya/grill-plugins --scope "$CLAUDE_PLUGIN_SCOPE"
claude plugin install grill@grill --scope "$CLAUDE_PLUGIN_SCOPE"
claude plugin marketplace add nakamori-naoya/write-doc-plugins --scope "$CLAUDE_PLUGIN_SCOPE"
claude plugin install write-doc@write-doc --scope "$CLAUDE_PLUGIN_SCOPE"
claude plugin marketplace add nakamori-naoya/domain-modeling-plugins --scope "$CLAUDE_PLUGIN_SCOPE"
claude plugin install domain-modeling@domain-modeling --scope "$CLAUDE_PLUGIN_SCOPE"
claude plugin list
```

一覧で導入を確認し、Claude Codeを再起動してください。

## 更新する

```bash
# Codex
codex plugin marketplace upgrade domain-modeling
codex plugin add domain-modeling@domain-modeling

# Claude Code（インストール時に合わせてuser / project / localを選ぶ）
CLAUDE_PLUGIN_SCOPE=user
claude plugin marketplace update domain-modeling
claude plugin update domain-modeling@domain-modeling --scope "$CLAUDE_PLUGIN_SCOPE"
```

更新後はCodexなら新しい会話で、Claude Codeなら再起動して確認してください。

## 公開インストール単位と内包する機能

利用者がインストールするのは`domain-modeling@domain-modeling`だけである。packageは`plugins/domain-modeling/`にあり、公開入口`skills/model-domain/`が`SKILL.md`（目的・入力・判断の本質・手順・停止条件・報告）、`playbook.yml`（工程順・入出力・scriptが読む契約）、`references/modeling.md`（割り当ての判断）、`scripts/`（`source.py`索引、`verify.py`検査）を持つ。設定fileは持たず、保存先は公開入力で受け取る。候補本文はagentがインメモリで保持して検査scriptへ標準入力で渡し、作業directory・一時file・後片付け工程を持たない。

## 検証

```bash
bash scripts/validate.sh
```

root契約（配置・manifest・隣接playbook.yml・禁止参照形。`../harness-tools/tools/validate-plugin-repository.py`）、保守toolの回帰検査（`../harness-tools/tools/test-hardening.py --repository`）、隣接`playbook.yml`の宣言と`script:`参照の実在、構文、消費側契約lint（`../harness-tools/tools/lint-consumer-contract.py`。実配布物の兄弟checkout `../grill-plugins/plugins/grill` と `../write-doc-plugins/plugins/write-doc` が要る）、所有script（`source.py` / `verify.py`）の典型例・負例・境界例を実行する。保守toolの参照元は兄弟checkout `../harness-tools/` だけで、無ければ検査は止まる（複製も同期機構も持たない）。CIは`.github/workflows/validate.yml`で `harness-tools` と依存providerを兄弟checkoutし、`harness-tools/ci/validate.sh` で同じcommandを実行する。workspace rootの`bash scripts/validate.sh <このrepositoryの絶対path>`は規約入口の検査と同じroot契約を掛ける。

[意味評価fixture](evals/scenarios.json)は`../harness-tools/scripts/run-evals.sh`（`../harness-tools/tools/evaluate-skills.py`）で生成modelと独立judgeへ渡し、入力、応答、criterionごとの逐語quoteとreasonを記録する。runnerのexit 0は全caseの記録完了だけを示し、品質承認を示さない。criterionの真偽は人またはagentが記録を再読して採否を判断するための意味証拠である。adapter非zero、不正な応答、根拠不整合など記録を完了できない操作失敗は非zeroで終了する。
