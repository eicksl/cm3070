import time
from reader import Reader


class StateManager:

    def __init__(self):
        self.reader = Reader(1, debug=True)
        self.interval = 4
        self.pn_to_pos = {0: ''}
        self.pos_to_pn = {}
        self.playersInHand = {}
        #self.actions = []
        self.street = ''
        self.line = ''
        self.holeCards = ''
        self.activePlayer = None
        self.lastWager = {'pn': None, 'amt': 1}  # player number and amount


    def printState(self):
        print('\n\nHole cards: ' + self.holeCards)
        print('\nPositions: ' + str(self.pos_to_pn))
        print('\nPlayers in hand: ' + str(self.playersInHand))
        print('\nStreet: ' + self.street)
        print('\nLine: ' + self.line)
        print('\nActive player: ' + str(self.activePlayer))
        print('\nLast wager: ' + str(self.lastWager))
        print('\n\n\n')


    def updateState(self):
        holeCards = self.reader.getHoleCards()
        if not holeCards:  # Hero not in hand
            return
        #pos_to_pn, pn_to_pos = self.reader.getPositions()
        if holeCards != self.holeCards:  # or pn_to_pos[0] != self.pn_to_pos[0]:
            self.pos_to_pn, self.pn_to_pos = self.reader.getPositions()
            if not self.pos_to_pn:
                return
            self.street = 'pre'
            self.line = ''
            self.holeCards = holeCards
            #self.pos_to_pn, self.pn_to_pos = pos_to_pn, pn_to_pos
            self.playersInHand = self.pn_to_pos.copy()
            self.lastWager.update({'pn': self.pos_to_pn['BB'], 'amt': 1})
        
        self.playersInHand = self.reader.updateplayersInHand(self.playersInHand)
        self.activePlayer = self.reader.updateActivePlayer(self.activePlayer, self.playersInHand)
        if self.street == 'pre':
            wagers, players = self.reader.getWagers(self.playersInHand, pre=True)
            """
            if self.activePlayer is not None:
                index = players.index(self.activePlayer)
                if self.activePlayer != players[0]:
                    wagers = wagers[index:] + wagers[:index]
                    players = players[index:] + players[:index]
            """
            print(wagers)
            actions = []
            for i in range(6):
                if i not in self.playersInHand:
                    if wagers[i] is None:
                        actions.append('F')
                    else:
                        print('Player made wager but is no longer in the hand')
                elif wagers[i] and players[i] != self.lastWager['pn']:
                    if wagers[i] == self.lastWager['amt']:
                        actions.append('C')
                    elif wagers[i] > self.lastWager['amt']:
                        actions.append('R')
                        self.lastWager = wagers[i]

        if len(self.line) > 0 and len(actions) > 0:
            self.line += '-'
        self.line += '-'.join(actions)
        if len(actions) > 0:
            print(self.line)
            print()

    
    def run(self):
        while True:
            start = time.time()
            self.updateState()
            print('Ran update in {} seconds'.format(time.time() - start))
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
    stateManager = StateManager()
    #stateManager.recordStates()
    stateManager.test_run()
