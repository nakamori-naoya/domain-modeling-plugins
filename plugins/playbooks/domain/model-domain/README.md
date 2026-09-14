# model-domain

業務知識・コアドメイン（domain-rule）の正本を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存するplaybook pluginです。業務知識の発見・反証、永続化、実装コード、層構成、画面、APIは作りません。

## 必要なplugin

同じpackage内の`domain-model`と、外部の`grill@grill`、`write-doc@write-doc`に依存する。外部packageへは公開playbookでだけ依存し、`playbook:`の工程として呼ぶ。相手の内部skill名、工程id、references、config、保存モード名、scriptの引数には依存しない。versionは固定せず、解決先のmanifest identityと自己宣言した契約を検査する。

正本を作る`bdd-discovery-and-formulation`は実行時の依存ではない。この playbook が受け取るのは、そのplaybookが保存した資料の絶対pathである。

差し替えたい利用者は`~/.config/harness-plugins/dependencies.yml`などで契約ID（`grill/grill`、`write-doc/write-doc`）に別の実体を束縛する。playbookの`requires`は変えない。

## 入力と出力

入力はdomain-rule型の資料1本（絶対path）です。既存のドメインモデル資料を同じ正本から更新する場合は、その資料の絶対pathも受け取ります。

工程は次の順です。

1. `grill`で、正本だけでは決まらない割り当て（集約の境界、状態ごとの型の分割、正本に無い語の扱い）を1問ずつ確かめる
2. 依頼・正本・決定・未決を根拠づけられた入力へ束ねる
3. 正本から業務用語・業務イベント・概念・常に守られること・状態・業務ルール・拒む理由・BDD番号・未決を機械的に索引にする
4. `assign-domain-model`が、索引の語だけを要素にして候補モデルを書く
5. `verify.py`が節と順序、正本に無い語、要素ごとの必須項目、操作の契約、BDDの対応の過不足を検査する
6. 検査済みモデル・正本のpath・決定と未決を1つの素材へ束ねる
7. `write-doc`が`domain-model`型の資料を1本保存する
8. この playbook が所有する中間成果物だけを削除する

最終資料の既定の置き場は`domain-model/`（作業repositoryの設定で変えられる）です。中間成果物は解決済み設定と同じ一時directoryへ置き、保存後に削除します。

## 検査で言えること

`verify.py`が通ったときに言えるのは、判定した述語が成り立ったことだけです。「モデルが正しい」「境界が適切」は判定していません。`warnings`（索引外だが正本の本文に現れる語、例外扱いの種別、対応しないBDD、対応のない要素）は合否ではなく、人が読み返す箇所の索引です。

## 設定

`<repo>/.harness-plugins/model-domain.config.yml`、personal設定、同梱既定の順で最上位の完全な1ファイルを選びます。`steps`を上書きする場合も、grill→根拠づけ→正本の索引→割り当て→verify→束ね→write-doc→自分の中間生成物の後片付けという責務契約は維持します。
