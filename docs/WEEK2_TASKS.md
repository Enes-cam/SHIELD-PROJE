# Week 2 görevleri

Tüm deney parametreleri `config/week2.json` dosyasından okunur. Kod içinde M,
seed, threshold, k veya yöntem listesi sabitlenmemiştir. PSO ve eski SHIELD
dosyaları bu çalışmada değiştirilmemiştir.

## Çalıştırma

```bash
PYTHONPATH=src python3 scripts/run_week2.py --task 1
PYTHONPATH=src python3 scripts/run_week2.py --task 2
PYTHONPATH=src python3 scripts/run_week2.py --task 3-4
```

Task 1 uzun sürebilir. Her `(circuit, M, seed)` sonucu
`results/week2/task1/activity_cache` altında saklanır. Komut kesilip yeniden
başlatılırsa tamamlanan simülasyonlar tekrar yapılmaz.

## Çıktılar

- Task 1: `rare_sets.csv`, `stability.csv`, altı stabilite grafiği ve c1908 debug çıktısı.
- Task 2: `graph_checks.csv` ve c1908 ilk 10 reverse traversal adımı.
- Task 3: bütün yöntem/k kombinasyonları için `selected_inputs.json`, c1908 sıralama debug çıktısı ve SHIELD DFS regresyon tablosu.
- Task 4: `input_selection_results.csv`, 12 grafik ve kaybedilen rare target debug çıktısı.

`tests/test_week2.py` c17 için dokümanda verilen kesin sonuçları ve Task 1
Jaccard kurallarını doğrular. Mevcut c880 testi aynı baseline parametreleriyle
48 rare target ve 23 effective input regresyonunu korur.
