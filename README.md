# SHIELD Modular Research Framework

Bu depo, SHIELD donanım Truva atı test üretim yaklaşımının özgün araştırma kodunu ve modülerleştirilmiş deney altyapısını içerir.

## Durum

- Özgün `PSO_DFS.py`, `DFS_bench.py` ve `Dalgebra.py` dosyaları korunmuştur.
- BENCH okuma, test üretme, simülasyon, activity, rarity, graph, reverse DFS, candidate generation, coverage, optimization, validation ve experiment sorumlulukları ayrılmıştır.
- Modüller `src/shield/` altındadır ve ortak veri sözleşmelerini kullanır.
- ISCAS-85 benchmark dosyaları `datasets/` altındadır.

## Hızlı başlangıç

Python 3.10 veya üzeri gereklidir.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[legacy]'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Modüler baseline deneyi:

```bash
PYTHONPATH=src python3 -m shield.cli datasets/c880.bench \
  --sample-size 1000 \
  --seed 42 \
  --rarity-method switching_activity \
  --threshold 0.1 \
  --minimum-target-impact 2 \
  --candidate-count 100 \
  --output results/c880_seed42.json
```

Özgün SHIELD PSO baseline'ını çalıştırmak için:

```bash
.venv/bin/python PSO_DFS.py
```

Bu komut ayrıntılı legacy çıktısı üretir. Doğrulanmış seed-42 özeti `results/legacy_c880_seed42.json` dosyasındadır.

Modüler PSO stratejisiyle C880 tam-coverage deneyi:

```bash
.venv/bin/shield-run datasets/c880.bench \
  --sample-size 1000 --seed 42 --threshold 0.1 \
  --minimum-target-impact 2 \
  --candidate-generation-method random_full_inputs \
  --candidate-count 6000 \
  --optimization-method pso \
  --pso-particles 40 --pso-iterations 100 \
  --output results/c880_modular_pso_seed42.json
```

Bu koşu 48 rare target, 23 selected input ve `%100` coverage üretir. Modüler PSO, hocanın `CandidatePool + CoverageMatrix + ProblemDefinition` sözleşmesine uyar; özgün legacy PSO'nun birebir iç uygulaması değildir.

## Belgeler

- Mimari ve modül sözleşmeleri: `docs/ARCHITECTURE.md`
- Baseline ve yeniden üretilebilirlik notları: `docs/BASELINE.md`
- Makaleler: `papers/`

## Önemli not

Modüler hat hem deterministik greedy set cover hem de `CandidatePool + CoverageMatrix + ProblemDefinition` sözleşmesi üzerinde çalışan discrete PSO seçeneğini destekler. Özgün PSO kodu da legacy karşılaştırma için korunmuştur. Makaledeki PSO ile aktif legacy kodun parametreleri farklı olduğundan paper replication ve legacy-code regresyonu ayrı raporlanır.
