import os
import numpy as np
from collections import OrderedDict


RAKE = 0.05  # used to estimate how much was raise/called on a prior street
RAKE_CAP = 15
TESSDATA_DIR = os.path.abspath('../tessdata')
MODEL_DIR = os.path.abspath('../model.keras')
IMAGE_DIR = os.path.abspath('../img') + '/'
CONFIG_DIR = os.path.abspath('../config') + '/'
CARD_RANKS = {
    '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8,
    'T': 9, 'J': 10, 'Q': 11, 'K': 12, 'A': 13
}
DECK = set([
    '2s', '3s', '4s', '5s', '6s', '7s', '8s', '9s', 'Ts', 'Js', 'Qs', 'Ks', 'As',
    '2c', '3c', '4c', '5c', '6c', '7c', '8c', '9c', 'Tc', 'Jc', 'Qc', 'Kc', 'Ac',
    '2d', '3d', '4d', '5d', '6d', '7d', '8d', '9d', 'Td', 'Jd', 'Qd', 'Kd', 'Ad',
    '2h', '3h', '4h', '5h', '6h', '7h', '8h', '9h', 'Th', 'Jh', 'Qh', 'Kh', 'Ah'
])
DECK_MAP = {card : i for (i, card) in enumerate(DECK)}
WIZ_SUIT_RANKS = {'c': 0, 'd': 1, 'h': 2, 's': 3}
POS_RANKS_LIST = ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BU']
POS_RANKS_DICT = {'SB': 0, 'BB': 1, 'LJ': 2, 'HJ': 3, 'CO': 4, 'BU': 5}
POS_RANKS_LIST_PRE = ['LJ', 'HJ', 'CO', 'BU', 'SB', 'BB']
POS_RANKS_DICT_PRE = {'LJ': 0, 'HJ': 1, 'CO': 2, 'BU': 3, 'SB': 4, 'BB': 5}
SUIT_PIXELS = OrderedDict([
    ('s', [117, 117, 117]), ('c', [126, 171, 97]),
    ('d', [100, 145, 160]), ('h', [165, 98, 98]), ('ep', 25)
])
OCR_MAP = {
    'e': '2', 'a': '4', 'S': '8', 'c': '9', 'g': '9', '10': 'T', 'lo': 'T',
    'lO': 'T', 'iO': 'T', 'IO': 'T', 'lio': 'T', '[|': 'T', '(0)': 'T',
    '-.': '5', 's:': '8', 'qT': '7', '-.)': '5', 'oe': '2', 'G': 'Q', '0': '9',
    's': '5', '=': '5'
}
HSV_LOWER = np.array([0, 0, 160], dtype=np.uint8)
HSV_UPPER = np.array([95, 110, 255], dtype=np.uint8)
#BET_BG_LOWER = np.array([19, 57, 3], dtype=np.uint8)
#BET_BG_UPPER = np.array([23, 68, 6], dtype=np.uint8)
BET_BG_LOWER = np.array([19, 57, 3], dtype=np.uint8)
BET_BG_UPPER = np.array([27, 76, 8], dtype=np.uint8)
