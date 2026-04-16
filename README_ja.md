# idea-search

LLM に「良いアイデアを出して」と聞くと、だいたい同じような無難な答えが返ってくる。
このシステムは、その問題を構造で解決しようとする試みです。

## 考え方

普通の LLM アイデア出しには3つの弱点がある:

1. **収束しすぎる** — 1回の呼び出しで「一番良い答え」を出そうとするので、安全で当たり障りのないものに収束する
2. **自分を評価できない** — 生成と評価が同じ文脈で行われるため、自己正当化バイアスがかかる
3. **方向性が潰れる** — 「上位1つ」を選ぶと、本当は面白かった別方向の案が消える

idea-search は、この3つに対して:

- 生成と評価を**完全に分離**する
- 複数の**役割（ロール）**が別々の視点でアイデアを出す
- 最終出力は「1つの最適解」ではなく、**方向性の異なる複数の良案**を返す
- 過去に出た案と似ていれば cliche としてフラグを立てる

さらに、1つの問題をいきなり探索するのではなく:

**Goal（大目標）→ Branch（戦略分岐）→ Method（具体手法）**

という階層で段階的に絞り込むことで、「広く浅い案」ではなく「選んだ方向の中で深い案」を出せるようにしている。

## セットアップ

```bash
git clone https://github.com/kakineko/idea-search.git
cd idea-search
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11 以上。

### 実 LLM を使いたい場合

API キーなしでも mock で動くが、実際に意味のある出力を得るには LLM 接続が必要。

**Claude Code CLI を使う場合**（サブスク内で済む。追加 API 課金なし）:
```bash
which claude  # PATH に claude があればOK
```

**Anthropic API を直接叩く場合**:
```bash
pip install -e ".[anthropic]"
export ANTHROPIC_API_KEY=sk-ant-...
```

## 実行例

### そのまま問題を投げる（フラット探索）

```bash
python -m idea_search run --input examples/sample_input.json --provider claude-cli
```

入力:
```json
{
  "problem": "小規模書店がディスカウントに頼らず生き残るには",
  "constraints": ["値引きなし", "予算5000ドル以下"],
  "context": "日米の都市部の独立系書店"
}
```

6つの生成ロール（Proposer / Reframer / Contrarian / AnalogyFinder / ConstraintHacker / Synthesizer）がそれぞれアイデアを出し、4つの評価ロール（Novelty / Feasibility / Value / Risk）が独立に採点する。結果はクラスタごとに方向性の違う上位案として返ってくる。

### 広い目標から段階的に探索する（階層探索）

```bash
# Branch の評価まで
python -m idea_search goal-search --input examples/goal_input.json --provider claude-cli

# Branch 選択 → 具体手法まで一気通貫
python -m idea_search hierarchical-full \
  --input examples/goal_input.json \
  --provider claude-cli \
  --rounds 1
```

入力:
```json
{
  "goal_statement": "1人で現実的にお金を稼ぐ方法を探せ",
  "constraints": ["低初期資本", "2週間以内に検証可能"],
  "domain_context": ["AIシステムに興味がある", "体系的に探索できるものが好み"]
}
```

内部では:
1. 目標を5つの戦略 Branch に分解（例: AI評価サービス / ニッチSaaS / データ商品...）
2. 各 Branch を6軸で評価（upside / cost / risk / 検証速度 / 適性 / データ入手性）
3. 上位 Branch を選択
4. 選ばれた Branch に対して、上のマルチロール method-search を実行

### パイプラインの効果を比較する

```bash
python -m idea_search compare \
  --input examples/sample_input.json \
  --out comparison.md
```

baseline（1発生成）/ generator-only / gen+eval / full の各段階を同じ問題で走らせて、多様性指標と人間採点用テーブルを出力する。

## Provider の選び方

| Provider | いつ使う | 必要なもの |
|----------|---------|-----------|
| `mock` | テスト、構造の確認 | なし |
| `claude-cli` | 実際の出力を見たい（CC サブスク内） | `claude` コマンド |
| `anthropic` | API で直接叩きたい | API キー + `pip install -e ".[anthropic]"` |

`--provider mock` がデフォルト。切り替えは `--provider claude-cli` を足すだけ。

## 主なオプション

| オプション | 内容 | デフォルト |
|-----------|------|----------|
| `--provider` | LLM の選択 | `mock` |
| `--rounds N` | method-search の反復回数 | 2 |
| `--top-k N` | 何本の Branch を探索するか | 1 |
| `--branches N` | 生成する Branch の数 | 5 |
| `--out <path>` | レポート保存先 | なし |

## 実際の比較結果

「1人で現実的にお金を稼ぐ方法」という同一目標で、3パターンを比較した。

**フラット + Claude**: 幅広い方向のアイデアが出る（AI監査、SaaS、コンテンツ etc.）。具体性は高いが、どの方向も浅い。

**階層 + mock**: Branch 名が「Data product for realistic」のようなテンプレ充填。意味的に無価値。

**階層 + Claude**: Branch 名が「AI Model Evaluation and Red-Teaming Service」のように domain-specific。選ばれた Branch 内で、航空業界の FMEA を LLM QA に移植する案や、製薬の CRO モデルを AI 評価に適用する案など、構造的アナロジーに基づく深い提案が出る。

| 観点 | フラット + Claude | 階層 + mock | 階層 + Claude |
|------|:-:|:-:|:-:|
| Branch の具体性 | — | テンプレ | domain-specific |
| ランキングの妥当性 | — | ノイズ | 制約を反映 |
| 手法の独自性 | 広く浅い | テンプレ | **1方向で深い** |
| すぐ動けるか | 高い | 低い | **最も高い** |

## 仕組み

```
Goal（大目標）
  │
  ├─ GoalDecomposer ─── 戦略 Branch を複数生成
  ├─ BranchEvaluator ── 6軸で独立評価
  ├─ BranchSelector ─── 上位 k 本を選択
  │
  └─ 選ばれた Branch ごとに MethodSearch を実行
       │
       ├─ 6 Generator roles ── 異なる角度でアイデア生成
       ├─ 4 Evaluator roles ── 独立に採点（score + 根拠 + 改善案）
       ├─ Cliche 検出 ──────── regex + archive 類似度
       └─ Clustering ────────── 方向ごとに上位案を抽出
```

### Branch 評価の6軸

| 軸 | 見るもの | composite |
|----|---------|-----------|
| upside | 成功したらどれだけ大きいか | + |
| cost | どれだけ金と時間がかかるか | - |
| risk | 失敗する確率と深刻さ | - |
| validation_speed | どれだけ早く検証できるか | + |
| personal_fit | 自分に合っているか | + |
| data_availability | 必要なデータや道具がすぐ手に入るか | + |

重み付けは `hierarchical/schema.py` の `BRANCH_AXIS_WEIGHTS` で変更できる。

### Synthesizer のルール

- **1ラウンド目**: 他の5ロールが出したアイデアを全部受け取って統合案を出す
- **2ラウンド目以降**: 前ラウンドの「高 novelty」「高 feasibility」「critic に壊された案の断片」を受け取って再構成する

## テスト

```bash
pytest  # 72 tests、全て API 不要
```

## 設定

`config/default.yaml` でラウンド数、類似度閾値、cliche パターン、クラスタリング設定を制御。

## 今後やれること

- **ロール追加**: `roles/prompts.py` にプロンプトを書いて config に足すだけ
- **評価軸追加**: schema を拡張して composite 計算式を調整
- **類似度の高度化**: 現在は Jaccard。embedding に差し替え可能（同じインターフェース）
- **Provider 追加**: `LLMProvider` を実装して `get_provider` に登録
- **ExecutionLoop**: 選ばれた Method を実際に試す検証ループ（未実装、構造的には追加可能）
- **Weight のチューニング**: Branch 評価の重みを config から調整可能にする
