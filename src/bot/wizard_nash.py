import json
import time
import requests
from src.bot.constants import CONFIG_DIR, CARD_RANKS, WIZ_SUIT_RANKS


class WizardNash:
    
    def __init__(self):
        # use JSON.parse(localStorage.getItem('user_info')) in the browser to get the access and
        # refresh tokens, then copy them to config/wizard-tokens.json
        self.gameType = "Cash6m50zComplex"
        self.cacheChange = "2022-02-06T00%3A00Z"
        self.baseUrl = "https://gtowizard.com/api/v1/poker/solution/"
        self.optionsUrl = "https://gtowizard.com/api/v1/poker/next-actions/"
        self.refreshUrl = "https://gtowizard.com/api/v1/token/refresh/"
        self.wait = True  # wait between intermediary requests
        self.waitInterval = 1.5
        self.depths = [20, 40, 50, 75, 100, 150, 200]
        self.session = requests.Session()
        self.cache = {}
        with open(CONFIG_DIR + 'wizard-cache.txt') as file:
            lines = file.read().split('\n')
            if len(lines) > 1:
                for i in range(0, len(lines), 2):
                    self.cache[lines[i]] = json.loads(lines[i+1])
        with open(CONFIG_DIR + 'wizard-headers.json') as file:
            self.headers = json.loads(file.read())
        with open(CONFIG_DIR + 'wizard-rf-headers.json') as file:
            self.rfHeaders = json.loads(file.read())
        with open(CONFIG_DIR + 'wizard-tokens.json') as file:
            tokens = json.loads(file.read())
        self.refreshToken = tokens['refresh']
        self.lastRefresh = tokens['lastRefresh']
        auth = {'Authorization': 'Bearer ' + tokens['access']}
        self.headers.update(auth)
        self.rfHeaders.update(auth)
        self.session.headers = self.headers


    def renewAccessToken(self):
        """
        Renews the access token. Note that, unlike Zenith, the access token must be set in the
        Authorization header for the refresh request to work. Use `refresh` for the JSON key
        in the POST request body and then use `access` when reading the response.
        """
        self.session.headers = self.rfHeaders
        string = '{' + '"refresh":' + '"{}"'.format(self.refreshToken) + '}'
        resp = self.session.post(self.refreshUrl, data=string)
        try:
            data = resp.json()
        except requests.exceptions.JSONDecodeError as error:
            print('\nStatus code: {}'.format(resp.status_code))
            print("Refresh request returned the following non-JSON response:\n\n" + resp.text)
            raise error
        if resp.status_code != 200 or 'access' not in data:
            print('\nStatus code: {}'.format(resp.status_code))
            raise Exception(
                "Request to refresh the access token returned the following response:\n\n"
                + json.dumps(resp.text, indent=4)
            )
        self._saveToken(data)
        self.session.headers = self.headers


    def _saveToken(self, token):
        self.lastRefresh = time.time()
        token.update({'refresh': self.refreshToken, 'lastRefresh': self.lastRefresh})
        with open(CONFIG_DIR + 'wizard-tokens.json', 'w') as file:
            file.write(json.dumps(token, indent=4))
        auth = {'Authorization': 'Bearer ' + token['access']}
        self.headers.update(auth)
        self.rfHeaders.update(auth)


    def sendRequest(self, url):
        if time.time() - self.lastRefresh > 300:
            self.renewAccessToken()
        resp = self.session.get(url)
        if resp.status_code == 204:
            return None  # node does not exist in the database
        try:
            data = resp.json()
        except requests.exceptions.JSONDecodeError as error:
            print('\nStatus code: {}'.format(resp.status_code))
            print("Refresh request returned the following non-JSON response:\n\n" + resp.text)
            raise error
        if resp.status_code == 401:
            raise Exception(
                "Request to GTOWizard returned a 401 response. It is likely that "
                + "the refresh token has expired.\n{}".format(json.dumps(data, indent=4))
            )
        elif resp.status_code != 200 or 'solutions' not in data:
            print('\nStatus code: {}'.format(resp.status_code))
            formatted = json.dumps(data, indent=4)
            raise Exception("Request to {} returned the following response:\n\n{}".format(url, formatted))
        return data


    def _saveOptions(self, data, state):
        options = []
        for obj in data['solutions']:
            a = obj['action']
            if a['code'][0] == 'R':
                options.append([a['code'], float(a['betsize']), float(a['betsize_by_pot'])])
        with open(CONFIG_DIR + 'wizard-cache.txt', 'a') as file:
            file.write('\n' + state + '\n' + json.dumps(options))
        self.cache[state] = options
        return options


    def _getOptions(self, state, stem):
        if state in self.cache:
            options = self.cache[state]
        else:
            url = self.baseUrl + state + stem
            print(url)
            data = self.sendRequest(url)
            if data is None:
                with open(CONFIG_DIR + 'wizard-cache.txt', 'a') as file:
                    file.write('\n{}\n[]'.format(state))
                return []
            if self.wait:
                time.sleep(self.waitInterval)
            options = self._saveOptions(data, state)
        
        return options


    def getPreActions(self, line, urlParams):
        asmpt = ''
        sawFirstRaise = False

        if len(line) > 1 and line[1]['pos'] == 'HJ' and line[1]['agg'] == 'C':
            return None

        for action in line:
            agg = action['agg']

            if agg != 'R':
                if agg == 'C' and not sawFirstRaise:
                    return None
                asmpt += agg + '-'
                continue

            if not sawFirstRaise:
                sawFirstRaise = True

            state = urlParams + asmpt[:-1]
            stem = (
                "&flop_actions=&turn_actions=&river_actions=&board=&cache_change="
                + self.cacheChange
            )
            options = self._getOptions(state, stem)
            if len(options) == 0:
                return None
            closest = min(options, key=lambda x: abs(x[1] - action['wager']))
            asmpt += closest[0] + '-'
        
        return asmpt[:-1]


    def getPostActions(self, asmptLine, realLine, urlParams, board):
        """Updates the assumptive line with post-flop actions"""
        streets = ['flop', 'turn', 'river']
        remaining = streets.copy()

        for i in range(len(streets)):
            street = streets[i]
            remaining.pop(0)
            urlParams += '&{}_actions='.format(street)

            line = realLine[street]
            if len(line) == 0:
                continue

            for action in line:
                if action['agg'] in ['B', 'R']:
                    state = urlParams + asmptLine[street][:-1]
                    for streetx in remaining:
                        urlParams += '&{}_actions='.format(streetx)
                    stem = '&board={}&cache_change={}'.format(board, self.cacheChange)
                    options = self._getOptions(state, stem)
                    if len(options) == 0:
                        return None
                    closest = min(options, key=lambda x: abs(x[1] - action['wager']))
                    asmptLine[street] += closest[0] + '-'
                else:
                    asmptLine[street] += action['agg'] + '-'
            
            asmptLine[street] = asmptLine[street][:-1]


    def _convertHoleCards(self, cards):
        hand = None
        c1, s1, c2, s2 = cards  # extract the card values and suits

        if c1 == c2:
            if WIZ_SUIT_RANKS[s1] > WIZ_SUIT_RANKS[s2]:
                hand = c1 + s1 + c1 + s2
            else:
                hand = c1 + s2 + c1 + s1
        else:
            if CARD_RANKS[c1] > CARD_RANKS[c2]:
                hand = cards
            else:
                hand = c2 + s2 + c1 + s1

        return hand


    def _getHandIndex(self, cards):
        index = -1
        c1, s1, c2, s2 = self._convertHoleCards(cards)

        if c1 != '2':
            for i in range(CARD_RANKS[c1] - 2, 0, -1):
                index += 16 * i
            index += (CARD_RANKS[c1] - 1) * 6
        
        index += 4 * WIZ_SUIT_RANKS[s1] * (CARD_RANKS[c1] - 1)
        if s1 == 'h':
            index += 1
        elif s1 == 's':
            index += 3

        index += 4 * (CARD_RANKS[c2] - 1) + WIZ_SUIT_RANKS[s2] + 1
        
        return index


    def getStrategy(self, line, effStack, holeCards, board):
        # ?gametype=Cash6m50zComplex&depth=100&stacks=&preflop_actions=R2.5-F-C-C-R15&flop_actions=&turn_actions=&river_actions=&board=&cache_change=2022-02-06T00%3A00Z
        depth = min(self.depths, key=lambda x: abs(x - effStack))
        urlParams = "?gametype={}&depth={}&stacks=&preflop_actions=".format(self.gameType, depth)
        asmptLine = {'pre': '', 'flop': '', 'turn': '', 'river': ''}
        asmptLine['pre'] = self.getPreActions(line['pre'], urlParams)
        if not asmptLine['pre']:
            return None, None
        urlParams += asmptLine['pre']

        self.getPostActions(asmptLine, line, urlParams, board)
        state = urlParams
        for street in ['flop', 'turn', 'river']:
            if asmptLine[street] == '':
                break
            state += '&{}_actions='.format(street) + asmptLine[street]
        
        url = (
            self.baseUrl + urlParams +
            "&flop_actions={}&turn_actions={}&river_actions={}&board={}&cache_change={}"
            .format(asmptLine['flop'], asmptLine['turn'], asmptLine['river'], board, self.cacheChange)
        )
        data = self.sendRequest(url)
        if data is None:
            return None, None
        if state not in self.cache:
            self._saveOptions(data, state)
        
        print(state)
        print()
        print(asmptLine)
        print()
        print(url)



if __name__ == '__main__':
    wizard = WizardNash()
    #url = wizard.baseUrl + "?gametype=Cash6m50zComplex&depth=100&stacks=&preflop_actions=R2.5-F&flop_actions=&turn_actions=&river_actions=&board=&cache_change=2022-02-06T00%3A00Z"

    line = {
        'pre': [
                {'pos': 'LJ', 'agg': 'F'}, {'pos': 'HJ', 'agg': 'R', 'wager': 2.12}, {'pos': 'CO', 'agg': 'F'},
                {'pos': 'BU', 'agg': 'F'}, {'pos': 'SB', 'agg': 'F'}, {'pos': 'BB', 'agg': 'C'}
            ],
        'flop': [{'agg': 'B', 'wager': 2.75}],
        'turn': [],
        'river': []
    }
    effStack = 112
    holeCards = 'AhJc'
    board = '4dTh2s'
    #res = wizard.getStrategy(line, effStack, holeCards, board)

    res = wizard._getHandIndex('TcTh')
    print(res)

    #time.sleep(2)
    wizard.session.close()

# https://gtowizard.com/api/v1/poker/next-actions/?gametype=CashHu500zSimple&depth=100&stacks=&preflop_actions=R2.5-R10-R24-C&flop_actions=X-X&turn_actions=&river_actions=&cache_change=2022-02-06T00%3A00Z
