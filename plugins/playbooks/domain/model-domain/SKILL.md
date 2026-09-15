---
name: model-domain
description: 業務知識・コアドメイン（domain-rule）の正本を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存する。正本だけでは決まらない割り当てはgrillで1問ずつ確かめる。「ドメインモデルを作って」「この業務資料を集約とVOに落として」「BDDから戦術DDDのモデルを設計して」と言われたとき、実装やデータモデルへ進む前に使う。業務知識の発見・反証、永続化、実装コード、層構成は扱わない。
---

# model-domain（正本の概念を、契約つきの要素へ写す）

**正本の明示索引に無い語を要素にしない。** 要素の名前は索引対象のユビキタス言語から取る。本文にだけ現れて必要に思えた語は、要素にせず「捨てた割り当て」か「未決」へ理由付きで残し、必要なら正本の反証へ戻す。

**割り当ては写像であって、発見ではない。** 新しい業務の事実が要ると分かったら、それはこの段取りの外（domain-ruleの発見・反証）へ戻す。ここで業務知識を足さない。

## 1. 実行契約を受け取る

このSKILLを実行する同じagentが、同じdirectoryの`playbook.yml`と本文から参照する資料を全文読み、利用者の入力と明示された資料を保持した一つの文脈で最後まで判断する。YAMLの`steps`は工程順・`needs`・`provides`の正本であり、宣言順に辿る。`agent_work: invoking_agent`は別skillや架空runtimeを呼ぶ印ではなく、このagentが同じ文脈で意味判断する工程である。`script:`は決定論的な索引抽出・構造検査・安全な後片付け、`playbook:`は依存先の公開Skill呼び出しだけを表す。必要な入力や結果が無ければ推測せず停止する。

`${.instructions.execution.directive}`と`${.instructions.interaction.directive}`に従い、`${.playbook.steps}`の認知責務を同じagentが上から実行し、決定論的toolの結果だけを工程間で受け渡す。外部packageは`playbook:`の工程でだけ呼び、§3の手順に従う。

[実行指示書](references/execution-guidance.md)を必ず読む。`playbook.yml`は工程順・依存・入出力を決定し、実行指示書は各工程で意識することと、grillへ渡す題材固有の文脈を補う。

## 2. 入力を確かめてから始める

**開始条件は、domain-ruleの正本が1本、絶対pathで指されていることである。** 次のどれかなら、推測せず、その1問を返して停止する。

| 観察 | 返す問い |
|---|---|
| 正本のpathが依頼に無い | 「どのdomain-rule資料を正本にしますか（絶対path）」 |
| pathが複数ある | 「どれを正本にしますか。モデルは正本1本につき1本です」 |
| 指されたファイルが業務知識・コアドメインの型でない（`# 概要`〜`# BDD`の見出しを持たない） | 「この資料はdomain-rule型ではありません。先にdiscover-domainで正本を作りますか」 |

既存のドメインモデル資料が同じ正本から作られていて、依頼が「更新」なら、その資料の絶対pathを同じ文脈に保持する。依頼に無い既存資料を探して更新扱いにしない。

## 3. 正本を先に索引にする

`prepare-work-directory`工程では、同じagentがsystem temporary directory内にrun専用`work_directory`を一つ作る。`index-source`では、同じdirectoryの`scripts/source.py`へ公開`playbook.yml`、domain-rule正本の絶対path、run専用directory内の出力pathを直接渡し、索引の絶対pathを受け取る。

索引は、正本の業務用語・業務イベント・概念・常に守られること・状態・誰が行えるか・業務ルール・拒む理由・BDD番号・未決を機械的に抜き出したものである。**索引の語だけが要素の名前になれる。** 正本が契約の節を持たなければここで止まる。正本を直してから再実行する。この索引を作ってから、正本と索引の両方から分かることを質問候補から除く。

## 4. 外部playbookの呼び方

`playbook:`の工程（`settle`と`document`）は、相手の公開契約だけを使って呼ぶ。相手のskill名、工程id、references、config、保存モード名、scriptの引数は使わない。呼び方は各公開契約の版に従う。

### settle（`grill`）

`grill`の公開契約が定める入力objectを公開Skill `grill:grill`へ直接渡し、公開入口の手順に従う。設定解決や`prepare.sh`は使わない。完了したら直接返された結果objectだけを読む。永続記録も必要な場合だけ利用者が明示した`output_to`を追加する。相手のrootから内部pathを組み立てず、内部の記録やログも読まない。

入力に`topic`（正本の題材名）、`context`（`purpose`・`audience`・`boundary`）、`questions`（`{id, question, recommendation}`。推奨は必ず添える）、`grounding`（正本の絶対path）を渡す。**正本と索引から読み取れることは問わない。** 問うのは、正本だけでは一つに決まらない割り当てだけである。何を問うかは[実行指示書](references/execution-guidance.md)の「settleで確かめること」に従い、題材固有の観点は`context`で渡して相手に持ち込ませない。

出力は`decisions`と`open_questions`である。対話結果、domain-rule正本、依頼、指定された既存資料は同じagentの文脈に保持し、値運搬だけの`ground`ファイルは作らない。

契約を満たさない出力（契約IDや版の不一致、`status`が`completed`でない、`rationale`の無い決定、`open`/`withdrawn`以外の状態）では停止する。全体への明示合意を得る前は後続工程へ進まない。`decisions`と`open_questions`はキーが存在する配列でなければならず、欠落、`null`、別の型を空配列へ補正しない。契約どおりの空配列は合法として受け入れる。

### document（`write-doc`）

公開契約v2の入力を公開Skill `write-doc:write-doc`へ直接渡す。`material`は同じagentが作って検査した本文を`{kind: text, content: <完成本文>}`としたobject配列にする。`document_type`に`${.playbook.document_type}`を渡し、`references`には[成果物の形](references/deliverable.md)の絶対pathを渡す。

保存先は、新規作成なら公開入力の`output_directory`と`name`、既存資料の更新なら利用者が明示した`existing_document_path`を`update_target`へ渡す。両方式は排他であり、新規の2値と更新先を同時に渡さない。新規作成先が依頼に無ければ、保存先やファイル名を推測せず利用者へ確認して停止する。

結果は`status`（`completed` | `failed`）と、成功時の`path`または失敗時の`reason`として直接受け取る。中間YAMLと出力YAMLは作らない。1回の呼び出しで作る資料は1本だけである。`status: completed`と絶対pathを確かめてから次へ進む。

## 5. 割り当てて検査する

`assign`工程へ入る前に[ドメイン要素へ割り当てる判断規律](references/modeling-judgment.md)を全文読む。同じagentが正本、索引、決定、未決、`${.playbook.contract}`とこの判断規律を同じ文脈で適用し、正本からの写像、8つの割り当て規律、各要素へ答える問いを満たす完成本文を作る。同じ本文をrun専用directoryの検査用一時ファイルへ書き、続く`verify`工程へ公開`playbook.yml`、候補、索引の絶対pathを直接渡す。

検査は述語だけを見る（節と順序、実装の節の混入、明示索引に無い語、要素ごとの必須項目と操作の契約、BDDと要素の対応記載、未決の有無）。**通らなければ`assign`へ戻って候補を直す。検査を緩めない。** 通ったら`warnings`を報告に写す。`warnings`は対応の必要性や過不足を断定せず、同じagentが正本と候補を読み返す箇所の索引である。

検査に通った本文は同じagentが保持し、値運搬だけの`material`ファイルを作らず`write-doc`へ`kind: text`で渡す。

## 6. 後片付けして報告する

最終資料の保存成功を確認した同じagentだけが、公開`playbook.yml`、`work_directory`、論理名つき絶対pathを`cleanup.py`へ直接渡す。`${.playbook.contract.cleanup}`で削除候補にしたrun専用directory内の今回の作業用成果物だけを後片付けする。保持対象、run専用directoryの外、symlink、追跡済みファイルは削除しない。

報告する内容:

- 保存した資料の絶対pathと、元にした正本の絶対path
- 要素一覧（要素名・種別）と、集約の境界
- **状態と型の分割** — どの状態で何ができ、何ができないか
- 捨てた割り当てと、その理由
- 未決と、何が分かれば確定するか
- 検査の`warnings`（例外扱いの種別、対応しないBDD、対応のない要素）。索引外の語はwarningではなく失敗である
- **機械検査が通ったときに言えるのは、判定した述語が成り立ったことだけである。** 「モデルは正しい」と書かない

資料が保存されるまで完了にしない。データモデル・実装コード・層構成は作らない。
