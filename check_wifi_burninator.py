#!/usr/bin/env python

import datetime
import os
from time import sleep
import netifaces
from gpiozero import Button, LED, DigitalOutputDevice, CPUTemperature


wifi_led = LED(11)
burninator_led = LED(26)

def check_axo_wifi():
  interfaces = netifaces.interfaces()
  addrs = netifaces.ifaddresses('wlan0')
  for addr in addrs.values():
    if addr[0]['addr'] == '10.0.1.2':
      return True
  return None


def check_burninator():
    result = os.system("/bin/netstat -na | /bin/grep 8765 | /bin/grep -q LISTEN ")
    if result == 0:
        return True
    else:
        return None

while True:
    if check_axo_wifi():
        if wifi_led.is_active == False:
            print(f"WiFi Became active at {datetime.datetime.now()}") 
        wifi_led.on()
    else:
        if wifi_led.is_active == True:
            print(f"Lost Wifi connection at {datetime.datetime.now()}") 
        wifi_led.off()
    if check_burninator():
        if burninator_led.is_active == False:
            print(f"Found burninator port at {datetime.datetime.now()}") 
        burninator_led.on()
    else:
        if burninator_led.is_active == True:
            print(f"Lost connection to burninator at {datetime.datetime.now()}") 
        burninator_led.off()
    sleep(5)


