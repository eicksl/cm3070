"""
FEATURES:

street as an integer
highest card on board
average rank (average of board cards)
flush possible
board is paired
4-straight or 4-flush on board
did turn/river bring 3-flush
did turn/river bring 4-flush
did turn/river bring 4-straight
did turn/river bring overcard
ratio of player's aggression to passiveness thus far in the hand
ratio of opponent's aggression to passiveness thus far in the hand
number of bets/raises on current street
player was last aggressor
SPR (with last aggressor)
amount to call as pct of pot (0 if check possible)
num players in hand
relative position divided by num players in hand

CSV header:
street,highCard,avgRank,flushPossible,boardPaired,hasFour,lc3flush,lc4flush,lc4straight,
lcOvercard,plAgg,opAgg,numAggCS,isLastAgg,spr,amtToCall,numPlayers,relPos,result
"""
import os
import re
from src.bot.constants import CARD_RANKS
from src.bot.util import hasFourStraight, lc_4straight


class Parser:
    def __init__(self, outPath='out.csv'):
        if not os.path.exists(outPath):
            with open(outPath, 'w') as file:
                file.write(
                    'street,highCard,avgRank,flushPossible,boardPaired,hasFour,lc3flush,lc4flush,'
                    + 'lc4straight,lcOvercard,plAgg,opAgg,numAggCS,isLastAgg,spr,amtToCall,'
                    + 'numPlayers,relPos,result\n'
                )
        self.outPath = outPath
        self.hands = None
        self.reset()


    def reset(self):
        self.pos = {}  # usernames to positions
        self.stacks = {}  # usernames to stacks
        self.inv = {}  # usernames to street investment
        self.actions = {}
        self.boardCards = []
        self.boardSuits = []
        self.street = 0
        self.pot = 0
        self.numAggCS = 0  # number of bets/raises on current street
        self.index = 2  # line index of file
        self.lastAgg = None  # last aggressor (string)
        self.lastWager = None  # float


    def resetInv(self):
        for player in self.inv:
            self.inv[player] = 0
        self.numAggCS = 0
        self.lastWager = 0


    def loadFile(self, path):
        try:
            with open(path, encoding='utf-8-sig') as file:
                text = file.read()
        except UnicodeDecodeError:
            with open(path, encoding='cp437') as file:
                text = file.read()
        self.hands = re.split('\n{2,}', text)
        self.hands.pop()

    
    def extract(self):
        for i in range(len(self.hands)):
            self.lines = self.hands[i].split('\n')
            self.reset()
            try:
                self.getPlayerInfo()
                if len(self.pos) > 2:
                    self.getPreAction()
                    if self.lines[self.index].startswith('*** FLOP'):
                        self.getPostAction()
            except:
                print('Error encountered. Skipping hand.')
            #print('{} out of {} hands completed'.format(i, len(self.hands)))


    def getPlayerInfo(self):
        pos = []
        while self.lines[self.index].startswith('Seat'):
            left, right = self.lines[self.index].split(': ')
            seat = int(left[5])
            name, right = re.split('\s\([$|€|£|�|ú]', right)
            stack = float(right.split()[0])
            pos.append([name, seat])
            self.stacks[name] = stack
            self.inv[name] = 0
            self.actions[name] = {'r': 1, 'c': 1}
            self.index += 1
        
        btn = int(self.lines[1].split('Seat #')[1][0])
        btnIndex = -1
        for i in range(len(pos)):
            if pos[i][1] == btn:
                btnIndex = i
                break
        
        pos = pos[btnIndex+1:] + pos[:btnIndex+1]
        for i in range(len(pos)):
            pos[i][1] = i + 1

        self.pos = dict(pos)

    
    def getPreAction(self):
        while not self.lines[self.index].startswith('***'):
            line = self.lines[self.index]
            if ': ' not in line:
                self.index += 1
                continue
            blindName, right = line.split(': ')
            try:
                blindAmt = float(right.split()[-1][1:])
            except ValueError:
                self.index += 1
                continue
            self.pot += blindAmt
            self.inv[blindName] += blindAmt
            self.stacks[blindName] -= blindAmt
            self.lastAgg = blindName
            self.index += 1

        self.index += 1
        while not self.lines[self.index].startswith('***'):
            line = self.lines[self.index]
            self.index += 1
            if ': ' not in line:
                continue
            name, right = line.split(': ')
            parts = right.split()
            self.addAction(name, parts)

        self.resetInv()


    def addAction(self, name, parts):
        if len(parts) == 0:
            return
        action = parts[0]
        if action == 'folds':
            del self.pos[name]
        elif action == 'checks':
            self.actions[name]['c'] += 1
        elif action == 'calls':
            callAmt = float(parts[1][1:])
            self.pot += callAmt
            self.stacks[name] -= callAmt
            self.inv[name] += callAmt
            self.actions[name]['c'] += 1
        elif action == 'bets':
            betAmt = float(parts[1][1:])
            self.pot += betAmt
            self.stacks[name] -= betAmt
            self.inv[name] += betAmt
            self.actions[name]['r'] += 1
            self.numAggCS += 1
            self.lastWager = betAmt
        elif action == 'raises':
            wager = float(parts[3][1:])
            raiseAmt = wager - self.inv[name]
            self.pot += raiseAmt
            self.stacks[name] -= raiseAmt
            self.inv[name] += raiseAmt
            self.actions[name]['r'] += 1
            self.lastAgg = name
            self.numAggCS += 1
            self.lastWager = wager


    def getActionResult(self, action):
        agg = None

        if action == 'folds':
            agg = 'F'
        elif action in ['checks', 'calls']:
            agg = 'C'
        elif action in ['bets', 'raises']:
            agg = 'R'
        
        return agg


    def getPostAction(self):
        while True:
            line = self.lines[self.index]
            if line.startswith('***'):
                parts = line.split()
                street = parts[1]
                if street not in ['FLOP', 'TURN', 'RIVER']:
                    break
                elif street == 'FLOP':
                    for i in range(3, 6):
                        card = parts[i].replace('[', '').replace(']', '')
                        self.boardCards.append(card[0])
                        self.boardSuits.append(card[1])
                elif street == 'TURN':
                    self.boardCards.append(parts[6][1])
                    self.boardSuits.append(parts[6][2])
                else:
                    self.boardCards.append(parts[7][1])
                    self.boardSuits.append(parts[7][2])
                self.street += 1
                self.resetInv()
            elif ': ' not in line:
                pass
            else:
                name, right = line.split(': ')
                parts = right.split()
                if len(parts) > 0:
                    result = self.getActionResult(parts[0])
                    if result:
                        self.addNodeInfo(name, result)
                        self.addAction(name, parts)
            self.index += 1


    def getOpponentAgg(self, name):
        """
        Finds the aggression factor for the opponent(s). If there are more than two players in
        the hand, the last aggressor's AF is used unless the player is the last aggressor - in
        which case, the average AF of all opponents is used. The AF for any given player is
        calculated as (bets + raises + 1) / (checks + calls + 1).

        :param name: username of the player to act
        :returns: the AF as a float
        """
        if name != self.lastAgg:
            return self.actions[self.lastAgg]['r'] / self.actions[self.lastAgg]['c']
        
        numOpponents = len(self.pos) - 1
        afTotal = 0
        for player in self.pos:
            if player != name:
                afTotal += self.actions[player]['r'] / self.actions[player]['c']
        
        return afTotal / numOpponents


    def spr(self, name):
        """
        Returns the effective stack-to-pot ratio. If multiway, the last aggressor's stack is
        used to determine the effective stack; however, if the player is the last aggressor,
        the average opponent stack is used.
        """
        pot = self.getEffPot(name)
        if name != self.lastAgg:
            return min(self.stacks[name], self.stacks[self.lastAgg]) / pot

        numOpponents = len(self.pos) - 1
        stacksTotal = 0
        for player in self.pos:
            if player != name:
                stacksTotal += self.stacks[player]

        avgOppStack = stacksTotal / numOpponents
        return min(self.stacks[name], avgOppStack) / pot


    def getRelPos(self, player):
        """
        Calculates the relative position of a player divided by the number of players in the
        hand. If the player is on the button, the output will be 1. Otherwise, the output will be
        in the range (0, 1).
        """
        seats = sorted(self.pos.values())
        relPos = seats.index(self.pos[player]) + 1
        return relPos / len(seats)


    def getEffPot(self, player):
        """Calculates the effective pot size."""
        diff = self.lastWager - self.inv[player]
        if self.numAggCS == 0 or diff <= self.stacks[player]:
            return self.pot

        pot = self.pot
        streetStack = self.stacks[player] + self.inv[player]
        for name in self.inv:
            if name != player and self.inv[name] > streetStack:
                pot -= self.inv[name] - streetStack

        return pot
        

    def getAmtToCall(self, player):
        """Calculates the amount to call as a percentage of the pot."""
        if self.numAggCS == 0:
            return 0
        
        diff = self.lastWager - self.inv[player]
        amtToCall = self.stacks[player] if diff > self.stacks[player] else diff
        
        return amtToCall / self.getEffPot(player)


    def addNodeInfo(self, player, result):
        """
        street,highCard,avgRank,flushPossible,boardPaired,hasFour,lc3flush,lc4flush,lc4straight,
        lcOvercard,plAgg,opAgg,numAggCS,isLastAgg,spr,amtToCall,numPlayers,relPos,result
        """
        cardRanks = [CARD_RANKS[x] for x in self.boardCards]
        highCard = max(cardRanks)
        avgRank = sum(cardRanks) / len(cardRanks)
        flushPossible = len(self.boardSuits) - len(set(self.boardSuits)) >= 2
        boardPaired = len(self.boardCards) != len(set(self.boardCards))
        has4flush = len(self.boardSuits) - len(set(self.boardSuits)) >= 3
        has4straight = hasFourStraight(self.boardCards)
        hasFour = has4straight or has4flush
        lcDominantSuit = self.boardSuits[-1] == max(
            set(self.boardSuits), key=self.boardSuits.count
        )
        lc3flush = flushPossible and lcDominantSuit
        lc4flush = has4flush and lcDominantSuit
        lc4straight = has4straight and lc_4straight(self.boardCards)
        lcOvercard = highCard == cardRanks[-1]
        plAgg = self.actions[player]['r'] / self.actions[player]['c']
        opAgg = self.getOpponentAgg(player)
        isLastAgg = player == self.lastAgg
        spr = self.spr(player)
        amtToCall = self.getAmtToCall(player)
        relPos = self.getRelPos(player)
        row = (
            '{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n'.format(
                self.street, highCard, avgRank, flushPossible, boardPaired, hasFour, lc3flush,
                lc4flush, lc4straight, lcOvercard, plAgg, opAgg, self.numAggCS, isLastAgg, spr,
                amtToCall, len(self.pos), relPos, result
            )
        )
        with open(self.outPath, 'a') as file:
            file.write(row)



if __name__ == '__main__':
    path = '../../data/'
    #if os.path.exists('out.csv'):
    #    os.remove('out.csv')
    files = [path + file for file in os.listdir(path)]
    parser = Parser()
    for i in range(10273, len(files)):
        file = files[i]
        parser.loadFile(file)
        print('Loaded ' + file.split(path)[1])
        parser.extract()
        print('{} out of {} files completed\n'.format(i+1, len(files)))
