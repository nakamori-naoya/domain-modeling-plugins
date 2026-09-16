---
name: model-domain
description: 業務知識・コアドメイン（domain-rule）の正本を1本受け取り、そこに現れる業務概念を値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約（事前条件・事後条件・拒む理由）を言語非依存で書いたドメインモデル資料を1本保存する。正本だけでは決まらない割り当てはgrillで1問ずつ確かめる。「ドメインモデルを作って」「この業務資料を集約とVOに落として」「BDDから戦術DDDのモデルを設計して」と言われたとき、実装やデータモデルへ進む前に使う。業務知識の発見・反証、永続化、実装コード、層構成は扱わない。
---

# model-domain（正本の概念を、契約つきの要素へ写す）

読み終えると、domain-rule正本1本の業務概念を、値オブジェクト、エンティティ、集約、ドメインイベントへ割り当て、各要素の目的、何でないか、不変条件、操作の契約を言語非依存で書いたドメインモデル資料1本を保存できる。成果物は業務を形にするエンジニアが同じ要素、同じ境界、同じ操作の契約を思い浮かべるための共通理解の材料であり、実装コード、永続化、層構成、画面、APIは別の資料が担う。

割り当ては写像であって、発見ではない。要素の名前は正本の明示索引にある語から取る。新しい業務の事実が要ると分かったら、この入口を止めて正本の反証へ戻す。

同じdirectoryの`playbook.yml`が工程順の正本である。このSKILLを読んだagentが、正本、依頼、対話結果を保持したまま`steps`を宣言順に辿り、最後まで同じ文脈で判断する。`agent_work: invoking_agent`の工程はこのagentの認知工程、`script:`の工程は明示した入力から閉じた結果を返す決定論的tool、`playbook:`の工程は外部公開Skillの直接呼び出しである。

## 入力

| 入力 | 内容 | 満たさないときの扱い |
|---|---|---|
| `domain_rule_path` | domain-rule正本の絶対path。1本だけ | 無ければ「どのdomain-rule資料を正本にしますか（絶対path）」、複数なら「どれを正本にしますか。モデルは正本1本につき1本です」を返して停止する |
| `user_input` | 依頼文。新規か更新か、既知の割り当て方針 | 読めなければ`settle`で問う |
| `existing_document_path` | 更新の場合だけ。同じ正本から作られた既存ドメインモデル資料の絶対path | 依頼に無い既存資料を探して更新扱いにしない |
| `output_directory` | 新規の場合だけ。既存の書き込み可能な絶対directory | 依頼に構成が示されていればそれに従う。無ければ既存資料の構成を読み、置き場と名前を一度だけ提案する。同名fileがあれば停止する |
| `name` | 新規の場合だけ。path要素を含まない`.md`file名。日本語名を許す | 同上 |

指されたfileがdomain-rule型でない（`# 概要`から`# BDD`までの見出しを持たない）場合は「この資料はdomain-rule型ではありません。先に正本を作りますか」を返して停止する。新規の2値と更新先は排他であり、同時に渡さない。

## 判断基準

`assign`の前に[ドメイン要素へ割り当てる判断規律](references/modeling-judgment.md)、[対応規則](references/mapping.md)、[割り当ての規律](references/disciplines.md)、[要素ごとの問い](references/element-questions.md)、[成果物の形](references/deliverable.md)を全文読む。読まずに割り当てると、正本に無い語を要素にするか、形が同じ語を1つにまとめる。

| 観察対象 | 述語 | 行動 |
|---|---|---|
| 要素にしたい語 | 正本の明示索引（`vocabulary`）にある | 要素にできる。無ければ要素にせず、「捨てた割り当て」か「未決」へ理由付きで残す。正本へ足すと決まったら止めて反証へ戻す |
| 業務用語 | 同一性で区別し状態が変わっても追う / 値で区別し生成時から制約を守る / 複数概念を一つの不変条件で束ねる境界の根 | それぞれエンティティ / 値オブジェクト / 集約ルートにする |
| 識別子を持つ語 | この文脈でその生成から終端までを扱い、他の事実から決め直せない | 集約にする。ライフサイクルを扱わず決め直せるなら導出される値オブジェクトにする |
| 業務イベント | この文脈の集約の操作の事後条件として起きる | 判断を始めるかどうかに関わらずドメインイベントにする。どの操作も発さないものは載せず「捨てた割り当て」へ |
| 常に守られること | 一要素の内側で守れる / 複数要素にまたがる / どの集約でも守れない | その要素の不変条件 / 集約の不変条件 / 守る場所を明示した集約間不変条件または未決 |
| 状態を持つ要素 | 状態によって呼べる操作が違う | 型を分ける。同じなら分けず、どちらも理由を書く |
| アクター | 型にしたくなる | 型にせず、操作の事前条件と拒む理由へ写す |
| 「確認する」と「変更する」 | 別の操作として並んでいる | 判断を事前条件、変更を事後条件、不成立を拒む理由にした一操作へまとめる。判定だけを使うBDDがある場合だけ独立判定を置く |
| 各要素・各操作 | いずれかのBDDに対応する | 残す。対応しないものは詳細から外し「捨てた割り当て」へ理由付きで移す |
| 複数集約の協働 | 識別子で参照 / 値として渡す / ドメインイベント / 呼び手が両方を操作、のどれかと、渡すもの、一貫性、片側だけ成立した場合が決まる | 書く。決まらなければ`settle`で問う |
| 決定にも未決にも無く、正本からも決まらない割り当て | 見つかった | 勝手に決めず停止し、その論点を返す |
| 検査の結果 | 通った | 通ったのは述語であり、「モデルは正しい」ではない。`warnings`は同じagentが正本と候補を読み返す箇所の索引として報告に写す |

## 手順

1. **prepare-work-directory。** system temporary directory内にこのrun専用の`work_directory`を一つ作る。索引と検査候補だけをそこへ置く。
2. **index-source（`scripts/source.py`）。** `python3 scripts/source.py --playbook playbook.yml --source <domain_rule_path> --output <work_directory>/source-index.json`を実行する。pathはこのSKILLと同じdirectoryを基準にする。正本の業務用語、業務イベント、概念、常に守られること、状態、誰が行えるか、業務ルール、拒む理由、BDD番号、未決を機械的に抜き出し、終了code 0でstdoutに`source_index_path`と件数を返す。正本が契約の節（`playbook.yml`の`contract.source_sections`）を持たなければ終了code 2と診断を返すので、正本を直してもらう。索引の`vocabulary`にある語だけが要素の名前になれる。
3. **settle（`grill`）。** [実行指示書](references/execution-guidance.md)の「settleで確かめること」に従い、正本と索引から読み取れることは問わず、正本だけでは一つに決まらない割り当て（集約の境界、状態ごとの型の分割、索引に無い語の扱い、形が同じ2つの語、集約どうしの協働、正本の未決の影響）だけを、推奨を添えて1問ずつ確かめる。入力は`contract: grill/grill`、`version: 1`、`topic`（正本の題材名）、`context`（`purpose`・`audience`・`boundary`）、`questions`（`{id, question, recommendation}`）、`grounding`（正本の絶対path）である。返った結果の`status`が`completed`で、`decisions`と`open_questions`が配列（各決定に`rationale`、各未決の`state`が`open`または`withdrawn`）であることを確かめる。欠落、`null`、別の型は停止する。全体への明示合意を得る前は後続へ進まない。
4. **assign。** 正本、索引、決定、未決を一つの文脈で読み、判断基準に従って完成本文を作る。順序は、要素一覧を決める → 各要素の詳細（要素ごとに`###`、項目ごとに`####`、操作ごとに`#### 操作: <操作名>`）を書く → モデル図（集約ごとに`### 集約: <集約名>`、`- 責務:`、`- 境界:`、Mermaid classDiagram。集約が2つ以上なら`### 集約どうしの関係`）を描く → 集約の境界を引く → 状態と型の分割を書く → BDDとの対応表（`| BDD | 要素 | 操作 | 成立を決める不変条件・事前条件 |`と`- 対応しないBDD:`、`- 対応のない要素・操作:`）を作る → 余りを落とす → 捨てた割り当てと未決を書く、である。空欄は残さず「なし」または未決へ送る理由を書く。同じ本文を`<work_directory>/candidate-model.md`へ書く。
5. **verify（`scripts/verify.py`）。** `python3 scripts/verify.py --playbook playbook.yml --candidate <work_directory>/candidate-model.md --source-index <work_directory>/source-index.json`を実行する。節と順序、実装の節の混入、明示索引に無い語、要素ごとの必須項目と操作の契約、モデル図のクラスと要素の一致、集約どうしの協働の手段、BDDと要素の対応記載、未決の有無を述語として検査し、終了code 0でstdoutに`verified_model_path`と`warnings`を返す。2なら通らないので`assign`へ戻って候補を直す。検査を緩めない。候補が直せないのは正本の側に問題があるときで、そのときは正本の反証へ戻す。
6. **document（`write-doc`）。** 検査済み本文を`{kind: text, content: <完成本文>}`の1要素配列で`material`に、`domain-model`を`document_type`に、[成果物の形](references/deliverable.md)の絶対pathを`references`に渡す。新規なら`output_directory`と`name`、更新なら`existing_document_path`を`update_target`として排他的に渡す。返った結果の`status`が`completed`で、`path`が指定した保存先（更新なら`update_target`）と一致することを確かめ、その`path`を`domain_model_document_path`にする。`failed`、結果欠落、path不一致なら理由を報告して停止する。
7. **cleanup（`scripts/cleanup.py`）。** 保存成功を確認した後だけ、`python3 scripts/cleanup.py --playbook playbook.yml --work-dir <work_directory> --artifact source_index=<索引の絶対path> --artifact candidate_model_path=<候補の絶対path> --artifact domain_model_document_path=<保存した資料の絶対path>`を実行する。`playbook.yml`の`contract.cleanup.delete_after_document`に宣言した論理名の成果物だけを、`work_directory`内の追跡されていない通常fileに限って削除し、終了code 0で削除・保持の一覧を返す。宣言に無い論理名、`preserve`の成果物、`work_directory`の外、symlink、追跡済みfileは削除せず、契約を満たさなければ終了code 2で何も削除しない。

## 停止条件

- 正本のpathが無い、複数ある、domain-rule型でない
- 索引化が終了code 2で終わった（正本が契約の節を持たない）
- `grill`が`completed`以外を返した、または`decisions` / `open_questions`が配列でない
- 決定にも未決にも無く、正本からも決まらない割り当てが見つかった。どの割り当てが決まらず、何が分かれば決まるかを返す
- 検査が通らず、候補を直しても解消しない。正本の側の問題なら反証へ戻す
- 新規作成先が依頼に無く確認もできない、`write-doc`が`completed`以外を返した

停止したときは部分的な候補を保存して完了にせず、どこまで確定し、何が分かれば続けられるかを返す。

## 報告

- 保存した資料の絶対pathと、元にした正本の絶対path
- 要素一覧（要素名・種別）と、集約の境界
- 状態と型の分割（どの状態で何ができ、何ができないか）
- 捨てた割り当てと、その理由
- 未決と、何が分かれば確定するか
- 検査の`warnings`（例外扱いの種別、対応しないBDD、対応のない要素）。索引外の語はwarningではなく失敗である
- 機械検査が通ったときに言えるのは、判定した述語が成り立ったことだけである
