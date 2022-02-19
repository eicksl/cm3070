import time
from reader import Reader
from util import POS_RANKS_LIST_PRE, POS_RANKS_DICT_PRE
from PIL import ImageGrab


class StateManager:

    def __init__(self, tableNum, debug=False):
        self.debug = debug
        self.reader = Reader(tableNum, debug=debug)
        self.interval = 1
        self.pn_to_pos = {0: ''}
        self.pos_to_pn = {}
        self.playersInHand = {}
        self.street = ''
        self.holeCards = ''
        self.pfRaises = 0  # preflop raises
        self.line = []  # elements are tuples in the form of (pn, action, investment)
        self.playerHistory = {}  # player-specific lines and investment per street
        self.pnLastActive = None  # active player from the last update
        self.pnActive = None  # currently active player
        self.lastWager = {'pn': None, 'amt': 1}  # player number and amount


    def resetPlayerHistory(self):
        for pos in POS_RANKS_LIST_PRE:
            self.playerHistory[pos] = {
                'line': {'pre': [], 'flop': [], 'turn': [], 'river': []},
                'invested': {'pre': 0, 'flop': 0, 'turn': 0, 'river': 0}
            }
        self.playerHistory['SB']['invested']['pre'] = 0.5
        self.playerHistory['BB']['invested']['pre'] = 1.0


    def printState(self):

        def _getLineString():
            string = ''
            for action in self.line:
                string += action[1] + '-'
            return string[:-1]
        
        print('\n\nHole cards: ' + self.holeCards)
        print('\nStreet: ' + self.street)
        print('\nPositions: ' + str(self.pos_to_pn))
        print('\nLast wager: ' + str(self.lastWager))
        print('\nPlayers in hand: ' + str(self.playersInHand))
        print('\nActive player: ' + str(self.pnActive))
        print('\nLine: ' + str(self.line))
        print('\nLine string: ' + _getLineString())
        print('\n\n\n')


    def getPlayersToCheck(self):
        """
        Returns a list of players to check. It will be a list of players
        that were in the hand at the previous timestep. The list will be
        sorted in the order of street position (LJ-BB for pre-flop and
        SB-BU for post-flop), starting with the player who was active at
        the previous time-step, or the first player in pre-flop position
        rank if it is the first time-step of the hand. If said player
        cannot be found in self.playersInHand, then the output list will
        begin with the next highest player in position rank who is still
        in the dictionary.

        NOTE: Could probably use simpler logic for post-flop.
        """
        def _getNextPlayer(pn):
            num = -1
            for i in range(1, 6):
                nextPlayer = (pn + i) % 6
                if nextPlayer in self.playersInHand:
                    num = nextPlayer
                    break
            return num

        players = list(self.playersInHand.keys())
        players.sort(key=lambda pn: POS_RANKS_DICT_PRE[self.pn_to_pos[pn]])
        #print(players)

        if not self.line:
        #if self.lastWager['pn'] == self.pos_to_pn['BB'] and self.lastWager['amt'] == 1:
            #if self.line and self.street == 'pre' and self.pnLastActive == self.pos_to_pn['BB']:
            #    return []
            if self.pos_to_pn['LJ'] in self.playersInHand:
                #print('A')
                lap = self.pos_to_pn['LJ']
            else:
                #print('B')
                lap =_getNextPlayer(self.pos_to_pn['LJ'])
        else:
            if self.pnLastActive in self.playersInHand:
                #print('C')
                lap = self.pnLastActive
            else:
                # set it to the closest next-acting player that is still in the hand
                #print('D')
                lap = _getNextPlayer(self.pnLastActive)

        #print('lap: ' + str(lap))
        lapInd = players.index(lap)

        #print('lapInd: ' + str(lapInd))
        return players[lapInd:] + players[:lapInd]


    def updateState(self):
        if not self.reader.isPreflop():
            return

        holeCards = self.reader.getHoleCards()
        if not holeCards:  # Hero not in hand
            return
        
        #pos_to_pn, pn_to_pos = self.reader.getPositions()
        if holeCards != self.holeCards:  # or pn_to_pos[0] != self.pn_to_pos[0]:
            self.pos_to_pn, self.pn_to_pos = self.reader.getPositions()
            if not self.pos_to_pn:  # no button found
                return
            self.street = 'pre'
            self.line.clear()
            self.resetPlayerHistory()
            self.pfRaises = 0
            self.holeCards = holeCards
            self.playersInHand = self.pn_to_pos.copy()
            self.lastWager.update({'pn': self.pos_to_pn['BB'], 'amt': 1})
            self.pnLastActive = self.pos_to_pn['BB']
        
        if self.street == 'pre':
            playersInHand = self.reader.getplayersInHand(self.playersInHand)
            self.pnActive = self.reader.getActivePlayer(playersInHand)
            if self.pnActive is None:
                return
            playersToCheck = self.getPlayersToCheck()
            self.playersInHand = playersInHand  # update after getPlayersToCheck

            actions = []
            print(playersToCheck)
            for pn in playersToCheck:
                history = self.playerHistory[self.pn_to_pos[pn]]
                if pn not in self.playersInHand:
                    action = (self.pn_to_pos[pn], 'F', 0)
                else:
                    wager = self.reader.getWager(pn)
                    if wager is None:
                        if history['invested'][self.street] > 0:
                            raise Exception("Could not read wager of player number " + str(pn))
                        break
                    elif (
                        wager < 1 or pn == self.pnActive
                        or pn == self.lastWager['pn'] and wager == self.lastWager['amt']
                    ):
                        break

                    #print(wager)
                    #print(self.pnActive)
                    assert wager >= self.lastWager['amt']

                    if wager == self.lastWager['amt']:
                        # update history with the amount called
                        history['invested'][self.street] += wager - history['invested'][self.street]
                        action = (self.pn_to_pos[pn], 'C', wager)
                    else:
                        history['invested'][self.street] += wager - history['invested'][self.street]
                        action = (self.pn_to_pos[pn], 'R', wager)
                        self.lastWager.update({'pn': pn, 'amt': wager})
                        self.pfRaises += 1

                actions.append(action)
                history['line'][self.street].append(action)

            #if len(self.line) > 0 and len(actions) > 0:
            #    self.line += '-'
            #self.line += '-'.join(actions)
            self.line += actions
            self.pnLastActive = self.pnActive

    
    def run(self):
        while True:
            if self.debug:
                path = '../img/debug/{}.png'.format(self.reader.debugState)
                ImageGrab.grab().save(path)

            start = time.time()
            self.updateState()

            if self.debug:
                self.reader.debugState += 1
                self.reader.debugFileName = 0

            print('Ran update in {} seconds'.format(time.time() - start))
            self.printState()
            time.sleep(self.interval)


    def test_run(self):
        import os
        path = '../img/debug'
        numFiles = len([name for name in os.listdir(path) if os.path.isfile(path + '/' + name)])
        for _ in range(numFiles):
            keyboard.wait('f9')
            start = time.time()
            self.updateState()
            self.reader.debugState += 1
            self.reader.debugFileName = 0
            print('Ran update in {} seconds'.format(time.time() - start))
            self.printState()


    def recordStates(self):
        from PIL import ImageGrab
        count = 0
        while True:
            keyboard.wait('f9')
            ImageGrab.grab().save('../img/states/{}.png'.format(count))
            count += 1



if __name__ == '__main__':
    import os, keyboard
    keyboard.add_hotkey('esc', lambda: os.system('taskkill /im winpty-agent.exe'))
    stateManager = StateManager(1, debug=True)
    #stateManager.recordStates()
    stateManager.run()
    #stateManager.test_run()
    """
    stateManager.playersInHand = {
        0: 'BU', 3: 'LJ', 4: 'HJ', 5: 'CO', 1: 'SB', 2: 'BB'
    }
    stateManager.pn_to_pos = stateManager.playersInHand.copy()
    stateManager.pos_to_pn = {stateManager.pn_to_pos[k] : k for k in stateManager.pn_to_pos}
    stateManager.pnLastActive = 2
    stateManager.pnActive = 3
    stateManager.lastWager['pn'] = 2
    res = stateManager.getPlayersToCheck()
    print(res)
    """
