# 期待する判定

この較正の資料は、2026-09-27-run1 の資料に、既知の欠陥を四つ埋めた写しである。grill の記録は元のままである。埋めた欠陥は次のとおりで、判定は欠陥の作り方から決まる。埋めていない条件は run1 の期待と同じにした。

一つ目は、集約に判定だけの操作「フォローできるか確かめる」を足した。業務知識に無い語でもある。二つ目は、状態遷移図に業務知識に無い「外した」状態と、そこから戻る矢印を足し、本文も同じフォローが戻る形に書き換えた（外した状態で「フォローを外す」の拒む理由も無い）。三つ目は、守ることの守り手を、役割ではなく「follows テーブルの一意制約と SERIALIZABLE の分離レベル」という手段で書いた。四つ目は、未決の重複の守り手から仮置きの断りを消し、決めたことにした（記録では仮置きのまま）。

採点役には、このファイルを読ませない。

## 判定

- boundary-invariant-scope: PASS
- boundary-set-rule-owner: FAIL
- boundary-not-aggregate: PASS
- command-no-check-only: FAIL
- command-missing-arrow-reason: FAIL（境目）
- command-state-from-knowledge: FAIL
- language-from-knowledge: FAIL
- language-english-name: PASS（境目）
- guess-marked: FAIL
- guess-no-rewrite-knowledge: FAIL（境目）
- shape-diagram-first: PASS
- shape-no-technology: FAIL
- shape-limited-values: PASS
- shape-open-questions: PASS
- grill-only-shape-changing: FAIL
- follow-pair-rule-outside: FAIL（境目）
- follow-limit-by-count: PASS
- follow-ended-not-revived: FAIL
- follow-foreign-facts: PASS

## 理由

guess-no-rewrite-knowledge は、業務知識と食い違う状態を提案として示さずにモデルの側で決めたので FAIL とした。業務知識の資料自体は書き換えていないので、どちらの文で読むかで分かれうる境目とした。follow-pair-rule-outside は、守り手が手段で書かれ役割が無いので FAIL と見るが、「集約の外で守る」形自体は保たれているので境目とした。

command-missing-arrow-reason は、足した「外した」状態で「フォローを外す」を呼ぶ組に拒む理由が無いので FAIL と期待した。採点役は、元の資料の「外すフォローが見つからないときは…拒む」をこの組に当てて PASS にした。外した状態のフォローは「見つかる」ので当たらないと読むが、文の読み方で分かれうるので境目とした。
