# This file is executed on every boot (including wake-boot from deepsleep)
print('booting...')

#import uos
#uos.dupterm(None, 1) # disable REPL on UART(0)
from machine import Pin

# free up memory
import esp
esp.osdebug(None)
import gc
gc.collect()

#import webrepl
#webrepl.start()
