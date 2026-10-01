#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《男娘恋爱物语》移植资源合成与压缩
- 立绘: base+brow+eye+mouth(+addon) 分层合成 -> 240x480 透明 PNG(P模式量化)
- CG: meicg1 分层合成 / meicg2 整图 -> 336x480 JPEG
- 背景: 原图缩放 -> 336x480 JPEG
- logo/title_bg
"""
import os, json
from PIL import Image

SRC = "/home/user/Doubao/chats/38445140291631362/_analyze/男娘恋爱物语_移植素材包/02_美术/images"
DST = "/home/user/Doubao/chats/38445140291631362/build/src/common"

CH_OUT = 480   # 立绘输出高度
BG_SIZE = (336, 480)
CH_WIDTH = 240

# ---------- 立绘表情组合 (face.rpy) ----------
MEI_FACES = {
    "smile":  ("brow01", "eye05", "mouth09", None), "no":   ("brow01", "eye02", "mouth12", None),
    "shadow": ("brow02", "eye06", "mouth01", None), "laugh":("brow06", "eye07", "mouth08", "addon01"),
    "smile2": ("brow02", "eye02", "mouth11", None), "wut":  ("brow06", "eye07", "mouth07", "addon01"),
    "smile3": ("brow01", "eye01", "mouth09", None), "no2":  ("brow01", "eye04", "mouth06", None),
    "proud":  ("brow02", "eye02", "mouth10", "addon01"), "smile4": ("brow01", "eye01", "mouth09", "addon01"),
    "proud2": ("brow05", "eye05", "mouth08", None), "buz":  ("brow02", "eye07", "mouth01", None),
    "smile5": ("brow01", "eye07", "mouth11", None), "proud3":("brow05", "eye05", "mouth10", "addon01"),
    "no3":    ("brow01", "eye05", "mouth04", None), "laugh2":("brow06", "eye07", "mouth08", None),
    "no4":    ("brow01", "eye02", "mouth06", None), "no5":  ("brow03", "eye06", "mouth12", None),
    "no6":    ("brow01", "eye06", "mouth06", None), "sad":  ("brow04", "eye03", "mouth06", None),
    "wut2":   ("brow06", "eye03", "mouth03", "addon01"), "no7": ("brow01", "eye04", "mouth06", "addon01"),
    "no8":    ("brow01", "eye02", "mouth06", "addon01"), "sad2": ("brow03", "eye02", "mouth12", "addon01"),
    "sick":   ("brow03", "eye06", "mouth12", "addon01"), "no9": ("brow01", "eye02", "mouth12", "addon01"),
    "sad3":   ("brow04", "eye03", "mouth06", "addon01"), "no10": ("brow01", "eye04", "mouth12", None),
    "buz2":   ("brow02", "eye07", "mouth01", "addon01"),
}
FEI_FACES = {
    "no":    ("brow05", "eye04", "mouth09", None), "smile": ("brow05", "eye04", "mouth10", None),
    "smile2":("brow05", "eye04", "mouth07", None), "smile3":("brow05", "eye02", "mouth06", None),
    "laugh": ("brow01", "eye04", "mouth05", None), "no2":   ("brow05", "eye04", "mouth02", None),
    "anger": ("brow03", "eye05", "mouth08", None), "anger2":("brow03", "eye05", "mouth01", None),
    "anger3":("brow04", "eye05", "mouth01", None), "no3":   ("brow05", "eye02", "mouth04", None),
    "no4":   ("brow05", "eye04", "mouth03", None), "no5":   ("brow04", "eye06", "mouth09", None),
    "wut":   ("brow01", "eye05", "mouth02", None), "anger4":("brow03", "eye05", "mouth02", None),
    "anger5":("brow03", "eye05", "mouth04", None), "anger6":("brow04", "eye01", "mouth01", None),
    "anger7":("brow04", "eye05", "mouth01", "addon01"), "laugh2":("brow01", "eye04", "mouth05", "addon01"),
    "no6":   ("brow04", "eye06", "mouth09", "addon01"), "anger8":("brow03", "eye05", "mouth08", "addon01"),
}

# 剧本实际用到的立绘（从转换后剧本扫描）
def used_chars():
    used = set()
    scn_dir = "/home/user/Doubao/chats/38445140291631362/build/src/common/scn"
    for fn in sorted(os.listdir(scn_dir)):
        if not fn.endswith(".txt"): continue
        for node in json.load(open(os.path.join(scn_dir, fn), encoding="utf-8")):
            if node[0] == 7 and node[1] != "*":
                used.add(node[1])
    return used

# ---------- meicg1 CG 组合 (cg.rpy) ----------
MEICG1_FACES = {
    "no":    ("brow01", "eye03", "mouth05", [], None),
    "no2":   ("brow04", "eye03", "mouth03", ["addon02"], "meicg1_m_blush1.png"),
    "cute":  ("brow05", "eye01", "mouth02", ["addon01"], None),
    "no3":   ("brow05", "eye02", "mouth03", ["addon02"], None),
    "cute2": ("brow01", "eye02", "mouth02", ["addon02"], None),
    "air":   ("brow05", "eye01", "mouth01", ["addon02"], "meicg1_m_blush2.png"),
    "cute3": ("brow05", "eye01", "mouth03", ["addon01"], None),
    "cute4": ("brow05", "eye03", "mouth03", ["addon02", "addon01"], None),
    "air2":  ("brow05", "eye01", "mouth01", ["addon01"], None),
}

def compose_layered(base, layers, out_size, mode):
    im = Image.open(base).convert("RGBA")
    for f in layers:
        if not f: continue
        p = os.path.join(os.path.dirname(base), f)
        if not os.path.exists(p):
            print(f"  缺层: {p}"); continue
        layer = Image.open(p).convert("RGBA")
        im = Image.alpha_composite(im, layer)
    return im.resize(out_size, Image.LANCZOS)

def save_png_p(im, path, colors=64):
    """RGBA -> P 模式量化，保留透明"""
    q = im.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG)
    q.save(path, "PNG", optimize=True)

def build_chars():
    out_dir = os.path.join(DST, "ch")
    os.makedirs(out_dir, exist_ok=True)
    used = used_chars()
    # mei
    for face, (br, ey, mo, add) in MEI_FACES.items():
        name = f"mei_{face}"
        if name not in used: continue
        base = os.path.join(SRC, "mei", "mei_base.png")
        layers = [f"mei/brow/mei_brow_{br}.png", f"mei/eye/mei_eye_{ey}.png", f"mei/mouth/mei_mouth_{mo}.png"]
        if add: layers.append(f"mei/addon/mei_addon_{add}.png")
        full = [os.path.join(SRC, "mei", "mei_base.png")] + [os.path.join(SRC, l) for l in layers]
        im = Image.open(base).convert("RGBA")
        for l in layers:
            im = Image.alpha_composite(im, Image.open(os.path.join(SRC, l)).convert("RGBA"))
        w = int(im.size[0] * CH_OUT / im.size[1])
        im = im.resize((w, CH_OUT), Image.LANCZOS)
        save_png_p(im, os.path.join(out_dir, f"{name}.png"))
        print(f"ch/{name}.png {os.path.getsize(os.path.join(out_dir, f'{name}.png'))//1024}KB")
    # fei
    for face, (br, ey, mo, add) in FEI_FACES.items():
        name = f"fei_{face}"
        if name not in used: continue
        layers = [f"fei/brow/fei_brow_{br}.png", f"fei/eye/fei_eye_{ey}.png", f"fei/mouth/fei_mouth_{mo}.png"]
        if add: layers.append(f"fei/addon/fei_addon_{add}.png")
        im = Image.open(os.path.join(SRC, "fei", "fei_base.png")).convert("RGBA")
        for l in layers:
            im = Image.alpha_composite(im, Image.open(os.path.join(SRC, l)).convert("RGBA"))
        w = int(im.size[0] * CH_OUT / im.size[1])
        im = im.resize((w, CH_OUT), Image.LANCZOS)
        save_png_p(im, os.path.join(out_dir, f"{name}.png"))
        print(f"ch/{name}.png {os.path.getsize(os.path.join(out_dir, f'{name}.png'))//1024}KB")

def build_cg():
    out_dir = os.path.join(DST, "ev")
    os.makedirs(out_dir, exist_ok=True)
    # meicg1 分层
    base = os.path.join(SRC, "meicg1", "meicg1_base.png")
    for face, (br, ey, mo, adds, blush) in MEICG1_FACES.items():
        im = Image.open(base).convert("RGBA")
        for l in [f"meicg1/brow/meicg1_brow_{br}.png", f"meicg1/eye/meicg1_eye_{ey}.png", f"meicg1/mouth/meicg1_mouth_{mo}.png"]:
            im = Image.alpha_composite(im, Image.open(os.path.join(SRC, l)).convert("RGBA"))
        for a in adds:
            im = Image.alpha_composite(im, Image.open(os.path.join(SRC, f"meicg1/addon/meicg1_addon_{a}.png")).convert("RGBA"))
        if blush:
            im = Image.alpha_composite(im, Image.open(os.path.join(SRC, "meicg1", blush)).convert("RGBA"))
        im = im.resize(BG_SIZE, Image.LANCZOS).convert("RGB")
        im.save(os.path.join(out_dir, f"evmeicg1_{face}.jpg"), "JPEG", quality=66, optimize=True)
        print(f"ev/evmeicg1_{face}.jpg {os.path.getsize(os.path.join(out_dir, f'evmeicg1_{face}.jpg'))//1024}KB")
    # meicg1_gallery
    im = Image.open(os.path.join(SRC, "meicg1_gallery.png")).convert("RGB").resize(BG_SIZE, Image.LANCZOS)
    im.save(os.path.join(out_dir, "evmeicg1_gallery.jpg"), "JPEG", quality=66, optimize=True)
    print(f"ev/evmeicg1_gallery.jpg {os.path.getsize(os.path.join(out_dir, 'evmeicg1_gallery.jpg'))//1024}KB")
    # meicg2 整图
    for f in ["kiss", "smile", "worry", "wut", "wut2"]:
        im = Image.open(os.path.join(SRC, "meicg2", f"meicg2 {f}.png")).convert("RGB").resize(BG_SIZE, Image.LANCZOS)
        im.save(os.path.join(out_dir, f"evmeicg2_{f}.jpg"), "JPEG", quality=66, optimize=True)
        print(f"ev/evmeicg2_{f}.jpg {os.path.getsize(os.path.join(out_dir, f'evmeicg2_{f}.jpg'))//1024}KB")

def build_bg():
    import glob
    out_dir = os.path.join(DST, "bg")
    os.makedirs(out_dir, exist_ok=True)
    bg_src = os.path.join(SRC, "bg")
    # 按文件名关键词匹配（原素材命名不统一：@2.png/.jpg/.png）
    targets = ["bg gate", "bg ground", "bg room", "bg room dark", "bg street2",
               "bg tea", "bg classroom", "bg resturant", "bg gym", "bg lake",
               "bg museum", "bg street2 night", "bg tea night", "bg room night"]
    for t in targets:
        out_name = t.replace(" ", "_")
        pats = [os.path.join(bg_src, t + "@2.jpg"), os.path.join(bg_src, t + "@2.png"),
                os.path.join(bg_src, t + ".jpg"), os.path.join(bg_src, t + ".png")]
        p = next((x for x in pats if os.path.exists(x)), None)
        if not p:
            print(f"  缺: {t}"); continue
        im = Image.open(p).convert("RGB").resize(BG_SIZE, Image.LANCZOS)
        im.save(os.path.join(out_dir, f"{out_name}.jpg"), "JPEG", quality=60, optimize=True)
        print(f"bg/{out_name}.jpg {os.path.getsize(os.path.join(out_dir, f'{out_name}.jpg'))//1024}KB")
    # 白/黑
    Image.new("RGB", BG_SIZE, (255, 255, 255)).save(os.path.join(out_dir, "bg_white.jpg"), "JPEG", quality=70)
    Image.new("RGB", BG_SIZE, (0, 0, 0)).save(os.path.join(out_dir, "bg_black.jpg"), "JPEG", quality=70)
    print("bg_white/bg_black done")

def build_logo():
    # logo: 用小美微笑 CG 裁中心 128x128
    im = Image.open(os.path.join(SRC, "meicg2", "meicg2 smile.png")).convert("RGB")
    im = im.resize(BG_SIZE, Image.LANCZOS)
    # 裁中央区域（头部位置偏上）→ 取中间偏上
    w, h = im.size
    crop = im.crop((w//2 - 60, h//2 - 90, w//2 + 60, h//2 + 30)).resize((128, 128), Image.LANCZOS)
    crop.save(os.path.join(DST, "logo.png"), "PNG", optimize=True)
    print(f"logo.png {os.path.getsize(os.path.join(DST, 'logo.png'))//1024}KB")
    # title_bg: 用博物馆背景做标题背景
    im = Image.open(os.path.join(SRC, "bg", "bg museum.png")).convert("RGB").resize(BG_SIZE, Image.LANCZOS)
    im.save(os.path.join(DST, "title_bg.jpg"), "JPEG", quality=62, optimize=True)
    print(f"title_bg.jpg {os.path.getsize(os.path.join(DST, 'title_bg.jpg'))//1024}KB")

if __name__ == "__main__":
    print("== 立绘 =="); build_chars()
    print("== CG =="); build_cg()
    print("== 背景 =="); build_bg()
    print("== logo/title =="); build_logo()
