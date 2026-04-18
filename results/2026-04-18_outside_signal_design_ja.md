# Outside Signal 設計ノート（日本語・作業メモ）

**日付**: 2026-04-18  
**ステータス**: 実装前の設計思考整理  
**文脈**: Built with Opus 4.7 ハッカソン準備（4/22-4/27）  
**目的**: 自分の思考整理用。英語版 `outside_signal_design.md` と対をなす。

## なぜ Outside signal が必要か

### 今の idea-search の問題

idea-search には内部評価層がある。4つの LLM judge が各アイデアを「新規性 / 実現可能性 / 価値 / リスク」でスコアリングする。

でも今日の実験で分かったこと：
- 評価器が明らかに収束してるアイデアに 9.0+ の高スコアを付ける
- 自己評価だけでは**本物の novel とそう聞こえるだけ**を区別できない

### これは本質的な問題

LLM が自分の出力を評価すると：
- 訓練分布内の「novel っぽさ」を拾えるが
- 本当の novel を捕まえられない
- 体系的に収束を見逃す

### だから「外側」の視点が必要

LLM 以外のデータ源で判断する layer を入れる。それが outside signal。

## 仮説の核心

**genuine novelty は、コンセプトが最近になって初めて一緒に議論され始めた形に見える**

たとえば：
- 「quantum」「error」「correction」は個別には古い（1900 年代から存在）
- 「quantum error correction」という組み合わせは 2000 年以降に集中し始めた
- この**組み合わせのタイミング**こそが novelty のシグナル

だから：
- **単語単独の頻度分析**では足りない（古い単語の組み合わせで novel はありえる）
- **完全一致のフレーズ検索**では表現の揺れを取り逃がす
- **ペアレベルの時系列共起**が適切な粒度

## データソースの選定

### 検討して却下したもの：Google Ngram Viewer

最初は 1800-2019 の書籍データを長期トレンドとして使う予定だった。

**却下理由**：
1. **2019 年までしかない**：LLM 時代のアイデア（2020 年以降の概念）を評価できない
2. **シンプル化**：Ngram が役に立たないなら、複数ソース併用する意味が薄い

最新データで勝負するしかない。

### 選んだもの：arXiv + Semantic Scholar

**arXiv（1991-現在）**：
- CS、ML、物理に強い
- 公式 REST API、`arxiv` パッケージ
- レート制限：3秒に1回
- 無料、認証不要

**Semantic Scholar（1900 年代-現在）**：
- 2億論文以上、カバー範囲が広い
- 医療、心理学、社会学、経済学なども含む
- 公式 REST API、`semanticscholar` パッケージ
- レート制限：100 req/5分（匿名）

**組み合わせる理由**：
arXiv 単独だと CS/物理以外のアイデアに弱い。Semantic Scholar でそこを補う。両方 hit すれば確度が上がる。

## アーキテクチャ
アイデアの記述（自然言語）
│
▼
[Claude で concept 抽出]
│
▼
concepts: ["quantum error correction", "fault tolerance", ...]
│
▼
[embedding でフィルタしながら pair 生成]
│ 近すぎる pair = 焼き直し → 除外
│ 遠すぎる pair = 無意味 → 除外
▼
filtered_pairs: [(A, B), (C, D), ...]
│
▼
[各 pair について年別共起件数を取得]
│
├─→ arXiv API: 年別の件数だけ
└─→ Semantic Scholar API: 年別の件数だけ
│
▼
yearly_counts: {2015: 2, 2016: 5, ..., 2024: 380, 2025: 800}
│
▼
[時系列の形から novelty を判定]
│
▼
novelty_score（pair ごと）
│
▼
[複数 pair を集約]
│
▼
reality_score（0-10）

## 一番大事な気づき：**件数だけ取ればいい**

論文のタイトル・アブスト・本文は**一切必要ない**。

知りたいのは「この pair を含む論文が、年ごとに何本あるか」それだけ。

### arXiv の場合

arXiv は Atom レスポンスに `<opensearch:totalResults>` フィールドを含む。これは**件数だけ返す**。

```python
query = f'all:"{pair[0]}" AND all:"{pair[1]}" AND submittedDate:[{year}01010000 TO {year}12312359]'
url = f'http://export.arxiv.org/api/query?search_query={quote(query)}&max_results=0'
# XML を parse、totalResults を取る
```

`max_results=0` なら実際の結果は返らず、件数だけ返る。超軽い。

### Semantic Scholar の場合

```python
results = sch.search_paper(
    query=f'"{pair[0]}" "{pair[1]}"',
    publication_date_or_year=f'{year}',
    limit=1
)
total = results.total
```

これも件数だけ取れる。

### データ量

- 1 pair × 12 年 = 整数 12 個 = **数十バイト**
- 1 アイデアあたり 10 pair = **数百バイト**
- 100 アイデア評価しても **数十 KB**

データベース不要、メモリ処理で十分。

## 実装計画（ハッカソン期間 4/22-4/28）

### Day 1（4/22 水）Kick-off 当日
- 環境確認（Claude Code、pytest、venv）
- `outside/arxiv_counts.py`：年別件数取得関数
- 1 pair で動作確認（例：quantum error correction × topological）

### Day 2（4/23 木）
- `outside/concept_extraction.py`：Claude で concept 抽出
- `outside/pair_filter.py`：embedding ベースのフィルタ
- end-to-end 動作：アイデア → concept → pair → arXiv 件数 → novelty

### Day 3（4/24 金）
- Semantic Scholar を追加
- 2 ソースの signal をどう統合するか
- ablation：arXiv のみ、S2 のみ、両方の比較

### Day 4-5（4/25 土、4/26 日）
- Inside signal（multi-persona evaluator）を実装
- Inside + Outside で reality_score を計算
- 既存の idea-search 出力に適用、LLM の composite score と比較

### Day 6-7（4/27 月、4/28 火）
- 結果分析、experiment notes 執筆
- デモ準備（動画 or ライブ）
- README 整備、提出

## 実装中に決めること（未確定項目）

### 1. concept 抽出の粒度

- 1 アイデアから何個抽出する？（3-5 個？もっと多い？）
- 単語だけ？複合フレーズも OK？
- Claude へのプロンプト設計が必要

### 2. pair フィルタの閾値

- embedding 距離が**どこまで近いと「近すぎ」**か？（0.3 未満？）
- **どこまで遠いと「遠すぎ」**か？（0.8 超？）
- 実験しながら調整

### 3. 時系列から novelty の判定ロジック

- 最近の急増 = novel だとして、**どれくらい急なら novel** か？
- 緩やかな増加 vs 突然の出現、どっちも signal？
- 候補メトリクス：
  - 2020 以降の件数 / 2020 以前の件数
  - 最初に非ゼロになった年
  - 直近 N 年の複利成長率

### 4. 複数 pair の集約

- pair ごとの novelty スコアを 1 つの reality_score にどう集約？
- 平均？最低値？embedding 距離で重み付け？

### 5. ソース間の不一致

- arXiv は novel と言うが Semantic Scholar は既存と言う場合
- 分野バイアスなのか本物の signal なのか、自動判別は難しい

## スコープの線引き

### ハッカソン MVP でやること
- pair レベル（2 concept）の共起分析
- arXiv + Semantic Scholar、件数のみ取得
- embedding フィルタ
- シンプルな heuristic 集約

### やらない（将来課題）
- triple、quadruple の組み合わせ（組み合わせ爆発）
- 引用ネットワーク分析（Uzzi の atypicality）
- 分野に応じてデータソースを切り替える（技術 → arXiv、ビジネス → Crunchbase）
- クエリ拡張（類義語、表現バリエーション）
- ビジネス系データソース（Product Hunt、Crunchbase、HN Algolia）

## 関連する研究

- **Uzzi et al., "Atypical Combinations and Scientific Impact"（Science 2013）**：論文の引用ペアの珍しさで novelty を測る
- **Schumpeter の新結合論**：経済学でのイノベーション理論
- **conceptual blending（Fauconnier）**：認知科学、2 つの文脈のブリッジが創造性

idea-search はこれらの手法を ideation 検証に転用している。引用ペアじゃなく concept ペア、post-hoc 測定じゃなくリアルタイム検証に。

## なぜこの設計が重要か

### idea-search の現状と課題

既に証明したこと：
- 役割分離は round 1 では多様性を生む
- でも archive feedback は round 2 で多様性崩壊を防げない
- 自己評価は収束を見逃す

**何ができてないか**：
- 「生成した多様なアイデア」のうち、**本物の novel** と **そう聞こえるだけ** を区別できない

Outside signal はそこの**誠実さの layer**。

### 応募チャットで言った主張と対応

> "An ideation harness that honestly tells you which ideas are promising vs which only sound promising."

これを実装するのが Outside signal。honestly = LLM 自身の主観じゃなく、外部データに根ざす。

## 個人的なメモ（自分用）

### このドキュメントの使い方

- 実装中に迷ったら、ここに戻って原点を確認する
- 実装で新しい気づきがあったら、ここに追記する（日付付き）
- 英語版 `outside_signal_design.md` は外向け（GitHub、ハッカソン審査官）、このドキュメントは内省用

### 今日の対話で得た重要な視点

1. **Ngram は要らない**：最新データがあればいい
2. **件数だけでいい**：論文の中身を取る必要ゼロ
3. **分野バイアスは Semantic Scholar で軽減**：arXiv 単独だと狭い
4. **pair が最適粒度**：triple は組み合わせ爆発、single は情報量薄い

### 未解決の不安

- ハッカソン 1週間で届くか：**たぶん届く、シンプル化したから**
- Inside signal（multi-persona）もあるが、こっちは自己評価問題の**延長**で、根本解決じゃない
- reality_score の重み付けロジックは正解がない：実験で決める

