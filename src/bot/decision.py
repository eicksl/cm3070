import eval7  # type: ignore
import numpy as np
from itertools import combinations
from src.bot.constants import DECK, DECK_MAP
from src.bot.model import Model


class Decision:

    @staticmethod
    def make(state) -> list:
        features = Model.getFeatures(state)
        pred = Model.getPrediction(features)
        for i in range(3):
            pred[i] = round(pred[i] * 100, 1)
        print(pred)


    @staticmethod
    def getHandMetrics_x(holeCards: list, boardCards: list) -> tuple:
        # remove hole cards and board cards from the deck
        deck = DECK.copy()
        knownCards = holeCards + boardCards
        for card in knownCards:
            deck.remove(card)


    @staticmethod
    def getRank(cards: list) -> float:
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
            ppot = (hp[2][0] + hp[2][1] / 2 + hp[1][0] / 2) / (sums[2] + sums[1] / 2)
            npot = (hp[0][2] + hp[1][2] / 2 + hp[0][1] / 2) / (sums[0] + sums[1] / 2)

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
        ehsBet = hs + (1 - hs) * ppot
        ehsCall = ehsBet - hs * npot
        return ehsCall, ehsBet


    @staticmethod
    def getNuttedPotential(holeCards: list, boardCards: list, numOpponents: list, k=0.93) -> float:
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
    holeCards = ['7s', '6s']
    boardCards = ['3h', '4c', 'Jh', '5c', '6h']
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
        nhp = Decision.getNuttedPotential(holeCards, boardCards, numOpponents)
        print('nhp: {}'.format(nhp))
