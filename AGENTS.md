# Project

スケジューリング最適化アルゴリズムの開発・検証プロジェクト。

本プロジェクトでは、生産スケジューリング問題に対する各種アルゴリズムを実装する

主な目的は以下。

* スケジューリングアルゴリズム実装、検証
* 計算時間の測定
* 解品質の比較
* 制約違反の検出
* アルゴリズム変更前後の性能比較
* 将来的な実運用アルゴリズムの選定

# Language

* Python 3.12
* コード内コメントは日本語
* 変数名・関数名・クラス名は原則英語
* ユーザーへの説明は日本語
* すでに日本語で記述された直接的コードは変更しない

# Development Policy

このプロジェクトでは、正しく動く事を第一にを重視する。

テストコードと最適化アルゴリズムを可能な限り分離すること。

# Important Rules

## 1. 勝手に仕様を変更しない

既存の制約条件、評価方法、データ構造を勝手に変更しないこと。

変更が必要な場合は、

* 変更理由
* 変更箇所
* 比較結果への影響

を明示すること。

## 2. 改善は一度に複数入れない

アルゴリズム改善を行う場合、

1つの変更ごとに性能を測定する。

複数の改善を同時に実装すると、
どの変更が効果を出したのか判定できないため避けること。

## 3. 再現性を確保する

乱数を使用する場合は原則としてseedを指定する。

基本値：

```python
SEED = 42
```

Python標準random、NumPyなど複数の乱数生成器を使用する場合は、
必要に応じてそれぞれseedを固定する。

## 4. 実行時間を測定する

アルゴリズムの性能比較では必ず実行時間を測定できる構造とする。

原則として以下を使用する。

```python
from time import perf_counter

start = perf_counter()

# 処理

elapsed = perf_counter() - start
```

短時間処理では `time.time()` より `perf_counter()` を優先する。

## 5. テストデータとアルゴリズムを分離する

以下を可能な限り分離する。

* テストデータ生成
* スケジューリングアルゴリズム
* 評価処理
* 制約チェック
* 結果出力
* 可視化

1つの巨大なmain関数に処理を集中させない。

# Algorithm

厳密解法だけを前提としない。

問題規模や目的に応じて以下を検討する。

* Greedy
* Dispatching Rule
* Local Search
* Hill Climbing
* Simulated Annealing
* Random Search
* Multi Start
* Beam Search
* Tabu Search
* Large Neighborhood Search
* Hybrid Algorithm

ヒューリスティック手法では、「最適解であること」より、「制限時間内で良い解を安定して取得すること」を重視


# Test Structure

テストは可能な限り以下の流れとする。

```text
テストデータ生成
    ↓
アルゴリズム実行
    ↓
スケジュール生成
    ↓
制約チェック
    ↓
目的関数計算
    ↓
実行時間測定
    ↓
結果保存
    ↓
比較
```

# Benchmark

アルゴリズム比較では同一の入力データを使用する。

比較中に各アルゴリズムごとに別のランダムデータを生成しない。

例えば、

```python
data = create_test_data(seed=42)

result_a = algorithm_a(data)
result_b = algorithm_b(data)
result_c = algorithm_c(data)
```

のような構造を優先する。

# Repeated Test

ヒューリスティックアルゴリズムでは、
1回の結果だけで優劣を判断しない。

必要に応じて複数回実行し、

* best
* worst
* mean
* median
* standard deviation
* execution time

を比較する。

# Constraint Validation

スケジュール生成後は、
目的関数値だけではなく制約違反を確認する。

最低限、必要に応じて以下を検証する。

* 同一機械の処理重複
* 同一作業者の作業重複
* 工程順序違反
* release time違反
* resource block違反
* horizon超過
* 負の開始時間
* start > end
* 未割当task
* task重複割当

# Performance

性能改善では計算量とメモリ使用量を意識する。

特に探索内部の高頻度ループでは以下を避ける。

* 不要なdeepcopy
* DataFrameの繰り返し操作
* 毎iterationでのソート
* 毎iterationでの巨大オブジェクト生成
* 不必要なlist変換
* 不必要なdict再構築

可能であれば、

* list
* dict
* set
* tuple
* heapq
* NumPy array
* bitmap

など適切なデータ構造を選択する。

# Optimization Policy

高速化を行う場合は、

変更前：

```text
score:
execution time:
memory:
```

変更後：

```text
score:
execution time:
memory:
```

のように比較できる状態を維持する。

速度向上と引き換えに解品質が低下する場合は、
そのトレードオフを明示する。

# Coding Style

関数はできる限り役割を1つにする。

例：

```python
create_test_data()
build_tasks()
create_schedule()
evaluate_schedule()
validate_schedule()
run_benchmark()
output_result()
```

意味のない短縮名を避ける。

悪い例：

```python
a
tmp2
xx
aaa
```

許容される例：

```python
machine_id
worker_id
start_time
end_time
candidate_list
best_score
```

# Data Structure

大量の探索を行う可能性があるため、
データ構造は速度を意識して設計する。

ただし、初期実装では可読性を優先してよい。

高速化が必要になった段階で、

* dataclass
* tuple
* list
* dict
* NumPy
* bitmap
* array

等への変更を検討する。

# Refactoring

性能比較中は大規模なリファクタリングを同時に行わない。

以下を分離する。

1. バグ修正
2. リファクタリング
3. アルゴリズム改善
4. 高速化

変更目的を混在させない。

# When Modifying Code

既存コードを変更する前に、

* 現在の処理
* 変更目的
* 変更範囲

を確認する。

変更後は最低限、

* syntax error
* runtime error
* 制約違反
* 結果の異常
* 実行時間悪化

を確認する。

# Codex Instructions

Codexは、要求されていない大規模変更を行わないこと。

特に以下は禁止する。

* 勝手な仕様変更
* 勝手な依存ライブラリ追加
* 全体構造の大規模変更
* 評価関数の無断変更
* テスト条件の無断変更
* seedの無断変更
* ベンチマーク条件の変更
* 「より良さそう」という理由だけで既存コードを削除すること

既存コードを活かした最小変更を優先する。

# Bug Fix Policy

バグを発見した場合は、
アルゴリズム改善と同時に修正しない。

可能であれば、

```text
バグ修正
↓
テスト
↓
結果確認
↓
アルゴリズム改善
```

の順で対応する。

# Output

テスト結果は後から比較できる形式を優先する。

候補：

* console
* CSV
* JSON
* Excel
* pandas DataFrame

最低限、以下を保存できる構造を推奨する。

```text
algorithm
seed
test_case
job_count
machine_count
worker_count
score
makespan
elapsed_time
constraint_violation
trial_count
```

# Final Priority

優先順位は以下。

1. 制約を守る
2. 同条件で比較できる
3. 結果を再現できる
4. 解品質を高める
5. 計算時間を短縮する
6. コードを整理する

性能改善を行う場合も、
比較可能性と再現性を壊さないこと。

# Confirmed Dummy Data Specifications

以下は、現在のダミーテストデータに関する決定事項である。

* 総加工時間の分換算では、現在の切り捨て処理を維持する。
* 段取時間は総加工時間に含めず、評価時に必ず加算する。
* 段取は工程単位で発生する。
* オーバーラップは、該当工程をすべて完了する前に次工程を開始できることを意味する。
* 同じ製品の工程構成は受注間で共通とする。
* 材料切断の作業者候補はCNC工程の作業者候補と同一とする。
* スケジューリング単位は分とする。単体加工時間の保持単位は現状どおりとする。
* 生産数、ワークサイズなどの乱数範囲は現状の設定を維持する。
* `Factory`の`seed`と`count`は将来利用する可能性があるため、未使用でも削除しない。
* Excel出力の工場情報は固定値を使用せず、`Factory`設定から動的に生成する。
* `product_select`と`priority`に許可されていない値が指定された場合は`ValueError`を発生させる。
