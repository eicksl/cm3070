import cv2
import numpy as np
from tesserocr import PyTessBaseAPI, PSM, OEM
from PIL import Image, ImageOps
from src.bot.constants import (
    SUIT_PIXELS, CARD_RANKS, OCR_MAP, BET_BG_LOWER, BET_BG_UPPER,
    HSV_LOWER, HSV_UPPER, IMAGE_DIR
)


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
    #print('Output: ' + api.GetUTF8Text())
    #print('List: ' + str(api.GetUTF8Text().strip().split())) 
    try:
        string = api.GetUTF8Text().strip().split()[0]
    except IndexError:
        return None
    
    if string in OCR_MAP:
        return OCR_MAP[string]
    elif string[0] not in CARD_RANKS:
        img.save(IMAGE_DIR + 'test/unknown.png')
        raise Exception(
            "getOcrCard: output string '{}' is unknown. Check unknown.png.".format(string)
        )
    return string[0]


def test_getOcrCard(api, imgName, scaleFactor, binThresh):
    images = ['../img/' + imgName]
    for img in images:
        pilImg = Image.open(img)
        pilImg = preprocessImage(pilImg, scaleFactor, binThresh)
        result = getOcrCard(api, pilImg)
        print(result)


def getCard(api, pilImg, scaleFactor, binThresh):
    npImg = np.array(pilImg)
    suit = getCardSuit(npImg)
    if not suit:
        return None
    img = preprocessImage(npImg, scaleFactor, binThresh)
    if img[img.shape[0]-1][0] == 0:
        # fixes issues that may occur due to the white portion of the avatar
        ind = int(img.shape[0] * 0.9)
        img[ind:] = np.full((img.shape[0]-ind, img.shape[1]), 255, dtype=np.uint8)
    #cv2.imwrite('../img/test/card-cropped.png', img)
    card = getOcrCard(api, Image.fromarray(img))
    if not card:
        pilImg.save(IMAGE_DIR + 'test/card-orig.png')
        img.save(IMAGE_DIR + 'test/card-mask.png')
        raise Exception("Could not read card image saved as card-orig.png and card-mask.png")
    return card + suit


def getOcrNumber(api, img, scaleFactor, binThresh, preprocess=True):
    if preprocess:
        img = preprocessImage(np.array(img), scaleFactor, binThresh)
    api.SetImage(img)
    number = None
    #print(api.GetUTF8Text())
    for result in api.GetUTF8Text().split():
        result = result.replace('/', '7').replace('S', '5').replace('A', '4')
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


def preprocessImage(img, scaleFactor, binThresh):
    """
    Takes a numpy image and applies preprocessing methods using a scale factor and
    a binary threshold.
    """
    def binarize(img, threshold):
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        img = cv2.blur(img, (5, 5))
        _, binarized = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)
        return binarized

    img = scaleImage(img, scaleFactor)
    img = binarize(img, binThresh)
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


def getOcrStack(api, pilImg, scaleFactor, binThresh, k=25):
    # create a mask for the image using a binary threshold
    img = cv2.cvtColor(np.array(pilImg), cv2.COLOR_RGB2GRAY)
    mask = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY_INV)

    # find the first black pixel in the mask, starting from the right
    mid = mask[1].shape[0] // 2  # vertical midpoint
    firstBlack = 0  # index of the first black pixel seen
    for i in range(mask[1].shape[1]-1, -1, -1):
        pixel = mask[1][mid][i]
        if pixel == 0:
            firstBlack = i
            break
    if firstBlack == 0:
        raise Exception("Cannot find black pixel in binary image for stack size")
    
    # remove the 'BB' portion of the image
    img = img[:, :firstBlack-k]
    #cv2.imwrite('../img/test/cropped.png', img)
    img = scaleImage(img, scaleFactor)
    _, mask = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY_INV)

    # pass the result onward to the OCR algorithm
    pilImg = Image.fromarray(mask)
    #pilImg.save('../img/test/foo.png')
    return getOcrNumber(api, pilImg, scaleFactor, binThresh, preprocess=False)


def getOcrBet(api, pilImg, scaleFactor, binThresh, isMainPot=False, B=68, C=240, k=5, m=2, p=37):
    """
    :param isMainPot: True if the image is the total pot, False otherwise
    """
    # first convert to BGR and threshold the image using a range of BGR values
    # which makes the dark-green background white and the rest black
    img = cv2.cvtColor(np.array(pilImg), cv2.COLOR_RGB2BGR)
    mask = cv2.inRange(img, BET_BG_LOWER, BET_BG_UPPER)
    #cv2.imwrite('../img/test/mask1.png', mask)

    # find the contour of the white portion of the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rect = None
    for cnt in contours:
        #print(cv2.contourArea(cnt))
        if cv2.contourArea(cnt) > C:
            rect = cv2.boundingRect(cnt)
    # if no contour, wager is not present, so just return None
    if rect is None:
        return None

    # crop the original using the bounding rect
    x, y, w, h = rect
    if isMainPot:
        img = img[y:y+h, x+k+p:x+w-k]
    else:
        img = img[y:y+h, x+k:x+w-k]
    
    # take the grayscale and perform binary thresholding
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY)
    #cv2.imwrite('../img/test/mask2.png', mask)

    # now find the first 'B' and crop it out of the grayscale image
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rect = None
    for i in range(len(contours)-1, -1, -1):
        #print(cv2.contourArea(contours[i]))
        if cv2.contourArea(contours[i]) >= B:
            rect = cv2.boundingRect(contours[i])
            break
    if rect is None:
        # the first 'B' should be present in the image so it can be fully removed
        # if it is cut in half, for example, the OCR output may be incorrect
        raise Exception("No 'B' found in wager image")
    img = img[:, :rect[0]-m]
    cv2.imwrite('../img/test/gray.png', img)

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
    #pilImg.save('../img/test/foo.png')
    return getOcrNumber(api, pilImg, scaleFactor, binThresh, preprocess=False)


def _boardToRanked(cards):
    """
    Helper function that converts a list of board cards to their corresponding integer ranks.
    If the average rank is below 7, then aces will be ranked lowest.

    :param cards: the board cards as a list of chars
    :returns: the board cards as a list of integers
    """
    noAces = []
    for card in cards:
        if card != 'A':
            noAces.append(card)
    avgRank = sum(CARD_RANKS[x] for x in noAces) / len(cards)
    toRank = lambda x: 0 if x == 'A' and avgRank < 7 else CARD_RANKS[x]
    return [toRank(x) for x in cards]


def hasFourStraight(boardCards):
    """
    Determines whether the board has four to a straight.

    :param boardCards: the board cards as a list of chars
    :returns: boolean
    """
    cards = list(set(boardCards))
    if len(cards) < 4:
        return False

    cards = sorted(_boardToRanked(cards), reverse=True)

    if len(cards) == 5:
        if cards[0] - cards[1] > cards[3] - cards[4]:
            cards.pop(0)
        else:
            cards.pop(4)

    n = 0
    for i in range(3):
        diff = cards[i] - cards[i+1]
        if diff > 2:
            return False
        elif diff != 1:
            n += 1

    if n > 1:
        return False

    return True


def lc_4straight(boardCards):
    """
    Determines whether the last card brought four to a straight. Assumes that the board
    has four to a straight.

    :param boardCards: the board cards as a list of chars
    :returns: boolean
    """
    if len(boardCards) < 5:
        return True

    cards = _boardToRanked(boardCards)
    lcRank = cards[-1]
    cards.sort(reverse=True)
    if cards[0] - cards[1] > cards[3] - cards[4]:
        removed = cards.pop(0)
    else:
        removed = cards.pop(4)
    
    return lcRank != removed


def mapRange(x, x0, x1, y0, y1):
    """
    For an input x in range [x0, x1], use linear interpolation to map x
    to some y in the range [y0, y1].
    """
    return (x - x0) * (y1 - y0) / (x1 - x0) + y0


def quadInterp(x, x0, y0, x1, y1, x2, y2):
    """
    Quadratic interpolation using the mid-way point (x1, y1).
    """
    g0 = (x - x1) * (x - x2) / (x0 - x1) * (x0 - x2)
    g1 = (x - x0) * (x - x2) / (x1 - x0) * (x1 - x2)
    g2 = (x - x0) * (x - x1) / (x2 - x0) * (x2 - x1)
    return y0 * g0 + y1 * g1 + y2 * g2



if __name__ == '__main__':
    api = PyTessBaseAPI(path='../tessdata', psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)
    #api.SetVariable("tessedit_char_whitelist", "0123456789.JQKA")

    path = '../img/test/57bb.png'
    scaleFactor = 4
    binThresh = 180

    #test_containsTemplate('tb1.png', 'playerActive.png')

    img = Image.open(path)
    
    #img = np.array(img)
    #img = scaleImage(img, scaleFactor)
    #img = cv2.blur(img, (5, 5))
    #_, img = cv2.threshold(img, binThresh, 255, cv2.THRESH_BINARY_INV)
    #cv2.imwrite('../../img/test/mask2-inv.png', img)
    #mg = Image.fromarray(img)

    res = getOcrBet(api, img, scaleFactor, binThresh, isMainPot=False)
    #res = getOcrBet_old(api, img, scaleFactor, binThresh)
    #res = getOcrNumber(api, img, scaleFactor, binThresh, preprocess=False)
    #res = getOcrStack(api, img, scaleFactor, binThresh)
    #print(res)

    #img = Image.open(path)
    #res = getCard(api, img, scaleFactor, binThresh)
    #res = getOcrCard(api, img)
    print(res)

    api.End()
