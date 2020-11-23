
from Schedulers import *
from so import *
import log


##
##  MAIN 
##
if __name__ == '__main__':
    log.setupLogger()
    log.logger.info('Starting emulator')

    ## setup our hardware and set memory size to 25 "cells"
    HARDWARE.setup(25,4)

    ## Switch on computer
    HARDWARE.switchOn()

    ## new create the Operative System Kernel
    # "booteamos" el sistema operativo
    print("Ingresa Scheduler:")
    kernel = Kernel(SchedulerFCFS())

    ##print("Se ejecuta scheduler", kernel)

    # Ahora vamos a intentar ejecutar 3 programas a la vez
    ##################
    prg1 = Program("prg1.exe", [ASM.CPU(2), ASM.IO(), ASM.CPU(3), ASM.IO(), ASM.CPU(2)])
    prg2 = Program("prg2.exe", [ASM.IO(),ASM.CPU(7)])
    prg3 = Program("prg3.exe", [ASM.CPU(4), ASM.IO(), ASM.CPU(1)])
    kernel.fileSystem.write("C:/prg1.exe", prg1)
    kernel.fileSystem.write("C:/prg2.exe", prg2)
    kernel.fileSystem.write("C:/prg3.exe", prg3)
    # execute all programs "concurrently"
   # kernel.run(prg1,1)
    #kernel.run(prg2,2)
    #kernel.run(prg3,3)


 # execute all programs "concurrently"
    kernel.run("C:/prg1.exe", 2)
    kernel.run("C:/prg2.exe", 3)
    kernel.run("C:/prg3.exe", 1)

