import cv2
import numpy as np
from PIL import Image

path_sm = '../img/test/chips1.png'
path_lg = '../img/test/chips1_lg.png'
path_foo = '../img/test/foo.png'

#img = cv2.imread(path_lg, cv2.IMREAD_GRAYSCALE)
#img = cv2.blur(img, (10, 10))
#cv2.imwrite('../img/test/gray_lg.png', img)

orig = cv2.imread(path_sm)

resized = cv2.resize(orig, (orig.shape[1] * 4, orig.shape[0] * 4), interpolation=cv2.INTER_CUBIC)
cv2.imwrite('../img/test/resized-cubic.png', resized)

blur = cv2.blur(orig, (4, 4))
#blur = orig
hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
lower = np.array([0, 0, 160], dtype=np.uint8)
upper = np.array([95, 110, 255], dtype=np.uint8)
mask = cv2.inRange(hsv, lower, upper)
out = cv2.bitwise_not(mask)

#cv2.imwrite('../img/test/blur.png', blur)
#cv2.imwrite('../img/test/mask.png', mask)
cv2.imwrite('../img/test/has-blur.png', out)

#_, img = cv2.threshold(img, 140, 255, cv2.THRESH_BINARY)
#cv2.imwrite('../img/test/blur_lg.png', img)
