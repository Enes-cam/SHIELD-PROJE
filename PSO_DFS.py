#######
# Auther: Mostafa
# 1403/02/13
#######
import numpy as np
from random import seed, randint
import random
from Dalgebra import *
from datetime import datetime
import DFS_bench
start = datetime.now()

# =============================================================================
# TÜRKÇE ÖĞRENME HARİTASI - ÖZGÜN SHIELD KODU
#
# Bu dosyada birçok görev tek Parser sınıfında birleşmiştir:
#   readFile / __loadCode       : BENCH okuma
#   __cirLevelization           : Gate seviyelerini belirleme
#   circuitSimulation           : Bir test vektörünü devrede çalıştırma
#   switchingActivity           : Net geçişlerini sayma
#   rare_net                    : SWA eşiğinin altındaki netleri seçme
#   fitness_function            : PSO adayının rare-net geçiş başarısı
#   PSO                         : Aktif parçacık sürüsü algoritması
#
# Dosyanın 261 ve 469 civarında başlayan büyük '# def PSO...' blokları aktif
# değildir; bunlar yorum satırına alınmış alternatif/deneysel sürümlerdir.
# Gerçekten çalışan PSO, 'def PSO(self, effective_inputs)' tanımıdır.
#
# YENİ MODÜLER SİSTEME EŞLEŞME
# ----------------------------
# readFile / __loadCode      -> circuit.py / CircuitReader -> CircuitIR
# __cirLevelization          -> CircuitIR.topological_gate_order hazırlanırken
# __inputRand                -> test_vectors.py (legacy uyumlu veya normal RNG)
# circuitSimulation          -> simulation.py / LogicSimulator
# switchingActivity          -> activity.py / ActivityAnalyzer
# rare_net                   -> rarity.py / RareTargetDetector
# DFS_bench.myfunc           -> graph.py + input_analysis.py
# aday test üretimi          -> candidate_generation.py
# rare target coverage      -> coverage.py / CoverageAnalyzer
# PSO ile seçim             -> Özgün hali BU DOSYADA korunuyor.
#                              optimization.py içindeki DiscretePSO ayrı ve
#                              deneysel bir stratejidir; özgün PSO'nun birebir
#                              taşınmış hali veya baseline sonucu değildir.
# bütün akışın yönetimi      -> experiment.py / ExperimentRunner
#
# Dalgebra.py ilişkisi:
# circuitSimulation -> __operate eski sistemde Dalgebra fonksiyonlarını çağırır.
# Yeni sistemde binary gate hesabı simulation._evaluate_gate içindedir. D/D'
# desteği modüler pipeline'a taşınmamıştır.
# =============================================================================


class Parser:
    def __init__(self, seed):
        # Bütün legacy çalışma durumu bu nesnede tutulur. seed hem Python random
        # hem NumPy random için ayarlanarak tekrar üretilebilirlik amaçlanır.
        self.seed = seed
        random.seed(self.seed)
        np.random.seed(self.seed)
        self.varIndex = {}
        self.varMap = {}
        # varMap özgün kodun merkezi devre veri yapısıdır.
        # Bir node listesinde önemli indeksler:
        # [1]=node adı, [2]=INPUT/OUTPUT türü, [3]=anlık değer,
        # [4]=gate tipi, [5]=giriş netleri, [10]=[0->1, 1->0] sayaçları.
        self.nodeLevel = {}
        self.sortedNode = []
        self.inputList = []
        self.outputList = []
        self.size = 0
        self.NoItr = 1000
        self.threshold = 0.1
        self.Coverage_ratio = 1

    def readFile(self, fileName):
        # BENCH dosyasını okur. Dikkat: yalnız parsing yapmaz; __loadCode sonunda
        # levelization, rastgele giriş, switching activity ve rarity adımlarını
        # da tetikler. Modülerleştirme ihtiyacının temel nedenlerinden biri bu.
        with open(fileName, "r") as f:
            lines = f.readlines()
            lines = [i for i in lines if i != '\n' and i[0] != '#']
            lines = [i.replace("\n", "").replace(" ", "") for i in lines]
            self.__loadCode(lines)
            return

    def __loadCode(self, lines):
        # INPUT/OUTPUT ve gate satırlarını varMap yapısına dönüştürür.
        counter = 1
        for code in lines:
            if code.strip() == '':
                continue
            # INPUT/OUTPUT
            elif code.casefold().find("=") == -1:
                var = code[code.index("(") + 1: code.index(")")]
                type = "INPUT" if (code.casefold().find("input") != -1) else "OUTPUT"
                if var in self.varMap:
                    # I/O  node type Buffer
                    if type == "OUTPUT" and self.varMap[var][2] == "INPUT":
                        newVar = var + 'o'
                        self.varMap[newVar] = [
                            counter, newVar, type, "_", "BUFF", [var], [], [1, 1], 0, [0, 0], "_"
                        ]
                        self.outputList.append(var)
                        counter += 1
                        self.size += 1
                        continue
                        # END I/O
                    self.varMap[var][2] = type
                    if type == "OUTPUT" and type not in self.outputList:
                        self.outputList.append(var)
                else:
                    self.varMap[var] = [counter, var, type, "_", "___", [], [], [-1, -1], 0, [0, 0], "_"]
                    self.varIndex[var] = counter
                    if type == "INPUT":
                        self.inputList.append(var)
                        self.varMap[var][7] = [1, 1]
                    else:
                        self.outputList.append(var)
                    counter += 1
                    self.size += 1
            else:
                # gate
                var = code[:code.index("=")]
                gate = code[code.index("=") + 1: code.index("(")]
                inputs = code[code.index("(") + 1: code.index(")")].split(",")

                if var in self.varMap:
                    self.varMap[var][4] = gate
                    self.varMap[var][5] = inputs
                else:
                    self.varMap[var] = [
                        counter, var, "___", "_", gate, inputs, [], [-1, -1], 0, [0, 0], "_"
                    ]
                    self.varIndex[var] = counter
                    counter += 1
                    self.size += 1

        self.__cirLevelization()
        self.__sortByLevel()
        self.__inputRand()
        self.switchingActivity()
        self.rare_net()
        # Yukarıdaki zincir readFile çağrısının neden yalnız "dosya okuma"
        # olmadığına dikkat edin.

        return

    #  Circuit Levelization
    # nodes have ability to have level
    def __nodeIsLevelable(self, node):
        return all(inp in self.nodeLevel for inp in self.varMap[node][5])

    # max level of input
    def __maxOfInp(self, inpLst):
        return max(self.nodeLevel[inp] for inp in inpLst)

    # create sorted node by level
    def __nodeLv(self, node):
        return self.nodeLevel[node]

    def __sortByLevel(self):
        # Simülasyonda bir gate, girdilerini üreten gate'lerden sonra çalışmalı.
        # Bu nedenle nodelar hesaplanan seviyeye göre sıralanır.
        self.sortedNode = sorted(self.nodeLevel.keys(), key=self.__nodeLv)
        self.inputList = sorted(self.inputList, key=self.__nodeLv)
        return

    # circuit Levelization
    def __cirLevelization(self):
        # Primary inputlar seviye 0'dır. Bir gate'in seviyesi, en yüksek giriş
        # seviyesinin 1 fazlasıdır. Tüm girişleri seviyelenmeden gate seviyelenmez.
        isUpdate = True
        allAssigned = False
        while (isUpdate and not allAssigned):
            isUpdate = False
            for line in self.varMap.values():
                node = line[1]
                if node in self.nodeLevel:
                    continue
                elif line[2] == "INPUT":
                    self.nodeLevel[node] = 0
                    isUpdate = True
                    # node is an input
                elif self.__nodeIsLevelable(node):
                    max = self.__maxOfInp(line[5])
                    self.nodeLevel[node] = 1 + max
                    isUpdate = True
                    if len(self.nodeLevel) == self.size:
                        allAssigned = True
        return

    def printSystem(self):
        print()
        print("SystemSpecification: ")
        print("|-----|------|-------|------|-----------------------|---------|")
        label = "|{:>5}|{:>6}|{:>7}|{:>6}|{:^9}|{:^14}|{:<14}".format(
            "node", "level", "type", "val", "gate", "input", "SWA"
        )
        print(label)
        print("|-----|------|-------|------|---------|--------------|---------|")

        for key in self.sortedNode:
            line = self.varMap[key]
            node = line[1]
            level = "inf" if node not in self.nodeLevel else self.nodeLevel[node]
            type = line[2]
            val = line[3]
            gate = line[4]
            cntr = ("(" + ",".join([str(key) for key in line[7]]) + ")") if line[7] != [-1 - 1] else "(u, u)"
            CO_ = str(line[8])
            SWA = str(line[10])
            MC = ("(" + ",".join([str(key) for key in line[9]]) + ")") if line[9] != [0, 0] else "[0, 0]"
            input = ','.join([str(key) for key in line[5]]) if line[5] else "_____"
            printLine = "|{:{f}>5}|{:{f}>6}|{:{f}>7}|{:{f}>6}|{:{f}>9}|{:{f}^12}|{:{f}^9}|{:{f}^9}|{:{f}^14}|{:{f}^14}|".format(
                node, level, type, val, gate, cntr, CO_, MC, input, SWA, f='_')
            print(printLine)
        return

    def printInOut(self):
        print("# of input list", len(self.inputList))
        print("# of output list", len(self.outputList))
        return

    def __clearValue(self):
        # Yeni simülasyondan önce tüm node değerlerini bilinmeyen '_' yapar.
        for var in self.varMap:
            self.varMap[var][3] = "_"
        return

    def circuitSimulation(self, inputVector):
        # LOGIC SIMULATION'IN ANA FONKSİYONU.
        # 1) Eski değerleri temizler.
        # 2) Primary input değerlerini yükler.
        # 3) Gate'leri seviye sırasıyla hesaplar.
        self.__clearValue()
        self.__initInput(inputVector)
        for var in self.sortedNode:
            if var in self.inputList:
                continue
            gate = self.varMap[var][4]
            inputs = self.varMap[var][5]
            result = self.__operate(var, gate, inputs)
            self.varMap[var][3] = result


    def __initInput(self, inputVector):
        # Test vektöründeki bitleri inputList sırasıyla primary inputlara yazar.
        for i in range(len(self.inputList)):
            node = self.inputList[i]
            value = inputVector[i]
            self.varMap[node][3] = value
        return

    def __operate(self, nodeOut, gate, inputNodes):
        # Gate'in giriş değerlerini varMap'ten toplar ve Dalgebra.py içindeki
        # uygun mantık fonksiyonuna gönderir.
        inputs = []  # list [0, 1, D, D']
        for node in inputNodes:
            canonical = nodeOut + "_" + node
            inputName = canonical if canonical in self.varMap else node  # var
            inputs.append(self.varMap[inputName][3])  # value of inputs
        if gate == "NOT":
            return NOT(inputs)
        if gate == "AND":
            return AND(inputs)
        if gate == "OR":
            return OR(inputs)
        if gate == "NAND":
            return NAND(inputs)
        if gate == "NOR":
            return NOR(inputs)
        if gate == "XOR":
            return XOR(inputs)
        if gate == "XNOR":
            return XNOR(inputs)
        if gate == "BUFF":
            return BUFF(inputs)

    def __inputRand(self):
        # LEGACY DAVRANIŞ UYARISI:
        # Döngüde NoItr adet vektör üretilir fakat circuitSimulation döngünün
        # dışında olduğu için yalnız son üretilen vektör simüle edilir.
        # Buna rağmen bu döngü random sayı üretecinin durumunu ilerletir.
        for _ in range(self.NoItr):
            inputVector = [str(randint(0, 1)) for _ in self.inputList]
        self.circuitSimulation(inputVector)
        return

    def switchingActivity(self):
        # ACTIVITY ANALYSIS.
        # NoItr adet rastgele vektör simüle edilir. Her node için arka arkaya
        # gelen değerler karşılaştırılarak 0->1 ve 1->0 sayıları tutulur.
        SwResult = {}
        prevState = {}
        changeCount = {}

        for node in self.sortedNode:
            SwResult[node] = [0, 0]
            changeCount[node] = {"0_to_1": 0, "1_to_0": 0}
            prevState[node] = None

        for _ in range(self.NoItr):
            inputVector = [str(randint(0, 1)) for _ in self.inputList]
            self.circuitSimulation(inputVector)
            for node in self.sortedNode:
                SWA0_1 = []
                currentValue = int(self.getValue(node))

                if prevState[node] is not None:
                    if prevState[node] == 0 and currentValue == 1:
                        changeCount[node]["0_to_1"] += 1
                    elif prevState[node] == 1 and currentValue == 0:
                        changeCount[node]["1_to_0"] += 1
                prevState[node] = currentValue
                SWA0_1.extend([changeCount[node]["0_to_1"], changeCount[node]["1_to_0"]])
                self.varMap[node][10] = SWA0_1

        return

    def rare_net(self):
        # RARE TARGET SEÇİMİ.
        # SWA = (0->1 + 1->0) / NoItr. threshold değerinden küçük gate çıkışları
        # rare kabul edilir. Primary inputlar gate_out_lst içinde olmadığı için
        # target listesine alınmaz.
        gate_out_lst = ["AND", "NAND", "OR", "NOR", "XOR", "XNOR", "BUFF", "NOT"]
        rare_list = []
        for node in self.sortedNode:
            if self.varMap[node][4] in gate_out_lst:
                rare_node = (self.varMap[node][10][0] + self.varMap[node][10][1]) / self.NoItr
                if rare_node < self.threshold:
                    rare_list.append([node, rare_node])

        return rare_list

    # -------------------------------------------------------------------------
    # AKTİF DEĞİL: Dinamik parametreli eski/alternatif PSO denemesi.
    # Aşağıdaki bütün PSO1 bloğu yorum satırıdır ve program tarafından çalışmaz.
    # -------------------------------------------------------------------------
    # def PSO1(self, effective_inputs): # dynamic
    #     num_particles = 150
    #     inertia_weight_start = 0.9
    #     inertia_weight_end = 0.4
    #     cognitive_weight_start = 2.4
    #     cognitive_weight_end = 1.0
    #     social_weight_start = 2.0
    #     social_weight_end = 2.5
    #     max_iterations = 150  # Maximum number of iterations
    #     rare_gates = self.rare_net()
    #     total_rare_gates = len(rare_gates)
    #     activated_rare_gates = set()
    #     test_vectors = []
    #     total_test_vectors_generated = 0
    #     cnt = 0

    #     def get_activated_rare_gates(position):
    #         self.circuitSimulation(position)
    #         activated = set()
    #         for rare_gate in rare_gates:
    #             gate_name = rare_gate[0]
    #             if int(self.getValue(gate_name)) == 1:
    #                 activated.add(gate_name)
    #         return activated

    #     particle_positions = []
    #     particle_velocities = []
    #     particle_best_positions = []
    #     particle_best_fitness = []

    #     sorted_effective_inputs = sorted(effective_inputs.items(), key=lambda x: x[1], reverse=True)

    #     # Initialize positions and velocities
    #     for _ in range(num_particles):
    #         position = np.array(['0'] * len(self.inputList))

    #         for idx, _ in sorted_effective_inputs:
    #             position[idx] = str(randint(0, 1))

    #         for idx in range(len(position)):
    #             if idx not in dict(sorted_effective_inputs).keys():
    #                 position[idx] = str(randint(0, 1))

    #         fitness = self.fitness_function(position, effective_inputs)
    #         velocity = np.random.uniform(-1, 1, len(self.inputList))  # Random initial velocity
    #         particle_positions.append(position)
    #         particle_velocities.append(velocity)
    #         particle_best_positions.append(position.copy())
    #         particle_best_fitness.append(fitness)

    #     global_best_position = max(particle_positions, key=lambda pos: self.fitness_function(pos, effective_inputs))
    #     global_best_fitness = max(particle_best_fitness)

    #     # Iterate until 100% rare gate coverage or max iterations
    #     iteration = 0
    #     while len(activated_rare_gates) < self.Coverage_ratio * total_rare_gates and iteration < max_iterations:
    #         total_test_vectors_generated += 1
    #         iteration += 1
    #         print(f"\nTest vector generation attempt: {total_test_vectors_generated}")

    #         # Dynamic parameter adjustment
    #         inertia_weight = inertia_weight_start - iteration * ((inertia_weight_start - inertia_weight_end) / max_iterations)
    #         cognitive_weight = cognitive_weight_start - iteration * ((cognitive_weight_start - cognitive_weight_end) / max_iterations)
    #         social_weight = social_weight_start + iteration * ((social_weight_end - social_weight_start) / max_iterations)

    #         for i in range(num_particles):
    #             # Update particle velocity
    #             cognitive_velocity = cognitive_weight * np.random.rand() * (particle_best_positions[i] != particle_positions[i])
    #             social_velocity = social_weight * np.random.rand() * (global_best_position != particle_positions[i])
    #             particle_velocities[i] = (inertia_weight * particle_velocities[i]) + cognitive_velocity + social_velocity

    #             # Update particle position based on velocity
    #             for j in range(len(particle_positions[i])):
    #                 if np.random.rand() < self.sigmoid(particle_velocities[i][j]):
    #                     particle_positions[i][j] = '1' if particle_positions[i][j] == '0' else '0'

    #             # Evaluate particle fitness
    #             fitness = self.fitness_function(particle_positions[i], effective_inputs)

    #             # Update personal best position
    #             if fitness > particle_best_fitness[i]:
    #                 particle_best_fitness[i] = fitness
    #                 particle_best_positions[i] = particle_positions[i].copy()

    #             # Update global best position
    #             if fitness > global_best_fitness:
    #                 global_best_fitness = fitness
    #                 global_best_position = particle_positions[i].copy()

    #             activated_by_particle = get_activated_rare_gates(particle_positions[i])
    #             new_rare_gates = activated_by_particle - activated_rare_gates
    #             if new_rare_gates:
    #                 print(f"Test vector {total_test_vectors_generated} (PSO) activated rare gates: {new_rare_gates}")
    #                 activated_rare_gates.update(new_rare_gates)
    #                 test_vectors.append(particle_positions[i])

    #             print(f"Total rare gates activated so far: {len(activated_rare_gates)}/{total_rare_gates}")
    #             cnt+=1
    #     print(f"\nGlobal best test vector: {global_best_position}")
    #     print(f"Global best fitness: {global_best_fitness}")
    #     print(f"\nMinimum number of tests needed to activate all rare gates: {len(test_vectors)}")
    #     print(f"Total number of test vectors generated: {total_test_vectors_generated}")
    #     print("cnt: ", cnt)
    #     return test_vectors

    # def sigmoid(self, x):
    #     return 1 / (1 + np.exp(-x))

    def PSO(self, effective_inputs):
        # AKTİF PSO BAŞLANGICI.
        # effective_inputs, DFS_bench.myfunc() tarafından üretilen
        # {input_index: etkilediği_rare_target_sayısı} sözlüğüdür.
        num_particles = len(self.inputList)
        # Aktif kod parçacık sayısını primary input sayısına eşitler.
        inertia_weight = 0.7
        cognitive_weight = 1.5
        social_weight = 1.4
        rare_gates = self.rare_net()
        # PSO'nun hedefleyeceği rare gate listesi mevcut activity sonucundan gelir.
        total_rare_gates = len(rare_gates)
        activated_rare_gates = set()
        test_vectors = []
        total_test_vectors_generated = 0
        total_coverage = 0  # Ortalama hesabı için toplam coverage değeri.

        def get_activated_rare_gates(position):
            # Bir parçacığı tam giriş vektörü olarak simüle eder. Çıkışı 1 olan
            # rare gate'leri bu test tarafından aktive edilmiş sayar.
            self.circuitSimulation(position)
            activated = set()
            for rare_gate in rare_gates:
                gate_name = rare_gate[0]
                if int(self.getValue(gate_name)) == 1:
                    activated.add(gate_name)
            return activated

        particle_positions = []
        particle_velocities = []
        particle_best_positions = []
        particle_best_fitness = []

        sorted_effective_inputs = sorted(effective_inputs.items(), key=lambda x: x[1], reverse=True)
        # Inputlar kaç rare target'ı etkilediklerine göre sıralanır.

        # Initialize positions and velocities of particles
        for _ in range(num_particles):
            # Her parçacık bir binary test vektörüdür. Başlangıç konumları ve
            # hızlar rastgele oluşturulur; pbest başlangıçta kendi konumudur.
            position = np.array(['0'] * len(self.inputList))

            for idx, _ in sorted_effective_inputs:
                position[idx] = str(randint(0, 1))

            for idx in range(len(position)):
                if idx not in dict(sorted_effective_inputs).keys():
                    position[idx] = str(randint(0, 1))

            fitness = self.fitness_function(position, effective_inputs)
            velocity = np.random.uniform(-1, 1, len(self.inputList))  # Random initial velocity
            particle_positions.append(position)
            particle_velocities.append(velocity)
            particle_best_positions.append(position.copy())
            particle_best_fitness.append(fitness)

        global_best_position = max(particle_positions, key=lambda pos: self.fitness_function(pos, effective_inputs))
        # Başlangıç sürüsündeki en yüksek fitness değerli konum gbest olur.
        global_best_fitness = max(particle_best_fitness)

        # Generate up to 100 test vectors
        while total_test_vectors_generated < 100:
            # Dış döngü 100 test üretim girişimi yapar. Coverage %100 olsa bile
            # aktif sürüm erken durmaz; 100 turun tamamını çalıştırır.
            total_test_vectors_generated += 1
            print(f"\nTest vector generation attempt: {total_test_vectors_generated}")

            for i in range(num_particles):
                # Update particle velocity
                cognitive_velocity = cognitive_weight * np.random.rand() * (particle_best_positions[i] != particle_positions[i])
                social_velocity = social_weight * np.random.rand() * (global_best_position != particle_positions[i])
                # Cognitive terim parçacığın kendi en iyisine, social terim
                # sürünün global en iyisine göre farklı bitleri yönlendirir.
                particle_velocities[i] = (inertia_weight * particle_velocities[i]) + cognitive_velocity + social_velocity

                # Update particle position based on velocity
                for j in range(len(particle_positions[i])):
                    if np.random.rand() < self.sigmoid(particle_velocities[i][j]):
                        particle_positions[i][j] = '1' if particle_positions[i][j] == '0' else '0'
                    # Sigmoid hız değerini bit-flip olasılığına dönüştürür.

                # Evaluate particle fitness
                fitness = self.fitness_function(particle_positions[i], effective_inputs)

                # Update personal best position
                if fitness > particle_best_fitness[i]:
                    # Yeni konum parçacığın geçmişinden iyiyse personal best güncellenir.
                    particle_best_fitness[i] = fitness
                    particle_best_positions[i] = particle_positions[i].copy()

                # Update global best position
                if fitness > global_best_fitness:
                    # Bütün sürü açısından daha iyi çözüm bulunduysa gbest güncellenir.
                    global_best_fitness = fitness
                    global_best_position = particle_positions[i].copy()

                activated_by_particle = get_activated_rare_gates(particle_positions[i])
                new_rare_gates = activated_by_particle - activated_rare_gates
                # Yalnız daha önce görülmemiş rare gate aktivasyonu sağlayan
                # parçacıklar nihai test_vectors listesine eklenir.
                if new_rare_gates:
                    print(f"Test vector {total_test_vectors_generated} (PSO) activated rare gates: {new_rare_gates}")
                    activated_rare_gates.update(new_rare_gates)
                    test_vectors.append(particle_positions[i])

                # Calculate coverage for this test vector
                coverage = len(activated_rare_gates) / total_rare_gates
                total_coverage += coverage

                print(f"Total rare gates activated so far: {len(activated_rare_gates)}/{total_rare_gates}")
                print(f"Coverage: {coverage * 100:.2f}%")

        # Calculate and print average coverage
        average_coverage = (total_coverage / total_test_vectors_generated) * 100
        # BİLİNEN LEGACY HATA: total_coverage her parçacıkta artırılır fakat
        # yalnız 100 dış tura bölünür. Bu yüzden yazdırılan ortalama %100'ü aşar.
        print(f"\nAverage coverage of 100 test vectors: {average_coverage:.2f}%")
        print(f"Total test vectors generated: {total_test_vectors_generated}")

        return test_vectors


    # -------------------------------------------------------------------------
    # AKTİF DEĞİL: Başka bir optimize PSO denemesi. Tüm blok yorum satırıdır.
    # -------------------------------------------------------------------------
    # def PSO(self, effective_inputs): # opti
    #     num_particles = 50  # Daha az parçacık kullanır.
    #     max_iterations = 100  # Daha az iterasyon kullanır.
    #     inertia_weight = 0.7  # Sabit eylemsizlik ağırlığı.
    #     cognitive_weight = 1.4  # Sabit bilişsel ağırlık.
    #     social_weight = 1.4  # Sabit sosyal ağırlık.

    #     rare_gates = self.rare_net()
    #     total_rare_gates = len(rare_gates)
    #     activated_rare_gates = set()
    #     test_vectors = []
    #     total_test_vectors_generated = 0

    #     def get_activated_rare_gates(position):
    #         """Mevcut konumun aktive ettiği rare gate'leri hesaplar."""
    #         self.circuitSimulation(position)
    #         return {
    #             gate[0] for gate in rare_gates if int(self.getValue(gate[0])) == 1
    #         }

    #     # Etkili inputları etki sayılarına göre sıralar.
    #     sorted_effective_inputs = sorted(effective_inputs.items(), key=lambda x: x[1], reverse=True)
    #     effective_input_indices = [idx for idx, _ in sorted_effective_inputs]

    #     # Parçacıkların başlangıç değerlerini oluşturur.
    #     particle_positions = np.zeros((num_particles, len(self.inputList)), dtype=str)
    #     particle_velocities = np.random.uniform(-1, 1, (num_particles, len(self.inputList)))
    #     particle_best_positions = np.copy(particle_positions)
    #     particle_best_fitness = np.full(num_particles, -np.inf)

    #     for i in range(num_particles):
    #         # Başlangıç konumunu etkili inputlara göre ayarlar.
    #         for idx in effective_input_indices:
    #             particle_positions[i, idx] = str(randint(0, 1))
    #         # Diğer konumlara rastgele değer atar.
    #         for idx in range(len(self.inputList)):
    #             if idx not in effective_input_indices:
    #                 particle_positions[i, idx] = str(randint(0, 1))

    #         # Başlangıç fitness değerini hesaplar.
    #         particle_best_fitness[i] = self.fitness_function(particle_positions[i], effective_inputs)
    #         particle_best_positions[i] = np.copy(particle_positions[i])

    #     # Global en iyi parçacığı bulur.
    #     global_best_position = particle_positions[np.argmax(particle_best_fitness)]
    #     global_best_fitness = max(particle_best_fitness)

    #     # PSO'nun ana döngüsü.
    #     iteration = 0
    #     while len(activated_rare_gates) < self.Coverage_ratio * total_rare_gates:
    #         total_test_vectors_generated += 1
    #         iteration += 1

    #         print(f"\nIteration {iteration}, Test vectors generated: {total_test_vectors_generated}")
    #         for i in range(num_particles):
    #             # Parçacık hızını hesaplar.
    #             r1 = np.random.rand(len(self.inputList))
    #             r2 = np.random.rand(len(self.inputList))
    #             cognitive_velocity = cognitive_weight * r1 * (particle_best_positions[i] != particle_positions[i])
    #             social_velocity = social_weight * r2 * (global_best_position != particle_positions[i])
    #             particle_velocities[i] = inertia_weight * particle_velocities[i] + cognitive_velocity + social_velocity

    #             # Parçacık konumunu günceller.
    #             sigmoid_values = 1 / (1 + np.exp(-particle_velocities[i]))
    #             particle_positions[i] = np.where(np.random.rand(len(self.inputList)) < sigmoid_values, '1', '0')

    #             # Yeni fitness değerini hesaplar.
    #             fitness = self.fitness_function(particle_positions[i], effective_inputs)

    #             # Parçacığın kişisel en iyi konumunu günceller.
    #             if fitness > particle_best_fitness[i]:
    #                 particle_best_fitness[i] = fitness
    #                 particle_best_positions[i] = np.copy(particle_positions[i])

    #             # Sürünün global en iyi konumunu günceller.
    #             if fitness > global_best_fitness:
    #                 global_best_fitness = fitness
    #                 global_best_position = np.copy(particle_positions[i])

    #             # Aktive edilen rare gate'leri kontrol eder.
    #             activated_by_particle = get_activated_rare_gates(particle_positions[i])
    #             new_rare_gates = activated_by_particle - activated_rare_gates
    #             if new_rare_gates:
    #                 activated_rare_gates.update(new_rare_gates)
    #                 test_vectors.append(particle_positions[i])
    #                 print(f"Particle {i} activated rare gates: {new_rare_gates}")
    #                 print(f"Total rare gates activated: {len(activated_rare_gates)}/{total_rare_gates}")

    #     # Nihai sonuçları yazdırır.
    #     print(f"\nGlobal best test vector: {global_best_position}")
    #     print(f"Global best fitness: {global_best_fitness}")
    #     print(f"Minimum number of test vectors needed: {len(test_vectors)}")
    #     print(f"Total test vectors generated: {total_test_vectors_generated}")

    #     return test_vectors

    def sigmoid(self, x):
        # Hızı 0..1 aralığında bit değiştirme olasılığına dönüştürür.
        return 1 / (1 + np.exp(-x))



    def fitness_function(self, position, effective_inputs):
        # FITNESS FONKSİYONU.
        # Önce yalnız effective input bitleri kullanılan tam bir vektör kurulur;
        # diğer inputlar 0 bırakılır. Ardından sıfır vektörü -> aday vektör çifti
        # simüle edilir ve rare netlerde oluşan toplam geçiş sayısı fitness olur.
        # Tüm bitleri başlangıçta 0 olan eksiksiz bir input vektörü oluşturur.
        inputVector_full = ['0'] * len(self.inputList)
        # Yalnızca etkili inputların bit değerlerini yerleştirir.
        for idx in effective_inputs:
            inputVector_full[idx] = position[idx]

        SwResult = {}
        prevState = {}
        changeCount = {}
        rare_lst = self.rare_net()
        for node in self.sortedNode:
            SwResult[node] = [0, 0]
            changeCount[node] = {"0_to_1": 0, "1_to_0": 0}
            prevState[node] = None

        inputVector_init = ['0'] * len(self.inputList)
        pairList = [[inputVector_init, inputVector_full]]

        for pair in pairList:
            changeCount = {node: {"0_to_1": 0, "1_to_0": 0} for node in self.sortedNode}
            prevState = {node: None for node in self.sortedNode}
            for inp_vec in pair:
                self.circuitSimulation(inp_vec)
                swa_lst = []

                for node in rare_lst:
                    SWA0_1 = []

                    currentvalue = int(self.getValue(node[0]))
                    if prevState[node[0]] is not None:
                        if prevState[node[0]] == 0 and currentvalue == 1:
                            changeCount[node[0]]["0_to_1"] += 1
                        elif prevState[node[0]] == 1 and currentvalue == 0:
                            changeCount[node[0]]["1_to_0"] += 1
                    prevState[node[0]] = currentvalue
                    SWA0_1.append([changeCount[node[0]]["0_to_1"], changeCount[node[0]]["1_to_0"]])

                    swa_lst.extend(SWA0_1)

                node_swa_lst = [sum(pair) for pair in swa_lst]
                fitness_values = sum(node_swa_lst)
        return fitness_values



    def crossover(self, parent1, parent2):
        crossover_point = np.random.randint(1, len(parent1) - 1)
        child1 = np.concatenate((parent1[:crossover_point], parent2[crossover_point:]))
        child2 = np.concatenate((parent2[:crossover_point], parent1[crossover_point:]))
        return child1, child2


    def SWA_Alpha(self):
        # Tüm nodeların normalize activity değerlerini çıkarır ve threshold
        # altında kaç tane olduğunu yazdırır. Ana rarity listesi için rare_net()
        # kullanılır; bu fonksiyon daha çok raporlama/debug amaçlıdır.
        SW_list = []
        for node in self.sortedNode:
            node_Alpha = ob.varMap[node][10][0] + ob.varMap[node][10][1]
            SW_list.append(node_Alpha)
            Alpha_list = [x / self.NoItr for x in SW_list]
        alph = sum(1 for i in Alpha_list if i <= self.threshold)
        print("alph: ", alph, "\n", "threshold: ", self.threshold)

        return Alpha_list

    def perturb_vector(self, vector, index):
        perturbed_vector = vector.copy()
        perturbed_vector[index] = '1' if perturbed_vector[index] == '0' else '0'  # Flip the bit
        return perturbed_vector

    def perturb_vectors(self, vectors):
        all_perturbed_vectors = []
        for vector in vectors:
            perturbed_vectors = []
            for i in range(len(vector)):
                perturbed_vector = self.perturb_vector(vector, i)
                perturbed_vectors.append(perturbed_vector)
            all_perturbed_vectors.append(perturbed_vectors)
        return all_perturbed_vectors

    def getValue(self, node):
        return self.varMap[node][3]


# =============================================================================
# ANA PROGRAM AKIŞI
# Dosya doğrudan çalıştırıldığında aşağıdaki satırlar yürütülür:
#   1) C880 okunur ve activity/rare netler çıkarılır.
#   2) Rare netlerden reverse DFS ile effective inputlar bulunur.
#   3) Aktif PSO test vektörleri üretir.
#   4) Süre ve activity bilgisi yazdırılır.
# =============================================================================
ob = Parser(seed=42)
test_lst = []

# The original implementation casts rare-net identifiers to int.  Use the
# equivalent G-prefix-free fixture retained specifically for legacy regression.
file_name = 'datasets/legacy/c880.bench'


ob.readFile(file_name)
# readFile burada parsing + levelization + activity + rarity çalıştırır.
ob.printSystem()

filtered_data = {0: 48, 1: 26, 2: 20, 3: 20, 4: 30, 5: 19, 6: 2, 7: 23, 8: 28, 9: 32, 10: 33, 11: 18, 12: 12, 13: 11, 14: 3, 15: 22, 16: 14, 34: 2, 35: 2, 36: 2, 38: 2, 39: 18, 59: 12}

idx_lst = [int(item[0]) for item in ob.rare_net()]

filtered_data = DFS_bench.myfunc(idx_lst, file_name)
# Reverse DFS sonucu: input index -> etkilediği rare target sayısı.
print(filtered_data)
print("idx_lst: ", idx_lst)
ob.PSO(filtered_data)
# Aktif PSO, reverse DFS sonucunu kullanarak test vektörleri arar.
print("time: ", (datetime.now() - start).total_seconds())
ob.SWA_Alpha()



##
