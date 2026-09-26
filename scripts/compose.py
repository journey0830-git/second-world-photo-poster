#!/usr/bin/env python3
"""将原照片和独立下半幅确定性合成为 3:4 PNG；不调用生成 API。"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageOps


def box_value(value):
    try:
        box = tuple(map(float, value.split(',')))
        if len(box) != 4 or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            raise ValueError
        return box
    except ValueError:
        raise argparse.ArgumentTypeError('主体坐标须为 0–1 内的 x0,y0,x1,y1')


def fit(image, size, anchor):
    w, h = image.size
    ratio = size[0] / size[1]
    cw, ch = (h * ratio, h) if w / h > ratio else (w, w / ratio)
    left, top = (w - cw) * anchor[0], (h - ch) * anchor[1]
    crop = (left, top, left + cw, top + ch)
    return image.resize(size, Image.Resampling.LANCZOS, box=crop), crop


def read_rgb(path):
    with Image.open(path) as image:
        if image.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P'):
            raise ValueError('请先提供 RGB/sRGB 照片，避免隐式 CMYK 色彩转换')
        image = ImageOps.exif_transpose(image)
        if 'A' in image.getbands() and image.getchannel('A').getextrema()[0] < 255:
            raise ValueError('请输入已铺满背景的不透明图像')
        if image.mode == 'P' and 'transparency' in image.info:
            raise ValueError('不接受透明索引图像')
        return image.convert('RGB')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--photo', required=True, type=Path)
    p.add_argument('--lower', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--width', type=int, default=1500)
    p.add_argument('--subject-box', type=box_value)
    p.add_argument('--anchor-x', type=float, default=0.5)
    p.add_argument('--anchor-y', type=float, default=0.5)
    p.add_argument('--crop-lower', action='store_true', help='已视觉确认允许居中裁切下半幅')
    a = p.parse_args()
    report_path = a.output.with_suffix('.json')
    try:
        if a.width <= 0 or a.width % 3:
            raise ValueError('width 必须为 3 的正整数倍')
        if not all(0 <= v <= 1 for v in (a.anchor_x, a.anchor_y)):
            raise ValueError('anchor 必须在 0–1 内')
        if a.output.suffix.lower() != '.png':
            raise ValueError('output 必须为 PNG')
        if a.output.exists() or report_path.exists():
            raise ValueError('输出或检查记录已存在；请换新文件名')
        photo, lower = read_rgb(a.photo), read_rgb(a.lower)
        size = (a.width, a.width * 2 // 3)
        upper, crop = fit(photo, size, (a.anchor_x, a.anchor_y))
        if a.subject_box:
            x0, y0, x1, y1 = a.subject_box
            bounds = (x0 * photo.width, y0 * photo.height, x1 * photo.width, y1 * photo.height)
            if any((bounds[0] < crop[0], bounds[1] < crop[1], bounds[2] > crop[2], bounds[3] > crop[3])):
                raise ValueError('当前裁切会切断给定主体：调整 anchor 或与用户解决比例冲突')
        if lower.width * 2 != lower.height * 3 and not a.crop_lower:
            raise ValueError('下半幅不是 3:2；确认安全裁切后显式传入 --crop-lower')
        bottom, lower_crop = fit(lower, size, (0.5, 0.5))
        canvas = Image.new('RGB', (size[0], size[1] * 2))
        canvas.paste(upper, (0, 0))
        canvas.paste(bottom, (0, size[1]))
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('xb') as stream:
            canvas.save(stream, format='PNG')
        with Image.open(a.output) as saved:
            actual = saved.crop((0, 0, size[0], size[1])).convert('RGB')
            match = ImageChops.difference(actual, upper).getbbox() is None
        if not match:
            raise ValueError('保存后上半幅像素核验失败')
        report = {
            'size': list(canvas.size), 'seam_y': size[1],
            'aspect_3_4': canvas.width * 4 == canvas.height * 3,
            'equal_halves': True, 'upper_matches_source_transform': match,
            'photo_crop_xyxy': list(crop), 'lower_crop_xyxy': list(lower_crop),
            'subject_box': a.subject_box,
            'photo_sha256': hashlib.sha256(a.photo.read_bytes()).hexdigest(),
            'lower_sha256': hashlib.sha256(a.lower.read_bytes()).hexdigest(),
            'poster_sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
            'visual_review': 'required: 主体身份、裁切完整度、纹理、立体感、互动、英文和留白',
            'color_note': '保留 RGB 通道值，仅等比重采样；输入应为 sRGB。输出不复制 EXIF。'
        }
        with report_path.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps({'poster': str(a.output), 'report': str(report_path), 'structural_checks': 'passed'}, ensure_ascii=False))
    except (ValueError, OSError) as e:
        p.exit(2, f'错误：{e}\n')


if __name__ == '__main__':
    main()
