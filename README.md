# Domain Modeling Plugins

業務知識・コアドメイン（domain-rule）の正本を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存する、Claude Code/Codex両対応のmarketplaceである。

## こんなときに使う

**業務として何が正しいかは確定したが、それを形にするエンジニアの頭の中のモデルが揃っていないときに使う。** 実装コードを書く前に、何を要素にし、どこに境界を引き、どの状態で何ができるかを一つの資料にする。

- 同じ正本を読んでも、人によって集約の境界が違う
- 「確認する」と「変更する」が別々の操作になっていて、確認したのに変更し忘れる形が書けてしまう
- 状態によって呼べる操作が違うのに、一つの型が全部の操作を持っている
- 正本に無い語（「〜ロット」「〜マネージャ」）が要素として増えていく
- 契約による設計をしたいが、事前条件・事後条件・拒む理由を書く場所が無い

業務知識の発見・反証（`discover-domain` / `formulate-domain`）、永続化（`discover-data-model`）、実装コード、層構成、画面、APIは扱わない。

## 公開入口

| 今の状況 | 公開入口 | 得られるもの |
|---|---|---|
| domain-rule正本があり、ドメインモデル資料を初めて作る | `model-domain` | 契約つきのdomain-model資料 |
| 既存のドメインモデル資料を、更新された正本に追従させる | `model-domain`（既存資料のpathを渡す） | 同じパスへ更新されたdomain-model資料 |

反証で新しい業務の事実が出たら、それはこの入口では扱わず、domain-rule側の`formulate-domain`へ戻す。モデル資料は正本の写像であり、正本を2つにしない。

## 利用例

```text
docs/domain/order-cancellation.md を正本に、ドメインモデル資料を作って。
```

```text
正本が更新されたので、docs/domain-model/order-cancellation-model.md を同じパスで更新して。
```

## 工程

1. **grill** — 正本だけでは決まらない割り当て（集約の境界、状態ごとの型の分割、正本に無い語の扱い）を1問ずつ確かめる
2. **根拠づけ** — 依頼・正本・決定・未決を束ねる
3. **正本の索引** — 業務用語・業務イベント・概念・常に守られること・状態・業務ルール・拒む理由・BDD番号・未決を機械的に抜き出す
4. **割り当て** — 索引の語だけを要素にし、要素ごとに目的・何でないか・持つもの・不変条件・生成の条件・協働相手と、操作の契約を書く
5. **検査** — 節と順序、正本に無い語、要素ごとの必須項目、操作の契約、BDDの対応の過不足を見る。通ったときに言えるのは述語が成り立ったことだけである
6. **write-doc** — `domain-model`型の資料を1本保存する
7. **後片付け** — 自分の中間成果物だけを削除する

割り当ての規律（正本に無い語を要素にしない／形が同じでも概念・コンテキストが違えば分ける／集合への規則を1件に持たせない／確認と変更を分けない／既定は不変で状態を持つのは集約だけ／BDDに対応しない要素は残さない／集約どうしの協働は手段を明記する／データの持ち方の語で業務の事実を書かない）は、[割り当ての規律](plugins/skills/domain/domain-model/references/disciplines.md)に該当条件・行動・非該当条件つきで置く。正本の節からモデル要素への対応は[対応規則](plugins/skills/domain/domain-model/references/mapping.md)にある。

## インストール

インストールするのは`domain-modeling@domain-modeling`です。外部の工程を実行するため、`grill@grill`、`write-doc@write-doc`も必要です。下のコマンドには、それらも含めています。正本を作る`bdd-discovery-and-formulation@bdd-discovery-and-formulation`は実行時の依存ではないので含めていません。

内部のスキルは同梱されています。個別にインストールせず、公開入口から利用してください。

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

利用者がインストールするのは`domain-modeling@domain-modeling`だけである。`model-domain` playbookと、その実行に使う`domain-model` skillは同じpackageへ内包する。内部機能をmarketplaceの個別インストール対象にはしない。中間生成物の後片付けは、playbookが自分の`scripts/cleanup.py`で行う。

## 検証

```bash
bash scripts/validate.sh
```

配布構造、公開manifest、依存の解決（実配布物の兄弟checkout `../grill-plugins` と `../write-doc-plugins` が要る）、負の試験、消費側契約lint、所有scriptの典型例・負例・境界例を実行する。実行基盤は`product-planning-plugins/shared/runtime-source`を正本とし、`scripts/sync-runtime.py --check`で複製の一致を検査する。
