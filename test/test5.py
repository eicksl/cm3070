from tesserocr import PyTessBaseAPI, PSM, OEM
from PIL import Image

with PyTessBaseAPI() as api:
    api = PyTessBaseAPI(path='../tessdata', psm=PSM.SINGLE_LINE, oem=OEM.LSTM_ONLY)
    api.SetVariable("tessedit_char_whitelist", "0123456789.JQKA")
    img = Image.open('../img/test/foo.png')
    api.SetImage(img)
    print(api.GetUTF8Text())
