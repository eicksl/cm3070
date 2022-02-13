from table_setup import TableSetup


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
            pass
        elif num == 2:
            TableSetup().run()
        else:
            print("\nInput is invalid\n\n")



if __name__ == '__main__':
    run()
