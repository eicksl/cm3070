import math
import eval7  # type: ignore
import numpy as np
from itertools import combinations
if __name__ != '__main__':
    from src.bot.model import Model
from src.bot.constants import DECK, DECK_MAP, POS_RANKS_DICT, RAKE, RAKE_CAP
from src.bot.util import mapRange


class Decision:

    # pre-flop ranges
    call_vs_6 = set(['JJ', 'TT', 'AQs', 'AQo', 'AJs', 'KQs'])
    raise_vs_6 = set(['AA', 'KK', 'QQ', 'AKs', 'AKo'])
    call_vs_20 = set(['QQ', 'JJ', 'AKs', 'AKo'])
    raise_vs_20 = set(['AA', 'KK'])


    # bet and raise sizes as pct of pot
    betSizes = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
    raiseSizes = [0.3, 0.5, 0.7, 0.9, 1.1, 1.3]

    @staticmethod
    def make(state) -> list:
        if state.street == 'pre':
            return Decision.make_pre(state)
        
        m = Decision.getMetrics(state)
        unopened = state.numAggCS == 0  # no one bet yet

        # check to PFR on flop when OOP
        if unopened and m['heroRelPos'] < m['laRelPos'] and state.street == 'flop':
            return [('X', 1)]

        valuePct = Decision.getValuePct(state, m)
        if valuePct > 0:
            if unopened:
                if m['heroRelPos'] < 1:
                    checkGetsAction = 1 - Model.predAllCheck(state)
                    return [('X', checkGetsAction), ('B', 1 - checkGetsAction, valuePct)]
                else:
                    return [('B', 1, valuePct)]
            else:
                return [('R', 1, valuePct)]

        if not unopened and Decision.canCall(state, m):
            return [('C', 1)]

        bluffPct = Decision.getBluffPct(state, m)
        if bluffPct > 0:
            if unopened:
                return [('B', 1, bluffPct)]
            else:
                return [('R', 1, bluffPct)]

        if unopened:
            return [('X', 1)]
        else:
            return [('F', 1)]


    @staticmethod
    def make_pre(state) -> list:
        wager = state.lastWager['amt']
        heroInv = state.history[state.pn_to_pos[0]]['invested'][state.street]
        hand = state.zenith.convertHoleCards(state.holeCards)

        if wager <= 6:
            if hand in Decision.raise_vs_6:
                return [('R', 1, 1.05)]
            elif hand in Decision.call_vs_6:
                return [('C', 1)]
        elif wager <= 20:
            if hand in Decision.raise_vs_20:
                return [('R', 1, 0.8)]
            elif hand in Decision.call_vs_20 and heroInv > 1:
                return [('C', 1)]
        elif hand in Decision.raise_vs_20:
            return [('R', 1, 1000)]

        if state.lastWager['pn'] == 0:  # limped to Hero in BB
            return [('X', 1)]
        
        return [('F', 1)]


    @staticmethod
    def getValuePct(state, m: dict) -> float:
        """
        If Hero's hand is strong enough to wager for value, it finds the most suitable sizing
        to use as a percentage of the pot. Returns 0 if the hand is not strong enough.
        """
        if state.numAggCS == 0:
            k = 0.8 if state.street != 'flop' and m['postAgg'] == 0 else 0.7
            agg = 'B'
            options = Decision.betSizes
        else:
            k = 0.93
            agg = 'R'
            options = Decision.raiseSizes

        z = 1 + m['postAgg'] + m['numOppCall'] * 1 / m['potOdds']
        #ehs = m['ehsAgg'] ** (1 + m['postAgg'])
        ehs = m['ehsAgg'] ** z
        print('getValuePct EHS:', ehs)
        if ehs < k:
            return 0
        
        # `worth` is basically how much we can value bet based on our hand strength
        worth = mapRange(m['ehsAgg'], k, 1, options[0], options[-1])
        # find the nearest size in the action-space list
        nearest = min(options, key=lambda x: abs(x - worth))
        # get its index
        index = options.index(nearest)
        # use the sizes up to that index
        sizes = options[:index+1]

        # multiply the complement of the predicted fold frequency response to using each size
        # by the size itself to determine which size is best to use
        sizeBest = evBest = 0
        for pct in sizes:
            if agg == 'B':
                putInPot = pct * state.unrakedPot
            else:
                putInPot = state.pctToWager('R', pct) - m['heroInv']
            if putInPot < 1:  # cannot wager less than 1 big blind
                continue
            getsAction = 1 - Model.predAllFold(state, agg, pct)
            ev = getsAction * putInPot
            if ev > evBest:
                evBest = ev
                sizeBest = pct

        return sizeBest


    @staticmethod
    def getBluffPct(state, m: dict) -> float:
        """
        If Hero's hand is suitable to bluff, it finds the most suitable sizing
        to use as a percentage of the pot. Returns 0 if the hand is not suitable.
        """
        if state.numAggCS == 0:
            k = 0.5
            # don't bluff if our hand has showdown value
            ehs = m['ehsAgg'] ** (1 + m['postAgg'])
            print('getBluffPct EHS:', ehs)
            if ehs > k:
                return 0
            agg = 'B'
            options = Decision.betSizes
        else:
            agg = 'R'
            options = Decision.raiseSizes
        
        sizeBest = evBest = 0
        for pct in options:
            if agg == 'B':
                putInPot = pct * state.unrakedPot
            else:
                putInPot = state.pctToWager('R', pct) - m['heroInv']
            if putInPot < 1:
                continue
            succeeds = Model.predAllFold(state, agg, pct)
            if state.street == 'river':
                ev = succeeds * m['rakedPot'] - (1 - succeeds) * putInPot
            else:
                ev = (
                    succeeds * m['rakedPot'] + (1 - succeeds)
                    * (m['nhp'] * m['rakedPot'] - (1 - m['nhp']) * putInPot)
                )
            if ev > evBest:
                evBest = ev
                sizeBest = pct
        
        return sizeBest


    @staticmethod
    def canCall(state, m: dict) -> bool:
        """
        Returns True if the hand makes for a suitable call, and False otherwise.
        """        
        z = m['postAgg'] + m['numOppCall'] * 1 / m['potOdds']
        ehs = m['ehsCall'] ** z
        print('canCall EHS:', ehs)
        if ehs >= 0.6:
            if m['potOdds'] > 20:
                return True

            r = mapRange(m['potOdds'], 20, 1, 0, 9)
            q = 1 / (r - 10) ** 2
            k = mapRange(q, 0, 1, 0.6, 1)
            print('canCall k', k)

            if ehs > k:
                return True
        
        if state.street != 'river':
            ev = m['nhp'] * m['rakedPot'] - (1 - m['nhp']) * m['callAmt']
            if ev > 0:
                return True

        return False


    @staticmethod
    def getMetrics(state) -> dict:
        lstHole = [state.holeCards[:2], state.holeCards[2:]]
        lstBoard = []
        for i in range(0, len(state.board), 2):
            lstBoard.append(state.board[i] + state.board[i+1])
        opponents = len(state.playersInHand)-1
        hs, ppot, npot = Decision.getHandMetrics1(lstHole, lstBoard, opponents)
        ehsCall, ehsAgg = Decision.getEffHandStrength(hs, ppot, npot)
        nhp = Decision.getNuttedPotential1(lstHole, lstBoard, opponents)
        postAgg, pps, numOppCall = Decision.getPostMetrics(state)
        rakedPot, heroInv, callAmt, potOdds = Decision.getStateMetrics(state)
        heroRelPos, laRelPos = Decision.getRelPos(state)
        return {
            'hs': hs, 'ppot': ppot, 'npot': npot, 'ehsCall': ehsCall, 'ehsAgg': ehsAgg,
            'postAgg': postAgg, 'pps': pps, 'heroRelPos': heroRelPos, 'laRelPos': laRelPos,
            'pct': Decision.lastWagerAsPct(state), 'nhp': nhp, 'rakedPot': rakedPot,
            'heroInv': heroInv, 'callAmt': callAmt, 'potOdds': potOdds, 'numOppCall': numOppCall
        }


    @staticmethod
    def lastWagerAsPct(state) -> float:
        """
        Returns the last bet or raise as a percentage of the pot.
        """
        if state.numAggCS == 0:
            return 0
        line = state.line[state.street]
        for i in range(len(line)-1, -1, -1):
            action = line[i]
            if action['agg'] in ['B', 'R']:
                return action['pctPot']
        raise Exception('Street line does not contain a non-zero wager')


    @staticmethod
    def getStateMetrics(state) -> tuple:
        """
        Returns the following useful metrics pertaining to the current state:
        the raked pot, Hero's street investment, the call amount, the pot odds
        """
        rakedPot = state.unrakedPot - min(RAKE * state.unrakedPot, RAKE_CAP)
        heroInv = state.history[state.pn_to_pos[0]]['invested'][state.street]
        if state.lastWager['amt'] is None:
            callAmt = 0
            potOdds = math.inf
        else:
            callAmt = state.lastWager['amt'] - heroInv
            potOdds = rakedPot / callAmt
        return rakedPot, heroInv, callAmt, potOdds


    @staticmethod
    def getPostMetrics(state) -> tuple:
        """
        Iterates over the line to find the total number of bets or raises that occurred
        post-flop as well as the number of players who saw each post-flop betting round
        up to the current round.
        """
        totAgg = 0
        pps = {}  # number of players per street
        pps[state.street] = len(state.playersInHand)
        numOppCall = 0  # num of opponents that called the last wager

        for street in state.line:
            if street == 'pre':
                continue
            players = set()
            for action in state.line[street]:
                if action['agg'] in ['B', 'R']:
                    totAgg += 1
                if street != state.street:
                    players.add(action['pos'])
                elif action['agg'] == 'F':
                    pps[state.street] += 1
                if street == state.street:
                    if action['agg'] == 'C' and action['wager'] == state.lastWager['amt']:
                        numOppCall += 1
            pps[street] = len(players)
        
        return totAgg, pps, numOppCall


    @staticmethod
    def getRelPos(state) -> float:
        """
        Returns a float in range [0, 1] representing Hero's position relative to the remaining
        opponents in the hand. For example, 0 is returned if Hero is first to act, and 1 is
        returned if Hero is last to act. In other cases, a fractional number is returned. Also
        returns the relative position of the last aggressor.
        """
        posRank = lambda pn: POS_RANKS_DICT[state.pn_to_pos[pn]]
        ranked = sorted(state.playersInHand.keys(), key=posRank)
        assert state.pnActive == 0
        hero = ranked.index(0) / (len(ranked) - 1)
        la = ranked.index(state.lastAgg) / (len(ranked) - 1)
        return hero, la


    @staticmethod
    def getRank(cards: list) -> int:
        hand = [eval7.Card(string) for string in cards]
        return eval7.evaluate(hand)


    @staticmethod
    def getHandStrength(holeCards: list, boardCards: list, numOpponents: int, deck: list) -> float:
        better = tied = worse = 0
        heroRank = Decision.getRank(holeCards + boardCards)

        for oppCombo in combinations(deck, 2):
            oppCards = list(oppCombo)
            oppRank = Decision.getRank(oppCards + boardCards)

            if heroRank > oppRank:
                better += 1
            elif heroRank == oppRank:
                tied += 1
            else:
                worse += 1

        return ((better + tied / 2) / (better + tied + worse)) ** numOpponents


    @staticmethod
    def getHandMetrics1(holeCards: list, boardCards: list, numOpponents: int) -> tuple:
        # remove hole cards and board cards from the deck
        deck = DECK.copy()
        knownCards = holeCards + boardCards
        for card in knownCards:
            deck.remove(card)
        
        better = tied = worse = 0  # used for hand strength
        hp = np.zeros((3, 3), dtype=np.uint)  # used for hand potential
        heroRank = Decision.getRank(holeCards + boardCards)

        for oppCombo in combinations(deck, 2):
            oppCards = list(oppCombo)
            oppRank = Decision.getRank(oppCards + boardCards)

            if heroRank > oppRank:
                better += 1
                hpIndex = 0
            elif heroRank == oppRank:
                tied += 1
                hpIndex = 1
            else:
                worse += 1
                hpIndex = 2

            if len(boardCards) == 5:
                continue

            deck.remove(oppCards[0])
            deck.remove(oppCards[1])

            for nextCard in deck:
                board = boardCards + [nextCard]

                hpHeroRank = Decision.getRank(holeCards + board)
                hpOppRank = Decision.getRank(oppCards + board)
                if hpHeroRank > hpOppRank:
                    hp[hpIndex][0] += 1
                elif hpHeroRank == hpOppRank:
                    hp[hpIndex][1] += 1
                else:
                    hp[hpIndex][2] += 1
            
            deck.add(oppCards[0])
            deck.add(oppCards[1])

        sums = np.sum(hp, axis=1)
        hs = ((better + tied / 2) / (better + tied + worse)) ** numOpponents
        if len(boardCards) == 5:
            ppot = npot = 0
        else:
            ppot = (hp[2][0] + hp[2][1] / 2 + hp[1][0] / 2) / (sums[2] + sums[1] / 2 + np.finfo(np.float32).eps)
            npot = (hp[0][2] + hp[1][2] / 2 + hp[0][1] / 2) / (sums[0] + sums[1] / 2 + np.finfo(np.float32).eps)

        return hs, ppot, npot


    @staticmethod
    def getHandMetrics2(holeCards: list, boardCards: list, numOpponents: int) -> tuple:

        def _getRank(hand: list) -> float:
            hand.sort(key=mapCard)
            strHand = ''.join(hand)
            if strHand in memo:
                rank = memo[strHand]
            else:
                rank = Decision.getRank(hand)
                memo[strHand] = rank
            return rank
        
        # remove hole cards and board cards from the deck
        deck = DECK.copy()
        knownCards = holeCards + boardCards
        for card in knownCards:
            deck.remove(card)
        
        memo = {}
        mapCard = lambda card: DECK_MAP[card]
        better = tied = worse = 0  # used for hand strength
        hp = np.zeros((3, 3), dtype=np.uint)  # used for hand potential
        heroRank = Decision.getRank(holeCards + boardCards)

        for oppCombo in combinations(deck, 2):
            oppCards = list(oppCombo)
            oppRank = Decision.getRank(oppCards + boardCards)

            if heroRank > oppRank:
                better += 1
                hpIndex = 0
            elif heroRank == oppRank:
                tied += 1
                hpIndex = 1
            else:
                worse += 1
                hpIndex = 2

            if len(boardCards) == 5:
                continue

            deck.remove(oppCards[0])
            deck.remove(oppCards[1])

            for boardCombo in combinations(deck, 5 - len(boardCards)):
                board = boardCards + list(boardCombo)
                
                hpHeroRank = _getRank(board + holeCards)
                hpOppRank = _getRank(board + oppCards)

                if hpHeroRank > hpOppRank:
                    hp[hpIndex][0] += 1
                elif hpHeroRank == hpOppRank:
                    hp[hpIndex][1] += 1
                else:
                    hp[hpIndex][2] += 1
            
            deck.add(oppCards[0])
            deck.add(oppCards[1])

        sums = np.sum(hp, axis=1)
        hs = ((better + tied / 2) / (better + tied + worse)) ** numOpponents
        if len(boardCards) == 5:
            ppot = npot = 0
        else:
            ppot = (hp[2][0] + hp[2][1] / 2 + hp[1][0] / 2) / (sums[2] + sums[1] / 2)
            npot = (hp[0][2] + hp[1][2] / 2 + hp[0][1] / 2) / (sums[0] + sums[1] / 2)

        return hs, ppot, npot


    @staticmethod
    def getEffHandStrength(hs: float, ppot: float, npot: float) -> tuple:
        ehsAgg = hs + (1 - hs) * ppot
        ehsCall = ehsAgg - hs * npot
        return ehsCall, ehsAgg


    @staticmethod
    def getNuttedPotential1(holeCards: list, boardCards: list, numOpponents: list, k=0.955) -> float:
        if len(boardCards) == 5:
            return None
        
        deck = DECK.copy()
        knownCards = holeCards + boardCards
        for card in knownCards:
            deck.remove(card)

        nutted = total = 0

        for card in list(deck):
            deck.remove(card)
            board = boardCards + [card]
            hs = Decision.getHandStrength(holeCards, board, numOpponents, deck)
            deck.add(card)
            total += 1
            if hs > k:
                nutted += 1

        return nutted / total


    @staticmethod
    def getNuttedPotential2(holeCards: list, boardCards: list, numOpponents: list, k=0.955) -> float:
        if len(boardCards) == 5:
            return None
        
        deck = DECK.copy()
        knownCards = holeCards + boardCards
        for card in knownCards:
            deck.remove(card)

        nutted = total = 0

        for combo in combinations(deck, 5 - len(boardCards)):
            runout = list(combo)
            for card in runout:
                deck.remove(card)
            board = boardCards + runout
            hs = Decision.getHandStrength(holeCards, board, numOpponents, deck)
            for card in runout:
                deck.add(card)
            total += 1
            if hs > k:
                nutted += 1

        return nutted / total



if __name__ == '__main__':
    holeCards = ['Jd', 'Js']
    boardCards = ['8c', '6s', '2s']
    numOpponents = 1

    print('holeCards: ' + str(holeCards))
    print('boardCards: ' + str(boardCards))
    #hs, ppot2, npot2 = Decision.getHandMetrics2(holeCards, boardCards, numOpponents)
    #print('\nhs: {}\n'.format(hs))
    #print('ppot2: {}, npot2: {}'.format(ppot2, npot2))
    #ehsCall2, ehsBet2 = Decision.getEffHandStrength(hs, ppot2, npot2)
    #print('ehsCall2: {}, ehsBet2: {}\n'.format(ehsCall2, ehsBet2))
    hs, ppot1, npot1 = Decision.getHandMetrics1(holeCards, boardCards, numOpponents)
    print('\nhs: {}\n'.format(hs))
    print('ppot1: {}, npot1: {}'.format(ppot1, npot1))
    ehsCall1, ehsBet1 = Decision.getEffHandStrength(hs, ppot1, npot1)
    print('ehsCall1: {}, ehsBet1: {}\n'.format(ehsCall1, ehsBet1))
    if len(boardCards) < 5:
        nhp1 = Decision.getNuttedPotential1(holeCards, boardCards, numOpponents)
        print('nhp1: {}'.format(nhp1))
        nhp2 = Decision.getNuttedPotential2(holeCards, boardCards, numOpponents)
        print('nhp2: {}'.format(nhp2))
