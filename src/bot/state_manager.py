import os
import time
import json
from random import SystemRandom
from src.bot.reader import Reader
from src.bot.zenith_nash import ZenithNash
from src.bot.wizard_nash import WizardNash
from src.bot.constants import (
    POS_RANKS_LIST_PRE, POS_RANKS_DICT_PRE, POS_RANKS_LIST_PRE,
    POS_RANKS_DICT, RAKE, RAKE_CAP, IMAGE_DIR
)
from PIL import ImageGrab


class StateManager:

    def __init__(self, tableNum, debug=False, verbose=False):
        # pn means "player number", pos means "position"
        self.debug = debug
        self.verbose = verbose
        self.reader = Reader(tableNum, debug=debug)
        self.zenith = ZenithNash()
        self.wizard = WizardNash()
        self.sawFlopHeadsUp = False
        self.effStack = None
        self.interval = 1
        self.pn_to_pos = {}  # int to str dict of player numbers and their positions
        self.pos_to_pn = {}  # inversion of the above
        self.playersInHand = {}
        self.street = 'pre'
        self.lastStreet = 'pre'
        self.holeCards = ''
        self.board = ''
        self.pot = None  # total raked pot as shown in the poker client, only used post-flop
        self.lastPot = 1.5
        self.unrakedPot = 1.5
        self.pfRaises = 0  # preflop raises
        # list elements of self.line are tuples in the form of (pos, action, investment)
        # investment here is the total money the player has in front of them after
        # performing that action
        self.line = {'pre': [], 'flop': [], 'turn': [], 'river': []}  # represents the state
        self.asmptLine = self.line.copy()
        self.playerHistory = {}  # player-specific lines and investment per street
        self.pnLastActive = None  # active player from the last update
        self.pnActive = None  # currently active player
        self.numActions = 0
        # numActions is the number of actions taken in the hand when Hero first became active,
        # used to prevent multiple calls to decision methods for the same node
        self.actionsAtHeroUpdate = None
        self.lastWager = {'pn': None, 'amt': None}  # pn and amount, reset every street


    def resetPlayerHistory(self):
        for pos in POS_RANKS_LIST_PRE:
            self.playerHistory[pos] = {
                'actions': {'pre': [], 'flop': [], 'turn': [], 'river': []},
                'invested': {'pre': 0, 'flop': 0, 'turn': 0, 'river': 0},
                'totalInv': 0
            }
        self.playerHistory['SB']['invested']['pre'] = 0.5
        self.playerHistory['SB']['totalInv'] = 0.5
        self.playerHistory['BB']['invested']['pre'] = 1.0
        self.playerHistory['BB']['totalInv'] = 1.0


    def printState(self):

        def _getLineString():
            string = ''
            for key in self.line:
                if len(self.line[key]) == 0:
                    continue
                string += ', ' + key[0].upper() + key[1:] + ' '
                for action in self.line[key]:
                    string += action['agg'] + '-'
                string = string[:-1]
            return string[2:]
        
        print('\n\nHole cards: ' + self.holeCards)
        print('\nPositions: ' + str(self.pos_to_pn))
        print('\nLast wager: ' + str(self.lastWager))
        print('\nPlayers in hand: ' + str(self.playersInHand))
        print('\nActive player: ' + str(self.pnActive))
        print('\nStreet: ' + self.street)
        print('\nUnraked pot: ' + str(self.unrakedPot))
        if self.verbose:
            print('\nLine: ' + json.dumps(self.line, indent=4))
            print('\nHistory: ' + json.dumps(self.playerHistory, indent=4))
        print('\nLine string: ' + _getLineString())
        print('\n\n\n')


    def getPlayersToCheck(self, beginStreet=False):
        """
        Returns a list of players to check. It will be a list of players
        that were in the hand at the previous timestep. The list will be
        sorted in the order of street position (LJ-BB for pre-flop and
        SB-BU for post-flop), starting with the player who was active at
        the previous time-step, or the first player in street position
        rank if it is the first time-step of the street. If said player
        cannot be found in self.playersInHand, then the output list will
        begin with the next highest player in position rank who is still
        in the dictionary.
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

        if self.street == 'pre':
            ranks = POS_RANKS_DICT_PRE
            first_pn = self.pos_to_pn['LJ']
        else:
            ranks = POS_RANKS_DICT
            first_pn = self.pos_to_pn['SB']

        #ranks = POS_RANKS_DICT_PRE if self.street == 'pre' else POS_RANKS_DICT
        players.sort(key=lambda pn: ranks[self.pn_to_pos[pn]])
        if beginStreet:
            return players

        if len(self.line[self.street]) == 0:
        #if self.lastWager['pn'] == self.pos_to_pn['BB'] and self.lastWager['amt'] == 1:
            #if self.line and self.street == 'pre' and self.pnLastActive == self.pos_to_pn['BB']:
            #    return []
            if first_pn in self.playersInHand:
                #print('A')
                lap = first_pn
            else:
                #print('B')
                lap =_getNextPlayer(first_pn)
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


    def updateEffStack(self):
        """Updates the effective stack size when heads up"""
        if len(self.playersInHand) > 2:
            return
        stacks = self.reader.getStacks(self.playersInHand)
        if stacks is None:
            print('Could not read stack size. Assuming 100bb effective.')
            return
        for pn in stacks:
            stacks[pn] += self.playerHistory[self.pn_to_pos[pn]]['totalInv']
        self.effStack = min(stacks.values())


    def addAction(self, pn, agg, wager):
        """Appends an action to the line and updates the player history"""
        pos = self.pn_to_pos[pn]
        history = self.playerHistory[pos]
        pctPot = 0

        # the following will be used to convert between pct of pot and BB raise sizes
        potAfterCall = None
        lastWager = self.lastWager['amt']

        if agg in ['C', 'B', 'R']:
            # amount is the additional amount put in
            # e.g. amount is 2 if BB calls a 3x open
            # the negative term should be zero in the case of a bet
            amount = wager - history['invested'][self.street]
            if agg == 'B':
                pctPot = wager / self.unrakedPot
            elif agg == 'R':
                potAfterCall = (
                    self.unrakedPot + (lastWager - history['invested'][self.street])
                )
                pctPot = (wager - lastWager) / potAfterCall
            self.unrakedPot += amount
            history['invested'][self.street] += amount
            history['totalInv'] += amount
            if agg != 'C':
                if self.street == 'pre':
                    self.pfRaises += 1
                self.lastWager.update({'pn': pn, 'amt': wager})
        
        action = {'pos': pos, 'agg': agg, 'wager': wager, 'pctPot': pctPot}
        #action = [pos, agg, pctPot, wager]
        if agg == 'R':
            action.update({'potAfterCall': potAfterCall, 'lastWager': lastWager})
            #action += [potAfterCall, lastWager]
        self.line[self.street].append(action)
        history['actions'][self.street].append(action)
        self.numActions += 1


    def initializeState(self, holeCards):
        self.pos_to_pn, self.pn_to_pos = self.reader.getPositions()
        if not self.pos_to_pn:  # no button found
            return
        self.board = ''
        self.street = 'pre'
        self.lastStreet = 'pre'
        self.line = {'pre': [], 'flop': [], 'turn': [], 'river': []}
        self.asmptLine = self.line.copy()
        self.sawFlopHeadsUp = False
        self.effStack = None
        self.resetPlayerHistory()
        self.pot = None
        self.lastPot = 1.5
        self.unrakedPot = 1.5
        self.pfRaises = 0
        self.numActions = 0
        self.actionsAtHeroUpdate = None
        self.holeCards = holeCards
        self.playersInHand = self.pn_to_pos.copy()
        self.lastWager.update({'pn': self.pos_to_pn['BB'], 'amt': 1})
        self.pnLastActive = self.pos_to_pn['LJ']  # NOTE: first player to act pre is not necessarily LJ
        #self.pnLastActive = self.pos_to_pn['BB']


    def updateState(self):
        holeCards = self.reader.getHoleCards()
        if not holeCards:  # Hero not in hand
            return
        #pos_to_pn, pn_to_pos = self.reader.getPositions()
        elif holeCards != self.holeCards:  # or pn_to_pos[0] != self.pn_to_pos[0]:
            self.initializeState(holeCards)
            if not self.pos_to_pn:  # no button found
                return

        playersInHand = self.reader.getplayersInHand(self.playersInHand)
        self.pnActive = self.reader.getActivePlayer(playersInHand)
        
        if self.pnActive is None:
            return

        playersToCheck = self.getPlayersToCheck()
        print(playersToCheck)

        street, self.board = self.reader.getStreetAndBoard(self.street, self.board)
        updated = False
        if street != self.street:
            self.updateLastStreetActions(playersInHand, playersToCheck)
            updated = True
            if self.street == 'pre' and len(playersInHand) == 2:
                self.sawFlopHeadsUp = True
            self.lastWager.update({'pn': None, 'amt': None})

        #if self.pnActive == 0 and self.numActions == self.actionsAtHeroUpdate:
        #    return
        
        self.street = street
        self.playersInHand = playersInHand
        if updated:
            playersToCheck = self.getPlayersToCheck(beginStreet=True)
            print(playersToCheck)
        
        #if street != 'pre':
        self.pot = self.reader.getPot()

        for pn in playersToCheck:
            history = self.playerHistory[self.pn_to_pos[pn]]

            # if the player is active and it is not a situation where Hero acted and then a villain
            # quickly bet or raised on the same steet, then break
            #print(pn == self.pnLastActive and self.street == self.lastStreet and self.pot != self.lastPot)
            if pn == self.pnActive and not (
                pn == self.pnLastActive and self.street == self.lastStreet and self.pot != self.lastPot
            ):
                #print('A')
                break
            
            if pn not in self.playersInHand:
                self.addAction(pn, 'F', 0)
                continue

            wager = self.reader.getWager(pn)
            if wager is None:
                if history['invested'][self.street] > 0:
                    raise Exception("Could not read wager of player number " + str(pn))
                elif self.lastWager['amt'] is None:
                    self.addAction(pn, 'X', 0)
                    continue
                else:
                    #print('B')
                    break
            elif wager < 1 or pn == self.lastWager['pn'] and wager == self.lastWager['amt']:
                #print('C')
                break

            #print(wager)
            assert self.lastWager['amt'] is None or wager >= self.lastWager['amt']
            if wager == self.lastWager['amt']:
                self.addAction(pn, 'C', wager)
            else:
                code = 'B' if self.lastWager['amt'] is None else 'R'
                self.addAction(pn, code, wager)

        if self.pnActive == 0:
            self.handleHeroDecision()
            self.actionsAtHeroUpdate = self.numActions
            #self.handleHeroDecision()

        self.pnLastActive = self.pnActive
        self.lastPot = self.pot
        self.lastStreet = self.street


    def updateLastStreetActions(self, playersInHand, playersToCheck):
        """
        Determines if there were any actions that occurred at the end of the prior street.
        For example, if the last player to act on a given street called or folded, this
        would have been missed.

        :param playersInHand: a pn-to-pos dict of the current players in the hand
        :param playersToCheck: the list of player numbers returned by getPlayersToCheck

        NOTE: here self.playersInHand and self.street are expected to have not yet been updated
        for the current timestep
        """
        # Situation 1: Hero called on last street (Hero is pnLastActive)
        # Solution 1:
        # Sitation 2: Villain snap-called on last street after Hero raised (Hero was pnLastActive)
        # Solution 2:
        # Situation 3: Villain snap-called after another villain called (Hero was not pnLastActive)
        # Solution 3:
        # * no one but Hero could have raised since Hero would've been given a turn to act

        # NOTE: new idea... I will assume that either one unseen call happened OR
        # one unseen raise and then one unseen call...
        # look at the player in the last position for the prior street who is now still in the hand...
        #
        # if we can add THElastWager - HISamountInvestedOnPriorStreet to self.unrakedPot and
        # have it be >= rakedPot, then we can assume that he called
        #
        # if this condition is not met, assume the pnLastActive raised and then this player called
        #
        # how can we know how much was called or raised/called?
        # case call: set it equal to [max(rakedPot - RAKE_CAP, rakedPot / (1 - RAKE)) - self.unrakedPot]
        # case r/c:
        rakedPot = self.reader.getPot(street=True)
        if rakedPot is None:
            print('Cannot read raked pot... Sleeping...')
            time.sleep(5)
            rakedPot = self.reader.getPot(street=True)

        # handle cases where the remaining players checked or folded
        if self.unrakedPot >= rakedPot:
            print('TEST: ', self.unrakedPot, rakedPot)
            for pn in playersToCheck:
                if pn in playersInHand:
                    if len(self.playerHistory[self.pn_to_pos[pn]]['actions'][self.street]) == 0:
                        self.addAction(pn, 'X', 0)
                else:
                    self.addAction(pn, 'F', 0)
            # nothing further to do, just return
            return

        # handle any fold actions that may have occurred otherwise
        remaining = []
        actions = {}
        for pn in playersToCheck:
            if pn not in playersInHand:
                actions[pn] = (pn, 'F', 0)
            else:
                remaining.append(pn)

        if len(remaining) == 0:
            # this should not happen since if everyone folded then the pot would be
            # roughly the same, but this was already checked at the beginning
            raise Exception("updateLastStreetActions: no players to handle")
        
        # handle cases where the last raise on the prior street was already recorded
        # i.e. any remaining players to act called
        total = self.unrakedPot
        if self.lastWager['amt'] is not None:
            for pn in remaining:
                inv = self.playerHistory[self.pn_to_pos[pn]]['invested'][self.street]
                total += self.lastWager['amt'] - inv
        # if, by adding to the prior-street investments of the remaining players to match
        # the prior-street last wager, we can equal or exceed the raked pot, then we can
        # assume that any remaining players whose prior-street investment was lower than
        # the last wager had called
        if total >= rakedPot:
            for pn in remaining:
                #if pn == self.lastWager['pn']:
                inv = self.playerHistory[self.pn_to_pos[pn]]['invested'][self.street]
                if inv == self.lastWager['amt']:
                    break
                actions[pn] = (pn, 'C', self.lastWager['amt'])
        # otherwise, assume that Hero bet or raised and villain(s) called
        else:
            # Hero is assumed to have acted aggressively as pnLastActive
            # however, the bet or raise amount is unknown and must be estimated
            #print(self.pnLastActive, playersToCheck, remaining)
            assert self.pnLastActive == playersToCheck[0] == remaining[0] == 0

            # unrakedEst is an estimate of what the actual unraked pot is for the current
            # timestep and is used to calculate Hero's prior-street raise sizing
            unrakedEst = min(rakedPot + RAKE_CAP, rakedPot / (1 - RAKE))

            # inv_st is the total investments of all remaining players for the last street
            inv_st = 0
            for pn in remaining:
                inv_st += self.playerHistory[self.pn_to_pos[pn]]['invested'][self.street]

            # calculate raise amount and update actions
            wager = round((unrakedEst - self.unrakedPot + inv_st) / len(remaining), 2)
            #print('wager: ' + str(wager))
            actions[0] = (0, 'B' if self.lastWager['amt'] is None else 'R', wager)
            remaining.pop(0)
            for pn in remaining:
                actions[pn] = (pn, 'C', wager)

        # update the state of the hand with the actions
        for pn in playersToCheck:
            if pn in actions:
                self.addAction(*actions[pn])


    def handleHeroDecision(self):

        def _pctToWager(agg, pctPot):
            if agg == 'B':
                wager = pctPot * self.unrakedPot
            else:
                heroInv = self.playerHistory[self.pn_to_pos[0]]['invested'][self.street]
                potAfterCall = self.unrakedPot + (self.lastWager['amt'] - heroInv)
                wager = pctPot * potAfterCall + self.lastWager['amt']
            return round(wager, 2)

        def _getPreDecisionString(decision, effStack):
            agg = decision[0]
            string = {'f': 'Fold', 'c': 'Call', 'r': 'Raise', 'j': 'All-in'}[agg]
            if agg == 'r':
                pct = decision[2]
                string += ' {}% ({} BB)'.format(round(pct * 100), _pctToWager('R', pct))
            elif agg == 'j':
                string += ' ({} BB)'.format(effStack)
            return string

        def _getPostDecisionString(decision):
            agg = decision[0]
            if agg == 'R' and self.lastWager['amt'] is None:
                agg = 'B'
            string = {'F': 'Fold', 'X': 'Check', 'C': 'Call', 'B': 'Bet', 'R': 'Raise'}[agg]
            if agg in ['B', 'R']:
                pct = decision[2]
                string += ' {}% ({} BB)'.format(round(pct * 100), _pctToWager(agg, pct))
            return string

        if self.actionsAtHeroUpdate == self.numActions:
            return
        
        self.printState()
        print('\nhandleHeroDecision')
        return

        if not self.effStack and len(self.playersInHand) == 2:
            self.updateEffStack()
        effStack = 100 if not self.effStack else self.effStack

        if self.street == 'pre':
            strategy, self.asmptLine = self.zenith.getStrategy(
                self.line['pre'], effStack, self.holeCards, self.pn_to_pos[0]
            )
        else:
            if not self.sawFlopHeadsUp:
                return
            strategy, self.asmptLine = self.wizard.getStrategy(
                self.line, effStack, self.holeCards, self.board
            )

        if strategy is None:
            print('No strategy available for the current state')
            return
        
        rng = SystemRandom().random()
        tot = 0
        decision = None
        for action in strategy:
            tot += action[1]
            if rng < tot:
                decision = action
                break
        assert decision is not None

        if self.street != 'pre':
            print('Line (A): {}'.format(self.asmptLine))
        print('Strategy: {}'.format(strategy))
        print('RNG: {}'.format(round(rng * 100)))
        if self.street == 'pre':
            strDecision = _getPreDecisionString(decision, effStack)
        else:
            strDecision = _getPostDecisionString(decision)
        print('Decision: {}\n'.format(strDecision))


    def run(self):
        if self.debug:
            path = IMAGE_DIR + 'debug'
            if not os.path.exists(path):
                os.makedirs(path)
        
        while True:
            if self.debug:
                path = IMAGE_DIR + 'debug/{}.png'.format(self.reader.debugState)
                ImageGrab.grab().save(path)

            start = time.time()
            self.updateState()

            if self.debug:
                self.reader.debugState += 1
                self.reader.debugFileName = 0

            print('Ran update in {} seconds'.format(time.time() - start))
            if self.pnActive != 0:
                self.printState()
            time.sleep(self.interval)


    def test_run(self):
        self.verbose = False
        path = IMAGE_DIR + 'debug'
        files = [name for name in os.listdir(path) if os.path.isfile(path + '/' + name)]
        nums = sorted([int(file.split('.')[0]) for file in files])
        minFileNum = nums[0]
        #minFileNum = int(files[0].split('.')[0])
        self.reader.debugState = minFileNum
        for i in range(minFileNum, minFileNum + len(files)):
            keyboard.wait('f9')
            start = time.time()
            print('File number: ' + str(i))
            self.updateState()
            self.reader.debugState += 1
            self.reader.debugFileName = 0
            print('Ran update in {} seconds'.format(time.time() - start))
            self.printState()


    def recordStates(self):
        path = IMAGE_DIR + 'states'
        if not os.path.exists(path):
            os.makedirs(path)
        
        count = 0
        while True:
            keyboard.wait('f9')
            ImageGrab.grab().save('{}states/{}.png'.format(IMAGE_DIR, count))
            count += 1



if __name__ == '__main__':
    import keyboard
    keyboard.add_hotkey('esc', lambda: os.system('taskkill /im winpty-agent.exe'))
    stateManager = StateManager(1, debug=True)
    #stateManager.recordStates()
    #stateManager.run()
    stateManager.test_run()
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
