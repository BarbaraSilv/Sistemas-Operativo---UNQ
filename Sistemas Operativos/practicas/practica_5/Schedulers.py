
from so import *
import heapq

## PRIORITY EXPROPIATIVO
class SchedulerPriorityExp():

    def __init__(self):
        self._readyQueue = [] #TODO: implementar con Map (claves = prioridades posibles, valores = listas de PCBs ready)
        self._count = 0

    def add(self, pcb):
        pcb.setAge(0)
        heapq.heappush(self._readyQueue, [pcb.priority, self._count, pcb])
        self._count += 1

    def next(self):
        self.ageAllPCB()
        return heapq.heappop(self._readyQueue).pop(2)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return pcb1.priority < pcb2.priority

    def ageAllPCB(self):
        for list in self._readyQueue:
            list[2].agePCB()

##/////////////////////////////////////////////////////////////////////////////////////////////////////////
##FCFS
class SchedulerFCFS():
        ## First Come First Served (Primero en llegar, Primero en ser Servido)
    def __init__(self):
        self._readyQueue = []

    def add(self, pcb):
        self._readyQueue.append(pcb)

    def next(self):
        return self._readyQueue.pop(0)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return False

##/////////////////////////////////////////////////////////////////////////////////////////////////
## PRIORITY NO EXPROPIATIVO
class SchedulerPriorityNoExp():
    def __init__(self):
        self._readyQueue = [] #TODO: implementar con Map (claves = prioridades posibles, valores = listas de PCBs ready)
        self._count = 0

    def add(self, pcb):
        pcb.setAge(0)
        heapq.heappush(self._readyQueue, [pcb.priority, self._count, pcb])
        self._count += 1

    def next(self):
        self.ageAllPCB()
        return heapq.heappop(self._readyQueue).pop(2)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1,pcb2):
        return False

    def ageAllPCB(self):
        for list in self._readyQueue:
            list[2].agePCB()
##///////////////////////////////////////////////////////////////////////////////////////////////



## ROUND ROBIN
class SchedulerRoundRobin():

    def __init__(self, quantum):
        super().__init__()
        HARDWARE.timer.quantum = quantum

    def add(self, pcb):
        self._readyQueue.append(pcb)

    def next(self):
        return self._readyQueue.pop(0)

    def isEmptyRQ(self):
        return len(self._readyQueue) == 0

    def mustExpropiate(self, pcb1, pcb2):
        return False
