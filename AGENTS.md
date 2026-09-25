> 共通の規約は /Users/naoya-nakamoriq/Documents/Github/harness-pluginsv2/AGENTS.md にある。ここには、この repository だけの規則を置く。

# domain-modeling

この repository は、業務知識の資料（domain-rule）から戦術 DDD のドメインモデル資料を作る skill `model-domain` を配布する。インストール対象は package `domain-modeling` 一つで、公開入口は `plugins/domain-modeling/skills/model-domain/` だけである。内部 skill は持たない。

- ドメインモデルは議論に使うので、図が主役である。資料の形は write-doc の domain-model 型の template が持ち、`model-domain` はその template を直接読む。
- domain-rule 資料は、bdd-discovery-and-formulation が作ったものを入力として受け取るだけで、書き換えない。domain-rule 資料に無い語を要素にしない。
- 利用者に問うときは `grill` を、資料を保存するときは `write-doc` を呼び、どちらも同梱しない。設定ファイルは置かず、保存先は依頼で受け取る。
