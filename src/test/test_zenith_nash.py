import unittest
import json
from src.bot.zenith_nash import ZenithNash


class TestStringMethods(unittest.TestCase):

    def setUp(self):
        self.zenith = ZenithNash()


    @unittest.skip("Limit requests when testing")
    def test_sendRequest(self):
        pos = 'SB'
        rset = '100_STD'
        url = (
            "https://preflop.zenith.poker/api/range_sets/{}/positions/{}/freqs?version={}"
            .format(rset, pos, self.versions[rset])
        )

        url = "https://preflop.zenith.poker/api/range_sets/100_STD/positions/LJ/freqs?node_path=LJr050%2FHJr080%2FCOc&version=20220109"

        data = self.zenith.sendRequest(url)
        self.assertIsInstance(data, dict)


    def test_getNodePath(self):
        effStack = 112
        line = [
            ['LJ', 'F', 0, 0], ['HJ', 'R', 0.6, 2.5, 2.5, 1], ['CO', 'F', 0, 0]
        ]
        expected = (
            "https://preflop.zenith.poker/api/range_sets/100_STD/positions/HJ/freqs"
            + "?node_path=HJr060%2FCOf&version=20220109"
        )
        result = self.zenith.getStrategy(line, effStack)
        self.assertEqual(result, expected)



if __name__ == '__main__':
    unittest.main()
