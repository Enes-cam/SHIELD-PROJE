# D-Algebra
# This file contains function for Boolean Operation
# NOT , BUF
# AND , OR
# NAND , NOR
# XOR, XNOR
def NOT(listInputs):
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
  output = listInputs[0]
  for i in range(1, len(listInputs)):
    output = XOR2(output, listInputs[i])
  return output

def NAND(listInputs):
    return NOT(AND(listInputs))

def NOR(listInputs):
    return NOT(OR(listInputs))

def XNOR(listInputs):
  return NOT(XOR(listInputs))

def BUFF(listInputs):
  return listInputs[0]

