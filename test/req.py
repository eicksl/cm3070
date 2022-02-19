import json
import requests


url = "https://gtowizard.com/api/v1/poker/solution/?gametype=Cash6m500zComplex&depth=100&stacks=&preflop_actions=F&flop_actions=&turn_actions=&river_actions=&board=&cache_change=2022-02-06T00%3A00Z"

with open('cookies.txt') as file:
    lstCookies = json.loads(file.read())

with open('../config/headers.json') as file:
    dctHeaders = json.loads(file.read())

s = requests.Session()
s.headers.update(dctHeaders)
for cookie in lstCookies:
    if cookie['name'] == '_gid' and cookie['value'].startswith('GA1.2'):
        continue
    s.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])

resp = s.get(url)
s.close()
print(resp.text)
