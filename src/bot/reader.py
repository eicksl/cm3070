import os, json, cv2
import numpy as np
from tesserocr import PyTessBaseAPI, PSM, OEM
from PIL import Image, ImageGrab
from src.bot.util import (
    getCard, getOcrBet, containsTemplate, getCardSuit, getOcrStack, villainHasCards
)
from src.bot.constants import CONFIG_DIR, IMAGE_DIR, TESSDATA_DIR


class Reader:

    def __init__(self, tableNum, debug=False):
        self.scaleFactor = 4
        self.binThresh = 160
        self.table = 'table' + str(tableNum)
        with open(CONFIG_DIR + 'tables.json') as file:
            self.areas = json.loads(file.read())
        self.api = PyTessBaseAPI(path=TESSDATA_DIR, psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)
        #self.api.SetVariable("tessedit_char_whitelist", "0123456789.JQKA")
        self.cvBtn = cv2.imread(IMAGE_DIR + 'button.png', cv2.IMREAD_GRAYSCALE)
        self.cvPlayerActive = cv2.imread(IMAGE_DIR + 'playerActive.png', cv2.IMREAD_GRAYSCALE)
        self.cvPlayerActiveTime = cv2.imread(IMAGE_DIR + 'playerActiveTIME.png', cv2.IMREAD_GRAYSCALE)
        self.debug = debug
        self.debugState = 0
        self.debugFileName = 0


    def getPilImage(self, bbox):
        if self.debug == False:
            return ImageGrab.grab(bbox)

        base = IMAGE_DIR + 'debug/'
        path = base + str(self.debugState) + '.png'
        img = Image.open(path).crop(bbox)
        path = base + 'out/' + str(self.debugState)
        if not os.path.isdir(path):
            os.makedirs(path)
        img.save('{}/{}.png'.format(path, self.debugFileName))
        self.debugFileName += 1
        return img


    def existsCard(self, cardPos):
        """Determines if a card exists at a given position"""
        bbox = self.areas[self.table]['boardCards'][cardPos]
        npImg = np.array(self.getPilImage(bbox))
        return getCardSuit(npImg) is not None


    def getHoleCards(self):
        bboxes = self.areas[self.table]['holeCards']
        pilCard1 = self.getPilImage(bboxes[0])
        strCard1 = getCard(self.api, pilCard1, self.scaleFactor, self.binThresh)
        if not strCard1:
            return None
        pilCard2 = self.getPilImage(bboxes[1])
        strCard2 = getCard(self.api, pilCard2, self.scaleFactor, self.binThresh)
        if not strCard2:
            return None
        return strCard1 + strCard2


    def getStreetAndBoard(self, street, board):
        """
        Returns the current street and board. Cards are only read when they need
        to be.
        """
        lstCardsPos = None

        if street == 'pre':
            if self.existsCard(0):
                street = 'flop'
                lstCardsPos = [0, 1, 2]
        elif street == 'flop':
            if self.existsCard(3):
                street = 'turn'
                lstCardsPos = [3]
        elif street == 'turn':
            if self.existsCard(4):
                street = 'river'
                lstCardsPos = [4]
        elif street == 'river':
            return street, board
        else:
            raise Exception("'{}' is not a valid street input".format(street))

        if lstCardsPos is None:
            return street, board
        
        for pos in lstCardsPos:
            bbox = self.areas[self.table]['boardCards'][pos]
            img = self.getPilImage(bbox)
            card = getCard(self.api, img, self.scaleFactor, self.binThresh)
            if not card:
                raise Exception("Card not found at position " + str(pos))
            board += card

        return street, board


    def getPositions(self):

        def getBtnIndex():
            for i in range(len(btnAreas)):
                img = self.getPilImage(btnAreas[i])
                img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
                if containsTemplate(img, self.cvBtn):
                    return i
            print("Unable to find button")
            return None

        btnAreas = self.areas[self.table]['buttons']
        btn = getBtnIndex()  # int in range [0, 5] representing the player number
        if btn is None:
            return None, None
        pos_to_pn = {
            'LJ': (btn + 3) % 6,
            'HJ': (btn + 4) % 6,
            'CO': (btn + 5) % 6,
            'BU': btn,
            'SB': (btn + 1) % 6,
            'BB': (btn + 2) % 6
        }
        pn_to_pos = {pos_to_pn[k] : k for k in pos_to_pn}
        return pos_to_pn, pn_to_pos

    
    def getplayersInHand(self, playersInHand):
        new = {0: playersInHand[0]}
        for num in playersInHand:
            if num == 0:
                continue
            bbox = self.areas[self.table]['cardBacks'][num]
            npImg = np.array(self.getPilImage(bbox))
            if villainHasCards(npImg):
                new[num] = playersInHand[num]
        return new

    """
    def getBets(self, playersInHand):
        bets = {}
        for num in playersInHand:
            bbox = self.areas[self.table]['bets'][num]
            pilImg = self.getPilImage(bbox)
            amount = getOcrNumber(self.api, pilImg, self.scaleFactor, self.binThresh)
            if amount:
                bets[num] = amount
        return bets
    """

    def getActivePlayer(self, playersInHand):
        for num in playersInHand:
            bbox = self.areas[self.table]['playerActive'][num]
            img = self.getPilImage(bbox)
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            if containsTemplate(img, self.cvPlayerActive) or containsTemplate(img, self.cvPlayerActiveTime):
                return num
        return None


    def getWager(self, pn):
        bbox = self.areas[self.table]['bets'][pn]
        img = self.getPilImage(bbox)
        return getOcrBet(self.api, img, self.scaleFactor, self.binThresh)


    def getPot(self, street=False):
        if street:
            potType = 'streetPot'
            main = False
        else:
            potType = 'pot'
            main = True
        bbox = self.areas[self.table][potType][0]
        img = self.getPilImage(bbox)
        return getOcrBet(self.api, img, self.scaleFactor, self.binThresh, isMainPot=main)


    def getStacks(self, playersInHand):
        stacks = {}
        for pn in playersInHand:
            bbox = self.areas[self.table]['stacks'][pn]
            img = self.getPilImage(bbox)
            stacks[pn] = getOcrStack(self.api, img, self.scaleFactor, self.binThresh)
            if stacks[pn] is None:
                return None
        return stacks



if __name__ == '__main__':
    reader = Reader(1)
    for i in range(6):
        bbox = reader.areas[reader.table]['buttons'][i]
        img = ImageGrab.grab(bbox)
        path = IMAGE_DIR + 'test/{}.png'.format(i)
        img.save(path)
