# model-domain

業務知識・コアドメイン（domain-rule）の正本を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存するplaybook pluginです。業務知識の発見・反証、永続化、実装コード、層構成、画面、APIは作りません。

## 必要なplugin

同じpackage内の`domain-model`と、外部の`grill@grill`、`write-doc@write-doc`に依存する。外部packageへは公開playbookでだけ依存し、`playbook:`の工程として呼ぶ。相手の内部skill名、工程id、references、config、保存モード名、scriptの引数には依存しない。versionは固定せず、解決先のmanifest identityと自己宣言した契約を検査する。

正本を作る`bdd-discovery-and-formulation`は実行時の依存ではない。この playbook が受け取るのは、そのplaybookが保存した資料の絶対pathである。

実行するagentは、同じ実行環境で利用可能な公開Skill `grill:grill`と`write-doc:write-doc`を直接呼ぶ。依存先repositoryのroot、cache、設定fileを探索・解決しない。

## 入力と出力

入力はdomain-rule型の資料1本（絶対path）です。既存資料を更新する場合はその絶対pathだけを保存先として受け取り、新規作成の場合は既存資料pathを渡さず`output_directory`と`name`を受け取ります。

工程は次の順です。

1. 同じagentがrun専用directoryを作る
2. 正本から業務用語・業務イベント・概念・常に守られること・状態・業務ルール・拒む理由・BDD番号・未決を機械的に索引にする
3. `grill`へ直接objectを渡し、正本と索引だけでは決まらない割り当てを1問ずつ確かめ、全体への明示合意を待つ
4. 同じagentが正本・索引・決定・未決を読み、索引の語だけを要素にして候補モデルを書く
5. `verify.py`が節と順序、索引に無い語、要素ごとの必須項目、操作の契約、BDDの対応の記載有無を検査する
6. 同じagentが検査済み本文をobject配列の`material`にして、排他的な新規／更新保存先とともに`write-doc`へ直接渡す
7. この playbook が所有する中間成果物だけを削除する

`grill`の`questions`、`decisions`、`open_questions`は契約どおりなら空配列も合法です。`grill`が未合意・失敗、または`write-doc`が`failed`なら後続工程へ進みません。成功時は`write-doc`が直接返した絶対`path`を最終成果として扱います。

## 検査で言えること

`verify.py`が通ったときに言えるのは、判定した述語が成り立ったことだけです。「モデルが正しい」「境界が適切」は判定していません。索引外の語は本文に現れていても失敗します。`warnings`（例外扱いの種別、対応しないと明示されたBDD、対応がないと明示された要素）は構造上の事実だけを示し、必要性・過不足は同じagentが読み返して判断します。

## 設定

repository保守では同梱runtimeを検査しますが、公開Skillのconsumer実行経路は外部依存の設定探索やruntime解決を行いません。
