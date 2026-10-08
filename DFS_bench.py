import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter

# =============================================================================
# Bu dosyanın üç temel görevi vardır:
#   1) BENCH dosyasını tekrar okumak: parser()
#   2) Devreyi NetworkX yönlü grafına çevirmek: grapher()
#   3) Rare netlerden geriye doğru gidip etkili primary inputları bulmak:
#      dfs_find_inputs_with_indices() ve myfunc()
#
# Dikkat: Modüler yeni yapıda BENCH'i yalnız Circuit Module okur. Bu dosya ise
# özgün SHIELD baseline kodudur ve öğrenme/karşılaştırma için korunmaktadır.
#
# YENİ MODÜLER SİSTEMDEKİ KARŞILIKLAR
# -----------------------------------
# parser()                         -> src/shield/circuit.py
#                                     CircuitReader.read() / CircuitIR
# grapher()                        -> src/shield/graph.py
#                                     CircuitGraphBuilder.build()
# dfs_find_inputs_with_indices()   -> src/shield/input_analysis.py
#                                     ReverseDFSInputAnalyzer.analyze()
# myfunc()                         -> Artık tek bir fonksiyon değildir.
#                                     Circuit, Graph ve Input Analysis
#                                     modülleri ExperimentRunner tarafından
#                                     sırayla çağrılır.
#
# Eski myfunc BENCH dosyasını tekrar okur. Yeni sistem bunu yapmaz: BENCH yalnız
# Circuit Module tarafından bir kez okunur; Graph ve Input Analysis modülleri
# sırasıyla CircuitIR, CircuitGraph ve RareTargets nesnelerini kullanır.
# =============================================================================

def sanitize(x):
    # BENCH satırlarından virgül, parantez ve boşluk gibi karakterleri temizler.
    return x.strip(',;\n ()')


def parser(file_, verbose=0):
    # BENCH -> input_nodes, output_nodes, gates, wires dönüşümü.
    # wires öğesi kabaca [net_adı, sürücü_node, tüketici_nodelar] biçimindedir.
    # YENİDE: CircuitReader bu bilgileri CircuitIR.gates ve
    # CircuitIR.connections alanlarına dönüştürür.
    with open(file_, 'r') as bench_file:
        input_nodes = []
        output_nodes = []
        gates = []
        wires = []

        for line in bench_file:
            line = line.strip()

            # Process inputs
            if line.startswith("INPUT"):
                node = sanitize(line.lstrip("INPUT"))
                input_nodes.append(node)

            # Process outputs
            elif line.startswith("OUTPUT"):
                node = sanitize(line.lstrip("OUTPUT"))
                output_nodes.append(node)

            # Process gate definitions
            elif "=" in line:
                # Split line by '=' to separate the output and the gate with its inputs
                output_port, gate_definition = line.split("=")
                output_port = sanitize(output_port)

                # Extract gate type and input ports
                gate_type, ports = gate_definition.strip().split("(")
                gate_type = gate_type.strip().lower()  # Lowercase to match colors later
                ports = [sanitize(x) for x in ports.split(",")]

                # Use the output port as the gate name
                gate_name = output_port
                gates.append(gate_name)

                # Create or update wires for connections
                existing_wire = next((w for w in wires if w[0] == output_port), None)
                if existing_wire:
                    existing_wire[1] = gate_name
                else:
                    wires.append([output_port, gate_name, []])

                for i in ports:
                    if i in input_nodes:
                        existing_wire = next((w for w in wires if w[0] == i), None)
                        if existing_wire:
                            existing_wire[2].append(gate_name)
                        else:
                            wires.append([i, i, [gate_name]])
                    else:
                        existing_wire = next((w for w in wires if w[0] == i), None)
                        if existing_wire:
                            existing_wire[2].append(gate_name)
                        else:
                            wires.append([i, ' ', [gate_name]])

    return input_nodes, output_nodes, gates, wires

def grapher(in_n, out_n, nodes, edges, verbose=0):
    # Parser çıktısını yönlü grafa çevirir.
    # Kenar yönü normal sinyal akışıdır: sürücü -> tüketici.
    # YENİDE: CircuitGraphBuilder, NetworkX kullanmadan CircuitIR.connections
    # üzerinden CircuitGraph.predecessors/successors sözlüklerini üretir.
    G = nx.DiGraph()
    G.add_nodes_from(in_n)
    G.add_nodes_from(out_n)
    G.add_nodes_from(nodes)  # Ensure all gate nodes are added

    colour_map = []
    size = []
    for node in G:
        if node in in_n:
            colour_map.append('red')
        elif node in out_n:
            colour_map.append('green')
        else:
            colour_map.append('blue')
        size.append(530 * len(node))

    for i in edges:
        for j in i[2]:
            G.add_edge(i[1], j, weight=6)

    # if verbose:
    #     print("\nNodes in Graph:", list(G.nodes))  # Print nodes in the graph for debugging

    # nx.draw(G, with_labels=True, node_color=colour_map, node_size=size, arrowsize=20, pos=nx.spring_layout(G, k=7))
    # plt.show()

    return G  # Return the graph for BFS

def dfs_find_inputs_with_indices(graph, target_nodes, input_nodes):
    # Her rare target için reverse DFS yapar.
    # graph.predecessors(node) kullanıldığı için normal sinyal yönünün tersine,
    # target'tan onu etkileyebilen primary inputlara doğru ilerlenir.
    # YENİDE: Aynı baseline yaklaşım ReverseDFSInputAnalyzer.analyze() içinde,
    # CircuitGraph + RareTargets -> SelectedInputs sözleşmesiyle çalışır.
    affected_inputs = {}

    # Check if target nodes are in the graph
    missing_nodes = [node for node in target_nodes if node not in graph]
    if missing_nodes:
        print(f"Warning: The following nodes are missing in the graph: {missing_nodes}")
        target_nodes = [node for node in target_nodes if node in graph]  # Only keep existing nodes

    for target in target_nodes:
        # Her target bağımsız gezilir. Aynı input bir target için yalnız bir kez
        # kaydedilsin diye visited ve tekrar kontrolü kullanılır.
        visited = set()
        stack = [target]
        affected_inputs[target] = []

        while stack:
            node = stack.pop()
            if node in input_nodes:  # if we reach an input node, it affects the target
                if node not in [inp[0] for inp in affected_inputs[target]]:
                    index = input_nodes.index(node)
                    affected_inputs[target].append((node, index))
            visited.add(node)

            # Traverse neighbors in the reverse direction (predecessors)
            for neighbor in graph.predecessors(node):
                if neighbor not in visited:
                    stack.append(neighbor)

    return affected_inputs
def myfunc(rare_int_node,file_name):
    # Özgün SHIELD ana akışının çağırdığı sarmalayıcı fonksiyon.
    # Rare net listesini alır; BENCH'i okur, graph'ı oluşturur, reverse DFS
    # çalıştırır ve inputların kaç rare neti etkilediğini sayar.
    # YENİDE: Bu orkestrasyon src/shield/experiment.py içindedir. Input Analysis
    # BENCH yolu almaz; hazır CircuitGraph ve RareTargets alır.
    # Run the DFS-based code
    in_n, out_n, nodes, edges = parser(file_name, verbose=0)
    G = grapher(in_n, out_n, nodes, edges, verbose=1)  # Enable verbose to see graph nodes

    # Example intermediate nodes

   #intermediate_nodes =  [348, 349, 350, 392, 400, 401, 402, 424, 427, 432, 437, 442, 446, 448, 449, 451, 475, 476, 477, 478, 479, 480, 481, 482, 488, 489, 490, 491, 502, 503, 504, 505, 506, 507, 508, 509, 511, 513, 515, 517, 522, 523, 524, 525, 526, 527, 528, 529]
    intermediate_nodes = rare_int_node
    rare_net = [str(i) for i in intermediate_nodes]
    # print("**rare_net: ", rare_net)
    # print("**: ", dfs_find_inputs_with_indices(G, rare_net, in_n))
    data = dfs_find_inputs_with_indices(G, rare_net, in_n)
    column_2 = [item[1] for sublist in data.values() for item in sublist]

    # Count occurrences of indices
    counter = Counter(column_2)
    # Örnek anlam: input index 0 değeri 48 ise bu input 48 rare target'ın
    # geriye doğru fan-in bölgesinde görülmüştür.

    # Threshold for count filtering
    threshold = 1
    # count > 1 filtresi uygulanır. Yeni modüler koddaki karşılığı
    # minimum_target_impact=2 ayarıdır.
    # print("****counter: ", counter)

    # Filter data based on the threshold
    data = {k: v for k, v in counter.items() if v > threshold}
    filtered_data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))
    # Önce importance değerine göre sıralansa da aşağıda tekrar index anahtarına
    # göre sıralanır. Bu nedenle dönen dict'in sırası önem sırası değildir;
    # değerler yine de etki sayısını taşır.

    # for index, node in enumerate(in_n):
    #     if index not in filtered_data:
    #         filtered_data[index] = 0

    # Sort the filtered_data by keys for a cleaner display
    filtered_data = dict(sorted(filtered_data.items()))

    print("filtered_data = ",filtered_data)

    # Display the result
    data = list(filtered_data.keys())
    data.sort()
    # print("&&data: ", data)

    # unique_list = list(set(column_2))
    # print(unique_list)
    return filtered_data
