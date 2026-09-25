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

## 進め方

domain-rule資料だけでは決まらず図の形を変える割り当てを`grill`で確かめ、`write-doc`の`domain-model`型のtemplateと書くときの規範を読んで、図を先に描き、図で表せないことだけを文章にして保存する。保存した資料に`verify.py`を一回かけ、図の語と記法の構造を確かめる。判断の要は[割り当ての判断](plugins/domain-modeling/skills/model-domain/references/modeling.md)と`SKILL.md`にある。

## インストール

インストールするのは`domain-modeling@domain-modeling`です。問いを確かめる`grill@grill`と、templateと書くときの規範を読む`write-doc@write-doc`も必要です。下のコマンドには、それらも含めています。domain-rule資料を作る`bdd-discovery-and-formulation@bdd-discovery-and-formulation`は実行時の依存ではないので含めていません。

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

利用者がインストールするのは`domain-modeling@domain-modeling`だけである。packageは`plugins/domain-modeling/`にあり、公開入口`skills/model-domain/`が`SKILL.md`、`references/modeling.md`（割り当ての判断）、`scripts/`（`source.py`がdomain-rule資料から語の索引を作り、`verify.py`が保存した資料を検査する）を持つ。設定ファイルは持たず、保存先は入力で受け取る。

## 検証

```bash
bash scripts/validate.sh
```

root契約（`../harness-tools/tools/validate-plugin-repository.py`）、保守toolの回帰検査（`../harness-tools/tools/test-hardening.py --repository`）、構文、消費側契約lint（`../harness-tools/tools/lint-consumer-contract.py`。兄弟checkout `../grill-plugins/plugins/grill` と `../write-doc-plugins/plugins/write-doc` が要る）、`source.py`と`verify.py`の典型例・負例・境界例（`tests/test-domain-modeling.sh`）を実行する。保守toolの参照元は兄弟checkout `../harness-tools/` だけで、無ければ検査は止まる。
