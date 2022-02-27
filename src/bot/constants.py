import os
import numpy as np
from collections import OrderedDict


RAKE = 0.05  # used to estimate how much was raise/called on a prior street
RAKE_CAP = 15
TESSDATA_DIR = os.path.abspath('../../tessdata')
IMAGE_DIR = os.path.abspath('../../img') + '/'
CONFIG_DIR = os.path.abspath('../../config') + '/'
CARD_RANKS = {
    '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8,
    'T': 9, 'J': 10, 'Q': 11, 'K': 12, 'A': 13
}
POS_RANKS_LIST = ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BU']
POS_RANKS_DICT = {'SB': 0, 'BB': 1, 'LJ': 2, 'HJ': 3, 'CO': 4, 'BU': 5}
POS_RANKS_LIST_PRE = ['LJ', 'HJ', 'CO', 'BU', 'SB', 'BB']
POS_RANKS_DICT_PRE = {'LJ': 0, 'HJ': 1, 'CO': 2, 'BU': 3, 'SB': 4, 'BB': 5}
SUIT_PIXELS = OrderedDict([
    ('s', [117, 117, 117]), ('c', [126, 171, 97]),
    ('d', [100, 145, 160]), ('h', [165, 98, 98]), ('ep', 25)
])
OCR_MAP = {'g': '9', '10': 'T', 'lo': 'T', 'lio': 'T'}
HSV_LOWER = np.array([0, 0, 160], dtype=np.uint8)
HSV_UPPER = np.array([95, 110, 255], dtype=np.uint8)
#BET_BG_LOWER = np.array([19, 57, 3], dtype=np.uint8)
#BET_BG_UPPER = np.array([23, 68, 6], dtype=np.uint8)
BET_BG_LOWER = np.array([19, 57, 3], dtype=np.uint8)
BET_BG_UPPER = np.array([27, 76, 8], dtype=np.uint8)
