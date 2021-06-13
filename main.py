import cv2
import imutils
from PIL import Image
from imutils.perspective import four_point_transform

import test
import utils
from paddleocr import PaddleOCR, draw_ocr

ocr = PaddleOCR(det_model_dir='./model/ch_ppocr_server_v2.0_det_infer',
                cls_model_dir='./model/ch_ppocr_mobile_v2.0_cls_infer',
                rec_model_dir='./model/ch_ppocr_server_v2.0_rec_infer',
                use_angle_cls=True, lang='ch', use_gpu=False)
font_path = './fonts/simfang.ttf'

DEBUG_MODE = False
distance_estimation = set()


def cv_show(img, msg=""):
    if DEBUG_MODE:
        cv2.imshow('temp', img)
        if msg:
            print(msg)
        cv2.waitKey(0)


def get_answer(base_image, img_path=None):
    gray = cv2.cvtColor(base_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    cv_show(blurred, msg="blurred img")
    edged = imutils.auto_canny(blurred)
    cv_show(edged, msg="edged")

    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    cv_show(thresh, "thresh")

    # 二值图像中查找轮廓
    cnts = cv2.findContours(thresh.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    boxes = [cv2.boundingRect(cnt) for cnt in cnts]

    cp_img = base_image.copy()

    for bbox in boxes:
        [x, y, w, h] = bbox
        cv2.rectangle(cp_img, (x, y), (x + w, y + h), (255, 0, 0), 2)

    cv_show(cp_img, "cp")
    lines = ocr.ocr(img_path, cls=True)
    w_threshod, h_threshod = utils.get_choice_wh(lines)

    def between(var, threshod):
        return threshod[0] <= var <= threshod[1]

    choice_boxes = []
    for box in boxes:
        [x, y, w, h] = box
        if between(w, w_threshod) and between(h, h_threshod):
            choice_boxes.append(box)
            cv2.rectangle(base_image, (x, y), (x + w, y + h), (255, 0, 0), 2)
    cv_show(base_image, 'finial')
    utils.compute_choice_interval(choice_boxes)
    utils.compute_choice_width(choice_boxes)
    ans = dict()
    for num, (res, box) in utils.analysis_orc_lines(lines).items():
        if res is None:
            print('题号 %d ocr 未识别出选项,使用距离估算' % num)
            distance_estimation.add(num)
            res = utils.find_choice_by_num_box(box, choice_boxes)
        ans[num] = res
    # for num, xywh in utils.extract_num(lines).items():
    #     if num in ans:
    #         print('题号 %d 重复判断' % num)
    #         continue
    #     print('题号 %d 使用距离估算' % num)
    #     ans[num] = utils.find_choice_by_num_box(utils.xywh2box(*xywh), choice_boxes)

    test.format_print_dict(ans)
    utils.write_lines('lines.txt', lines)
    ocr_boxes = [line[0] for line in lines]
    im_show = draw_ocr(base_image, ocr_boxes, None, None, font_path=font_path)
    im_show = Image.fromarray(im_show)
    im_show.save('result.jpg')
    return ans


def filter_boxes(boxes, image):
    area = image.shape[0] * image.shape[1]
    valid_boxes = []
    max_area = 0
    for box in boxes:
        [_, _, w, h] = box
        if w > h and w / h < 3.0 and w * h < area / 8:
            valid_boxes.append(box)
            max_area = max(max_area, w * h)
    threshod = max_area * 0.6
    ret = []
    for box in valid_boxes:
        [_, _, w, h] = box
        if w * h > threshod:
            ret.append(box)
    return ret


def judge(ret, answer):
    count = 0
    for num, choice in answer.items():
        if num not in ret:
            print('题号 %d 没有识别出来' % num)
            continue
        if ret[num] != choice:
            msg = '距离估算错误' if num in distance_estimation else 'ocr 识别错误'
            print('题号 %d 识别错误 %s (%s), 原因:%s' % (num, ret[num], choice, msg))

            continue
        count += 1
    print('正确率:%.2f %d/%d' % (count / len(answer.keys()), count, len(answer.keys())))


if __name__ == '__main__':
    img_path = './images/t6.jpg'
    image = cv2.imread(img_path)
    ret = get_answer(image, img_path)
    answer = utils.read_answer('./answer/t6.txt')
    judge(ret, answer)
