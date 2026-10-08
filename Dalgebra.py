# D-Algebra
# This file contains function for Boolean Operation
# NOT , BUF
# AND , OR
# NAND , NOR
# XOR, XNOR

# =============================================================================
# Bu dosya devrenin mantık kapılarını yazılım ortamında taklit eder.
# PSO_DFS.py içindeki circuitSimulation(), bir gate'i hesaplarken burada
# tanımlanan AND/OR/NOT/... fonksiyonlarından uygun olanını çağırır.
#
# Değerler sayı değil string olarak taşınır: '0', '1', 'D' ve "D'".
# D ve D' klasik ATPG'deki hata gösterimleridir. SHIELD'ın mevcut akışında
# çoğunlukla 0 ve 1 kullanılır; fakat eski D-algebra desteği korunmuştur.
#
# YENİ MODÜLER SİSTEMDEKİ KARŞILIĞI
# ---------------------------------
# Bu dosyanın 0/1 mantık kapısı davranışları yeni sistemde şuraya taşındı:
#   src/shield/simulation.py
#     -> _evaluate_gate(gate_type, inputs)
#     -> LogicSimulator.simulate(circuit, vectors)
#
# Eski sistemde çağrı zinciri:
#   PSO_DFS.Parser.circuitSimulation()
#     -> Parser.__operate()
#       -> bu dosyadaki AND/OR/NOT/... fonksiyonları
#
# Yeni sistemde çağrı zinciri:
#   ExperimentRunner
#     -> LogicSimulator.simulate(CircuitIR, TestVectorSet)
#       -> simulation._evaluate_gate(...)
#
# ÖNEMLİ FARK:
# Yeni SHIELD pipeline'ı binary test vektörleriyle çalıştığı için modüler
# LogicSimulator yalnız 0 ve 1 değerlerini destekler. Bu dosyadaki 'D' ve "D'"
# desteği yeni simülatöre taşınmadı. D-algebra kodu silinmedi; legacy/ATPG
# deneyi olarak burada korunuyor fakat mevcut modüler deney akışında çalışmıyor.
# Yani Dalgebra.py yeni modüller tarafından import edilmez.
# =============================================================================

def NOT(listInputs):
  # NOT tek girdiyi tersler. D ile D' de birbirinin tersidir.
  # Yeni binary karşılığı: src/shield/simulation.py::_evaluate_gate("NOT", ...)
  a = listInputs[0]
  if (a == '0'):
    return '1'
  elif (a == '1'):
    return '0'
  elif (a == 'D'):
    return 'D\''
  elif (a == 'D\''):
    return 'D'
  else:
    return 'Invalid Input'

def AND(listInputs):
  # AND için controlling value 0'dır: herhangi bir giriş 0 ise sonuç 0.
  # Yeni binary karşılığı: src/shield/simulation.py::_evaluate_gate("AND", ...)
  if '0' in listInputs:
    return '0'
  elif 'D' in listInputs and 'D\'' in listInputs:
    return '0'
  elif 'D' in listInputs:
    return 'D'
  elif 'D\'' in listInputs:
    return 'D\''
  else:
    return '1'

def OR(listInputs):
  # OR için controlling value 1'dir: herhangi bir giriş 1 ise sonuç 1.
  # Yeni binary karşılığı: src/shield/simulation.py::_evaluate_gate("OR", ...)
  if '1' in listInputs:
    return '1'
  elif 'D' in listInputs and 'D\'' in listInputs:
    return '1'
  elif 'D' in listInputs:
    return 'D'
  elif 'D\'' in listInputs:
    return 'D\''
  else:
    return '0'

def XOR2(a, b):
  # İki girdili XOR. Çok girdili XOR aşağıda bu fonksiyonu tekrar tekrar çağırır.
  if a == b:
    # 1XOR1 0XOR0 DXORD D'XORD'
    return '0'
  elif (a == '0' or b == '0') and (a == '1' or b =='1'):
    # 1XOR0 or 0XOR1
    return '1'
  elif (a == '0' or b == '0'):
    # 0XORD or 0XORD'
    return a if b == '0' else b
  elif (a == '1' or b == '1'):
    # 1XORD or 1XORD'
    return NOT(a) if b == '1' else NOT(b)
  else: # DXORD'
    return '1'

def XOR(listInputs):
  # Girdileri soldan sağa ikişerli XOR'layarak tek sonuç üretir.
  # Yeni binary karşılığı: sum(inputs) % 2 hesabıdır.
  output = listInputs[0]
  for i in range(1, len(listInputs)):
    output = XOR2(output, listInputs[i])
  return output

def NAND(listInputs):
    # NAND = AND sonucunun tersi.
    # Yeni binary karşılığı simulation._evaluate_gate içinde bulunur.
    return NOT(AND(listInputs))

def NOR(listInputs):
    # NOR = OR sonucunun tersi.
    # Yeni binary karşılığı simulation._evaluate_gate içinde bulunur.
    return NOT(OR(listInputs))

def XNOR(listInputs):
  # XNOR = XOR sonucunun tersi.
  # Yeni binary karşılığı simulation._evaluate_gate içinde bulunur.
  return NOT(XOR(listInputs))

def BUFF(listInputs):
  # Buffer giriş değerini değiştirmeden geçirir.
  # Yeni binary karşılığı simulation._evaluate_gate("BUFF", ...)
  return listInputs[0]
