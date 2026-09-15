> 作業を始める前に、workspace正本入口 `/Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md` を読み、そこから指定される共通規約とこのrepository固有の規則を適用する。

# AGENTS.md

このrepositoryは、業務知識・コアドメイン（domain-rule）の正本から戦術DDDのドメインモデル資料を作るmarketplaceである。marketplaceへ公開するインストール対象は`domain-modeling` playbook packageだけにし、個々のplaybookと下段skillを別entryへ公開しない。`write-doc`と`grill`は同梱せず、別repositoryにはそのrepositoryが公開するplaybook packageだけで依存する。**外部packageは`playbook:`の工程でだけ呼ぶ。`skill:`や`script:`で指さない。** 呼び方は相手の公開契約に従う。`grill`は契約v1の入力YAMLを公開入口へ直接渡し、指定した`output_to`から結果を読む。`write-doc`は契約v2のobject配列の素材と明示した保存先を公開入口へ直接渡し、直接結果を受け取る。内部skill名・工程id・references・config・保存モード名・scriptの引数・exit codeは文書にもscriptにも書かない。正本を作る`bdd-discovery-and-formulation`は実行時の依存ではなく、その資料の絶対pathを入力として受け取るだけである。後片付けは自分のscriptで、自分が所有する中間成果物だけを削除する。依存versionは固定せず、解決先が自己宣言した契約を検査する。違反は`bash scripts/lint-consumer-contract.py`が落とす。変更後は`bash scripts/validate.sh`を実行する。
