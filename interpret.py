import collections
import re
from telnetlib import NOP
import xml.etree.ElementTree as ET
import sys
import os.path as OP
import fileinput

#classy na jednotlive objekty pre informacie ktore patria k sebe
class instruct:
    def __init__(self, OPcode):
        self.OPcode = OPcode
        self.args = []
    def addArgument(self, arg):
        self.args.append(arg)

class arg:
    def __init__(self, type, val):
        self.type = type
        self.val = val
        

class frameVar:
    def __init__(self, holdingValue, holdingType):
        self.holdingType = holdingType
        self.holdingValue = holdingValue

class dataStackVal:
    def __init__(self, holdingValue, holdingType):
        self.holdingType =  holdingType
        self.holdingValue = holdingValue

#nahradenie escape sekvencí za ich hodnotu (použité pri WRITE inštrukci)

def RemoveEscapeSequences(stringik):
    for escapeseq in re.findall(r'\\[0-9]{3}', str(stringik)):
                asc_val = escapeseq.lstrip('\\')
                stringik = stringik.replace(escapeseq, chr(int(asc_val)))
    return stringik

#Funkcie pre kontrolu syntaxe

def SyntaxControlBool(thing):
    if (thing != 'true' and thing != 'false'):
        return False
    else:
        return True

def SyntaxControlInteger(thing):
    if (re.match(r'^[+-]?[0-9]+$', thing)):
        return True
    return False

def SyntaxControlString(thing):
    if (thing == None):
        thing = ""
    if (re.match(r'^.*[\s#]+.*$', thing)):
        return False
    if (re.match(r'^.*[\\]+.*$', thing)):
        if not(re.match(r'^.*\\[0-9]{3}.*$', thing)):
            return False
    return True

def SyntaxControlNil(thing):
    if (thing == 'nil'):
        return True
    return False

def SyntaxControlType(thing):
    if (thing == 'int' or thing == 'bool' or thing == 'string'):
        return True
    return False

def SyntaxControlVar(thing):
    if (re.match(r'^(LF|TF|GF)@[a-zA-Z_\-$&%*!?][a-zA-Z0-9_\-$&%*!?]*$', thing)):
        return True
    return False
def SyntaxControlLabel(thing):
    if (re.match(r'^[a-zA-Z\-_$&%*!?][a-zA-Z\-_$&%*!?0-9]*$', thing)):
        return True
    return False

def SyntaxControlSymbol(type, text):
    if (type == 'string'):
        if not(SyntaxControlString(text)):
            sys.exit(32)
    elif (type == 'bool'):
        if not(SyntaxControlBool(text)):
            sys.exit(32)
    elif (type == 'int'):
        if not(SyntaxControlInteger(text)):
            sys.exit(32)
    elif (type == 'nil'):
        if not(SyntaxControlNil(text)):
            sys.exit(32)
    elif (type == 'var'):
        if not(SyntaxControlVar(text)):
            sys.exit(32)
    else:
        sys.exit(32)  # ak to nieje podporovany typ tak chyba
    return True


#OPCODE ⟨var⟩ ⟨symb⟩
ArgsVarSymb = ['MOVE', 'INT2CHAR', 'STRLEN', 'TYPE', 'NOT']
#OPCODE ⟨var⟩
ArgsVar = ['DEFVAR', 'POPS']
#OPCODE
Args0 = ['CREATEFRAME', 'PUSHFRAME', 'POPFRAME', 'RETURN', 'BREAK']
#OPCODE <LABEL>
ArgsLabel = ['CALL', 'LABEL', 'JUMP']
#OPCODE <symb> 
ArgsSymbol = ['WRITE', 'EXIT', 'DPRINT', 'PUSHS']
#OPCODE <var> <symb> <symb>
ArgsVarSymbSymb =['ADD', 'SUB', 'MUL', 'IDIV','LT', 'GT', 'EQ', 'AND', 'OR', 'STRI2INT', 'CONCAT', 'GETCHAR', 'SETCHAR']
#OPcode ⟨var⟩ ⟨type⟩
ArgsVarType = ['READ']
#OPCODE <label> <symb> <symb>   
ArgsLabelSymbSymb = ['JUMPIFEQ', 'JUMPIFNEQ']

ArgumentOptions = ['string', 'bool', 'int', 'nil', 'var', 'type', 'label']

###  Argument parsing

sourcePath=""
inputPath=""
sourcePathSet=False
inputPathSet=False

if (len(sys.argv) < 2) or (len(sys.argv) > 3):
    print("Nesprávne parametre\n", file=sys.stderr)
    sys.exit(10)

if (sys.argv[1] == "--help"):
    if (len(sys.argv) > 2):
        print("--help parameter nesmie byť kombinovaný s ďalšími parametrami", file=sys.stderr)
        sys.exit(10)

    print("Program interpretuje kód v jazyku IPPCODE22 zapísaný v XML\n")
    print("Použitie:\n")
    print("python3.8 interpret.py [--help] [--source=<cesta k .src>] [--input=<cesta k inputu>]\n")
    print("--help -parameter môže byť použitý len osamote\n")
    print("aspoň jeden z parametrov --source alebo --input musí byť zadaný a chýbajúci bude čítaný z stdin\n")
    print("prípadný výstup na stdout\n")
    sys.exit(0)
elif sys.argv[1][:9] == "--source=":
    sourcePath=sys.argv[1][9:]
    sourcePathSet=True
elif sys.argv[1][:8] == "--input=":
    inputPath=sys.argv[1][8:]
    inputPathSet=True
else: 
    print("Nesprávne parametre\n", file=sys.stderr)
    sys.exit(10)

if (len(sys.argv) == 3):
    if (sys.argv[2] == "--help"):
        print("--help parameter nesmie byť kombinovaný s ďalšími parametrami", file=sys.stderr)
        sys.exit(10)
    elif sys.argv[2][:9] == "--source=":
        if sourcePathSet:
            print("Nesprávne parametre\n", file=sys.stderr)
            sys.exit(10)
        sourcePath=sys.argv[1][9:]
    elif sys.argv[2][:8] == "--input=":
        if inputPathSet:
            print("Nesprávne parametre\n", file=sys.stderr)
            sys.exit(10)
        inputPath=sys.argv[2][8:]
    else: 
        print("Nesprávne parametry\n", file=sys.stderr)
        sys.exit(10)
else:
    if sourcePathSet:
        inputPath=sys.stdin
    else:
        sourcePath=sys.stdin

file = None
if inputPath is not sys.stdin:
    try:
        file = open(inputPath, "r")
    except:
        print("Nepodarilo sa otvoriť input file!\n", file=sys.stderr)
        sys.exit(11)

###  načítanie XML
try:
    tree = ET.parse(sourcePath)
except IOError:
    print("Nepodarilo sa otvoriť XML\n", file=sys.stderr)
    sys.exit(11)
except ET.ParseError:
    print("Nevalidný XML formát\n", file=sys.stderr)
    sys.exit(31)

try:
    rootXML = tree.getroot()
except:
    sys.exit(32)


#XML základná kontrola
if rootXML.tag != 'program':
    exit(32)
if rootXML.get('language') != None:
    if rootXML.attrib["language"].upper() != "IPPCODE22":
        print("Nesprávny language tag\n", file=sys.stderr)
        sys.exit(32)
else:
    print("Chýbajúci language tag\n", file=sys.stderr)
    sys.exit(32)
InstructionDict = collections.OrderedDict()
UsedOrders = [] #Pole pre použité čísla poradia inštrukcí (zistenie duplikácí)

# kompletná syntaktická kontrola, či sú správne typy argumentov a či majú v sebe správne hodnoty, správny počet argumentov
for instruction in rootXML:
    if instruction.tag.upper() != 'INSTRUCTION':
        exit(32)  
    instructKeys = list(instruction.attrib.keys())
    if(len(instructKeys) != 2):
        exit(32)
    if not('order' in instructKeys) or not('opcode' in instructKeys):
        exit(32)
    if not(re.match("[123456789][0123456789]*", instruction.attrib['order'])):
        exit(32)
    if(int(instruction.attrib['order']) in UsedOrders):
        exit(32)
    UsedOrders.append(int(instruction.attrib['order']))
    order = int(instruction.attrib['order'])
    OPcode =instruction.attrib['opcode'].upper()

    if not(OPcode in ArgsVarSymb or OPcode in ArgsVar or OPcode in Args0 or OPcode in ArgsLabel or OPcode in ArgsSymbol or OPcode in ArgsVarSymbSymb or OPcode in ArgsVarType or OPcode in ArgsLabelSymbSymb):
        sys.exit(32)
    
    if (OPcode in ArgsVarSymb):
        if (len(instruction) != 2):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
        arg1set = False
        arg2set = False
        arg1toadd = None
        arg2toadd = None
        for atribute in instruction:
            if not (re.match(r'^arg[12]$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
            if (atribute.tag == 'arg1'):
                if (arg1set):
                    sys.exit(32)
                arg1set = True
                if not(atribute.attrib['type'] == 'var'):
                    sys.exit(32)
                if not(SyntaxControlVar(atribute.text)):
                    sys.exit(32)
                arg1toadd = arg(atribute.attrib['type'], atribute.text)
            elif (atribute.tag == 'arg2'):
                if (arg2set):
                    sys.exit(32)
                arg2set = True
                if not(atribute.attrib['type'] in ArgumentOptions):
                    sys.exit(32)
                if not(SyntaxControlSymbol(atribute.attrib['type'],atribute.text)):
                    sys.exit(32)
                arg2toadd = arg(atribute.attrib['type'], atribute.text)
            else:
                sys.exit(32)
        
        InstructionDict[order].addArgument(arg1toadd)
        InstructionDict[order].addArgument(arg2toadd)
    
    elif (OPcode in ArgsVar):
        if (len(instruction) != 1):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)

        for atribute in instruction:
            if not (re.match(r'^arg1$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
           
            if not(atribute.attrib['type'] == 'var'):
                sys.exit(32)
            if not(SyntaxControlVar(atribute.text)):
                sys.exit(32)
            
            InstructionDict[order].addArgument(arg(atribute.attrib['type'], atribute.text))
    elif (OPcode in Args0):
        if (len(instruction) != 0):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
    
    elif (OPcode in ArgsLabel):
        if (len(instruction) != 1):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
        for atribute in instruction:
            if not (re.match(r'^arg1$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
            if not(atribute.attrib['type'] == 'label'):
                exit(32)
            if not(SyntaxControlLabel(atribute.text)):
                exit(32)
            InstructionDict[order].addArgument(arg(atribute.attrib['type'], atribute.text))
    
    elif (OPcode in ArgsSymbol):
        if (len(instruction) != 1):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
        for atribute in instruction:
            if not (re.match(r'^arg1$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
            if not(SyntaxControlSymbol(atribute.attrib['type'],atribute.text)):
                exit(32)
            InstructionDict[order].addArgument(arg(atribute.attrib['type'], atribute.text))
    
    elif (OPcode in ArgsVarSymbSymb):
        if (len(instruction) != 3):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
        arg1set = False
        arg2set = False
        arg3set = False
        arg1toadd = None
        arg2toadd = None
        arg3toadd = None
        for atribute in instruction:
            if not (re.match(r'^arg[123]$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
            if (atribute.tag == 'arg1'):
                if (arg1set):
                    sys.exit(32)
                arg1set = True
                if not(atribute.attrib['type'] == 'var'):
                    sys.exit(32)
                if not(SyntaxControlVar(atribute.text)):
                    sys.exit(32)
                arg1toadd = arg(atribute.attrib['type'], atribute.text)
            elif (atribute.tag == 'arg2'):
                if (arg2set):
                    sys.exit(32)
                arg2set = True
                if not(atribute.attrib['type'] in ArgumentOptions):
                    sys.exit(32)
                if not(SyntaxControlSymbol(atribute.attrib['type'],atribute.text)):
                    sys.exit(32)
                arg2toadd = arg(atribute.attrib['type'], atribute.text)
            elif (atribute.tag == 'arg3'):
                if (arg3set):
                    sys.exit(32)
                arg3set = True
                if not(atribute.attrib['type'] in ArgumentOptions):
                    sys.exit(32)
                if not(SyntaxControlSymbol(atribute.attrib['type'],atribute.text)):
                    sys.exit(32)
                arg3toadd = arg(atribute.attrib['type'], atribute.text)
            else:
                sys.exit(32)
        
        InstructionDict[order].addArgument(arg1toadd)
        InstructionDict[order].addArgument(arg2toadd)
        InstructionDict[order].addArgument(arg3toadd)
    
    elif (OPcode in ArgsVarType):
        if (not(len(instruction) == 2)):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
        arg1set = False
        arg2set = False
        arg1toadd = None
        arg2toadd = None
        for atribute in instruction:
            if not (re.match(r'^arg[12]$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
            if (atribute.tag == 'arg1'):
                if (arg1set):
                    sys.exit(32)
                arg1set = True
                if not(atribute.attrib['type'] == 'var'):
                    sys.exit(32)
                if not(SyntaxControlVar(atribute.text)):
                    sys.exit(32)
                arg1toadd = arg(atribute.attrib['type'], atribute.text)
            elif (atribute.tag == 'arg2'):
                if (arg2set):
                    sys.exit(32)
                arg2set = True
                if not(atribute.attrib['type'] == 'type'):
                    sys.exit(32)
                if not(SyntaxControlType(atribute.text)):
                    sys.exit(32)
                arg2toadd = arg(atribute.attrib['type'], atribute.text)
            else:
                sys.exit(32)
        
        InstructionDict[order].addArgument(arg1toadd)
        InstructionDict[order].addArgument(arg2toadd)
        
    elif (OPcode in ArgsLabelSymbSymb):
        if (len(instruction) != 3):
            sys.exit(32)
        InstructionDict[order] = instruct(OPcode)
        arg1set = False
        arg2set = False
        arg3set = False
        arg1toadd = None
        arg2toadd = None
        arg3toadd = None
        for atribute in instruction:
            if not (re.match(r'^arg[123]$', atribute.tag)):
                sys.exit(32)
            if not('type' in atribute.attrib.keys()):
                sys.exit(32)
            if (atribute.tag == 'arg1'):
                if (arg1set):
                    sys.exit(32)
                arg1set = True
                if not(atribute.attrib['type'] == 'label'):
                    sys.exit(32)
                if not(SyntaxControlLabel(atribute.text)):
                    sys.exit(32)
                arg1toadd = arg(atribute.attrib['type'], atribute.text)
            elif (atribute.tag == 'arg2'):
                if (arg2set):
                    sys.exit(32)
                arg2set = True
                if not(atribute.attrib['type'] in ArgumentOptions):
                    sys.exit(32)
                if not(SyntaxControlSymbol(atribute.attrib['type'],atribute.text)):
                    sys.exit(32)
                arg2toadd = arg(atribute.attrib['type'], atribute.text)
            elif (atribute.tag == 'arg3'):
                if (arg3set):
                    sys.exit(32)
                arg3set = True
                if not(atribute.attrib['type'] in ArgumentOptions):
                    sys.exit(32)
                if not(SyntaxControlSymbol(atribute.attrib['type'],atribute.text)):
                    sys.exit(32)
                arg3toadd = arg(atribute.attrib['type'], atribute.text)
            else:
                sys.exit(32)
        
        InstructionDict[order].addArgument(arg1toadd)
        InstructionDict[order].addArgument(arg2toadd)
        InstructionDict[order].addArgument(arg3toadd)
#zoradenie inštrukcí
UsedOrders.sort()
#vytváranie slovníkov pre a polí pre interpretáciu
frames = {}
frames["GF"] = {}
frames["LF"] = None
frames["TF"] = None
framesStack = []
Labels = collections.OrderedDict()   #nazovLabelu : OrderInstrukcie na ktory skocit
callStack = []
dataStack = []
currInstructionNum = 0

#najprv prejdeme a len naplníme Label dictionary aby skákajúce inštrukcie vedeli skákat aj na naveštia pred nimi samími
labelsSetupCount = 0
while(labelsSetupCount < len(UsedOrders)):
    currInstruction = InstructionDict[UsedOrders[labelsSetupCount]]

    if (currInstruction.OPcode == 'LABEL'):
        labelName = currInstruction.args[0].val
        
        if (labelName in Labels):
            sys.exit(52)

        Labels[labelName] = labelsSetupCount+1
        

    labelsSetupCount+=1

# v tomto cykli interpretujeme postupne všetky inštrukcie

while(currInstructionNum < len(UsedOrders)):
    currInstruction = InstructionDict[UsedOrders[currInstructionNum]]
    
    #vždy podla OP kódu zistíme o akú inštrukciu ide a interpretujeme ju
    if (currInstruction.OPcode == 'MOVE'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        valToMove = None
        dataTypeToMove = None 

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            valToMove = arg2parts[0]
            dataTypeToMove = currInstruction.args[1].type
            
            frames[varFrame][varName].holdingType = dataTypeToMove
            frames[varFrame][varName].holdingValue = valToMove

        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            
            frames[varFrame][varName].holdingType = frames[var2Frame][var2Name].holdingType
            frames[varFrame][varName].holdingValue = frames[var2Frame][var2Name].holdingValue
    
    if (currInstruction.OPcode == 'CREATEFRAME'):
        frames["TF"] = None
        frames["TF"] = {}

    if (currInstruction.OPcode == 'PUSHFRAME'):
        if (frames["TF"] == None):
            sys.exit(55)
        framesStack.append(frames["TF"])
        frames['LF'] = framesStack[-1]
        frames["TF"] = None
   
    if (currInstruction.OPcode == 'POPFRAME'):

        if (frames['LF'] == None or len(framesStack) == 0):
            sys.exit(55)
        frames['TF'] = None
        frames['TF'] = framesStack.pop()
        if (len(framesStack) > 0):
            frames['LF'] = framesStack.pop()
            framesStack.append(frames['LF'])
        else:
            frames['LF'] = None

    if (currInstruction.OPcode == 'DEFVAR'):
        arg1parts = currInstruction.args[0].val.split('@')
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        
        if (varName in frames[varFrame]):
            sys.exit(54)
        
        frames[varFrame][varName] = frameVar(None, None)

    if (currInstruction.OPcode == 'CALL'):
        callStack.append(currInstructionNum+1)

        labelName = currInstruction.args[0].val
        
        if (not(labelName in Labels)):
            sys.exit(52) #skok na neexistujuci label

        currInstructionNum = Labels[labelName]
        
        continue

    if (currInstruction.OPcode == 'RETURN'):
        if (len(callStack) == 0):
            sys.exit(56) # volam RETURN nad prazdnym zasobnikom chyba

        currInstructionNum = callStack.pop()
        continue
    
    if (currInstruction.OPcode == 'PUSHS'):
        arg1parts = currInstruction.args[0].val.split('@')
        
        if (len(arg1parts) == 1):   #hard value
            val = arg1parts[0]
            dataType = currInstruction.args[0].type      
            dataStack.append(dataStackVal(val, dataType))
           

        elif (len(arg2parts) == 2): #premenna
            varFrame = arg1parts[0]
            varName = arg1parts[1]
            
            if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (varFrame == 'TF'):
                 if (frames['TF'] == None):
                    sys.exit(55)
            
            if (not(varName in frames[varFrame])):
                sys.exit(54)
            
            varHoldVal = frames[varFrame][varName].holdingValue
            varHoldType = frames[varFrame][varName].holdingType           
            dataStack.append(dataStackVal(varHoldVal, varHoldType))
            
    if (currInstruction.OPcode == 'POPS'):
        if (len(dataStack) == 0):
            sys.exit(56) #prazdny datastack, nema sa aka hodnota pridat do premennej
        
        arg1parts = currInstruction.args[0].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        topStack = dataStack.pop()

        frames[varFrame][varName].holdingValue = topStack.holdingValue
        frames[varFrame][varName].holdingType = topStack.holdingType
       

    #ADD ⟨var⟩ ⟨symb1⟩ ⟨symb2⟩ 
    if (currInstruction.OPcode == 'ADD'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'int')):
                    sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'int')):
                sys.exit(53)
            val1 = int(frames[var2Frame][var2Name].holdingValue)


          
        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
           
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'int')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
           
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'int')):
                sys.exit(53)
            val2 = int(frames[var3Frame][var3Name].holdingValue)
            
        addedVal = val1 + val2
        frames[varFrame][varName].holdingType = 'int'
        frames[varFrame][varName].holdingValue = addedVal

     #SUB ⟨var⟩ ⟨symb1⟩ ⟨symb2⟩ 
    if (currInstruction.OPcode == 'SUB'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'int')):
                    sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'int')):
                sys.exit(53)
            val1 = int(frames[var2Frame][var2Name].holdingValue)



        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'int')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
               
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'int')):
                sys.exit(53)
            val2 = int(frames[var3Frame][var3Name].holdingValue)

        subbedVal = val1 - val2
        frames[varFrame][varName].holdingType = 'int'
        frames[varFrame][varName].holdingValue = subbedVal

    #MUL ⟨var⟩ ⟨symb1⟩ ⟨symb2⟩ 
    if (currInstruction.OPcode == 'MUL'):        
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
            if (frames['LF'] == None):
                sys.exit(55)     
        elif (varFrame == 'GF'):
            if (frames['GF'] == None):
                sys.exit(55)
        if (varFrame == 'TF'):
            if (frames['TF'] == None):
                sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'int')):
                sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'int')):
                sys.exit(53)
            val1 = int(frames[var2Frame][var2Name].holdingValue)



        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'int')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'int')):
                sys.exit(53)
            val2 = int(frames[var3Frame][var3Name].holdingValue)

        mulVal = val1 * val2
        frames[varFrame][varName].holdingType = 'int'
        frames[varFrame][varName].holdingValue = mulVal
    
    #IDIV ⟨var⟩ ⟨symb1⟩ ⟨symb2⟩ 
    if (currInstruction.OPcode == 'IDIV'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
            if (frames['LF'] == None):
                sys.exit(55)     
        elif (varFrame == 'GF'):
            if (frames['GF'] == None):
                sys.exit(55)
        if (varFrame == 'TF'):
            if (frames['TF'] == None):
                sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'int')):
                sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'int')):
                sys.exit(53)
            val1 = int(frames[var2Frame][var2Name].holdingValue)



        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'int')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'int')):
                sys.exit(53)
            val2 = int(frames[var3Frame][var3Name].holdingValue)

        if (val2 == 0):
            sys.exit(57)
        divVal = val1 // val2
        frames[varFrame][varName].holdingType = 'int'
        frames[varFrame][varName].holdingValue = divVal

    if (currInstruction.OPcode == 'LT' or currInstruction.OPcode == 'GT' or currInstruction.OPcode == 'EQ'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
            if (frames['LF'] == None):
                sys.exit(55)     
        elif (varFrame == 'GF'):
            if (frames['GF'] == None):
                sys.exit(55)
        if (varFrame == 'TF'):
            if (frames['TF'] == None):
                sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            val1 = int(frames[var2Frame][var2Name].holdingValue)



        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
            dataType2 = currInstruction.args[2].type
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)

            dataType2 = frames[var3Frame][var3Name].holdingType
            val2 = int(frames[var3Frame][var3Name].holdingValue)
        if (dataType1 == 'int' and dataType2 == 'int'):
            if (currInstruction.OPcode == 'LT'):
                if(val1 < val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'GT'):
                if(val1 > val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'EQ'):
                if(val1 == val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'

        elif (dataType1 == 'bool' and dataType2 == 'bool'):
            if (currInstruction.OPcode == 'LT'):
                if(val1 == 'false' and val2 == 'true'):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'GT'):
                if(val1 == 'true' and val2 == 'false'):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'EQ'):
                if(val1 == val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
        elif (dataType1 == 'string' and dataType2 == 'string'):
            if (currInstruction.OPcode == 'LT'):
                if(val1 < val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'GT'):
                if(val1 > val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'EQ'):
                if(val1 == val2):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
        elif (dataType1 == 'nil' or dataType2 == 'nil'):
            if(currInstruction.OPcode == 'EQ'):
                if (dataType1 == 'nil' and dataType2 == 'nil'):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            else:
                sys.exit(53)
        else:
            sys.exit(53)


    if (currInstruction.OPcode == 'AND' or currInstruction.OPcode == 'OR'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
            if (frames['LF'] == None):
                sys.exit(55)     
        elif (varFrame == 'GF'):
            if (frames['GF'] == None):
                sys.exit(55)
        if (varFrame == 'TF'):
            if (frames['TF'] == None):
                sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            val1 = int(frames[var2Frame][var2Name].holdingValue)



        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
            dataType2 = currInstruction.args[2].type
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)

            dataType2 = frames[var3Frame][var3Name].holdingType
            val2 = int(frames[var3Frame][var3Name].holdingValue)
        if (dataType1 == 'bool' and dataType2 == 'bool'):
            if (currInstruction.OPcode == 'AND'):
                if(val1 == 'true' and val2 == 'true'):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
            elif(currInstruction.OPcode == 'OR'):
                if(val1 == 'true' or val2 == 'true'):
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'true'
                else:
                    frames[varFrame][varName].holdingType = 'bool'
                    frames[varFrame][varName].holdingValue = 'false'
        else:
            sys.exit(53)
    
    if (currInstruction.OPcode == 'NOT'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        
        if (varFrame == 'LF'):
            if (frames['LF'] == None):
                sys.exit(55)     
        elif (varFrame == 'GF'):
            if (frames['GF'] == None):
                sys.exit(55)
        if (varFrame == 'TF'):
            if (frames['TF'] == None):
                sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = int(arg2parts[0])
            dataType1 = currInstruction.args[1].type
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            val1 = int(frames[var2Frame][var2Name].holdingValue)

        if (dataType1 == 'bool'):
            
            if(val1 == 'true'):
                frames[varFrame][varName].holdingType = 'bool'
                frames[varFrame][varName].holdingValue = 'false'
            else:
                frames[varFrame][varName].holdingType = 'bool'
                frames[varFrame][varName].holdingValue = 'true'
        else:
            sys.exit(53)

    if (currInstruction.OPcode == 'INT2CHAR'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val = arg2parts[0]
            dataType = currInstruction.args[1].type
            #ak to nie je int tak 58?
            if(not(dataType == 'int')):
                sys.exit(58)

            frames[varFrame][varName].holdingType = 'string'
            try:
                frames[varFrame][varName].holdingValue = chr(int(val))
            except:
                sys.exit(58) #nepodarilo sa previest cez chr(), pravdepodobne zlý range

        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            val = frames[var2Frame][var2Name].holdingValue
            dataType = frames[var2Frame][var2Name].holdingType
            #ak to nie je int tak 58?
            if(not(dataType == 'int')):
                sys.exit(58)
        
            frames[varFrame][varName].holdingType = 'string'
            try:
                frames[varFrame][varName].holdingValue = chr(int(val))
            except:
                sys.exit(58) #nepodarilo sa previest cez chr(), pravdepodobne zlý range

    if (currInstruction.OPcode == 'STRI2INT'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = arg2parts[0]
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'string')):
                    sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'string')):
                sys.exit(53)
            val1 = frames[var2Frame][var2Name].holdingValue


          
        if (len(arg3parts) == 1):   #hard value
            val2 = int(arg3parts[0])
           
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'int')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
           
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'int')):
                sys.exit(53)
            val2 = int(frames[var3Frame][var3Name].holdingValue)
            
        if (not(val2 >= 0 and val2 < len(val1))):
            sys.exit(58)

        frames[varFrame][varName].holdingType = 'int'
        try:
            frames[varFrame][varName].holdingValue = ord(val1[val2])
        except:
            sys.exit(58)

    if (currInstruction.OPcode == 'READ'):
        arg1parts = currInstruction.args[0].val.split('@')
        ReadType =  currInstruction.args[1].val
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)
        try:
            
            if inputPath is not sys.stdin:
                readText = file.readline()
            else:
                readText = input()
                
            if (readText[-1] == '\n'): #ak sa pridala nova lina na koniec tak ju odstranime
                readText = readText[:-1]
        except:
            ReadType = 'nil'
        
        if (ReadType == 'nil' or readText == None):
            readText = 'nil'
        elif (ReadType == 'bool'):
            if(readText.upper() == 'TRUE'):
                readText = 'true'
            else:
                readText = 'false'
        elif (ReadType == 'int'):
            try:
                intik = int(readText)
            except:
                readText = 'nil'
                ReadType = 'nil'
        #elif (ReadType == 'string'):
            #v stringu asi môže byť všetko, mal som tu kontrolu na syntax stringu ale discord testy pravia ze medzeri mozu byt v stringu z readu tak asi netreba
            #if not(SyntaxControlString(readText)):
                #here
                #readText = 'nil'
                #ReadType = 'nil'
        
        frames[varFrame][varName].holdingType = ReadType
        frames[varFrame][varName].holdingValue = readText

    if (currInstruction.OPcode == 'WRITE'):
        arg1parts = currInstruction.args[0].val.split('@')
        
        val1 = None
        dataType1 = None

        if (len(arg1parts) == 1):   #hard value
            val1 = arg1parts[0]
            dataType1 = currInstruction.args[0].type

        elif (len(arg1parts) == 2): #premenna
            varFrame = arg1parts[0]
            varName = arg1parts[1]
            
            if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(varName in frames[varFrame])):
                sys.exit(54)
            
            dataType1 = frames[varFrame][varName].holdingType
            val1 = frames[varFrame][varName].holdingValue
            
        if (dataType1 == 'string'):
            
            print(RemoveEscapeSequences(val1), end = '')
        elif (dataType1 == 'int'):
            print(int(val1), end = '')
        elif (dataType1 == 'bool'):
            print(val1, end = '')
        elif (dataType1 == 'nil'):
            print("", end = '')
        else:
            print("", end = '')

    if (currInstruction.OPcode == 'CONCAT'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = arg2parts[0]
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'string')):
                    sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'string')):
                sys.exit(53)
            val1 = frames[var2Frame][var2Name].holdingValue



        if (len(arg3parts) == 1):   #hard value
            val2 = arg3parts[0]
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'string')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'string')):
                sys.exit(53)
            val2 = frames[var3Frame][var3Name].holdingValue

        concatVal = val1 + val2
        frames[varFrame][varName].holdingType = 'string'
        frames[varFrame][varName].holdingValue = concatVal
    
    if (currInstruction.OPcode == 'STRLEN'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val = None
        dataType = None 

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val = arg2parts[0]
            dataType = currInstruction.args[1].type

        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType = frames[var2Frame][var2Name].holdingType
            val = frames[var2Frame][var2Name].holdingValue
        if (not(dataType == 'string')):
            sys.exit(53)

        frames[varFrame][varName].holdingType = 'int'
        frames[varFrame][varName].holdingValue = len(val) #esc?

    if (currInstruction.OPcode == 'GETCHAR'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val1 = arg2parts[0]
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'string')):
                    sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'string')):
                sys.exit(53)
            val1 = frames[var2Frame][var2Name].holdingValue



        if (len(arg3parts) == 1):   #hard value
            val2 = arg3parts[0]
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'int')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'int')):
                sys.exit(53)
            val2 = frames[var3Frame][var3Name].holdingValue

        if(not(int(val2) >= 0 and int(val2) < len(val1))):
            sys.exit(58)
        
        frames[varFrame][varName].holdingType = 'string'
        frames[varFrame][varName].holdingValue = val1[val2]
    
    if (currInstruction.OPcode == 'SETCHAR'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        if (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (not(frames[varFrame][varName].holdingType == 'string')):
            sys.exit(53)

        if (len(arg2parts) == 1):   #hard value
            val1 = arg2parts[0]
            dataType1 = currInstruction.args[1].type
            if (not(dataType1 == 'int')):
                    sys.exit(53)      
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            if (not(dataType1 == 'int')):
                sys.exit(53)
            val1 = frames[var2Frame][var2Name].holdingValue



        if (len(arg3parts) == 1):   #hard value
            val2 = arg3parts[0]
            dataType2 = currInstruction.args[2].type
            if (not(dataType2 == 'string')):
                sys.exit(53) 
        elif (len(arg3parts) == 2): #premenna
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            if (not(dataType2 == 'string')):
                sys.exit(53)
            val2 = frames[var3Frame][var3Name].holdingValue

        if(not(int(val1) >= 0 and int(val1) < len(frames[varFrame][varName].holdingValue))):
            sys.exit(58)
        
        if(frames[varFrame][varName].holdingValue == ''):
            sys.exit(58)
        if(len(val2)<1):
            sys.exit(58)
        newString = frames[varFrame][varName].holdingValue[:int(val1)] + val2[0] + frames[varFrame][varName].holdingValue[int(val1)+1:]
        frames[varFrame][varName].holdingValue = newString

    if (currInstruction.OPcode == 'TYPE'):
        arg1parts = currInstruction.args[0].val.split('@')
        arg2parts = currInstruction.args[1].val.split('@')
        
        varFrame = arg1parts[0]
        varName = arg1parts[1]
        
        val = None
        dataType = None

        if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
        elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
        elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
        if (not(varName in frames[varFrame])):
            sys.exit(54)

        if (len(arg2parts) == 1):   #hard value
            val = arg2parts[0]
            dataType = currInstruction.args[1].type
            
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (varFrame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType = frames[var2Frame][var2Name].holdingType
            if(dataType == None): #ak neinicializovana premenna tak ma None datatype
                dataType = ''
            val = frames[var2Frame][var2Name].holdingValue
        
       
        frames[varFrame][varName].holdingType = 'string'
        frames[varFrame][varName].holdingValue = dataType

    if (currInstruction.OPcode == 'LABEL'):
       currInstructionNum+=1
       continue
    
    if (currInstruction.OPcode == 'JUMP'):
        navesti = currInstruction.args[0].val
        if(not(navesti in Labels)):
            sys.exit(52)
        navestiNum = Labels[navesti]
        currInstructionNum = navestiNum
        continue

    if (currInstruction.OPcode == 'JUMPIFEQ'):
        navesti = currInstruction.args[0].val
        if(not(navesti in Labels)):
            sys.exit(52)
        navestiNum = Labels[navesti]
        #a teraz kontrola ci sa ma skocit alebo nie
        
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (len(arg2parts) == 1):   #hard value
            val1 = arg2parts[0]
            dataType1 = currInstruction.args[1].type
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            val1 = frames[var2Frame][var2Name].holdingValue

        if (len(arg3parts) == 1):   #hard value
            val2 = arg3parts[0]
            dataType2 = currInstruction.args[2].type
        elif (len(arg3parts) == 2): #premenna
           
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            val2 = frames[var3Frame][var3Name].holdingValue
        
        if(dataType1 == dataType2 or dataType1 == 'nil' or dataType2 == 'nil' or val2 == 'nil' or val1 == 'nil'):
            if(dataType1 == 'int' and dataType2 == 'int'):  #int potrebuje special treatment lebo +21 alebo 21 je to iste napr.
                if(int(val1) == int(val2)):
                    currInstructionNum = navestiNum
                    continue
            elif(val1 == val2):
                currInstructionNum = navestiNum
                continue
        else:
            sys.exit(53)

    if (currInstruction.OPcode == 'JUMPIFNEQ'):
        navesti = currInstruction.args[0].val
        if(not(navesti in Labels)):
            sys.exit(52)
        navestiNum = Labels[navesti]
        #a teraz kontrola ci sa ma skocit alebo nie
        
        arg2parts = currInstruction.args[1].val.split('@')
        arg3parts = currInstruction.args[2].val.split('@')
        
        
        val1 = None
        dataType1 = None
        val2 = None
        dataType2 = None

        if (len(arg2parts) == 1):   #hard value
            val1 = arg2parts[0]
            dataType1 = currInstruction.args[1].type
        elif (len(arg2parts) == 2): #premenna
            var2Frame = arg2parts[0]
            var2Name = arg2parts[1]
            
            if (var2Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var2Frame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (var2Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var2Name in frames[var2Frame])):
                sys.exit(54)
            
            dataType1 = frames[var2Frame][var2Name].holdingType
            val1 = frames[var2Frame][var2Name].holdingValue

        if (len(arg3parts) == 1):   #hard value
            val2 = arg3parts[0]
            dataType2 = currInstruction.args[2].type
        elif (len(arg3parts) == 2): #premenna
           
            var3Frame = arg3parts[0]
            var3Name = arg3parts[1]
            
            if (var3Frame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (var3Frame == 'GF'):
                if (frames['GF'] == None):
                    sys.exit(55)
            elif (var3Frame == 'TF'):
                if (frames['TF'] == None):
                    sys.exit(55)
            if (not(var3Name in frames[var3Frame])):
                sys.exit(54)
            
            dataType2 = frames[var3Frame][var3Name].holdingType
            val2 = frames[var3Frame][var3Name].holdingValue
        
        if(dataType1 == dataType2 or dataType1 == 'nil' or dataType2 == 'nil' or val2 == 'nil' or val1 == 'nil'):
            if(dataType1 == 'int' and dataType2 == 'int'):  #int potrebuje special treatment lebo +21 alebo 21 je to iste napr.
                if(not(int(val1) == int(val2))):
                    currInstructionNum = navestiNum
                    continue
            elif(not(val1 == val2)):
                currInstructionNum = navestiNum
                continue

        else:
            sys.exit(53)

    if (currInstruction.OPcode == 'EXIT'):
        arg1parts = currInstruction.args[0].val.split('@')
        val = None
        dataType = None
        if (len(arg1parts) == 1):   #hard value
            val = arg1parts[0]
            dataType = currInstruction.args[0].type

        elif (len(arg2parts) == 2): #premenna
            varFrame = arg1parts[0]
            varName = arg1parts[1]
            
            if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (varFrame == 'TF'):
                 if (frames['TF'] == None):
                    sys.exit(55)
            
            if (not(varName in frames[varFrame])):
                sys.exit(54)
            
            val = frames[varFrame][varName].holdingValue
            dataType = frames[varFrame][varName].holdingType

        if (dataType == 'int'):
            if(int(val) >= 0 and int(val) <= 49):
                sys.exit(int(val))
            else:
                sys.exit(57)
        else:
            sys.exit(53)
          
    if (currInstruction.OPcode == 'DPRINT'):
        
        arg1parts = currInstruction.args[0].val.split('@')
        val = None
        dataType = None
        if (len(arg1parts) == 1):   #hard value
            val = arg1parts[0]
            dataType = currInstruction.args[0].type

        elif (len(arg2parts) == 2): #premenna
            varFrame = arg1parts[0]
            varName = arg1parts[1]
            
            if (varFrame == 'LF'):
                if (frames['LF'] == None):
                    sys.exit(55)     
            elif (varFrame == 'GF'):
                 if (frames['GF'] == None):
                    sys.exit(55)
            elif (varFrame == 'TF'):
                 if (frames['TF'] == None):
                    sys.exit(55)
            
            if (not(varName in frames[varFrame])):
                sys.exit(54)
            
            val = frames[varFrame][varName].holdingValue
            dataType = frames[varFrame][varName].holdingType
        print(val, file=sys.stderr)

    if (currInstruction.OPcode == 'BREAK'):
        currInstOrder = currInstructionNum+1
        print("Počet vykonaných inštrukí: " + str(currInstOrder), file = sys.stderr)
        print("Pozícia v kóde (order): " + str(UsedOrders[currInstOrder]), file = sys.stderr) #vypíše order tejto práve vykonávanej inštrukcie
    
    currInstructionNum+=1



sys.exit(0)
