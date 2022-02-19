import json


with open('all.txt') as file:
    strings = file.read().split('},')
    strings[-1] += '}'

cookies = []
for string in strings:
    if '.gtowizard.com' in string:
        cookie = json.loads(string + '}')
        print(cookie['name'], cookie['value'])
        print()
        cookies.append(cookie)

with open('cookies.txt', 'w') as file:
    file.write(json.dumps(cookies))
