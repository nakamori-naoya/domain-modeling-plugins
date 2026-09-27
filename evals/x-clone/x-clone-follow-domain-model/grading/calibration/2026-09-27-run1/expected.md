# 期待する判定

この較正の資料は、2026-09-27 の1回目の実行（claude plugin eval、`--runs 1 --ablation none`）で作られた `domain-model.md` と grill の記録である。下の判定は、eval を組んだ担当が資料、記録、業務知識を読んで出したもので、採点役がこれを再現できるかで採点の形を確かめる。境目と書いた条件は、読み方で判定が分かれうるので、一致の数を別に数える。

採点役には、このファイルを読ませない。

## 判定

- boundary-invariant-scope: PASS
- boundary-set-rule-owner: PASS
- boundary-not-aggregate: PASS
- command-no-check-only: PASS
- command-missing-arrow-reason: FAIL
- command-state-from-knowledge: PASS
- language-from-knowledge: PASS
- language-english-name: PASS（境目）
- guess-marked: PASS
- guess-no-rewrite-knowledge: PASS
- shape-diagram-first: PASS
- shape-no-technology: PASS
- shape-limited-values: PASS
- shape-open-questions: PASS
- grill-only-shape-changing: FAIL
- follow-pair-rule-outside: PASS
- follow-limit-by-count: PASS
- follow-ended-not-revived: PASS
- follow-foreign-facts: PASS

## 理由

grill-only-shape-changing は、問1と問2の答えに「仮置きではない（業務知識の資料の事実で答えた）」とあり、業務知識から決まることを問うているので FAIL とした。

language-english-name は、業務知識で英名が未定の利用者IDに `UserId` を置いている。図の注記と未決で仮の識別子だと断っているが、候補を業務知識への提案には書いていない。断りがあるので PASS とし、提案に書くことまで求めるかで分かれるので境目とした。

集合への規則（二人の間の重複、フォロー上限、同時に起きたとき）は、どれも「フォローを記録する側」という役割で守り手が書かれ、上限はフォロー中の人数を受け取る形なので、境界と守り手の条件はすべて PASS とした。

command-missing-arrow-reason は、業務知識が拒む理由を持つ「一度もフォローしていない相手のフォローを外す」を、「コマンドを呼ぶ前に呼び手が…拒む」とコマンドの外に置いているので FAIL とした。
