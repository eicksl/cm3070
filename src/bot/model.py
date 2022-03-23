import numpy as np
from copy import deepcopy
from keras.models import load_model
from src.bot.util import hasFourStraight, lc_4straight
from src.bot.constants import MODEL_DIR, CARD_RANKS, POS_RANKS_DICT


class Model:

    class State:
        """Copies select info from the StateManager object"""
        def __init__(self, state):
            self.unrakedPot = state.unrakedPot
            self.playersInHand = state.playersInHand.copy()
            self.pn_to_pos = state.pn_to_pos.copy()
            self.history = deepcopy(state.history)
            self.lastAgg = state.lastAgg

    model = load_model(MODEL_DIR)

    # which index to use for each feature
    indToFeature = {
        0: 'street', 1: 'highCard', 2: 'avgRank', 3: 'flushPossible', 4: 'boardPaired',
        5: 'hasFour', 6: 'lc3flush', 7: 'lc4flush', 8: 'lc4straight', 9: 'lcOvercard',
        10: 'plAgg', 11: 'opAgg', 12: 'numAggCS', 13: 'isLastAgg', 14: 'spr',
        15: 'amtToCall', 16: 'numPlayers', 17: 'relPos'
    }

    # indices of input array to normalize
    minmax = [0, 1, 2, 16, 17]
    unbounded = [10, 11, 12, 14]
    #boolean = [3, 4, 5, 6, 7, 8, 9, 13]

    # maps indices to (min, max) tuples for min-max normalization
    minmaxMap = {0: (1, 3), 1: (1, 13), 2: (1, 13), 16: (2, 6), 17: (1/6, 1)}

    @staticmethod
    def getPrediction(features: dict) -> np.ndarray:
        fa = np.zeros((1, len(Model.indToFeature)), dtype=np.float32)  # feature array
        for i in range(fa.size):
            fa[0][i] = features[Model.indToFeature[i]]
        Model.normalize(fa)
        return Model.model.predict(fa)[0]
    

    @staticmethod
    def normalize(fa: np.ndarray) -> None:
        for i in Model.minmax:
            denom = Model.minmaxMap[i][1] - Model.minmaxMap[i][0]
            fa[0][i] = (fa[0][i] - Model.minmaxMap[i][0]) / denom

        for i in Model.unbounded:
            fa[0][i] = fa[0][i] / (1 + fa[0][i])


    @staticmethod
    def getFeatures(state) -> dict:
        pos = state.pn_to_pos[state.pnActive]
        boardCards = []
        boardSuits = []
        for i in range(0, len(state.board), 2):
            boardCards.append(state.board[i])
            boardSuits.append(state.board[i+1])
        cardRanks = [CARD_RANKS[x] for x in boardCards]
        highCard = max(cardRanks)
        has4flush = len(boardSuits) - len(set(boardSuits)) >= 3
        has4straight = hasFourStraight(boardCards)
        lcDominantSuit = boardSuits[-1] == max(set(boardSuits), key=boardSuits.count)
        flushPossible = len(boardSuits) - len(set(boardSuits)) >= 2

        return {
            'street': ['pre', 'flop', 'turn', 'river'].index(state.street),
            'highCard': highCard,
            'avgRank': sum(cardRanks) / len(cardRanks),
            'flushPossible': flushPossible,
            'boardPaired': len(boardCards) != len(set(boardCards)),
            'hasFour': has4straight or has4flush,
            'lc3flush': flushPossible and lcDominantSuit,
            'lc4flush': has4flush and lcDominantSuit,
            'lc4straight': has4straight and lc_4straight(boardCards),
            'lcOvercard': highCard == cardRanks[-1],
            'plAgg': state.history[pos]['r'] / state.history[pos]['c'],
            'opAgg': Model.getOpponentAgg(state.pnActive, state),
            'numAggCS': state.numAggCS,
            'isLastAgg': state.pnActive == state.lastAgg,
            'spr': Model.spr(state.pnActive, state),
            'amtToCall': Model.getAmtToCall(state.pnActive, state),
            'numPlayers': len(state.playersInHand),
            'relPos': Model.getRelPos(state.pnActive, state)
        }

    
    @staticmethod
    def getOpponentAgg(pn: int, state) -> float:
        """
        Finds the aggression factor for the opponent(s). If there are more than two players in
        the hand, the last aggressor's AF is used unless the player is the last aggressor - in
        which case, the average AF of all opponents is used. The AF for any given player is
        calculated as (bets + raises + 1) / (checks + calls + 1).

        :param pn: identifier [0, 5] of the player to act
        :param state: the relevant state
        :returns: the AF as a float
        """
        if pn != state.lastAgg:
            pos = state.pn_to_pos[state.lastAgg]
            return state.history[pos]['r'] / state.history[pos]['c']
        
        afTotal = 0
        for player in state.playersInHand:
            if player != pn:
                pos = state.pn_to_pos[player]
                afTotal += state.history[pos]['r'] / state.history[pos]['c']
        
        return afTotal / (len(state.playersInHand) - 1)


    @staticmethod
    def getEffPot(pn: int, state) -> float:
        """Calculates the effective pot size"""
        pos = state.pn_to_pos[pn]
        lastWager = 0 if state.lastWager['amt'] is None else state.lastWager['amt']
        diff = lastWager - state.history[pos]['invested'][state.street]
        if state.numAggCS == 0 or diff <= state.stacks[pn]:
            return state.unrakedPot

        pot = state.unrakedPot
        streetStack = state.stacks[pn] + state.history[pos]['invested'][state.street]
        for key in state.history:
            if key != pos and state.history[key]['invested'][state.street] > streetStack:
                pot -= state.history[key]['invested'][state.street] - streetStack

        return pot


    @staticmethod
    def spr(pn: int, state) -> float:
        """
        Returns the effective stack-to-pot ratio. If multiway, the last aggressor's stack is
        used to determine the effective stack; however, if the player is the last aggressor,
        the average opponent stack is used.
        """
        pot = Model.getEffPot(pn, state)
        if pn != state.lastAgg:
            return min(state.stacks[pn], state.stacks[state.lastAgg]) / pot

        numOpponents = len(state.playersInHand) - 1
        stacksTotal = 0
        for player in state.playersInHand:
            if player != pn:
                stacksTotal += state.stacks[player]

        avgOppStack = stacksTotal / numOpponents
        return min(state.stacks[pn], avgOppStack) / pot


    @staticmethod
    def getAmtToCall(pn: int, state) -> float:
        """Calculates the amount to call as a percentage of the pot."""
        if state.numAggCS == 0:
            return 0
        
        pos = state.pn_to_pos[pn]
        lastWager = 0 if state.lastWager['amt'] is None else state.lastWager['amt']
        diff = lastWager - state.history[pos]['invested'][state.street]
        amtToCall = state.stacks[pn] if diff > state.stacks[pn] else diff
        
        return amtToCall / Model.getEffPot(pn, state)


    @staticmethod
    def getRelPos(pn: int, state) -> float:
        """
        Calculates the relative position of a player divided by the number of players in the
        hand. If the player is on the button, the output will be 1. Otherwise, the output will be
        in the range (0, 1).
        """
        posRank = lambda pn: POS_RANKS_DICT[state.pn_to_pos[pn]]
        relPos = sorted(state.playersInHand.keys(), key=posRank).index(pn) + 1
        return relPos / len(state.playersInHand)
