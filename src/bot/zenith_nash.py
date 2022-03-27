import json
import time
import requests
from src.bot.constants import CONFIG_DIR, CARD_RANKS


class ZenithNash:

    def __init__(self):
        self.loginUrl = (
            "https://zenith.poker/oauth/authorize/?response_type=code"
            + "&redirect_uri=https://preflop.zenith.poker/auth/token"
            + "&client_id=8FIAStlXPCyq9mm5KoajXlYPeVtKvJYMzjZKbDL5"
        )
        self.refreshUrl = "https://preflop.zenith.poker/auth/refresh"  # POST
        self.baseUrl = "https://preflop.zenith.poker/api/range_sets"
        self.versions = {
            '50_STD': '20211116',
            '100_STD': '20220109',
            '200_STD': '20210517'
        }
        # if actual raise amt is < lowest raise option - thresh OR > highest + thresh,
        # then zenith is not used
        self.thresh = 20
        self.session = requests.Session()
        with open(CONFIG_DIR + 'rfi-ranges.json') as file:
            self.rfi = json.loads(file.read())
        with open(CONFIG_DIR + 'zenith-login-cookies.txt') as file:
            self.loginCookies = file.read().strip()
        with open(CONFIG_DIR + 'zenith-cookies.txt') as file:
            self.cookies = file.read().strip()
        with open(CONFIG_DIR + 'zenith-login-headers.json') as file:
            self.loginHeaders = json.loads(file.read())
        with open(CONFIG_DIR + 'zenith-headers.json') as file:
            self.headers = json.loads(file.read())
        with open(CONFIG_DIR + 'zenith-rf-headers.json') as file:
            self.rfHeaders = json.loads(file.read())
        with open(CONFIG_DIR + 'zenith-tokens.json') as file:
            tokens = json.loads(file.read())
        self.refreshToken = tokens['refresh_token']
        self.lastRefresh = tokens['lastRefresh']
        self.loginHeaders.update({'Cookie': self.loginCookies})
        self.rfHeaders.update({'Cookie': self.cookies})
        self.headers.update({
            'Authorization': 'Bearer ' + tokens['access_token'],
            'Cookie': self.cookies
        })
        self.session.headers = self.headers
        self.cache = {}  # maps node paths to action options
        with open(CONFIG_DIR + 'zenith-cache.txt') as file:
            lines = file.read().split('\n')
            for i in range(0, len(lines), 2):
                self.cache[lines[i]] = json.loads(lines[i+1])
        self.inv = {}
        self.resetAsmptValues()
        self.indices = self.getIndices()


    def resetAsmptValues(self):
        # used for calculating the assumptive state
        self.pot = 1.5
        self.lastWager = 1.0
        self.inv.update({'LJ': 0, 'HJ': 0, 'CO': 0, 'BU': 0, 'SB': 0.5, 'BB': 1.0})


    def getIndices(self):
        """
        Generates a dict that will map any given preflop hand to its appropriate index
        in the array returned by JSON responses.
        """
        indices = {}
        data = self.rfi['LJ']['100_STD']['frequency']
        for i in range(len(data)):
            indices[data[i]['_row']] = i
        return indices


    def login(self):
        self.session.headers = self.loginHeaders
        resp = self.session.get(self.loginUrl, allow_redirects=False)
        self.session.headers = self.loginHeaders.copy().update({
            'Cookie': self.cookies, 'TE': 'trailers'
        })
        resp = self.session.get(resp.headers['Location'], allow_redirects=False)

        url = resp.headers['location']
        tokens = {}
        params = url.split('?')[1].split('&')
        for string in params:
            tok = string.split('=')
            tokens[tok[0]] = tok[1]
        del tokens['expires_in']

        resp = self.session.get(url)
        if resp.status_code == 200:
            print('Logged in to Zenith successfully')
        
        self._saveTokens(tokens)
        self.session.headers = self.headers


    def renewTokens(self):
        # POST data should be the single key-value pair 'refreshToken': TOKEN
        # when reading the response, use keys 'access_token' and 'refresh_token'
        # access tokens expire after two hours (as per the 'expires_in' field)
        self.session.headers = self.rfHeaders
        string = '{' + '"refreshToken":' + '"{}"'.format(self.refreshToken) + '}'
        resp = self.session.post(self.refreshUrl, data=string)
        try:
            data = resp.json()
        except requests.exceptions.JSONDecodeError as error:
            print('\nStatus code: {}'.format(resp.status_code))
            print("Refresh request returned the following non-JSON response:\n\n" + resp.text)
            raise error
        if resp.status_code != 200 or 'access_token' not in data:
            if resp.status_code == 400:
                self.login()
                return
            print('\nStatus code: {}'.format(resp.status_code))
            raise Exception(
                "Request to refresh the access token returned the following response:\n\n"
                + json.dumps(resp.text, indent=4)
            )
        self._saveTokens(data)
        self.session.headers = self.headers


    def _saveTokens(self, tokens):
        self.lastRefresh = time.time()
        tokens['lastRefresh'] = self.lastRefresh
        with open(CONFIG_DIR + 'zenith-tokens.json', 'w') as file:
            file.write(json.dumps(tokens, indent=4))
        self.refreshToken = tokens['refresh_token']
        self.headers.update({'Authorization': 'Bearer ' + tokens['access_token']})


    def _effStackToRangeSet(self, line, effStack):
        """
        Gets the appropriate range set string given the effective stack sizes.

        :param effStack: the effective stack size, assumed to be 100 if the hand
        is not heads up
        """
        if effStack < 75:
            return '50_STD'
        elif effStack < 150:
            return '100_STD'
        # only query strategies for 200bb if the LJ folded,
        # since they are unavailable otherwise
        if line[0][0] != 'LJ' or line[0][1] == 'F':
            return '200_STD'
        # use 100bb if LJ did not fold
        return '100_STD'


    def _getFirstAction(self, line):
        """
        Returns the index in the line list of the action of the first player to not fold.
        """
        for i in range(len(line)):
            if line[i]['agg'] != 'F':
                return i
        return None


    def _getMinPct(self, pos):
        # min raise: 2x the last wager minus current investment of min-raiser before the min-raise
        invBeforeRaise = self.inv[pos]
        minWager = 2 * self.lastWager - invBeforeRaise
        potAfterCall = self.pot + (self.lastWager - invBeforeRaise)
        return (minWager - self.lastWager) / potAfterCall


    def _getNearestRaise(self, path, action, url, rset):
        if path == '' and rset == '100_STD':
            options = self.rfi[action['pos']][rset]['nextOptions']
        elif path in self.cache:
            options = self.cache[path]
        else:
            url += '?node_path={}&version={}'.format(path, self.versions[rset])
            data = self.sendRequest(url)
            if data['terminal'] == True:
                print('Node path does not exist in the Zenith database')
                return None, None
            options = data['nextOptions']
            with open(CONFIG_DIR + 'zenith-cache.txt', 'a') as file:
                file.write('\n' + path + '\n' + json.dumps(options))
            self.cache[path] = options
        
        sizes = []
        hasMin, hasJam = False, False
        # `a` is an optional action that might be used to construct the assumptive line
        # `a` is distinct from the variable `action` which is the real action that was taken
        for a in options:
            if a[2] == 'r':
                # parse the raise pct as an int
                string = a[4:] if a[3] == '0' else a[3:]
                sizes.append(int(string))
            elif a[2] == 'm':
                hasMin = True
                sizes.append(self._getMinPct(action['pos']) * 100)
            elif a[2] == 'j':
                hasJam = True
                #sizes.append(int(rset.split('_')[0]))

        sizes.sort()
        pct = action['pctPot'] * 100
        if pct < sizes[0] - self.thresh:
            return None, None
        elif pct > sizes[-1] + self.thresh:
            # TODO: may want to use the exact jam pct of pot instead of 100x the pot
            return (100, 'j') if hasJam else (None, None)
        
        nearest = min(sizes, key=lambda x: abs(x - pct))
        strNearest = str(nearest)
        if hasMin and nearest == sizes[0]:
            return sizes[0] / 100, 'min'
        elif len(strNearest) == 2:
            strNearest = '0' + strNearest
        
        return nearest / 100, 'r' + strNearest


    def getNodePath(self, line, faIndex, url, rset):
        # HJr060-COf-BUf-SBr150-BBc
        # HJr060-COc-BUc-SBf
        path = ''
        asmptLine = []

        for i in range(faIndex, len(line)):
            action = line[i]
            if i > faIndex:
                path += '%2F'

            amtToCall = self.lastWager - self.inv[action['pos']]

            if action['agg'] == 'F':
                path += action['pos'] + 'f'
                asmptLine.append(action)
                continue
            elif action['agg'] == 'C':
                path += action['pos'] + 'c'
                if action['wager'] == self.lastWager:
                    asmptLine.append(action)
                else:
                    mod = action.copy()
                    mod['wager'] = self.lastWager
                    asmptLine.append(mod)
                self.pot += amtToCall
                self.inv[action['pos']] += amtToCall
            else:
                assert action['agg'] == 'R'
                pctRaise, pctRaiseStr = self._getNearestRaise(path, action, url, rset)
                if not pctRaise:
                    return None, None
                path += action['pos'] + pctRaiseStr  # e.g. 'COmin', 'COr080', 'COj'
                #mod = {key: action[key] for key in ['pos', 'agg', 'wager', 'pctPot']}
                # add assumptive values at the current node
                potAfterCall = self.pot + amtToCall
                wager = pctRaise * potAfterCall + self.lastWager
                #minWager = 2 * lastWager - inv[action['pos']]
                #minPct = (minWager - lastWager) / potAfterCall
                mod = {
                    'pos': action['pos'],
                    'agg': 'R',
                    'wager': wager,
                    'pctPot': pctRaise,
                    'potAfterCall': potAfterCall,
                    'lastWager': self.lastWager
                }
                asmptLine.append(mod)
                amtPutIn = wager - self.inv[action['pos']]
                self.pot += amtPutIn
                self.inv[action['pos']] += amtPutIn
                self.lastWager = wager

        return path, line[:faIndex] + asmptLine


    def getStrategy(self, line, effStack, holeCards, heroPos):
        faIndex = self._getFirstAction(line)
        heroHand = self.convertHoleCards(holeCards)
        rset = self._effStackToRangeSet(line, effStack)

        if faIndex is None:
            # no one limped or raised yet, so use an RFI range
            data = self.rfi[heroPos][rset]
            strategy = self.computeBestResponse(data, heroHand, heroPos)
            return strategy, {'pre': line}
        
        url = '{}/{}/positions/{}/freqs'.format(self.baseUrl, rset, line[faIndex]['pos'])
        nodePath, asmptLine = self.getNodePath(line, faIndex, url, rset)
        if not nodePath:
            return None, line
        
        url += '?node_path={}&version={}'.format(nodePath, self.versions[rset])
        data = self.sendRequest(url)
        if data['terminal'] == True:
            return None, line

        if nodePath not in self.cache:
            with open(CONFIG_DIR + 'zenith-cache.txt', 'a') as file:
                file.write('\n' + nodePath + '\n' + json.dumps(data['nextOptions']))
        
        assert heroPos in data['nextOptions'][0]
        strategy = self.computeBestResponse(data, heroHand, heroPos)
        self.resetAsmptValues()

        return strategy, {'pre': asmptLine}


    def sendRequest(self, url):
        if time.time() - self.lastRefresh > 7000:
            self.renewTokens()
        resp = self.session.get(url)
        data = resp.json()
        if resp.status_code == 401:
            raise Exception(
                "Request to Zenith returned a 401 response. It is likely that "
                + "the refresh token has expired.\n{}".format(json.dumps(data, indent=4))
            )
        elif resp.status_code != 200 or 'terminal' not in data:
            print('\nStatus code: {}'.format(resp.status_code))
            formatted = json.dumps(data, indent=4)
            raise Exception("Request to {} returned the following response:\n\n{}".format(url, formatted))
        return data


    def convertHoleCards(self, cards):
        c1, s1, c2, s2 = cards  # extract the card values and suits
        if c1 == c2:
            return c1 * 2  # pocket pair
        hand = c1 + c2 if CARD_RANKS[c1] > CARD_RANKS[c2] else c2 + c1
        if s1 == s2:
            return hand + 's'  # suited
        return hand + 'o'  # off-suit
        

    def computeBestResponse(self, data, heroHand, heroPos):
        # find the average frequency for each action across the range of hands
        avg = dict(map(lambda key: (key, 0), data['nextOptions']))
        for hand in data['frequency']:
            cards = hand['_row']
            weight = sum(x for x in hand.values() if not isinstance(x, str))
            if weight == 0:
                continue

            if len(cards) == 2:
                combos = 6
            else:
                combos = 4 if cards[2] == 's' else 12
            
            #hand = dict(map(lambda key: (key, hand[key] / weight), hand))  # normalize
            #x hand = list(map(lambda x: x / weight, hand))  # normalize
            for action in hand:
                if action != '_row':
                    avg[action] += hand[action] * combos

        sumAvg = sum(avg.values())
        avg = dict(map(lambda key: (key, avg[key] / sumAvg), avg))
        
        # merge all non-all-in raise sizing into one action by normalizing and then
        # taking a weighted average

        # first isolate the raise sizings and frequencies and calculate a weighted
        # average raise sizing that will be used across the entire range
        sizings, freqs = [], []
        for k, v in avg.items():
            if k[2] == 'r':
                # extract the pct of pot as a float
                pct = k.split('r')[1]
                if pct[0] == '0':
                    pct = pct[1:]
                pct = float(pct)
            elif k[2] == 'm':
                pct = self._getMinPct(heroPos) * 100
            else:
                continue
            sizings.append(pct)
            freqs.append(v)

        # normalize and take the weighted average
        tot = sum(freqs)
        freqs = [x / tot for x in freqs]
        avg = sum(sizings[i] * freqs[i] for i in range(len(freqs)))

        # now get the freqs for Hero's specific hand and merge the raise options into
        # the average that was found above
        totRaise = 0
        options = []
        hand = data['frequency'][self.indices[heroHand]].copy()
        del hand['_row']
        # sum used for normalization
        tot = sum(hand.values())
        for action, freq in hand.items():
            if action[2] not in ['m', 'r']:
                options.append((action[2], freq / tot))
            else:
                totRaise += freq
        if totRaise > 0:
            # avg is the average raise size across the range as a pct of pot
            options.append(('r', totRaise / tot, avg / 100))
        
        # sort the action options by level of aggression
        rank = {'f': 1, 'c': 2, 'r': 3, 'j': 4}
        options.sort(key=lambda a: rank[a[0]])

        return options



if __name__ == '__main__':
    zenith = ZenithNash()

    #url = 'https://preflop.zenith.poker/api/range_sets/200_STD/positions/SB/freqs?version=20210517'
    #zenith.sendRequest(url)

    #zenith.foo(1.5, 1, 0, 'A3o')
    zenith.login()
    """
    line = [
        {'pos': 'LJ', 'agg': 'F'},
        {'pos': 'HJ', 'agg': 'R', 'wager': 2.25, 'pctPot': 0.5, 'potAfterCall': 2.5, 'lastWager': 1.0},
        {'pos': 'CO', 'agg': 'F'},
        {'pos': 'BU', 'agg': 'R', 'wager': 7.65, 'pctPot': 0.9, 'potAfterCall': 6.0, 'lastWager': 2.5},
        {'pos': 'SB', 'agg': 'F'},
        {'pos': 'BB', 'agg': 'F'},
        {'pos': 'HJ', 'agg': 'R', 'wager': 14.0, 'pctPot': 0.37797619047619047, 'potAfterCall': 16.8, 'lastWager': 7.65}
    ]
    effStack = 112
    holeCards = 'Qh9h'
    heroPos = 'BU'

    strategy, asmptLine = zenith.getStrategy(line, effStack, holeCards, heroPos)
    print(strategy)
    print()
    print(asmptLine)
    """
    
    time.sleep(2)
    zenith.session.close()
