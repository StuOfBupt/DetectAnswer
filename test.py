import json

import yaml

import numpy as np
from imutils.perspective import four_point_transform
import cv2
import imutils
from PIL import Image


def format_print_dict(d):
    print(json.dumps(d, indent=4, ensure_ascii=False))  # 缩进4空格，中文字符不转义成Unicode)


def load_config():
    f = open('settings.yaml')
    cf = yaml.load(f, Loader=yaml.FullLoader)
    format_print_dict(cf)
    cf['ANS_IMG_KERNEL'] = np.ones((2, 2), np.uint8)
    cf['CHOICE_IMG_KERNEL'] = np.ones((2, 2), np.uint8)
    return cf


def trans(base_image):
    gray = cv2.cvtColor(base_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = imutils.auto_canny(blurred)
    cnts = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    docCnt = None
    # 寻找答题卡区域
    if len(cnts) > 0:
        # 轮廓按照面积降序排列
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                docCnt = approx
                break
    else:
        return
    paper = four_point_transform(base_image, docCnt.reshape(4, 2))
    im = Image.fromarray(paper)
    im.save('trans.jpg')





if __name__ == '__main__':
    img_path = './images/t5.jpg'
    image = cv2.imread(img_path)
    trans(image)