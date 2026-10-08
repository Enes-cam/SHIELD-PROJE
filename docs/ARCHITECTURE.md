# SHIELD Modüler Altyapı Tasarımı

Bu proje, özgün SHIELD araştırma kodunu algoritmaların bağımsız değiştirilebildiği ve deneylerin tekrarlanabildiği bir altyapıya dönüştürür. `PSO_DFS.py`, `DFS_bench.py` ve `Dalgebra.py` dosyaları karşılaştırma amacıyla değiştirilmeden korunur.

## Temel kural

BENCH dosyasını yalnız Circuit Module okur. Diğer modüller dosya yoluna veya BENCH sözdizimine değil `CircuitIR` nesnesine bağımlıdır. Her modül yalnız tanımlı girdilerini alır ve yeni bir çıktı nesnesi döndürür.

Coverage ve Validation modülleri somut `LogicSimulator` sınıfına bağlı değildir. Yalnız `SimulationPort` adlı açık arayüzü kullanırlar; gerçek simülatör Experiment Module tarafından enjekte edilir. Böylece simülasyon yöntemi değiştirilirken bu modüllerin iç kodu değiştirilmez.

Rare Target Module yalnız `ActivityInfo`, rarity yöntemi ve threshold alır. Hedef olmaya uygun gate-output netlerinin listesi `ActivityInfo` sözleşmesinin parçasıdır; bu modül `CircuitIR` almaz.

## Veri akışı

```text
BENCH -> CircuitIR
CircuitIR + sample_size + seed -> TestVectorSet
CircuitIR + TestVectorSet -> SimulationResults
SimulationResults -> ActivityInfo
ActivityInfo + method + threshold -> RareTargets
CircuitIR -> CircuitGraph
CircuitGraph + RareTargets -> SelectedInputs
CircuitIR + SelectedInputs -> CandidatePool
CircuitIR + CandidatePool + RareTargets -> CoverageMatrix
CandidatePool + CoverageMatrix + ProblemDefinition -> SelectedTestSet
SelectedTestSet + HT Circuit + HT Ground Truth -> ValidationResults
ExperimentConfiguration -> ExperimentResults
```

`TestVectorSet` ve `RareTargets` dışarıdan hazırlanarak sonraki modüle doğrudan verilebilir.

## Modül eşlemesi

| İstenen modül | Uygulama |
|---|---|
| Circuit | `shield.circuit.BenchCircuitReader` |
| Test Vector | `shield.test_vectors` |
| Logic Simulation | `shield.simulation.LogicSimulator` |
| Activity Analysis | `shield.activity.ActivityAnalyzer` |
| Rare Target | `shield.rarity.RareTargetSelector` |
| Graph | `shield.graph.CircuitGraphBuilder` |
| Input Analysis | `shield.input_analysis.ReverseDFSInputAnalyzer` |
| Candidate Generation | `shield.candidate_generation.RandomSelectedInputCandidateGenerator` |
| Coverage | `shield.coverage.CoverageAnalyzer` |
| Optimization | `shield.optimization.GreedyCoverageOptimizer`, `shield.optimization.DiscretePSOOptimizer` |
| Validation | `shield.validation.HTValidator` |
| Experiment | `shield.experiment.ExperimentRunner` |

## SHIELD baseline kararları

- Rarity baseline: `switching_activity`
- Test-vector baseline: `shield_legacy_random`; özgün kodun parsing sonrasında üretip attığı rastgele vektörleri de tüketerek seed-42 karakterizasyonunu tekrarlar.
- Input analysis baseline: reverse DFS
- Reverse DFS için `minimum_target_impact=2`, özgün `DFS_bench.py` içindeki `count > 1` davranışını temsil eder.
- Özgün PSO kodu silinmemiştir. Modüler Optimization Module, greedy ve sözleşmeye uygun discrete PSO stratejilerini seçebilir.
- Makaledeki PSO parametreleri ile aktif `PSO_DFS.py` parametreleri aynı değildir. Bu nedenle paper-result replikasyonu ile legacy-code regresyonu ayrı deneyler olarak ele alınmalıdır.

## Yeni yöntem ekleme

Yeni bir rarity yöntemi `ActivityInfo -> RareTargets`, yeni bir input sıralama yöntemi `CircuitGraph + RareTargets -> SelectedInputs`, yeni optimizer ise `CandidatePool + CoverageMatrix + ProblemDefinition -> SelectedTestSet` sözleşmesini korumalıdır.
