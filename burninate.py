#!/usr/bin/env python

import asyncio
import atexit
from time import sleep

from websockets.server import serve
from  gpiozero import Button, LED, DigitalOutputDevice


import logging
logger = logging.getLogger('websockets')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())



# Create our own Pyro class, reversing high/low because cheap relay board
class Pyro(DigitalOutputDevice):
    def __init__(self, pin):
        DigitalOutputDevice.__init__(self, pin, active_high=False, initial_value=False)

# Pyros
valves = [
    None,  # using 1-indexing to match pyro-relay board.
    Pyro(17),  # outside right (from the fire station)
    Pyro(22),  # middle right
    Pyro(27),  # inside right
    Pyro(4),   # inside left
    Pyro(23),  # middle left
    Pyro(24),  # outside left
    Pyro(25),  # Tail
    Pyro(9),   # extra
]

# viewed from the fire pedestal
stalks = {
    'right-outside': 1,
    'right-middle': 2,
    'right-inside': 3,
    'left-inside': 4,
    'left-middle': 5,
    'left-outside': 6,
    'tail': 7
} 

def allFireOff():
    global valves
    for valve in valves:
        if not valve:
            continue
        valve.off()

atexit.register(allFireOff)

async def ignition_timer(websocket, flames, duration, repetitions=1, rep_delay=None, start_delay=0):
    print("ingition_timer_1")
    await asyncio.sleep(start_delay)
    for rep in range(0,repetitions):
        for flame in flames:
            valves[flame].on()

        await asyncio.sleep(duration)

        for flame in flames:
            valves[flame].off()

        if repetitions > 1:
            await asyncio.sleep(rep_delay or duration)

        if websocket.close_rcvd:
            break

async def ignition_timer2(flames, duration, repetitions):
    print("ingition_timer_2")
    for rep in range(0,repetitions):
        for flame in flames:
            valves[flame].on()

        await asyncio.sleep(duration)

        for flame in flames:
            valves[flame].off()

        await asyncio.sleep(duration)


def run_sequence(sequence):
    pass

async def echo(websocket):
    global valves, stalks
    logging.warning(websocket.path)
    endpoint = websocket.path.split('/')[2]
    if endpoint == 'sequence1':
        while not websocket.close_rcvd:
            coro = ignition_timer(websocket, [1,3,5],.375,3)
            coro2 = ignition_timer(websocket, [2,4,6],.250,5)
            task1 = asyncio.create_task(coro)
            task2 = asyncio.create_task(coro2)
            await task1
            await task2


    elif endpoint == 'sequence3':
        while not websocket.close_rcvd:
            pattern1 = ignition_timer(websocket, [1,6], .2, 1, .4, 0)
            pattern2 = ignition_timer(websocket, [2,5], .2, 1, .4, .5)
            pattern3 = ignition_timer(websocket, [3,4], .2, 1, .4, 1)
            pattern4 = ignition_timer(websocket, [7,], .2, 1, .4, 1.5)

            task1 = asyncio.create_task(pattern1)
            task2 = asyncio.create_task(pattern2)
            task3 = asyncio.create_task(pattern3)
            task4 = asyncio.create_task(pattern4)
            await task1
            await task2
            await task3
            await task4

    elif endpoint == 'sequence2':
        while not websocket.close_rcvd:
            tasks = {}
            patterns = []
            patterns.append(ignition_timer(websocket, [1,], .2, 1, 2, 0))
            patterns.append(ignition_timer(websocket, [2,], .2, 1, 2, .2))
            patterns.append(ignition_timer(websocket, [3,], .2, 1, 2, .4))
            patterns.append(ignition_timer(websocket, [4,], .2, 1, 2, .6))
            patterns.append(ignition_timer(websocket, [5,], .2, 1, 2, .8))
            patterns.append(ignition_timer(websocket, [6,], .2, 1, 2, 1))
            patterns.append(ignition_timer(websocket, [5,], .2, 1, 2, 1.2))
            patterns.append(ignition_timer(websocket, [4,], .2, 1, 2, 1.4))
            patterns.append(ignition_timer(websocket, [3,], .2, 1, 2, 1.6))
            patterns.append(ignition_timer(websocket, [2,], .2, 1, 2, 1.8))
            #patterns.append(ignition_timer(websocket, [2,], .2, 1, 2.2, 2))

            for pattern in patterns:
                tasks[patterns.index(pattern)] = asyncio.create_task(pattern)

            for task in tasks:
                await tasks[task]

    elif endpoint == 'all':
        try:
            for flame in valves[1:]:
                flame.on()
            async for message in websocket:
                await websocket.send(message)
            logging.warning(f"stopping fire on all stalks!")
            for flame in valves[1:]:
                flame.off()
        except:
            logging.warning(f"EMERGENCY stopping fire on all stalks!")
            for flame in valves[1:]:
                flame.off()


    elif endpoint in stalks.keys():
        try:
            logging.warning(f"firing stalk {endpoint}")
            valves[stalks[endpoint]].on()
            async for message in websocket:
                await websocket.send(message)
            valves[stalks[endpoint]].off()
            logging.warning(f"stopping fire on stalk {endpoint}")
        except:
            valves[stalks[endpoint]].off()


async def main():
    async with serve(echo, "0.0.0.0", 8765):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
    exit(0)
    for valve in valves:
        if valve == None:
            continue
        print(valve)
        valve.on()
        sleep(0.250)
        valve.off()

# for valve in valves:
#     if valve == None:
#         continue
#     for i in range(0,1):
#         valve.on()
#         sleep(0.066)
#         valve.off()
#         sleep(0.250)



