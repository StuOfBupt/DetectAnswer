from functools import cmp_to_key
from test import load_config

config = load_config()


# 根据 orc 切分结果获取一个选项框的宽和高区域范围
def get_choice_wh(lines):
    boxes = [line[0] for line in lines]
    heights = []
    for box in boxes:
        heights.append(box[-1][1] - box[0][1])
    # 高的计算直接拿平均宽度 * 1.5
    avg_h = sum(heights) / len(heights)
    min_h = avg_h * 0.7
    max_h = avg_h * 1.5
    min_w = min_h * 2
    max_w = max_h * 2
    return (min_w, max_w), (min_h, max_h)


# 分析 ocr 结果
def analysis_orc_lines(lines: list):
    # 只包含题号的
    # 只包含选项的
    # 包含题号和选项
    choice = config['choices']

    # 返回 text 中有多少个数字以及每个数字的起始位置
    # eg. '12ABD 24 BCD'
    def split_line_by_num(text: str):
        result = []
        length = len(text)
        i = 0
        while i < length:
            if not text[i].isdigit():
                i += 1
                continue
            j = i + 1
            while j < length:
                if text[j].isdigit():
                    j += 1
                else:
                    break
            result.append(i)
            i = j
        return result

    # 过滤文本 留下数字和大写的选项
    def filter(text):
        s = ""
        for c in text:
            if c.isalpha() and c.upper() in choice:
                s += c.upper()
                continue
            if c.isdigit():
                s += c
        return s

    def get_choice(text):
        res = []
        for c in choice:
            res.append(c in text)
        if sum(res) != len(choice) - 1:
            return None
        for i in range(len(res)):
            if not res[i]:
                return choice[i]
        return None

    # 分析题目和其选项
    # 返回题号和它对应的选项，若没有则置为 None
    def analysis(text: str):
        if text.isdigit():
            return int(text), None
        elif text.isalnum():
            num = ""
            for c in text:
                if not c.isdigit():
                    break
                num += c
            if not num.isdigit():
                return None, None
            return int(num), get_choice(text)
        else:
            return None, None

    # 返回 {题目--->（选项， 位置）}
    ret = dict()
    for line in lines:
        txt, confidence = line[1]
        if txt.isdigit() and confidence <= 0.85:
            # 纯数字的置信度应大于 0.85
            continue
        box = line[0]
        X, Y, W, H = box2xywh(box)
        texts = split_line_by_num(txt)
        if not texts:
            # 不包含数字的行 直接过滤
            continue
        length = len(txt)
        for i in range(len(texts)):
            start = texts[i]
            end = length
            if i + 1 < len(texts):
                end = texts[i + 1]
            text = txt[start: end]
            s = filter(text)
            num, res = analysis(s)
            if num:
                # 若 num 不在 或者 单单分析出题号，则使用距离估算
                x = X + (start / length) * W
                w = W * (end - start) / length
                if num not in ret or res is None:
                    ret[num] = (res, xywh2box(x, Y, w, H))
    return ret


def find_choice_by_num_box(num_box, choice_boxes):
    h0, h1 = num_box[0][1], num_box[-1][1]
    x0 = num_box[0][0] + (h1 - h0) * 1.5  # 题目所在 x 位置
    candidate = []
    for box in choice_boxes:
        x, y0, w, h = box
        y1 = y0 + h
        min_y = min(y0, h0)
        max_y = max(y1, h1)
        # 选项在题目右侧并且横向有交集，则加入备选序列
        if (x + w / 2) > x0 and (max_y - min_y) < (h + h1 - h0):
            candidate.append(box)
    # 没有候选项，返回 None
    if len(candidate) == 0:
        print('没有候选项')
        return None

    # 按照 x 坐标排序
    def compare(b1, b2):
        if b1[0] == b2[0]:
            return 0
        elif b1[0] < b2[0]:
            return -1
        else:
            return 1

    candidate.sort(key=cmp_to_key(compare))
    choice = candidate[0]
    x, y, w, h = choice
    choice = ['A', 'B', 'C', 'D']
    if config['choice_width'] > 0:
        w = config['choice_width']
    interval = config['choice_interval']
    idx = int((x - x0) / (w + interval))
    print('选项宽度: %.2f\t估算偏移:%d' % (w, idx))
    if idx >= len(choice):
        return choice[-1]
    else:
        return choice[idx]


def read_answer(file):
    ret = dict()
    with open(file) as fr:
        for line in fr.readlines():
            line = line.strip().split(' ')
            ret[int(line[0])] = line[1]
    return ret


def write_lines(file, lines):
    with open(file, 'w') as fr:
        for line in lines:
            fr.write(line[1][0])
            fr.write('\t置信度:%.2f' % line[1][1])
            fr.write('\n')


# 计算每个选项框之间的间隙
def compute_choice_interval(choice_boxes: list):
    if len(choice_boxes) < 2:
        return

    # 先按照 x 坐标排序
    def cmp_x(b1, b2):
        if b1[0] == b2[0]:
            return 0
        elif b1[0] < b2[0]:
            return -1
        else:
            return 1

    choice_boxes.sort(key=cmp_to_key(cmp_x))
    intervals = []
    for box in choice_boxes:
        x, _, w, _ = box
        if len(intervals) == 0:
            intervals.append([x, x + w])
            continue
        last = intervals[-1]
        if x > last[1]:
            intervals.append([x, x + w])
        else:
            last[1] = x + w
    interval = 9999
    for i in range(len(intervals) - 1):
        # 计算最小间隔作为每个选项的间隔
        interval = min(intervals[i + 1][0] - intervals[i][1], interval)
    config['choice_interval'] = interval
    print('选项间间隔：%.2f' % interval)


# 计算选项框的平均宽度
def compute_choice_width(choice_boxes: list):
    widths = []
    for box in choice_boxes:
        _, _, w, _ = box
        widths.append(w)

    # 选项小于 10 直接计算平均
    if len(widths) >= 10:
        widths.sort()
        length = len(widths)
        # 长度大于 10 取其中 60% 作为依据
        length = length // 5
        widths = widths[length: -length]
    config['choice_width'] = sum(widths) / len(widths)


# 从 ocr 文本行中提取选项和位置
# 一个文本行中可能有多个，返回列表结果 [[num, x, y, w, h], ...]
def extract_num_pos(line: list):
    result = []
    txt, _ = line[1]
    # 不包含数字,过滤
    if not any([c.isdigit() for c in txt]):
        return result
    box = line[0]
    # 文本框的坐标,宽高
    X, Y = box[0]
    W = box[1][0] - X
    H = box[-1][1] - Y
    i = 0
    length = len(txt)
    while i < length:
        if not txt[i].isdigit():
            i += 1
            continue
        j = i + 1
        while j < length:
            if txt[j].isdigit():
                j += 1
            else:
                break
        num = int(txt[i: j])
        x = X + W * (i / length)
        # 认为数字的宽度等于高度
        w = H
        result.append([num, x, Y, w, H])
        i = j
    return result


def extract_num(lines: list):
    ret = dict()
    for line in lines:
        nums = extract_num_pos(line)
        if not nums:
            continue
        for item in nums:
            ret[item[0]] = item[1:]
    return ret


def xywh2box(x, y, w, h):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def box2xywh(box):
    x, y = box[0]
    w = box[1][0] - x
    h = box[-1][1] - y
    return x, y, w, h
