> 作業を始める前に、workspace規約入口 `/Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md` を読み、そこから指定される共通規約とこのrepository固有の規則を適用する。

# AGENTS.md

このrepositoryは、業務知識・コアドメイン（domain-rule）の正式な定義から戦術DDDのドメインモデル資料を作るmarketplaceである。

- marketplaceへ公開するインストール対象は`domain-modeling` package 1つで、公開入口は`plugins/domain-modeling/skills/model-domain/`だけである。内部skillは持たない。directory名、`SKILL.md`の`name`、隣接`playbook.yml`の`name`は同じ一つの名前にする。
- `SKILL.md`は目的、入力、判断基準（観察対象と二者択一の述語を肯定形で）、手順、停止条件、出力を持つ。実行基盤の配管（環境変数によるroot解決、設定解決script、`${.…}`マクロ、同期block）を書かない。入口が使うtool（`scripts/source.py` / `verify.py`）は入口directory基準の相対pathで示し、入力（標準入力の本文と正式な定義のpath）、出力、終了code、失敗時に止まるか回復するかを宣言する。scriptが読む契約は隣接`playbook.yml`の`contract`だけである。
- 設定fileを持たない。保存先（`output_directory` / `name` / `existing_document_path`）は公開入力で受け取り、既定値を持たない。案件固有の値をSKILL・reference・fixtureの既定にしない。
- `write-doc`と`grill`は同梱せず、`playbook.yml`の`requires`と`playbook:`工程だけで依存する。相手の内部skill名・工程id・references・config・保存モード名・scriptの引数・exit codeは文書にもscriptにも書かない。`grill`は契約v1の入力objectを公開入口へ直接渡し、`write-doc`は契約v2のobject配列の素材と排他的な新規／更新保存先を公開入口へ直接渡し、直接結果を受け取る。
- 正式な定義を作る`bdd-discovery-and-formulation`は実行時の依存ではなく、その資料の絶対pathを入力として受け取るだけである。正式な定義の明示索引に無い語を要素にせず、新しい業務の事実が要ると分かったら仮説を未決に残して資料を完成させ、正式な定義の反証を提案する。
- agentが作った候補本文は検査scriptへ標準入力で渡す。作業directory、一時file、後片付け工程を置かない。
- 変更後は`bash scripts/validate.sh`と、workspace rootの`bash scripts/validate.sh <このrepositoryの絶対path>`を実行する。保守tool（root validator、消費側契約lint、回帰検査、release、eval runner）の参照元は兄弟checkout `../harness-tools/tools/` だけで、このrepositoryは複製を持たない。違反は`../harness-tools/tools/lint-consumer-contract.py`と`tests/test-domain-modeling.sh`が落とす。
