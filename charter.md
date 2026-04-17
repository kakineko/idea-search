---
# ============================================================
# Machine-readable constraints. All values start as null and
# are filled in by the President (社長) over time.
# Comments below each key show the expected shape — they are
# not enforced; downstream loaders should treat null as
# "unspecified, fall back to module default."
# ============================================================

charter_version: 0          # bump on every meaningful edit
last_reviewed_on: null      # ISO-8601 date (e.g. 2026-04-17)

budget:
  monthly_usd: null         # e.g. 50
  per_run_usd: null         # e.g. 0.50
  total_cap_usd: null       # hard ceiling; halt when exceeded

stop_conditions:
  max_runs_per_day: null            # e.g. 20
  max_consecutive_failures: null    # e.g. 3
  max_cost_per_hour_usd: null       # e.g. 5
  max_wallclock_minutes_per_run: null

risk:
  acceptable_failure_rate: null     # 0.0 – 1.0
  irreversible_actions_allowed: false
  external_writes_allowed: false    # API calls that mutate state

escalation:
  cost_overrun_pct: null            # e.g. 20  (= 120% of budget)
  failure_streak: null              # e.g. 5
  novelty_collapse_threshold: null  # avg pairwise jaccard above this → escalate

review_cadence_days: null           # how often the President revisits this file
---

# Charter

> **Role of this document.**
> This is the **single input from the President (社長) to the harness.**
> Every module in this repo — `idea-search` today, downstream verifiers
> tomorrow — is expected to read this file and treat it as authoritative.
> Modules MUST NOT mutate it. Changes happen only through an explicit
> review by the President and are recorded in the *Change Log* below.
> Empty fields mean "use module defaults" — the system must boot with
> this file in its initial all-placeholder state.

---

## Mission

<!--
1〜3行で装置の目的を書く。
例:
- 「曖昧な問いから検証可能な仮説候補を多方向に生成し、下流の自動検証に渡す」
- 「人間の最終判断を二次目的とし、構造化候補の安定供給を主目的とする」
- 「短期はベースライン超え、中期は人手レビュー削減、長期は自動検証ループの自走」
-->

## Boundaries

<!--
やらないこと / 触らないことを箇条書き。
例:
- 本人の許可なしに外部 API へ書き込みを行わない
- charter.md 自身を自動編集しない
- 個人情報や顧客データを扱う問いに自動応答しない
- 未署名の設定変更で本番経路を切り替えない
-->

## Risk Tolerance

<!--
リスクに対する哲学・方針を散文で。具体的な数値は YAML フロントマターへ。
例:
- 「探索は積極的に。ただし不可逆な操作は常に承認を経る」
- 「コストは月次予算に対し ±20% 以内なら自走、それを超えたら停止して報告」
- 「失敗より沈黙を嫌う。停止する場合は理由をログに残す」
-->

## Success Criteria

### Short term (〜1ヶ月)
<!--
例:
- compare サブコマンドで `full` モードが `baseline-single` に対し
  cluster_count_proxy で +1 以上を安定して示す
- mock provider のみでテストカバレッジ 80% 以上
-->

### Mid term (〜3ヶ月)
<!--
例:
- 下流検証パイプライン (Task C 以降) と JSON スキーマで疎結合に接続
- Anthropic provider 経由で実問題に対する週次レポートが自動生成される
-->

### Long term (〜1年)
<!--
例:
- 人間の最終判断を必要とせず、検証通過率で意思決定可能な状態
- charter.md の `escalation` 条件以外、社長の介入が不要
-->

## Emergency Stop Conditions

<!--
ハーネスが即時停止すべき状況を列挙。
YAML 側の閾値と対応させること。
例:
- `total_cap_usd` を超過した
- `max_consecutive_failures` 回連続で失敗した
- 出力の avg_pairwise_similarity が `novelty_collapse_threshold` を超えた
  （= 多様性が崩壊し装置の存在意義が消えた）
- charter.md 自体が読めない / パースできない
-->

## Tone & Style

<!--
生成物 (アイデア、レポート、コミットメッセージ) のトーン指針。
LLM プロンプトに混ぜて使う想定。
例:
- 「断定より仮説。`〜と思われる` ではなく `〜なら検証可能` の形で書く」
- 「マーケ的修辞を避け、機構と前提を明示する」
- 「日本語応答時もコード識別子・ファイル名は英語ベースで保つ」
-->

## Escalation Policy

<!--
社長 (President) を呼ぶ条件と、その呼び方。
例:
- 予算が `cost_overrun_pct` を超えた → 24h 以内に Slack/email でサマリ
- 同一原因で連続 `failure_streak` 回失敗 → 即時停止して原因を 1 ページで報告
- charter.md の前提と現実が矛盾し始めた → 改訂提案を PR として提出
-->

## Change Log

<!--
charter.md への変更履歴。手動で追記する。フォーマット:
- YYYY-MM-DD  v{charter_version}  変更概要 / 承認者
例:
- 2026-04-17  v0  初版テンプレート作成 (placeholder のみ)
- 2026-05-01  v1  budget.monthly_usd を 50 に設定
-->
