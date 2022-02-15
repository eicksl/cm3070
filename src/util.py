import cv2
import numpy as np
from collections import OrderedDict
from tesserocr import PyTessBaseAPI, PSM, OEM
from PIL import Image, ImageOps


CHIP_AREA_THRESH = 200  # threshold to use for the contour area of a stack of chips
B_AREA = 69  # contour area of 'B' in 'BB' (big blinds)
POS_RANKS_LIST = ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BU']
POS_RANKS_DICT = {'SB': 0, 'BB': 1, 'LJ': 2, 'HJ': 3, 'CO': 4, 'BU': 5}
POS_RANKS_LIST_PRE = ['LJ', 'HJ', 'CO', 'BU', 'SB', 'BB']
POS_RANKS_DICT_PRE = {'LJ': 0, 'HJ': 1, 'CO': 2, 'BU': 3, 'SB': 4, 'BB': 5}
SUIT_PIXELS = OrderedDict([
    ('s', [117, 117, 117]), ('c', [126, 171, 97]),
    ('d', [100, 145, 160]), ('h', [165, 98, 98]), ('ep', 25)
])


def getOcrString(api, img):
    """Used for player names"""
    api.SetImage(img)
    return api.GetUTF8Text().strip()


def test_getOcrString(api, imgName, scaleFactor, binThresh):
    images = ['img/' + imgName]
    for img in images:
        #api.SetImageFile(img)
        pilImg = Image.open(img)
        pilImg = preprocessImage(pilImg, scaleFactor, binThresh)
        result = getOcrString(api, pilImg)
        print(result)


def getCardSuit(npImg):
    """
    Returns an element of {'s', 'c', 'd', 'h'}, or None if no suit could be determined.
    The suit is determined by looking at the average RGB values of the middle row.
    """
    s, c, d, h, ep = SUIT_PIXELS.values()
    #row = npImg[npImg.shape[0] // 2]
    #r, g, b = np.round(np.mean(row, axis=0))
    r, g, b = np.round(np.mean(np.mean(npImg, axis=0), axis=0))
    #print([r, g, b])
    suit = None
    if r in range(s[0]-ep, s[0]+ep) and g in range(s[1]-ep, s[1]+ep) and b in range(s[2]-ep, s[2]+ep):
        suit = 's'
    elif r in range(c[0]-ep, c[0]+ep) and g in range(c[1]-ep, c[1]+ep) and b in range(c[2]-ep, c[2]+ep):
        suit = 'c'
    elif r in range(d[0]-ep, d[0]+ep) and g in range(d[1]-ep, d[1]+ep) and b in range(d[2]-ep, d[2]+ep):
        suit = 'd'
    elif r in range(h[0]-ep, h[0]+ep) and g in range(h[1]-ep, h[1]+ep) and b in range(h[2]-ep, h[2]+ep):
        suit = 'h'
    return suit


def villainHasCards(npImg):
    """Determines if the villain has cards using the same method in getCardSuit"""
    row = npImg[npImg.shape[0] // 2]
    red, green, blue = np.round(np.mean(row, axis=0))
    #print([red, green, blue])
    if red in range(144, 184) and green in range(65, 105) and blue in range(63, 103):
        return True
    else:
        return False


def getOcrCard(api, img):
    """
    Returns a char representing the card value, e.g. '9', 'T', 'J', etc
    """
    api.SetImage(img)
    string = api.GetUTF8Text().strip()
    #if len(string) == 0 or (len(string) == 2 and string != '10') or len(string) > 2:
    #    raise Exception("String '{}' is not an acceptable card value".format(string))
    if string in ['10', 'lo']:
        return 'T'
    return string


def test_getOcrCard(api, imgName, scaleFactor, binThresh):
    images = ['../img/' + imgName]
    for img in images:
        pilImg = Image.open(img)
        pilImg = preprocessImage(pilImg, scaleFactor, binThresh)
        result = getOcrCard(api, pilImg)
        print(result)


def getCard(api, img, scaleFactor, binThresh):
    npImg = np.array(img)
    suit = getCardSuit(npImg)
    if not suit:
        return None
    img = preprocessImage(img, scaleFactor, binThresh, npImg)
    card = getOcrCard(api, img)
    return card + suit


def getOcrNumber(api, img, scaleFactor, binThresh, preprocess=True):
    if preprocess:
        img = preprocessImage(img, scaleFactor, binThresh)
    api.SetImage(img)
    number = None
    #print(api.GetUTF8Text())
    for result in api.GetUTF8Text().split():
        try:
            number = float(result)
            break
        except ValueError:
            pass

    return number


def test_getOcrNumber(api, imgName, scaleFactor, binThresh):
    img = Image.open('../img/test/' + imgName)
    result = getOcrNumber(api, img, scaleFactor, binThresh)
    print(result)


def scaleImage(img, scaleFactor):
    """Scales a pillow image by a specified factor"""
    return img.resize((img.size[0] * scaleFactor, img.size[1] * scaleFactor))


def preprocessImage(img, scaleFactor, binThresh, npImg=None):

    def binarize(img, threshold, npImg):
        if npImg is None:
            npImg = np.array(img)
        img = cv2.cvtColor(npImg, cv2.COLOR_RGB2GRAY)
        _, binarized = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)
        return Image.fromarray(binarized)

    img = scaleImage(img, scaleFactor)
    img = binarize(img, binThresh, npImg)
    return img


def test_preprocessImage(imgName, scaleFactor, binThresh):
    img = Image.open('../img/test/' + imgName)
    gray = ImageOps.grayscale(img)
    gray.save('../img/test/gray.png')
    img = preprocessImage(img, scaleFactor, binThresh)
    img.save('../img/test/binarized.png')


def containsTemplate(area, template, threshold=0.9):
    """
    Determines whether a template exists in a source image.

    :param: area: a cv2 grayscale area image
    :param template: a cv2 grayscale template image
    :param threshold: a confidence threshold
    :returns: boolean
    """
    result = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
    #print(np.max(result))
    return True if np.max(result) > threshold else False


def test_containsTemplate(areaImgName, templateImgName):
    areaCv2Img = cv2.imread('../img/states/out/0/' + areaImgName, cv2.IMREAD_GRAYSCALE)
    templateCv2Img = cv2.imread('../img/' + templateImgName, cv2.IMREAD_GRAYSCALE)
    templateFound = containsTemplate(areaCv2Img, templateCv2Img)
    print(templateFound)


def getOcrBet(api, pilImg, scaleFactor, binThresh, k=2):
    """
    :param k: constant to add to x+w of the left-most chip to the bet amount
    """
    img = cv2.cvtColor(np.array(pilImg), cv2.COLOR_RGB2GRAY)
    _, img = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if (len(contours) == 0):
        return None
    
    cntAreas = np.zeros(len(contours))
    cntRects = np.zeros((len(contours), 4), dtype=np.uint16)
    for i in range(len(contours)):
        cntAreas[i] = cv2.contourArea(contours[i])
        cntRects[i] = cv2.boundingRect(contours[i])
    # arg-sorted by the contour x position
    indices = np.apply_along_axis(lambda rect: rect[0], 1, cntRects).argsort()

    b1_u = -1  # index of the first 'B' in the unsorted arrays
    b1_s = -1  # index of the first 'B' in the sorted indices array

    for i in range(len(indices)):
        # indices[i] is the index of the would-be-sorted array
        if cntAreas[indices[i]] == B_AREA:
            b1_u = indices[i]
            b1_s = i
            break
    if b1_u == -1:
        raise Exception("Could not find a 'B' in the bet amount image")
    
    x, _, w, _ = cntRects[b1_u]
    img = np.delete(img, np.s_[x:], axis=1)

    chip = -1  # index of the chip closest to the bet amount in the unsorted arrays
    for i in range(b1_s, -1, -1):
        if cntAreas[indices[i]] > CHIP_AREA_THRESH:
            chip = indices[i]
            break
    if chip > -1:
        x, _, w, _ = cntRects[chip]
        img = np.delete(img, np.s_[:x+w+k], axis=1)

    img = cv2.bitwise_not(img)
    pilImg = scaleImage(Image.fromarray(img), scaleFactor)
    pilImg.save('../img/test/foo.png')

    return getOcrNumber(api, pilImg, scaleFactor, binThresh, preprocess=False)



if __name__ == '__main__':
    api = PyTessBaseAPI(path='../tessdata', psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)

    path = '../img/test/felt.png'
    scaleFactor = 4
    binThresh = 160

    img = Image.open(path)
    res = getOcrBet(api, img, scaleFactor, binThresh)
    print(res)

    #test_preprocessImage(imgName, scaleFactor, binThresh)
    #test_getOcrNumber(api, imgName, scaleFactor, binThresh)

    api.End()
