import unittest
from src.bot.util import hasFourStraight, lc4straight


class TestUtil(unittest.TestCase):

    def test_hasFourStraight(self):
        boardCards = ['4', '3', '2', 'A', 'Q']
        self.assertTrue(hasFourStraight(boardCards))
        boardCards = ['4', 'K', 'T', 'A', 'Q']
        self.assertTrue(hasFourStraight(boardCards))
        boardCards = ['7', '3', '2', 'A', 'Q']
        self.assertFalse(hasFourStraight(boardCards))
        boardCards = ['8', 'T', '7', 'K', 'J']
        self.assertTrue(hasFourStraight(boardCards))
        boardCards = ['6', '2', '7', 'A', 'T']
        self.assertFalse(hasFourStraight(boardCards))
        boardCards = ['6', '7', '7', '8', 'T']
        self.assertTrue(hasFourStraight(boardCards))
        boardCards = ['8', '8', '7', '7', '9']
        self.assertFalse(hasFourStraight(boardCards))


    def test_lc4straight(self):
        boardCards = ['5', '4', '8', '6']
        self.assertTrue(lc4straight(boardCards))
        boardCards = ['5', '4', 'K', '7', '6']
        self.assertTrue(lc4straight(boardCards))
        boardCards = ['5', '4', '6', '7', 'K']
        self.assertFalse(lc4straight(boardCards))
        boardCards = ['5', '4', '2', 'K', 'A']
        self.assertTrue(lc4straight(boardCards))
        boardCards = ['Q', '6', 'J', 'K', 'A']
        self.assertTrue(lc4straight(boardCards))



if __name__ == '__main__':
    unittest.main()
