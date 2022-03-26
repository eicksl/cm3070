import os, keyboard
from src.bot.table_setup import TableSetup
from src.bot.state_manager import StateManager


def printMainMenu():
    print("\n\nMain menu options:\n")
    print("(0) Exit program")
    print("(1) Run RTA")
    print("(2) Table setup")
    print("\nAwaiting keyboard input...\n")


def run():
    while True:
        printMainMenu()
        try:
            num = int(input())
        except ValueError:
            print("\nInput is invalid\n\n")
            continue
        
        if num == 0:
            print()
            exit(0)
        elif num == 1:
            StateManager(1, debug=True).run()
        elif num == 2:
            TableSetup().run()
        else:
            print("\nInput is invalid\n\n")



if __name__ == '__main__':
    keyboard.add_hotkey('esc', lambda: os.system('taskkill /im winpty-agent.exe'))
    sm = StateManager(1, debug=True)
    #sm.run()
    sm.test_run()
