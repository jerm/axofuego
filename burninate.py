#!/usr/bin/env python

import asyncio
import atexit
from time import sleep

from websockets.server import serve
import websockets
from gpiozero import Button, LED, DigitalOutputDevice, CPUTemperature


import logging
logger = logging.getLogger('websockets')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())



# Create our own Poofer class, reversing high/low because cheap relay board
class Poofer(DigitalOutputDevice):
    def __init__(self, pin):
        DigitalOutputDevice.__init__(self, pin, active_high=False, initial_value=False)

# Poofers
valves = [
    None,  # using 1-indexing to match pyro-relay board.
    Poofer(17),  # outside right (from the fire station)
    Poofer(22),  # middle right
    Poofer(27),  # inside right
    Poofer(4),   # inside left
    Poofer(23),  # middle left
    Poofer(24),  # outside left
    Poofer(25),  # Tail
    Poofer(9),   # extra
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


async def get_cpu_temp():
    global connected_clients
    while True:
        cputemp = CPUTemperature().temperature
        print(f"reporting CPU temp as {cputemp}")
        message = f"CPU Temperature: {cputemp:.1f} C"
        # Send the message to all connected clients
        for websocket in connected_clients:
            try:
                await websocket.send(message)
            except:
                print(f"Failed updating CPU temp for client: {websocket}")

        # Wait for 10 seconds before sending the next update
        await asyncio.sleep(10)

def run_sequence(sequence):
    pass

async def handle_client(websocket):
    global valves, stalks
    logging.warning(websocket.path)
    endpoint = websocket.path.split('/')[2]
    if endpoint == 'cputemp':
        print("adding client to cputemp list")
        # Add the client's WebSocket connection to the list of connected clients
        connected_clients.add(websocket)
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
        finally:
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
        finally:
            valves[stalks[endpoint]].off()

    try:
        # Continuously listen for messages from the client (if necessary)
        async for message in websocket:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if endpoint == 'cputemp':
            # Remove the client's WebSocket connection when it is closed
            connected_clients.remove(websocket)
        else:
            print("stop the fire")



if __name__ == "__main__":
    # Set to store connected WebSocket clients
    connected_clients = set()
    start_server = websockets.serve(handle_client, "0.0.0.0", 8765)
    asyncio.get_event_loop().run_until_complete(asyncio.gather(start_server, get_cpu_temp()))
    asyncio.get_event_loop().run_forever()

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



