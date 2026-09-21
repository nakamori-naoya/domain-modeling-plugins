# Domain Modeling Plugins

業務知識・コアドメイン（domain-rule）の正式な定義を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存する、Claude Code/Codex両対応のmarketplaceである。

## こんなときに使う

**業務として何が正しいかは確定したが、それを形にするエンジニアの頭の中のモデルが揃っていないときに使う。** 実装コードを書く前に、何を要素にし、どこに境界を引き、どの状態で何ができるかを一つの資料にする。

- 同じ正式な定義を読んでも、人によって集約の境界が違う
- 「確認する」と「変更する」が別々の操作になっていて、確認したのに変更し忘れる形が書けてしまう
- 状態によって呼べる操作が違うのに、一つの型が全部の操作を持っている
- 正式な定義に無い語（「〜ロット」「〜マネージャ」）が要素として増えていく
- 契約による設計をしたいが、事前条件・事後条件・拒む理由を書く場所が無い

業務知識の発見・反証、永続化、実装コード、層構成、画面、APIは扱わない。

## 公開入口

| 今の状況 | 公開入口 | 得られるもの |
|---|---|---|
| domain-ruleの正式な定義があり、ドメインモデル資料を初めて作る | `model-domain` | 契約つきのdomain-model資料 |
| 既存のドメインモデル資料を、更新された正式な定義に追従させる | `model-domain`（既存資料のpathを渡す） | 同じパスへ更新されたdomain-model資料 |

反証で新しい業務の事実が出たら、それはこの入口では扱わず、domain-rule側の反証へ戻す。モデル資料は正式な定義の写像であり、正式な定義を2つにしない。保存先は依頼で示すか、示されなければ入口が既存資料の構成を読んで一度だけ提案する。

## 利用例

```text
docs/domain/order-cancellation.md を正式な定義に、ドメインモデル資料を作って。
```

```text
正式な定義が更新されたので、docs/domain-model/order-cancellation-model.md を同じパスで更新して。
```

## 工程

1. **正式な定義の索引** — 業務用語・業務イベント・概念・常に守られること・状態・業務ルール・拒む理由・BDD番号・未決を機械的に抜き出し、標準出力へ返す（fileには書かない）
2. **grill** — 正式な定義と索引だけでは決まらない割り当て（集約の境界、状態ごとの型の分割、索引に無い語の扱い）のうち成果を左右する問いを順に渡して確かめる。対話の作法と問う数の上限は`grill`の公開契約に従い、問われなかった論点は推奨を仮置きして未決に載せる
3. **同一agentの判断** — 依頼・正式な定義・索引・決定・未決を一つの文脈で読む
4. **割り当て** — 索引の語だけを要素にし、要素ごとに目的・何でないか・持つもの・不変条件・生成の条件・協働相手と、操作の契約を書く。正式な定義に無い概念は要素にせず、`## 業務知識へ提案する概念`（名前・なぜ要るか・導いた業務ルール・BDD・足すべき節）へ分け、報告で`formulate-domain`（bdd）へ`references`として渡す次の一手を示す。この入口はdomain-ruleを書き換えない
5. **検査** — 候補本文を標準入力で渡し、正式な定義のpathから導いた索引に対して節と順序、明示索引に無い語、要素ごとの必須項目、操作の契約、BDDと要素の対応記載、業務知識へ提案する概念の表（提案した語が要素一覧に無い）を見る。通ったときに言えるのは構造述語が成り立ったことだけで、必要性や過不足は同じagentが意味判断する
6. **write-doc** — `domain-model`型の資料を1本保存する

割り当ての規律（正式な定義に無い語を要素にしない／形が同じでも概念・コンテキストが違えば分ける／集合への規則を1件に持たせない／確認と変更を分けない／既定は不変で状態を持つのは集約だけ／BDDに対応しない要素は残さない／集約どうしの協働は手段を明記する／データの持ち方の語で業務の事実を書かない）は、[割り当ての規律](plugins/domain-modeling/skills/model-domain/references/disciplines.md)に該当条件・行動・非該当条件つきで置く。正式な定義の節からモデル要素への対応は[対応規則](plugins/domain-modeling/skills/model-domain/references/mapping.md)にある。

## インストール

インストールするのは`domain-modeling@domain-modeling`です。外部の工程を実行するため、`grill@grill`、`write-doc@write-doc`も必要です。下のコマンドには、それらも含めています。正式な定義を作る`bdd-discovery-and-formulation@bdd-discovery-and-formulation`は実行時の依存ではないので含めていません。

公開入口は`model-domain`の1つで、内部skillは持ちません。

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

利用者がインストールするのは`domain-modeling@domain-modeling`だけである。packageは`plugins/domain-modeling/`にあり、公開入口`skills/model-domain/`が`SKILL.md`（目的・入力・判断基準・手順・停止条件・出力）、`playbook.yml`（工程順・入出力・scriptが読む契約）、`references/`（割り当ての規律、対応規則、要素ごとの問い、成果物の形、実行指示書）、`scripts/`（`source.py`索引、`verify.py`検査）を持つ。設定fileは持たず、保存先は公開入力で受け取る。候補本文はagentがインメモリで保持して検査scriptへ標準入力で渡し、作業directory・一時file・後片付け工程を持たない。

## 検証

```bash
bash scripts/validate.sh
```

root契約（配置・manifest・隣接playbook.yml・禁止参照形。`../harness-tools/tools/validate-plugin-repository.py`）、保守toolの回帰検査（`../harness-tools/tools/test-hardening.py --repository`）、隣接`playbook.yml`の宣言と`script:`参照の実在、構文、消費側契約lint（`../harness-tools/tools/lint-consumer-contract.py`。実配布物の兄弟checkout `../grill-plugins/plugins/grill` と `../write-doc-plugins/plugins/write-doc` が要る）、所有script（`source.py` / `verify.py`）の典型例・負例・境界例を実行する。保守toolの参照元は兄弟checkout `../harness-tools/` だけで、無ければ検査は止まる（複製も同期機構も持たない）。CIは`.github/workflows/validate.yml`で `harness-tools` と依存providerを兄弟checkoutし、`harness-tools/ci/validate.sh` で同じcommandを実行する。workspace rootの`bash scripts/validate.sh <このrepositoryの絶対path>`は規約入口の検査と同じroot契約を掛ける。

[意味評価fixture](evals/scenarios.json)は`../harness-tools/scripts/run-evals.sh`（`../harness-tools/tools/evaluate-skills.py`）で生成modelと独立judgeへ渡し、入力、応答、criterionごとの逐語quoteとreasonを記録する。runnerのexit 0は全caseの記録完了だけを示し、品質承認を示さない。criterionの真偽は人またはagentが記録を再読して採否を判断するための意味証拠である。adapter非zero、不正な応答、根拠不整合など記録を完了できない操作失敗は非zeroで終了する。
