class State:
    """
    Copies select info from the StateManager object so as not to modify it.
    Used when predicting the probability of hypothetical game tree nodes.
    """
    def __init__(self, state):
        self.pnActive = state.pnActive
        self.pot = state.unrakedPot
        self.street = state.street
        self.board = state.board
        self.playersInHand = state.playersInHand.copy()
        self.stacks = state.stacks.copy()
        self.lastWager = state.lastWager.copy()
        self.pn_to_pos = state.pn_to_pos
        self.inv = {}
        self.actions = {}
        for pos in state.history:
            pn = state.pos_to_pn[pos]
            self.inv[pn] = state.history[pos]['invested'][state.street]
            self.actions[pn] = {
                'r': state.history[pos]['r'],
                'c': state.history[pos]['c']
            }
        self.lastAgg = state.lastAgg
        self.numAggCS = state.numAggCS
        self.getNextPlayer = state.getNextPlayer
