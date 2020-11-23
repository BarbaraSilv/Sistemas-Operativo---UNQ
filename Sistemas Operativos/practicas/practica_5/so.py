#!/usr/bin/env python

from hardware import*
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

# emulates the core of an Operative System
class Kernel():

    def __init__(self, scheduler):

        ## setup interruption handlers
        newHandler = NewInterruptionHandler(self)
        HARDWARE.interruptVector.register(NEW_INTERRUPTION_TYPE, newHandler)

        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

        ioInHandler = IoInInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_IN_INTERRUPTION_TYPE, ioInHandler)

        ioOutHandler = IoOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_OUT_INTERRUPTION_TYPE, ioOutHandler)

        timeoutHandler = TimeoutInterruptHandler(self)
        HARDWARE.interruptVector.register(TIMEOUT_INTERRUPTION_TYPE, timeoutHandler)

        ## controls the Hardware's I/O Device
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice)
        self._memoryManager = MemoryManager()
        self._fileSystem= FileSystem()
                    # setup so components
        self._scheduler = scheduler
        self._dispatcher = Dispatcher(self._memoryManager)
        self._loader = Loader(self._memoryManager,self._fileSystem)
        self._pcbTable = PCBTable()

    @property
    def memoryManager(self):
        return self._memoryManager
    @property
    def fileSystem(self):
        return self._fileSystem
    @property
    def ioDeviceController(self):
        return self._ioDeviceController
    @property
    def scheduler(self):
        return self._scheduler
    @property
    def dispatcher(self):
        return self._dispatcher
    @property
    def loader(self):
        return self._loader
    @property
    def pcbTable(self):
        return self._pcbTable



    def load_program(self, program):
        # loads the program fin main memory
        progSize = len(program.instructions)
        for index in range(0, progSize):
            inst = program.instructions[index]
            HARDWARE.memory.write(index, inst)

    ## emulates a "system call" for programs execution
    def run(self, path, priority):
        dictNewParam = {'path': path, 'priority': priority} ## nuevo diccionario con el nombre y prioridad
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, dictNewParam) ## Crea interrupciones (en este caso recibe un new)
        HARDWARE.interruptVector.handle(newIRQ) ## guarda el tipo de interrupción y la interrupción

    def __repr__(self):
        return "Kernel "
###///////////////////////////////////////////////////////////////////////////////////////////////////
###///////////////////////////////////////////////////////////////////////////////////////////////////

class Dispatcher():

    def __init__(self, memoryManager):
        self._memoryManager = memoryManager

    def save(self, pcb):
        pcb.setPc(HARDWARE.cpu.pc)
        HARDWARE.cpu.pc = -1
        log.logger.info("El dispatcher guarda {pid}")

    def load(self, pcb):
        pageTablePCB = self._memoryManager.getPageTable(pcb.pid)
        HARDWARE.cpu.pc = pcb.pc
        HARDWARE.timer.reset()
        HARDWARE.mmu.resetTLB()

        for i in pageTablePCB.getPages():
            HARDWARE.mmu.setPageFrame(i,pageTablePCB.getFrame(i))
        ##Por cada pag toma el marco
    @property
    def memoryManager(self):
        return self._memoryManager


class FileSystem():
##es el componente del sistema operativo encargado de administrar y facilitar el
# uso de las memorias periféricas, ya sean secundarias o terciarias.

    def __init__(self):
        self._dictPathProgram = {}
    def write(self, path, prg):
        self._dictPathProgram[path] = prg
        log.logger.info("{this_path} has a new referenced program".format(this_path=path))
    def read(self, path):
        return self._dictPathProgram[path]
    def availablePaths(self): #extra, para la consola
        return self._dictPathProgram.keys()

class Loader():

    def __init__(self,memoryManeger,fileSystem):
        self._fileSystem = fileSystem
        self._frameSize = HARDWARE.mmu.frameSize
        self._memoryManager = memoryManeger

    def load(self, pcb):
        program = self._fileSystem.read(pcb.path)
        framedInstructions = self.splitInstructions(program.instructions) # lo divide para que entre en el marco

        availableFrames = self._memoryManager.allocFrames(len(framedInstructions)) ## longitud de los marcos libres l
        log.logger.info("The program at {prg_path} is going to use the next frames: {frame_list}".format(prg_path=pcb.path,frame_list=availableFrames ))

        newPageTable = PageTable() # Creamos la PageTable del proceso y lo guarda en memoria

        for n in range(0, len(availableFrames)):
            newPageTable.addPF(n, availableFrames[n])

        self._memoryManager.putPageTable(pcb.pid, newPageTable)
        self.loadPages(framedInstructions, availableFrames)
        log.logger.info(HARDWARE.memory)  ## Tira el cuadro en consola

    def loadPages(self, instructions, listFrames):

        for n in range(0, len(instructions)):
            frameID = listFrames[n]
            self.loadPage(instructions[n], frameID)

    def loadPage(self, pageInstructions, frameID):
        frameBaseDir = frameID * self._frameSize
        for index in range(0, len(pageInstructions)):
            HARDWARE.memory.write(frameBaseDir + index, pageInstructions[index])

    def splitInstructions(self, instructions):
        ##Recibe una lista de instrucciones y las divide pror la cantidad de marcos
        return list(chunks(instructions, self._frameSize))

    # @nextProgram.setter
    def setNextProgram(self, value):
        self._nextProgram = value




## emulates an Input/Output device controller (driver)
class IoDeviceController():

    def __init__(self, device):
        self._device = device
        self._waiting_queue = []
        self._currentPCB = None

    def runOperation(self, pcb, instruction):
        pair = {'pcb': pcb, 'instruction': instruction}
        # append: adds the element at the end of the queue
        self._waiting_queue.append(pair)
        # try to send the instruction to hardware's device (if is idle)
        self.__load_from_waiting_queue_if_apply()

    def getFinishedPCB(self):
        finishedPCB = self._currentPCB
        self._currentPCB = None
        self.__load_from_waiting_queue_if_apply()
        return finishedPCB

    def __load_from_waiting_queue_if_apply(self):
        if (len(self._waiting_queue) > 0) and self._device.is_idle:
            ## pop(): extracts (deletes and return) the first element in queue
            pair = self._waiting_queue.pop(0)
            #print(pair)
            pcb = pair['pcb']
            instruction = pair['instruction']
            self._currentPCB = pcb
            self._device.execute(instruction)

    def __repr__(self):
        return "IoDeviceController for {deviceID} running: {currentPCB} waiting: {waiting_queue}".format(deviceID=self._device.deviceId, currentPCB=self._currentPCB, waiting_queue=self._waiting_queue)


## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))

    def runNextProgram(self):
        #hay algo en lista de espera
        if not self.kernel.scheduler.isEmptyRQ() :
            #obtiene el sig
            nextPCB = self.kernel.scheduler.next()
            self.correrPrograma(nextPCB)

    def agregarAReadyQueue(self,pcb):
        pcb.changeStateTo(Ready())
        self.kernel.scheduler.add(pcb)
        log.logger.info("{prg_name} se ha agregado a la ReadyQueue".format(prg_name=pcb.path))

    def expropiar(self,pcb):
        self.kernel.dispatcher.save(pcb)


    def correrPrograma(self,pcb):
        self.kernel.dispatcher.load(pcb)
        pcb.changeStateTo(Running())
        self.kernel.pcbTable.setRunningPCB(pcb)
        log.logger.info("{prg_name} is now running".format(prg_name=pcb.path))


    def runOrSetReady(self,pcbAgregar):
        pcbRunning = self.kernel.pcbTable.runningPCB
        if self.kernel.pcbTable.runningPCB is None:
            self.correrPrograma(pcbAgregar)
        elif self.kernel.scheduler.mustExpropiate(pcbAgregar,pcbRunning):
             self.expropiar(pcbRunning)
             self.agregarAReadyQueue(pcbRunning)
             self.correrPrograma(pcbAgregar)
        else:
            self.agregarAReadyQueue(pcbAgregar)





class NewInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        dictNewParam = irq.parameters
        priority = dictNewParam['priority']
        path = dictNewParam['path']
        if path in self.kernel.fileSystem.availablePaths():
           self.agregarAlPCB(path,priority)
        else:
            log.logger.info("#  ERROR 002: failed to find a referenced program at    --> {r_path}".format(r_path=path))



    def agregarAlPCB(self,path,priority):

        if (len(self.kernel.fileSystem.read(path).instructions)) > self.kernel.memoryManager.getFreeMemory():
            log.logger.info("#  ERROR 001: not enough memory to load the required program at    --> {this_path}".format(
                this_path=path))
            # error no hay suficiente memoria para cargar
        else:
            newPCB = PCB(path, priority)
            self.kernel.pcbTable.add(newPCB)
            self.kernel.loader.load(newPCB)
            log.logger.info("Program at {prg_name} has been loaded".format(prg_name=path))
            self.runOrSetReady(newPCB)

class KillInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        killPCB = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(killPCB)

        killPCB.changeStateTo(Terminated())

        self.kernel.pcbTable.setRunningPCB(None)

        self.kernel.memoryManager.freePageTable(killPCB.pid)

        log.logger.info("{prg_name} has been handled by ioDevice".format(prg_name=killPCB.path))

        self.runNextProgram()


class IoInInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        operation = irq.parameters
        inPCB = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(inPCB)
        inPCB.changeStateTo(Waiting())
        self.kernel.pcbTable.setRunningPCB(None)
        self.kernel.ioDeviceController.runOperation(inPCB, operation)
        log.logger.info(self.kernel.ioDeviceController)
        log.logger.info("{prg_name} is being handled by ioDevice".format(prg_name=inPCB.path))
        self.runNextProgram()


class IoOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        outPCB = self.kernel.ioDeviceController.getFinishedPCB()
        log.logger.info(self.kernel.ioDeviceController)
        log.logger.info("{prg_name} is being handled by ioDevice".format(prg_name= outPCB.path))
        self.runOrSetReady(outPCB)


class TimeoutInterruptHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        timeoutPCB = self.kernel.pcbTable.runningPCB

        self.kernel.dispatcher.save(timeoutPCB)
        timeoutPCB.changeStateTo(Ready())
        self.kernel.scheduler.add(timeoutPCB)
        log.logger.info("{prg_name} has been timed out and added to ReadyQueue".format(prg_name=timeoutPCB.path))
        self.kernel.pcbTable.setRunningPCB(None)
        log.logger.info("Timer has been resetted")
        self.runNextProgram()

class PageTable:

    def __init__(self):
        self._dictPageFrame = {}

    def addPF(self, page, frame):
        self._dictPageFrame[page] = frame

    def getFrame(self, page):
        return self._dictPageFrame[page]

    def getFrames(self):
        return self._dictPageFrame.values()

    def getPages(self):
        return self._dictPageFrame.keys()

class PCB():
    ##Es un bloque o registro de datos que contiene diversa información relacionada con el proceso: Estado del proceso
    ##Identificador
    ##Registros del CPU
    ##Prioridad
    ##Estado de Entrada/Salida
    def __init__(self,path,priority):
        self._path = path
        self._pid = 0
        self._pc = 0
        self._state = New()
        self._processPriority = priority
        self._age = 0
    @property
    def path(self):
        return self._path
#
    @property
    def priority(self):
        if self._age < 5:
            return self._processPriority
        elif self._age < 10 and self._processPriority > 1:
            return self._processPriority - 1
        elif self._age < 15 and self._processPriority > 2:
            return self._processPriority - 2
        elif self._age < 20 and self._processPriority > 3:
            return self._processPriority - 3
        else:
            return 1
    def setPriority(self, priority):
        self._processPriority = priority

    def getAge(self):
        return self._age

    def setAge(self, value):
        self._age = value

    def agePCB(self):
        if self._state == Running() or self._state == Waiting():
            pass
        else:
            self.setAge(self._age + 1)
            log.logger.info("{prg_name} has been aged to age {prg_age}".format(prg_name=self._path, prg_age=self._age))

    @property
    def pid(self):
       return self._pid
#
    # @pid.setter
    def setPid(self, pid):
        self._pid = pid
#
    @property
    def pc(self):
        return self._pc
#
    # @pc.setter
    def setPc(self, pc):
        self._pc = pc
#
    @property
    def state(self):
        return self._state
#
    # @state.setter tiraba error en el NEW
    def changeStateTo(self, state):
        self._state = state
#

class PCBTable():
    def __init__(self):
        self._PCBTable = dict()
        self._runningPCB = None
        self._PIDCounter = 0

    def get(self, pid):
        return self._PCBTable[pid]

    def add(self, pcb):
        pcb.setPid(self._PIDCounter)
        self._PCBTable[self._PIDCounter] = pcb
        self.getNewPID()

    def remove(self, pid):
        del self._PCBTable[pid]

    @property
    def runningPCB(self):
        return self._runningPCB

    # @runningPCB.setter
    def setRunningPCB(self, pcb):
        self._runningPCB = pcb

    def getNewPID(self):
        self._PIDCounter += 1



class MemoryManager:

    def __init__(self):
        self._frameSize = HARDWARE.mmu.frameSize
        self._freeFrames = []  # todos los frames(marcos) libres
        self._dictPageTables = {}
        self.initFreeFrames()
        log.logger.info("{prg_name} marcos que tengo  ".format(prg_name=(len(self._freeFrames))))

    def initFreeFrames(self):
        ## inicia los marcos libres
         for i in range(0, ((HARDWARE.memory.size // self._frameSize) - 1)):

             self._freeFrames.append(i)

    def allocFrames(self, n):
        ## Una lista de todos los marcos libres
        retf = []
        for i in range(0, n):
            nextFrame = self._freeFrames.pop(0)
            retf.append(nextFrame)
        return retf

    def putPageTable(self, pid, pageTable):
        ## Realiza una pagina
        self._dictPageTables[pid] = pageTable

    def getPageTable(self, pid):
        ## retorna una pagina con el pid indicado en el parametro
        return self._dictPageTables[pid]


    def freePageTable(self, pid):
           # Retorna una nueva lista de frames libres eliminando el que con tiene el pid pasado por parametro
        framesToFree = self._dictPageTables.pop(pid).getFrames() # la lista con los marcos que quedan libres
        for frame in framesToFree:
            self._freeFrames.append(frame)  ## agrega los libres a freeFrames
        log.logger.info("{prg_name} Se elimino memoria {prg_dir}  ".format(prg_name=(len(self._freeFrames)),prg_dir= pid ))
        return True

    def getFreeMemory(self):
        return (len(self._freeFrames)) * self._frameSize

#ESTADOS EN CLASES
class New():
    def __init__(self):
        pass
    def __repr__(self):
        return "New"
class Ready():
    def __init__(self):
        pass
    def __repr__(self):
        return "Ready"
class Waiting():
    def __init__(self):
        pass
    def __repr__(self):
        return "Waiting"
class Running():
    def __init__(self):
        pass
    def __repr__(self):
        return "Running"
class Terminated():
    def __init__(self):
        pass
    def __repr__(self):
        return "Terminated"

    ## FUNCIONES AUXILIARES UNIVERSALES
def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]