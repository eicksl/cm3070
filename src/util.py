import cv2
import numpy as np
from collections import OrderedDict
from tesserocr import PyTessBaseAPI, PSM, OEM
from PIL import Image, ImageOps


POS_RANKS_LIST = ['SB', 'BB', 'LJ', 'HJ', 'CO', 'BU']
POS_RANKS_DICT = {'SB': 0, 'BB': 1, 'LJ': 2, 'HJ': 3, 'CO': 4, 'BU': 5}
POS_RANKS_LIST_PRE = ['LJ', 'HJ', 'CO', 'BU', 'SB', 'BB']
POS_RANKS_DICT_PRE = {'LJ': 0, 'HJ': 1, 'CO': 2, 'BU': 3, 'SB': 4, 'BB': 5}
SUIT_PIXELS = OrderedDict([
    ('s', [117, 117, 117]), ('c', [126, 171, 97]),
    ('d', [100, 145, 160]), ('h', [165, 98, 98]), ('ep', 25)
])
OCR_MAP = {'g': '9', '10': 'T', 'lo': 'T'}
HSV_LOWER = np.array([0, 0, 160], dtype=np.uint8)
HSV_UPPER = np.array([95, 110, 255], dtype=np.uint8)
BET_BG_LOWER = np.array([19, 57, 3], dtype=np.uint8)
BET_BG_UPPER = np.array([23, 68, 6], dtype=np.uint8)


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
    if string in OCR_MAP:
        return OCR_MAP[string]
    return string[0]


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
    """
    Scales an image by a specified factor. The image can be in either numpy
    or pillow format.
    """
    if isinstance(img, np.ndarray):
        return cv2.resize(
            img, (img.shape[1] * scaleFactor, img.shape[0] * scaleFactor),
            interpolation=cv2.INTER_CUBIC
        )
    else:
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
    areaCv2Img = cv2.imread('../img/test/' + areaImgName, cv2.IMREAD_GRAYSCALE)
    templateCv2Img = cv2.imread('../img/' + templateImgName, cv2.IMREAD_GRAYSCALE)
    templateFound = containsTemplate(areaCv2Img, templateCv2Img)
    print(templateFound)


def getOcrBet(api, pilImg, scaleFactor, binThresh, B=69, C=50, k=5, m=2):
    # first convert to BGR and threshold the image using a range of BGR values
    # which makes the dark-green background white and the rest black
    img = cv2.cvtColor(np.array(pilImg), cv2.COLOR_RGB2BGR)
    mask = cv2.inRange(img, BET_BG_LOWER, BET_BG_UPPER)

    # find the contour of the white portion of the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rect = None
    for cnt in contours:
        if cv2.contourArea(cnt) > C:
            rect = cv2.boundingRect(cnt)
    # if no contour, wager is not present, so just return None
    if rect is None:
        return None

    # crop the original using the bounding rect
    x, y, w, h = rect
    img = img[y:y+h, x+k:x+w-k]

    # take the grayscale and perform binary thresholding
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY)

    # now find the first 'B' and crop it out of the grayscale image
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rect = None
    for i in range(len(contours)-1, -1, -1):
        if cv2.contourArea(contours[i]) >= B:
            rect = cv2.boundingRect(contours[i])
            break
    if rect:
        img = img[:, :rect[0]-m]

    # scale the image, apply median blurring for noise reduction, and then
    # threshold it to get a black number on a white background
    img = scaleImage(img, scaleFactor)
    img = cv2.blur(img, (5, 5))
    _, mask = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY_INV)

    # pass the result onward to the OCR algorithm
    pilImg = Image.fromarray(mask)
    #pilImg.save('../img/test/foo.png')
    return getOcrNumber(api, pilImg, scaleFactor, binThresh, preprocess=False)


def getOcrBet_old(api, pilImg, scaleFactor, binThresh, B=69, k=2):
    """
    :param k: constant to add to x+w of the left-most chip to the bet amount

    TODO: pass the width of the table to the function and use that to estimate
    what B_AREA, CHIP_AREA_THRESH, and k should be
    """
    # an HSV-colour image will be used later to binarize the text
    npImg = np.array(pilImg)
    hsv = cv2.cvtColor(npImg, cv2.COLOR_RGB2HSV)
    
    # for now, find the contours of the image using the grayscale
    img = cv2.cvtColor(npImg, cv2.COLOR_RGB2GRAY)
    #cv2.imwrite('../img/test/gray.png', img)
    _, img = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY)
    #cv2.imwrite('../img/test/binarized.png', img)
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if (len(contours) == 0):
        return None
    
    # get the areas and bounding rects of all the contours
    cntAreas = np.zeros(len(contours))
    cntRects = np.zeros((len(contours), 4), dtype=np.uint16)
    for i in range(len(contours)):
        cntAreas[i] = cv2.contourArea(contours[i])
        cntRects[i] = cv2.boundingRect(contours[i])
    # and now arg-sort them by the bounding rect's x position
    indices = np.apply_along_axis(lambda rect: rect[0], 1, cntRects).argsort()

    b1_u = -1  # index of the first 'B' in the unsorted arrays
    b1_s = -1  # index of the first 'B' in the sorted indices array

    for i in range(len(indices)):
        # indices[i] is the index of the would-be-sorted array
        if cntAreas[indices[i]] == B:
            b1_u = indices[i]
            b1_s = i
            break
    
    chip = -1  # index of the chip closest to the bet amount in the unsorted arrays

    if b1_u > -1:  # a 'B' was found
        x, _, w, _ = cntRects[b1_u]
        # delete the pixel columns of the first 'B' from the HSV iamge along with
        # everything to the right of it
        hsv = np.delete(hsv, np.s_[x:], axis=1)

        for i in range(b1_s, -1, -1):
            if cntAreas[indices[i]] > B:
                chip = indices[i]
                break
    else:
        # a 'B' should be present if the image is on the right side of the table and
        # the bbox is positioned appropriately, so in all likelihood this is a
        # situation where the chips are on the left side of the number and the 'BB'
        # text was cut off
        for i in range(len(indices)-1, -1, -1):
            if cntAreas[indices[i]] > B:
                chip = indices[i]
                break
    # if a chip could be found in the grayscale image, remove it from the HSV image
    # along with everything to the left of it
    if chip > -1:
        x, _, w, _ = cntRects[chip]
        hsv = np.delete(hsv, np.s_[:x+w+k], axis=1)

    # now that any chips have been removed the image, the image is first scaled and
    # then median blur is applied to it for noise reduction, after which it is
    # then binarized using given range of HSV values to distinguish the white-ish text
    hsv = scaleImage(hsv, scaleFactor)
    hsv = cv2.blur(hsv, (5, 5))
    result = cv2.bitwise_not(cv2.inRange(hsv, HSV_LOWER, HSV_UPPER))

    # pass the result onward to the OCR algorithm
    pilImg = Image.fromarray(result)
    pilImg.save('../img/test/foo.png')
    return getOcrNumber(api, pilImg, scaleFactor, binThresh, preprocess=False)



if __name__ == '__main__':
    api = PyTessBaseAPI(path='../tessdata', psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)

    path = '../img/test/chips8.png'
    scaleFactor = 4
    binThresh = 160

    #test_containsTemplate('tb1.png', 'playerActive.png')

    img = Image.open(path)
    res = getOcrBet(api, img, scaleFactor, binThresh)
    print(res)

    #img = Image.open(path)
    #res = getCard(api, img, scaleFactor, binThresh)
    #print(res)

    api.End()
