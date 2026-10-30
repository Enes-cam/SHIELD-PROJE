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

Task 1 tek başına doğrudan da çalıştırılabilir:

```bash
PYTHONPATH=src python3 scripts/rarity_stability.py --config config/week2.json
```

Task 1 uzun sürebilir. Her `(circuit, M, seed)` sonucu
`results/week2/task1/activity_cache` altında saklanır. Komut kesilip yeniden
başlatılırsa tamamlanan simülasyonlar tekrar yapılmaz.

## Çıktılar

- Task 1: `rare_sets.csv`, `stability.csv`, altı stabilite grafiği ve c1908 debug çıktısı.
- Task 2: `graph_checks.csv` ve c1908 ilk 10 reverse traversal adımı.
- Task 3: bütün yöntem/k kombinasyonları için `selected_inputs.json`, c1908 sıralama debug çıktısı ve SHIELD DFS regresyon tablosu.
- Task 4: `input_selection_results.csv`, 12 grafik ve kaybedilen rare target debug çıktısı.

`tests/test_week2.py` c17 için dokümanda verilen kesin sonuçları, Task 1
Jaccard kurallarını ve altı devrenin özgün SHIELD rare target sayılarını doğrular.
Mevcut c880 testi 48 rare target ve 23 effective input regresyonunu korur.

Task 3 yorumu: özgün SHIELD, yalnızca en az iki rare target'a ulaşan input'ları
tutar. Belgede tanımlanan P_R ve k=%100 seçimi ise en az bir rare target'a
ulaşan bütün input'ları içerir. Bu iki kural c3540 ve c5315'te farklı kümeler
verir. Pozitif `shield_dfs` skoruna sahip input'lar özgün `DFS_bench.myfunc`
ile altı devrede eşleşir; `shield_dfs_regression.csv` k=%100 seçimindeki farkı
gizlemeden gösterir. Deneylerde belgedeki P_R ve k=%100 kuralı uygulanır.
