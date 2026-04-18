# Phase 2 実装計画（ハッカソン 4/22-4/28）

**Date**: 2026-04-18
**Context**: Built with Opus 4.7 hackathon 準備
**関連ドキュメント**:
- `results/2026-04-18_outside_signal_design_ja.md`（Outside signal 詳細設計）
- `results/2026-04-18_agent_teams_poc.md`（Agent Teams 動作確認）

## 核心理解

このハッカソンの本質は **Outside signal の実装と検証**。

システム面（Agent Teams 移植、phase 切り分け）は 1 日で終わる見込み。
既存の idea-search コードは構造が綺麗で、Claude Code に任せれば素直に移植できる。
PoC で Agent Teams の動作と制約（ネスト不可）も確認済み。

残り 6 日は Outside signal と向き合う時間。ここが他の参加者との差別化になる。

## 日程

### Day 1（4/22 水）：システム面を一気に仕上げる

- 1:00 AM JST Kick-off Zoom（1-2時間、depending on length）
- 3:00 AM 寝る
- 10:00 AM 開始

やること:
- 既存 idea-search に branch 切る: `git checkout -b phase2/agent-teams-port`
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` で Claude Code 起動
- Claude Code に依頼して Agent Teams 版 idea-search を作る
  - baseline モード
  - full モード（multi-round, archive）
- Phase 1（idea gen）→ Phase 2（validation）の切り分け
- Validator teammate の骨格（実質 noop で可）

Day 1 終了時点の目標:
- Agent Teams で idea generation が回ってる
- Phase 1 → Phase 2 のフローが動く（Phase 2 は中身空でも OK）
- commit して push

### Day 2（4/23 木）：Outside signal 実装開始

- arXiv API の件数取得関数（`opensearch:totalResults` を使う）
- 1 concept pair で年別件数が取れることを確認
- test 書く

### Day 3（4/24 金）：concept 抽出 + pair 生成

- Claude API で idea から concept 抽出
- pair 生成ロジック
- embedding フィルタ（sentence-transformers で近すぎ・遠すぎ除外）
- end-to-end: idea → concepts → pairs → arXiv counts

### Day 4（4/25 土）：Semantic Scholar 追加、ソース融合

- semanticscholar パッケージで S2 件数取得
- arXiv と S2 の結果を結合
- ablation 実験: arXiv only / S2 only / both

### Day 5（4/26 日）：novelty 判定 + reality score

- 時系列から novel 判定するロジック実装
  - 候補: 最近 N 年の成長率、初出年、post-2020 vs pre-2020 比
- pair ごとの novelty を 1 score に集約
- Inside signal の最小実装（multi-persona、薄く）
- reality_score = f(inside, outside)

### Day 6（4/27 月）：検証実験

- 既知 novel idea / 既知 stale idea で動作確認
- パラメータ tuning
- 誤判定分析
- 結果を `results/` に書く

### Day 7（4/28 火）：提出日

- デモ動画 or slide
- README 整備
- 提出

## 優先順位と切り捨て判断

### 最優先（死守）
- Outside signal の動作
- 検証結果（既知の idea で効くかどうかのデータ）

### 次点
- Agent Teams 移植が動くこと
- Phase 1 → Phase 2 のフロー

### 切り捨て候補（時間なければ諦める）
- Inside signal の精緻化（最小実装で妥協）
- Hierarchical validation の実装（設計ノートだけで十分）
- Agent Teams の凝った使い方（動けば OK）

## Go/No-Go 基準

### Day 1 終了時点

**Go**: Agent Teams 版で idea gen が動く
→ Day 2 以降の予定通り進行

**No-Go**: Agent Teams で詰まる
→ Python 版に戻して Day 2 以降 Outside signal に集中
→ 提出時は「Agent Teams 移植は中断、既存 Python 版で validation engine を実装」と正直に

### Day 4 終了時点

**Go**: arXiv + Semantic Scholar で 1 idea の validation が回る
→ Day 5-6 で検証に集中

**No-Go**: ソース統合が不安定
→ arXiv only に縮小、Day 5-6 で検証に集中

### Day 6 終了時点

**Go**: 既知 novel/stale idea で妥当な差が出てる
→ Day 7 で仕上げ

**No-Go**: 検証結果が出せない
→ Day 7 で「現状の限界」として正直に整理、future work を書く

## リスクと対処

| リスク | 対処 |
|---|---|
| arXiv API のエラー対応 | Day 2 で early に error handler 書く |
| 件数取得が遅い | 並列処理 + ローカルキャッシュ |
| novel 判定が効かない | 閾値・ロジック見直し、小さいサンプルで iterate |
| Agent Teams で詰まる | Day 1 に即判断、Python 版に fallback |
| レート制限（S2 の 100 req/5min） | 待機キュー、キャッシュ、最悪 API key 申請 |
| 時間足りない | Inside signal の精緻化 → 最小実装に切り替え |

## 今日（4/18）時点で確認済み

- [x] ハッカソン応募完了、Pending 中
- [x] Opus 4.7 の Claude Max プラン動作確認
- [x] Agent Teams の基本動作確認（挨拶リレー OK）
- [x] Agent Teams のネスト不可を確認、平坦化戦略確立
- [x] Outside signal の設計整理（arXiv + Semantic Scholar、件数のみ query）
- [x] ハッカソン期間の Wi-Fi 確保（ポケット WiFi レンタル + 4/25 自宅 Wi-Fi 開通）

## Kick-off までにやれること

- Ngram・arXiv の仕様を再確認する程度は可
- 詳細実装は Kick-off 後（応募で出したルールを守るため）
- G検定の勉強を進める（5/9 本番、ハッカソン中は手が回らない前提）
