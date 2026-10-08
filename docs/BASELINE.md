# Baseline ve Yeniden Üretilebilirlik

## Kaynak durumu

Özgün GitHub deposu Python kaynaklarını içeriyor ancak BENCH dosyalarını, bağımlılık kilidini ve deney komutlarını içermiyor. Makaledeki standart giriş/çıkış sayılarına uyan ISCAS-85 BENCH dosyaları Tallinn Teknik Üniversitesi benchmark arşivinden `datasets/` dizinine eklenmiştir.

## İki ayrı baseline

1. **Legacy-code baseline:** `PSO_DFS.py` içindeki aktif parametreler ve mevcut davranış.
2. **Paper configuration:** Makalede yazan 150 parçacık, 100 iterasyon, dinamik inertia 0.9 -> 0.4, cognitive 2.4 ve social 2.0 ayarları.

Aktif kod paper configuration ile uyuşmadığı için sonuçlar aynı başlık altında raporlanmamalıdır.

## Doğrulanmış c880 legacy sonucu

Seed 42, 1000 karakterizasyon vektörü ve 0.1 SWA eşiğiyle özgün kod 48 rare gate ve 23 effective input üretmiştir. Aktif PSO son durumda 48/48 gate kapsadığını yazdırmıştır. Çalışma süresi bu makinede 13.064 saniyedir. Yazdırılan `%5923.48 average coverage` değeri, toplamın parçacık sayısına bölünmemesinden kaynaklanan bilinen legacy hesap hatasıdır.

Modüler karakterizasyon hattı aynı seed ve RNG tüketim sırasıyla 48 rare target ve 23 selected input değerlerini otomatik regresyon testinde tekrar üretmektedir. `random_full_inputs` ile 6000 aday kullanılan modüler greedy ve discrete PSO deneylerinin ikisi de 48 hedefte `%100` coverage üretmiştir. Bunlar modüler sözleşmenin sonuçlarıdır; özgün legacy PSO'nun iç arama iziyle aynı oldukları iddia edilmez.

## Karşılaştırılması gereken ara çıktılar

1. Primary input/output ve gate listesi
2. Seed ile üretilen `TestVectorSet`
3. `SimulationResults`
4. `ActivityInfo`
5. `RareTargets`
6. `CircuitGraph`
7. Reverse DFS `SelectedInputs`
8. Candidate ve coverage verileri
9. Seçilen test seti
10. Coverage ve çalışma süresi

## Bilinen legacy sorunları

- BENCH dosyası `PSO_DFS.py` ve `DFS_bench.py` tarafından ayrı ayrı okunuyor.
- `Parser.readFile()` parsing dışında simülasyon, activity ve rarity işlemlerini de tetikliyor.
- Aktif PSO, makaledeki parametreleri kullanmıyor.
- `average_coverage` toplamı her parçacıkta artırılırken yalnız 100 dış iterasyona bölünüyor.
- Import sırasında ana deney otomatik çalışıyor.
- `__inputRand()` çok sayıda vektör üretip yalnız son vektörü simüle ediyor.

Bu davranışlar sessizce değiştirilmemeli; düzeltmeler ayrı commit ve testlerle yapılmalıdır.
