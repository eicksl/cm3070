import sys
import json
import threading
import win32gui, win32ui
from win32api import GetSystemMetrics, GetSysColor
#from util import preprocessImage, getOcrString, getOcrCard, getOcrNumber
from pynput import mouse
from PIL import ImageGrab


class TableSetup():

    def __init__(self):
        self.displayBoxes = False
        self.coordinates = None
        self.clickState = {}
        with open('config/tables.json') as file:
            self.config = json.loads(file.read())


    def drawBoxesToScreen(self, strTable):
        dc = win32gui.GetDC(0)
        dcObj = win32ui.CreateDCFromHandle(dc)
        hwnd = win32gui.WindowFromPoint((0,0))
        brush = win32ui.CreateBrush()
        brush.CreateSolidBrush(GetSysColor(26))
        monitor = (0, 0, GetSystemMetrics(0), GetSystemMetrics(1))

        while True:
            for arr in self.config[strTable].itervalues():
                for bbox in arr:
                    dcObj.FrameRect(bbox, brush)
            if self.displayBoxes == False:
                win32gui.InvalidateRect(hwnd, monitor, True)
                break


    def getIntegerInput(self, max, string):
        while True:
            print("\nEnter the {} number ({}-{}) or 0 to abort...\n".format(string, max))
            num = input()

            try:
                num = int(num)
            except ValueError:
                print("\nInput is invalid\n\n")
                continue
                
            if num < 0 or num > max:
                print("\nInput is invalid\n\n")
                continue
            
            return num


    def saveConfig(self):
        with open('config/tables.json', 'w') as file:
            file.write(json.dumps(self.config, indent=4, sort_keys=True))


    def getBbox(self):
        print("\nClick the top-left corner of the pot size search area\n")
        print("Awaiting mouse click...")
        sys.stdout.flush()
        with mouse.Listener(on_click=self.onClick) as listener:
            listener.join()
        self.clickState['first'] = self.coordinates
        print("\nSelected coordinates: " + str(self.coordinates) + "\n\n")
        sys.stdout.flush()

        print("\nClick the bottom-right corner of the pot size search area\n")
        print("Awaiting mouse click...")
        sys.stdout.flush()
        with mouse.Listener(on_click=self.onClick) as listener:
            listener.join()
        self.clickState['second'] = self.coordinates
        print("\nSelected coordinates: " + str(self.coordinates) + "\n\n")

        bbox = self.clickState['first'] + self.clickState['second']
        self.clickState = None
        return bbox


    def printMenu(self):
        print("\n\nTable setup options:\n")
        print("(0) Return to main menu")
        print("(1) Display bounding boxes")
        print("(2) Hide bounding boxes")
        print("(3) Set pot size area")
        print("(4) Set bet size areas")
        print("(5) Set stack size areas")
        print("(6) Set hole card areas")
        print("(7) Set board card areas")
        print("(8) Set \"action on Hero\" image")
        print("(9) Set search area for \"action on Hero\" image")
        print("(10) Set button image")
        print("(11) Set search areas for button image")
        print("(12) Set back of card image")
        print("(13) Set search areas for back of card image")
        print("\nAwaiting keyboard input...\n")


    def onClick(self, x, y, button, pressed):
        self.coordinates = (x, y)
        if not pressed:
            # Stop listener
            return False


    def setArea(self, table, jsonKey, index=1):
        """
        :param table: the table key, e.g. 'table1'
        :param jsonKey: the next key, e.g. 'pot', 'bets', etc
        :param index: 1-based index of the array
        """
        bbox = self.getBbox()
        self.config[table][jsonKey][index-1] = bbox
        self.saveConfig()


    def run(self):
        tableNum = self.getIntegerInput(6, 'table')
        if tableNum == 0:
            return
        
        strTable = 'table' + str(tableNum)

        while True:
            self.printMenu()

            try:
                num = int(input())
            except ValueError:
                print("\nInput is invalid\n\n")
                continue
            
            if num == 0:
                # Return to main menu
                self.displayBoxes = False
                break
            elif num == 1:
                # Display bounding boxes
                self.displayBoxes = True
                threading.Thread(target=self.drawBoxesToScreen, args=(strTable,)).start()
            elif num == 2:
                # Hide bounding boxes
                self.displayBoxes = False
            elif num == 3:
                # Set pot size area
                self.setArea(strTable, 'pot')
                self.saveConfig()
            elif num == 4:
                # Set bet size areas
                playerNum = self.getIntegerInput(6, 'player')
                if playerNum == 0:
                    continue
                self.setArea(strTable, 'bets', playerNum)
            elif num == 5:
                # Set stack size areas
                playerNum = self.getIntegerInput(6, 'player')
                if playerNum == 0:
                    continue
                self.setArea(strTable, 'stacks', playerNum)
            elif num == 6:
                # Set hole card areas
                cardNum = self.getIntegerInput(2, 'card')
                if cardNum == 0:
                    continue
                self.setArea(strTable, 'holeCards', cardNum)
            elif num == 7:
                # Set board card areas
                cardNum = self.getIntegerInput(5, 'card')
                if cardNum == 0:
                    continue
                self.setArea(strTable, 'boardCards', cardNum)
            elif num == 8:
                # Set "action on hero" image
                bbox = self.getBbox()
                img = ImageGrab.grab(bbox)
                img.save('img/heroActive.png')
            elif num == 9:
                # Set search area for "action on hero" image
                self.setArea(strTable, 'heroActive')
            elif num == 10:
                # Set button image
                bbox = self.getBbox()
                img = ImageGrab.grab(bbox)
                img.save('img/button.png')
            elif num == 11:
                # Set search areas for button image
                playerNum = self.getIntegerInput(6, 'player')
                if playerNum == 0:
                    continue
                self.setArea(strTable, 'buttons', playerNum)
            elif num == 12:
                # Set back of card image
                bbox = self.getBbox()
                img = ImageGrab.grab(bbox)
                img.save('img/cardBack.png')
            elif num == 13:
                # Set search areas for back of card image
                playerNum = self.getIntegerInput(6, 'player')
                if playerNum == 0:
                    continue
                self.setArea(strTable, 'cardBacks', playerNum)
            else:
                print("\nInput is invalid\n\n")



if __name__ == '__main__':
    setup = TableSetup()
    setup.run()
