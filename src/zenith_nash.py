import json
import time
import requests
from random import SystemRandom
from util import CARD_RANKS


# MIN RAISE: 2X THE LAST WAGER MINUS CURRENT INVESTMENT OF MIN-RAISER BEFORE THE MIN-RAISE

class ZenithNash:

    def __init__(self):
        #self.baseUrl = 'https://preflop.zenith.poker/api/range_sets/100_STD/positions/HJ/freqs?version=20220109'
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
        self.nodePath = {}  # maps table numbers to the node path of the last request
        self.session = requests.Session()
        with open('../config/rfi-ranges.json') as file:
            self.rfi = json.loads(file.read())
        with open('../config/zenith-login-cookies.txt') as file:
            self.loginCookies = file.read().strip()
        with open('../config/zenith-cookies.txt') as file:
            self.cookies = file.read().strip()
        with open('../config/zenith-login-headers.json') as file:
            self.loginHeaders = json.loads(file.read())
        with open('../config/zenith-headers.json') as file:
            self.headers = json.loads(file.read())
        with open('../config/zenith-rf-headers.json') as file:
            self.rfHeaders = json.loads(file.read())
        with open('../config/zenith-tokens.json') as file:
            tokens = json.loads(file.read())
        self.refreshToken = tokens['refresh_token']
        self.lastRefresh = tokens['lastRefresh']
        self.loginHeaders.update({'Cookie': self.loginCookies})
        self.rfHeaders.update({'Cookie': self.cookies})
        self.headers.update({
            'Authorization': 'Bearer ' + tokens['access_token'],
            'Cookie': self.cookies
        })
        with open('../config/zenith-cache.json') as file:
            self.cache = json.loads(file.read())
        self.session.headers = self.headers
        self.indices = self.getIndices()


    def getIndices(self):
        """
        Generates a dict that will map any given preflop hand to its appropriate index
        in the array returned by JSON responses.
        """
        indices = {}
        data = self.rfi['LJ']['100_STD']
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
            print('\nStatus code: {}'.format(resp.status_code))
            raise Exception(
                "Request to refresh the access token returned the following response:\n\n"
                + json.dumps(resp.data, indent=4)
            )
        self._saveTokens(data)


    def _saveTokens(self, tokens):
        self.lastRefresh = time.time()
        tokens['lastRefresh'] = self.lastRefresh
        with open('../config/zenith-tokens.json', 'w') as file:
            file.write(json.dumps(tokens, indent=4))
        self.refreshToken = tokens['refresh_token']
        self.headers.update({'Authorization': 'Bearer ' + tokens['access_token']})
        self.session.headers = self.headers


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
        if line[0][0] == 'LJ' and line[0][1] == 'F':
            return '200_STD'
        # use 100bb if LJ did not fold
        return '100_STD'


    def _getFirstAction(self, line):
        """
        Returns the index in the line list of the action of the first player to not fold.
        """
        for i in range(len(line)):
            if line[i][1] != 'F':
                return i
        return None


    def _getNearestRaise(self, path, amt, pfRaises):
        if path in self.cache:
            pass



    def _getNodePath(self, line, faIndex, pfRaises):
        # HJr060-COf-BUf-SBr150-BBc
        # HJr060-COc-BUc-SBf        
        for i in range(faIndex, len(line)):
            action = line[i]
            if i > faIndex:
                path += '%2F'
            base = action[0] + action[1].lower()
            if action[1] in ['F', 'C']:
                path += base
                continue
            path += base + self._getNearestRaise(path, action[2], pfRaises)

        return path



    def getStrategy(self, line, effStack, pfRaises):
        faIndex = self.getFirstAction(line)
        if faIndex is None:
            # no one limped or raised yet, so use an RFI range
            return
        rset = self._effStackToRangeSet(line, effStack)
        url = '{}/{}/positions/{}/freqs'.format(self.baseUrl, rset, line[faIndex][0])
        nodePath = self._getNodePath(line, faIndex, pfRaises)
        url += '?node_path={}&version={}'.format(nodePath, self.versions[rset])


    def clearCache(self, tableNum):
        self.nodePath[tableNum] = ''


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
        elif resp.status_code != 200 or 'frequency' not in data:
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
        

    def foo(self, pot, lastWager, heroInv, heroHand):
        url = "https://preflop.zenith.poker/api/range_sets/100_STD/positions/SB/freqs?node_path=SBr100%2FBBr100%2FSBr060&version=20220109"
        
        resp = {}
        resp['frequency'] = self.rfi['BU']['100_STD']
        resp['nextOptions'] = [
            'BUf', 'BUc', 'BUr040', 'BUr050', 'BUr060', 'BUr070', 'BUr080',
            'BUr090', 'BUr100', 'BUr120', 'BUr160'
        ]

        #resp = self.sendRequest(url)

        # find the average frequency for each action across the range of hands
        avg = dict(map(lambda key: (key, 0), resp['nextOptions']))
        for hand in resp['frequency']:
            cards = hand['_row']
            del hand['_row']
            weight = sum(hand.values())
            if weight == 0:
                continue

            if len(cards) == 2:
                combos = 6
            else:
                combos = 4 if cards[2] == 's' else 12
            
            #hand = dict(map(lambda key: (key, hand[key] / weight), hand))  # normalize
            #x hand = list(map(lambda x: x / weight, hand))  # normalize
            for action in hand:
                avg[action] += hand[action] * combos

        avg = dict(map(lambda key: (key, avg[key] / sum(avg.values())), avg))
        
        # merge all non-all-in raise sizing into one action by normalizing and then
        # taking a weighted average

        # first isolate the raise actions and create a new list to store the merged actions
        actions, sizings, freqs = [], [], []
        for k, v in avg.items():
            if k[2] == 'r':
                # extract the pct of pot as a float
                pct = k.split('r')[1]
                if pct[0] == '0':
                    pct = pct[1:]
                pct = float(pct)
            elif k[2] == 'm':
                wager = (2 * lastWager - heroInv) / pot
                amtRaised = wager - lastWager
                potAfterCall = pot + lastWager - heroInv
                pct = amtRaised / potAfterCall
            else:
                actions.append((k[2], v))
                continue
            sizings.append(pct)
            freqs.append(v)

        # normalize and take the weighted average
        tot = sum(freqs)
        freqs = [x / tot for x in freqs]
        avg = sum([sizings[i] * freqs[i] for i in range(len(freqs))])
        # tot is overall raise frequency, avg is the average raise size
        actions.append(('r', tot, avg))
        # sort by the level of aggression
        rank = {'f': 1, 'c': 2, 'r': 3, 'j': 4}
        actions.sort(key=lambda a: rank[a[0]])

        x = 0
        for a in actions:
            freq = a[1]
            x += freq
        print(x)
            


if __name__ == '__main__':
    zenith = ZenithNash()

    #url = 'https://preflop.zenith.poker/api/range_sets/200_STD/positions/SB/freqs?version=20210517'
    #zenith.sendRequest(url)

    zenith.foo(1.5, 1, 0)
    #zenith.login()

    #time.sleep(2)
    zenith.session.close()
