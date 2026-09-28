# Domain Modeling Plugins

業務知識の資料（business-knowledge）と実装の間で生じる設計上の判断を議論するため、ドメインモデル資料の叩き台を作る Claude Code/Codex 両対応の marketplace である。ドメインモデルは実装仕様ではなく、候補と未決を人が検討する資料である。

## こんなときに使う

**BDD で業務上の振る舞いは共有できているが、その規則を実装のどの責務に置くかを議論したいときに使う。** 一回の変更で守る境界、状態や値の持ち主、複数の要素にまたがる規則の保証先など、BDDだけでは一意に決まらない候補を少ない図と文章に置く。

同じ業務知識の資料を読んでも境界候補が異なるとき、複数件にまたがる規則を誰が保証するか曖昧なとき、コマンド処理に必要な外部の事実や読み取り判断が見えにくいときに使う。業務知識にない要素名も、仮説として明示すれば議論の候補にできる。業務知識の発見・反証、永続化の詳細、実装コード、層構成、画面、APIは扱わない。

## 公開入口

公開入口は`model-domain`の1つである。業務知識の資料の絶対pathを渡すと議論用の叩き台を作り、既存資料のpathも渡すと、変更が及ぶ箇所を同じパスで更新する。業務知識にない語や決まりは、仮説として区別し、業務知識への提案または未決として扱う。この入口は業務知識の資料を書き換えない。

## 利用例

```text
docs/domain/library-lending.md を元に、ドメインモデル資料を作って。
```

```text
業務知識の資料が更新されたので、docs/domain-model/library-lending-model.md を同じパスで更新して。
```

## 進め方

BDDから実装へ移るときに設計判断が分かれる点を`grill`で確かめ、`write-doc`の`domain-model`型のtemplateと書くときの規範を読んで、図を使った叩き台を保存する。保存した資料に`verify.py`を一回かけ、クラス図の構造とBDD参照の実在を確かめる。境界・責務・仮説の妥当性は人が評価する。判断の要は[割り当ての判断](plugins/domain-modeling/skills/model-domain/references/modeling.md)と`SKILL.md`にある。

## インストール

インストールするのは`domain-modeling@domain-modeling`です。問いを確かめる`grill@grill`と、templateと書くときの規範を読む`write-doc@write-doc`も必要です。下のコマンドには、それらも含めています。業務知識の資料を作る`bdd-discovery-and-formulation@bdd-discovery-and-formulation`は実行時の依存ではないので含めていません。

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

利用者がインストールするのは`domain-modeling@domain-modeling`だけである。packageは`plugins/domain-modeling/`にあり、公開入口`skills/model-domain/`が`SKILL.md`、`references/modeling.md`（割り当ての判断）、`scripts/`（`source.py`が業務知識資料のBDD見出しを読み、`verify.py`がクラス図の構造とBDD参照の実在を検査する）を持つ。設計候補や業務知識にない要素を通すため、検査結果は設計の妥当性を保証しない。設定ファイルは持たず、保存先は入力で受け取る。

## 検証

```bash
bash scripts/validate.sh
```

root契約（`../harness-tools/tools/validate-plugin-repository.py`）、保守toolの回帰検査（`../harness-tools/tools/test-hardening.py --repository`）、構文、`verify.py`の構造上の正例・反例（`tests/test-domain-modeling.sh`）を実行する。保守toolの参照元は兄弟 checkout `../harness-tools/` だけで、無ければ検査は止まる。
