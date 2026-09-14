# domain-model

業務知識・コアドメインの正本と索引から、索引の語だけを要素にして値オブジェクト・エンティティ・集約・ドメインイベントへ割り当て、各要素の目的・何でないか・不変条件・操作の契約を書いた候補モデルを1本保存する単一skill pluginです。業務知識を足さず、実装の型やクラスの書き方は書きません。

## 参考資料

- [対応規則](references/mapping.md) — 正本の節から、モデルの要素へ
- [割り当ての規律](references/disciplines.md) — 該当条件・行動・非該当条件つきの8規律（正本に無い語／形が同じでも分ける／集合の規則／確認と変更／不変が既定／BDD対応表の余り／集約どうしの協働／データの持ち方の語を使わない）
- [要素ごとの問い](references/element-questions.md) — 各要素で必ず答える問い

## 設定

`<repo>/.harness-plugins/domain-model.config.yml`、personal設定、同梱既定の順で最上位の完全な1ファイルを選びます。候補の既定の置き場は`domain-model/candidates`で、playbookの後片付けで削除されます。
