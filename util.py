import cv2
import numpy as np
from tesserocr import PyTessBaseAPI, PSM, OEM
from PIL import Image


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


def getOcrCard(api, img):
    """
    Returns a char representing the card value, e.g. '9', 'T', 'J', etc
    """
    api.SetImage(img)
    string = api.GetUTF8Text().strip()
    if len(string) == 0 or (len(string) == 2 and string != '10') or len(string) > 2:
        raise Exception("String '{}' is not an acceptable card value".format(string))
    if string == '10':
        return 'T'
    return string


def test_getOcrCard(api, imgName, scaleFactor, binThresh):
    images = ['img/' + imgName]
    for img in images:
        pilImg = Image.open(img)

        #avgGray = np.average(cv2.cvtColor(np.array(pilImg), cv2.COLOR_RGB2GRAY))
        #print(avgGray)

        pilImg = preprocessImage(pilImg, scaleFactor, binThresh)
        result = getOcrCard(api, pilImg)
        print(result)


def getOcrNumber(api, img):
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
    images = ['img/' + imgName]
    for img in images:
        pilImg = Image.open(img)
        pilImg = preprocessImage(pilImg, scaleFactor, binThresh)
        result = getOcrNumber(api, pilImg)
        print(result)


def preprocessImage(img, scaleFactor, binThresh):

    def scaleImage(img, scaleFactor):
        return img.resize((img.size[0] * scaleFactor, img.size[1] * scaleFactor))

    def binarize(img, threshold):
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        _, binarized = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)
        return Image.fromarray(binarized)

    img = scaleImage(img, scaleFactor)
    img = binarize(img, threshold=binThresh)
    return img


def test_preprocessImage(imgName, scaleFactor, binThresh):
    img = Image.open('img/' + imgName)
    img = preprocessImage(img, scaleFactor, binThresh)
    img.save('img/out.png')



if __name__ == '__main__':
    api = PyTessBaseAPI(path='tessdata', psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)

    testImgName = 'felt.png'
    scaleFactor = 4
    binThresh = 180
    test_preprocessImage(testImgName, scaleFactor, binThresh)
    test_getOcrCard(api, testImgName, scaleFactor, binThresh)

    api.End()
