import keyboard
import time
from random import random
from src.bot.util import mapRange
from src.bot.constants import HOTKEYS


class Actor:

    @staticmethod
    def perform(state, action: tuple) -> None:
        if state.street == 'pre' and state.lastWager['pn'] == 0:
            agg = 'X'
        else:
            agg = action[0].upper()
        if state.street == 'pre' and agg == 'R' and state.numAggCS == 0:
            if state.pn_to_pos[0] == 'SB':
                time.sleep(mapRange(random(), 0, 1, 0.5, 1.5))
                Actor.send('f10')
                time.sleep(mapRange(random(), 0, 1, 0.12, 0.25))
                Actor.send('up')
            else:
                Actor.send('left')
                time.sleep(mapRange(random(), 0, 1, 0.05, 0.18))
                Actor.send('up')
        else:
            match agg:
                case 'F':
                    #time.sleep(mapRange(random(), 0, 1, 2, 4.5))
                    Actor.send('down')
                case 'X':
                    #time.sleep(mapRange(random(), 0, 1, 2, 5))
                    Actor.send('right')
                case 'C':
                    #time.sleep(mapRange(random(), 0, 1, 3, 7))
                    Actor.send('tab')
                case 'J':
                    #time.sleep(mapRange(random(), 0, 1, 4, 8))
                    Actor.send('plus')
                    time.sleep(mapRange(random(), 0, 1, 1, 3))
                    Actor.send('up')
                case _:
                    # bet or raise action
                    pct = action[2]
                    code = round(pct * 100 / 2.5) * 25
                    useShift = False
                    if code > 2050:
                        key = 'plus'
                    elif code >= 1100:
                        useShift = True
                        code -= 1000
                        key = HOTKEYS[code]
                    else:
                        key = HOTKEYS[code]
                    #time.sleep(mapRange(random(), 0, 1, 3, 7))
                    Actor.send(key)
                    time.sleep(mapRange(random(), 0, 1, 1, 3))
                    Actor.send('up')


    @staticmethod
    def fastFold() -> None:
        Actor.send('down')


    @staticmethod
    def send(key: str) -> None:
        keyboard.press(key)
        time.sleep(mapRange(random(), 0, 1, 0.05, 0.3))
        keyboard.release(key)


    @staticmethod
    def shiftSend(key: str) -> None:
        keyboard.press('shift')
        time.sleep(mapRange(random(), 0, 1, 0.25, 0.6))
        keyboard.press(key)
        time.sleep(mapRange(random(), 0, 1, 0.05, 0.3))
        if random() > 0.2:
            keyboard.release(key)
            time.sleep(mapRange(random(), 0, 1, 0.05, 0.18))
            keyboard.release('shift')
        else:
            keyboard.release('shift')
            time.sleep(mapRange(random(), 0, 1, 0.06, 0.28))
            keyboard.release(key)
