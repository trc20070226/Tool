#!/usr/bin/env python3
"""
批量处理照片,准备上传到网站的 photos 文件夹。

做了什么:
  1. 缩小照片(长边最多 2000 像素)并压缩成 JPG
  2. 自动转正手机拍照时的方向
  3. 按拍摄日期重命名,例如 2026-10-18-01.jpg
     (如果原文件名有意义,比如 boston-sunset.jpg,会保留成 2026-10-18-boston-sunset.jpg)
  4. 支持 iPhone 的 HEIC 照片(需要安装 pillow-heif)

用法:
  python3 photo_tool.py                 处理 input_photos 文件夹,结果放进 output_photos
  python3 photo_tool.py 我的照片        处理指定文件夹
  python3 photo_tool.py 我的照片 结果    指定输入和输出文件夹
"""

import re
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # 没装也能处理 JPG/PNG,只是不能读 HEIC

# ===== 可以改的设置 =====
MAX_SIDE = 2000      # 长边最大像素
QUALITY = 82         # JPG 质量(1~100),80 左右肉眼基本看不出区别
DEFAULT_IN = "input_photos"
DEFAULT_OUT = "output_photos"
# ========================

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

# 像 IMG_1234、DSC00012、PXL_20260101_123456789 这种相机默认名,没有意义,不保留
GENERIC = re.compile(r"(?i)(img|dsc|dscf|pxl|mvimg|image|photo)?[_\-\s]*[\dE_\-\s]*")


def taken_time(path: Path) -> datetime:
    """优先读 EXIF 里的拍摄时间,读不到就用文件修改时间。"""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            raw = None
            try:
                raw = exif.get_ifd(0x8769).get(36867)  # DateTimeOriginal
            except Exception:
                pass
            raw = raw or exif.get(306)  # DateTime
            if raw:
                return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def clean_stem(stem: str) -> str:
    """把原文件名整理成适合做网址的短名字;没有意义的返回空字符串。"""
    if GENERIC.fullmatch(stem):
        return ""
    s = re.sub(r"\s+", "-", stem.strip())
    s = re.sub(r'[\\/:*?"<>|#%&+]', "", s)
    return s.strip("-_.")


def to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def kb(n: int) -> str:
    return f"{n / 1024:.0f}KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f}MB"


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN)
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT)

    if not src.is_dir():
        print(f"找不到文件夹:{src}")
        print(f"请先新建一个叫 {src} 的文件夹,把照片放进去,再运行一次。")
        src.mkdir(exist_ok=True)
        return

    files = [p for p in src.iterdir() if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(".")]
    if not files:
        print(f"{src} 里没有找到照片(支持 jpg、png、webp、heic)。")
        return

    dst.mkdir(exist_ok=True)

    # 按拍摄时间排序,这样同一天的编号和拍摄顺序一致
    items = sorted(((taken_time(p), p) for p in files), key=lambda t: (t[0], t[1].name))

    day_count = {}
    total_before = total_after = 0
    done = 0

    for when, path in items:
        day = when.strftime("%Y-%m-%d")
        day_count[day] = day_count.get(day, 0) + 1
        stem = clean_stem(path.stem)
        name = f"{day}-{stem}" if stem else f"{day}-{day_count[day]:02d}"

        out = dst / f"{name}.jpg"
        n = 2
        while out.exists():  # 重名时自动加后缀,不会覆盖
            out = dst / f"{name}-{n}.jpg"
            n += 1

        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                img = to_rgb(img)
                img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                img.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        except Exception as e:
            print(f"跳过 {path.name}:{e}")
            if path.suffix.lower() in (".heic", ".heif"):
                print("  提示:读取 HEIC 需要先运行  pip3 install pillow-heif")
            continue

        before, after = path.stat().st_size, out.stat().st_size
        total_before += before
        total_after += after
        done += 1
        print(f"{path.name}  →  {out.name}   {kb(before)} → {kb(after)}")

    print()
    print(f"完成:处理了 {done} 张照片,总大小 {kb(total_before)} → {kb(total_after)}")
    print(f"结果在文件夹:{dst.resolve()}")
    print("把里面的图片上传到 GitHub 仓库的 photos 文件夹就可以了。")


if __name__ == "__main__":
    main()
