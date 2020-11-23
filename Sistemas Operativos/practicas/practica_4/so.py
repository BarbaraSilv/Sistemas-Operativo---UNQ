from hardware import *
import log
import heapq

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
####

class Dispatcher():

    def __init__(self):
        pass

    def save(self, pcb):
        pcb.setPc(HARDWARE.cpu.pc)
        HARDWARE.cpu.pc = -1
        log.logger.info("Dispatcher save {pId}".format(pId=pcb.pid))
    def load(self, pcb):
        HARDWARE.cpu.pc = pcb.pc
        HARDWARE.mmu.baseDir = pcb.baseDir
        log.logger.info("Dispatcher load {pId}".format(pId=pcb.pid))
###
class Loader():

    def __init__(self):
        self._nextProgram = 0

    def load(self, pcb, program):
        pcb.setBaseDir(self._nextProgram)
        for i in  program.instructions:
            HARDWARE.memory.write(self._nextProgram, i)
            self._nextProgram = self._nextProgram + 1
        log.logger.info(HARDWARE.memory)


###


##
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
        return "IoDeviceController for {deviceID} running: {currentPCB} waiting: {waiting_queue}".format(deviceID=self._device.deviceId, currentPCB=self._currentPCB , waiting_queue=self._waiting_queue)


## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))

    def runnningNext(self):
        if not self.kernel.scheduler.isEmptyRQ():
            nextPCB = self.kernel.scheduler.getNext()
            log.logger.info(nextPCB.pid)
            self.correrPrograma(nextPCB)

    def agregarAReady(self,pcb):
        pcb.changeStateTo(State.Ready)
        self.kernel.scheduler.add(pcb)

    def correrPrograma(self,pcb):
        pcb.changeStateTo(State.Running)
        self.kernel.pcbTable.setRunningPCB(pcb)
        self.kernel.dispatcher.load(pcb)

    def runOrReady(self,pcb):
        PCBRun = self.kernel.pcbTable.runningPCB
        if not self.kernel.pcbTable.hasRunning():
            pcb.changeStateTo(State.Running)
            self.kernel.pcbTable.setRunningPCB(pcb)
            self.kernel.dispatcher.load(pcb)
        elif self.kernel.scheduler.mustExpropiate(pcb, PCBRun):
            #eXPROPIA
            self.kernel.dispatcher.save()
            self.agregarAReady(PCBRun)
            self.correrPrograma(pcb)
        else:
            self.agregarAReady(pcb)

class TimeoutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        timeOut =  self.kernel.pcbTable.running
        self.kernel.dispatcher.save(timeOut)
        self.kernel.scheduler.add(timeOut)
        timeOut.changeStateTo(State.Ready)
        self.kernel.dispatcher.load(self.kernel.scheduler.getNext())

class NewInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        dictNewParam = irq.parameters
        priority = dictNewParam['priority']
        program = dictNewParam['program']
        pcb = self.kernel.pcbTable.newAndAdd(program.name,priority)
        self.kernel.loader.load(pcb, program)
        self.runOrReady(pcb)


class KillInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        killPCB = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(killPCB)
        killPCB.changeStateTo(State.Terminated)
        self.kernel.pcbTable.setRunningPCB(None)
        log.logger.info(" Program Finished ")
        self.runnningNext()


class IoInInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
            running = self.kernel.pcbTable.runningPCB
            self.kernel.dispatcher.save(running)
            running.changeStateTo(State.Waiting)
            self.kernel.pcbTable.setRunningPCB(None)
            self.kernel.ioDeviceController.runOperation(running, irq)
            self.runnningNext()


class IoOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        pcb = self.kernel.ioDeviceController.getFinishedPCB()
        log.logger.info(self.kernel.ioDeviceController)
        self.runOrReady(pcb)



class PCB():
    def __init__(self,path,prioridad):
        self._pid = 0
        self._baseDir = 0
        self._pc = 0
        self._state = State.New
        self._path = path
        self._prioridad = prioridad

    @property
    def path(self):
        return self._path
    @property
    def pid(self):
        return self._pid

    # @pid.setter
    def setPid(self, pid):
        self._pid = pid

    @property
    def baseDir(self):
        return self._baseDir

    # @baseDir.setter
    def setBaseDir(self, baseDir):
        self._baseDir = baseDir

    @property
    def pc(self):
        return self._pc

    # @pc.setter
    def setPc(self, pc):
        self._pc = pc

    @property
    def state(self):
        return self._state

    # @state.setter tiraba error en el NEW
    def changeStateTo(self, state):
        self._state = state
class SchedulerFCFS():

    def __init__(self):
        self._readyQueue = []

    def add(self, pcb):
        self._readyQueue.append(pcb)

    def getNext(self):
        return self._readyQueue.pop(0)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return False


class SchedulerPriorityNExp():

    def __init__(self):
        self._readyQueue = [] #TODO: implementar con Map (claves = prioridades posibles, valores = listas de PCBs ready)
        self._count = 0

    def add(self, pcb):
        pcb.setAge(0)
        heapq.heappush(self._readyQueue, [pcb.getPriority(), self._count, pcb])
        self._count += 1

    def next(self):
        self.ageAllPCB()
        return heapq.heappop(self._readyQueue).pop(2)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return False

    def ageAllPCB(self):
        for list in self._readyQueue:
            list[2].agePCB()


class SchedulerPriorityExp():

    def __init__(self):
        self._readyQueue = [] #TODO: implementar con Map (claves = prioridades posibles, valores = listas de PCBs ready)
        self._count = 0

    def add(self, pcb):
        pcb.setAge(0)
        heapq.heappush(self._readyQueue, [pcb.getPriority(), self._count, pcb])
        self._count += 1

    def next(self):
        self.ageAllPCB()
        return heapq.heappop(self._readyQueue).pop(2)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return pcb1.getPriority() < pcb2.getPriority()

    def ageAllPCB(self):
        for list in self._readyQueue:
            list[2].agePCB()

class SchedulerRoundRobin():

    def __init__(self, quantum):
        self._readyQueue = []
        HARDWARE.timer.quantum = quantum

    def add(self, pcb):
        self._readyQueue.append(pcb)

    def next(self):
        return self._readyQueue.pop(0)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return False



class PCBTable():
    def __init__(self):
        self._PCBTable = dict()
        self._runningPCB = None
        self._PIDCounter = 0

    def get(self, pid):
        return self._PCBTable[pid]

    def newAndAdd(self,path, prioridad):
        pcb = PCB(path, prioridad)
        pcb.setPid(self._PIDCounter)
        self._PCBTable[self._PIDCounter] = pcb
        self.getNewPID()
        return pcb

    def remove(self, pid):
        del self._PCBTable[pid]

    def hasRunning(self):
        return not (self.runningPCB == None)

    @property
    def runningPCB(self):
        return self._runningPCB

    # @runningPCB.setter
    def setRunningPCB(self, pcb):
        self._runningPCB = pcb

    def getNewPID(self):
        self._PIDCounter += 1



# emulates the core of an Operative System
class Kernel():

    def __init__(self,scheduler):
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice)
        # setup so components
        self._scheduler = scheduler
        self._dispatcher = Dispatcher()
        self._loader = Loader()
        self._pcbTable = PCBTable()

        ## setup interruption handlers
        newHandler = NewInterruptionHandler(self)
        HARDWARE.interruptVector.register(NEW_INTERRUPTION_TYPE, newHandler)

        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

        ioInHandler = IoInInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_IN_INTERRUPTION_TYPE, ioInHandler)

        ioOutHandler = IoOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_OUT_INTERRUPTION_TYPE, ioOutHandler)




    @property
    def ioDeviceController(self):
        return self._ioDeviceController

    @property
    def scheduler(self):  # y darle mensajes para conocer esos componentes
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



    def run(self, program, priority):
        dictNewParam = {'program': program, 'priority': priority}
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, dictNewParam)
        HARDWARE.interruptVector.handle(newIRQ)

    def __repr__(self):
        return "Kernel "
#ESTADOS EN CLASES

class State():
    New = "new"
    Running = "running"
    Ready = "ready"
    Waiting = "waiting"
    Terminated = "terminated"