#!/usr/bin/env python

from hardware import *
import log



## emulates a compiled program
class Program():

    def __init__(self, name, instructions):
        self._name = name
        self._instructions = self.expand(instructions)

    @property
    def name(self):
        return self._name

    @property
    def instructions(self):
        return self._instructions

    def addInstr(self, instruction):
        self._instructions.append(instruction)

    def expand(self, instructions):
        expanded = []
        for i in instructions:
            if isinstance(i, list):
                ## is a list of instructions
                expanded.extend(i)
            else:
                ## a single instr (a String)
                expanded.append(i)
            
        ## now test if last instruction is EXIT
        ## if not... add an EXIT as final instruction
        last = expanded[-1]
        if not ASM.isEXIT(last):
            expanded.append(INSTRUCTION_EXIT)

        return expanded

    def __repr__(self):
        return "Program({name}, {instructions})".format(name=self._name, instructions=self._instructions)


## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))



class KillInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        log.logger.info(" Program Finished ")
        # por ahora apagamos el hardware porque estamos ejecutando un solo programa
        if len(self.kernel.readyQueue) == 0:
            HARDWARE.switchOff()
        else:
            self.kernel.clean_memory()
            # resets memory before next program
            self.kernel.executeBatch(self.kernel.readyQueue)
        


# emulates the core of an Operative System
class Kernel():

    def __init__(self):
        ## setup interruption handlers
        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)
        self._readyQueue = []


    def clean_memory(self):
        memSize = len(HARDWARE.memory._cells)
        for i in range(0, memSize):
            HARDWARE.memory.write(i, '')

    def load_program(self, program):
        # loads the program in main memory  
        progSize = len(program.instructions)
        for index in range(0, progSize):
            inst = program.instructions[index]
            HARDWARE.memory.write(index, inst)

    @property
    def readyQueue(self):
        return self._readyQueue
    ## emulates a "system call" for programs execution  
    def setReadyQueue(self,program):
        self._readyQueue = program
    def run(self, program):
        self.load_program(program)
        log.logger.info("\n Executing program: {name}".format(name=program.name))
        log.logger.info(HARDWARE)
        self._procesoCorriendo = program
        # set CPU program counter at program's first intruction
        HARDWARE.cpu.pc = 0

    def executeBatch(self,batch):
     #falta agregar el encargado de ejecutar la lista de procesos 
        self.run(batch[0])
        self.setReadyQueue(batch[1:])


    def __repr__(self):
        return "Kernel "
