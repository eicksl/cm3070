import numpy as np
from keras.models import load_model
from src.bot.util import hasFourStraight, lc_4straight
from src.bot.constants import MODEL_DIR, CARD_RANKS, POS_RANKS_DICT
from src.bot.state import State


class Model:

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

    # maps indices to (min, max) tuples for min-max normalization
    minmaxMap = {0: (1, 3), 1: (1, 13), 2: (1, 13), 16: (2, 6), 17: (1/6, 1)}

    @staticmethod
    def pred(state, agg: str, pct: float=0) -> np.ndarray:
        """
        Given a state and an action, predict the probability distribution for the next
        opponent to act assuming that the action is taken by the currently active player.
        If a StateManager object is passed, relevant info will be copied so as not to
        modify the original state.

        :param state: a State or StateManager instance
        :param agg: action code in the set {'F', 'X', 'C', 'B', 'R'}
        :param pct: a percentage of pot specified for bet or raise actions
        """
        if not isinstance(state, State):
            state = State(state)

        pn = state.pnActive
        match agg:
            case 'F':
                del state.playersInHand[pn]
            case 'X':
                state.actions[pn]['c'] += 1
            case 'C':
                callAmt = min(state.stacks[pn], state.lastWager['amt'] - state.inv[pn])
                state.pot += callAmt
                state.stacks[pn] -= callAmt
                state.inv[pn] += callAmt
                state.actions[pn]['c'] += 1
            case 'B':
                betAmt = pct * state.pot
                if betAmt > state.stacks[pn]:
                    raise Exception("Bet amount cannot exceed the player's stack size")
                state.pot += betAmt
                state.stacks[pn] -= betAmt
                state.inv[pn] += betAmt
                state.lastWager.update({'pn': pn, 'amt': betAmt})
                state.lastAgg = pn
                state.actions[pn]['r'] += 1
                state.numAggCS += 1
            case 'R':
                callAmt = state.lastWager['amt'] - state.inv[pn]
                state.stacks[pn] -= callAmt
                potAfterCall = state.pot + callAmt
                raiseAmt = min(state.stacks[pn], pct * potAfterCall)
                totAmt = callAmt + raiseAmt
                if raiseAmt > state.stacks[pn]:
                    raise Exception("Raise amount cannot exceed the player's stack size")
                state.pot += totAmt
                state.stacks[pn] -= raiseAmt
                state.inv[pn] += totAmt
                wager = state.lastWager['amt'] + raiseAmt
                state.lastWager.update({'pn': pn, 'amt': wager})
                state.lastAgg = pn
                state.actions[pn]['r'] += 1
                state.numAggCS += 1
            case _:
                raise Exception('Invalid action code')

        state.pnActive = state.getNextPlayer(pn)
        fa = Model.getFeatureArray(state)

        return Model.model.predict(fa)[0]


    @staticmethod
    def predAllFold(state, agg: str, pct: float) -> float:
        """
        Given a state and a bet or raise action, predict the probability of all
        remaining opponents folding.
        """
        if not isinstance(state, State):
            state = State(state)

        fold = Model.pred(state, agg, pct)[0]
        if len(state.playersInHand) == 2:
            return fold
        while len(state.playersInHand) > 2:
            fold *= Model.pred(state, 'F')[0]

        return fold


    @staticmethod
    def predAllCheck(state) -> float:
        """
        Given a state, predict the probability of all remaining opponents checking
        after the currently active player checks.
        """
        if not isinstance(state, State):
            state = State(state)

        posRank = lambda pn: POS_RANKS_DICT[state.pn_to_pos[pn]]
        pnLast = sorted(state.playersInHand.keys(), key=posRank)[-1]

        check = Model.pred(state, 'X')[1]
        if state.pnActive == pnLast:
            return check
        while state.pnActive != pnLast:
            check *= Model.pred(state, 'X')[1]

        return check
    

    @staticmethod
    def normalize(fa: np.ndarray) -> None:
        for i in Model.minmax:
            denom = Model.minmaxMap[i][1] - Model.minmaxMap[i][0]
            fa[0][i] = (fa[0][i] - Model.minmaxMap[i][0]) / denom

        for i in Model.unbounded:
            fa[0][i] = fa[0][i] / (1 + fa[0][i])


    @staticmethod
    def getFeatureArray(state: State) -> np.ndarray:
        """
        Converts the state object to a normalized array of features that can be
        understood by the opponent model.
        """
        pn = state.pnActive
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

        features = {
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
            'plAgg': state.actions[pn]['r'] / state.actions[pn]['c'],
            'opAgg': Model.getOpponentAgg(state),
            'numAggCS': state.numAggCS,
            'isLastAgg': pn == state.lastAgg,
            'spr': Model.spr(state),
            'amtToCall': Model.getAmtToCall(state),
            'numPlayers': len(state.playersInHand),
            'relPos': Model.getRelPos(state)
        }

        fa = np.zeros((1, len(Model.indToFeature)), dtype=np.float32)  # feature array
        for i in range(fa.size):
            fa[0][i] = features[Model.indToFeature[i]]
        Model.normalize(fa)

        return fa

    
    @staticmethod
    def getOpponentAgg(state: State) -> float:
        """
        Finds the aggression factor for the opponent(s). If there are more than two players in
        the hand, the last aggressor's AF is used unless the player is the last aggressor - in
        which case, the average AF of all opponents is used. The AF for any given player is
        calculated as (bets + raises + 1) / (checks + calls + 1).

        :param pn: identifier [0, 5] of the player to act
        :param state: the relevant state
        :returns: the AF as a float
        """
        pn = state.pnActive
        if pn != state.lastAgg:
            return state.actions[pn]['r'] / state.actions[pn]['c']
        
        afTotal = 0
        for player in state.playersInHand:
            if player != pn:
                afTotal += state.actions[pn]['r'] / state.actions[pn]['c']
        
        return afTotal / (len(state.playersInHand) - 1)


    @staticmethod
    def getEffPot(state: State) -> float:
        """Calculates the effective pot size"""
        pn = state.pnActive
        lastWager = 0 if state.lastWager['amt'] is None else state.lastWager['amt']
        diff = lastWager - state.inv[pn]
        if state.numAggCS == 0 or diff <= state.stacks[pn]:
            return state.pot

        pot = state.pot
        streetStack = state.stacks[pn] + state.inv[pn]
        for key in state.inv:
            if key != pn and state.inv[key] > streetStack:
                pot -= state.inv[key] - streetStack

        return pot


    @staticmethod
    def spr(state: State) -> float:
        """
        Returns the effective stack-to-pot ratio. If multiway, the last aggressor's stack is
        used to determine the effective stack; however, if the player is the last aggressor,
        the average opponent stack is used.
        """
        pn = state.pnActive
        pot = Model.getEffPot(state)
        if pn != state.lastAgg:
            return min(state.stacks[pn], state.stacks[state.lastAgg]) / pot

        stacksTotal = 0
        for player in state.playersInHand:
            if player != pn:
                stacksTotal += state.stacks[player]

        avgOppStack = stacksTotal / (len(state.playersInHand) - 1)
        return min(state.stacks[pn], avgOppStack) / pot


    @staticmethod
    def getAmtToCall(state: State) -> float:
        """Calculates the amount to call as a percentage of the pot."""
        if state.numAggCS == 0:
            return 0
        
        pn = state.pnActive
        pos = state.pn_to_pos[pn]
        lastWager = 0 if state.lastWager['amt'] is None else state.lastWager['amt']
        diff = lastWager - state.inv[pn]
        amtToCall = state.stacks[pn] if diff > state.stacks[pn] else diff
        
        return amtToCall / Model.getEffPot(state)


    @staticmethod
    def getRelPos(state: State) -> float:
        """
        Calculates the relative position of a player divided by the number of players in the
        hand. If the player is on the button, the output will be 1; otherwise, the output will be
        in the range (0, 1).
        """
        posRank = lambda pn: POS_RANKS_DICT[state.pn_to_pos[pn]]
        relPos = sorted(state.playersInHand.keys(), key=posRank).index(state.pnActive) + 1
        return relPos / len(state.playersInHand)
