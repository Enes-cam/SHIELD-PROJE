# Özgün SHIELD kodundan modüler sisteme geçiş haritası

Bu belge, özgün dosyalardaki kodun yeni sistemde nerede bulunduğunu ve aktif
deney akışında nasıl çalıştığını gösterir.

## `Dalgebra.py`

Eski akışta `PSO_DFS.Parser.__operate()`, kapı türüne göre `Dalgebra.py`
içindeki `AND`, `OR`, `NOT`, `NAND`, `NOR`, `XOR`, `XNOR` veya `BUFF`
fonksiyonunu çağırır.

Yeni sistemde binary kapı davranışları `src/shield/simulation.py` içindeki
`_evaluate_gate()` fonksiyonunda, devrenin tamamının simülasyonu ise
`LogicSimulator.simulate(CircuitIR, TestVectorSet)` içinde bulunur.

`Dalgebra.py` ayrıca `D` ve `D'` değerlerini destekler. Modüler SHIELD akışı
binary test vektörleri kullandığı için bu destek yeni simülatöre taşınmadı.
Dosya legacy/ATPG deneyi olarak korunur ve modüler pipeline tarafından import
edilmez.

## `DFS_bench.py`

| Özgün bölüm | Yeni karşılığı | Veri sözleşmesi |
|---|---|---|
| `parser()` | `circuit.CircuitReader` | BENCH → `CircuitIR` |
| `grapher()` | `graph.CircuitGraphBuilder` | `CircuitIR` → `CircuitGraph` |
| `dfs_find_inputs_with_indices()` | `input_analysis.ReverseDFSInputAnalyzer` | `CircuitGraph + RareTargets` → `SelectedInputs` |
| `myfunc()` | `experiment.ExperimentRunner` tarafından yapılan orkestrasyon | Modüller sırayla çağrılır |

Önemli fark: özgün `myfunc()` BENCH dosyasını tekrar okur. Yeni yapıda BENCH'i
yalnız Circuit Module okur. Diğer modüller hazır veri nesnelerini kullanır.

## `PSO_DFS.py`

| Özgün bölüm | Yeni karşılığı |
|---|---|
| `readFile()`, `__loadCode()` | `circuit.py` |
| levelization ve sıralama | `CircuitIR.topological_gate_order` |
| rastgele test vektörleri | `test_vectors.py` |
| `circuitSimulation()` | `simulation.py` |
| `switchingActivity()` | `activity.py` |
| `rare_net()` | `rarity.py` |
| `DFS_bench.myfunc()` çağrısı | `graph.py` + `input_analysis.py` |
| aday üretimi | `candidate_generation.py` |
| aday–target kapsaması | `coverage.py` |
| deney akışının tamamı | `experiment.py` |

Özgün aktif PSO algoritması `PSO_DFS.py` içinde korunmaktadır. Yeni
`optimization.py` dosyasındaki `DiscretePSOOptimizer`, modüler optimizer
sözleşmesini göstermek için eklenmiş ayrı bir uygulamadır; özgün SHIELD PSO'nun
birebir taşınmış hali değildir.

## Modüler çalışma zinciri

```text
ExperimentConfiguration
    → CircuitReader
    → TestVectorGenerator
    → LogicSimulator
    → ActivityAnalyzer
    → RareTargetDetector
    → CircuitGraphBuilder
    → ReverseDFSInputAnalyzer
    → CandidateGenerator
    → CoverageAnalyzer
    → Optimizer
    → HTValidator (istenirse)
    → ExperimentResults
```
