#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_qlwh.py — 《千恋＊万花》内容包校验器

校验项：
  1. game.txt 可解析，场景列表完整（chunk001..112）
  2. 每个 chunk 为合法 JSON 数组，节点类型合法，标签块内唯一
  3. 资源引用存在：
     - 节点2 背景   → src/common/bg/<name>.jpg
     - 节点3/7 立绘 → src/common/ch/<key>.png
     - 节点5 事件图 → src/common/ev/<name>.{jpg|png}（ev*→jpg，其余→png）
  4. 跳转目标可解析：
     - 节点4 选项目标 / 节点6 跳转目标 → 本块标签 或 "场景id@标签"（跨块）
     - 节点6 含 "gameend"/"endrecollection" 视为结局跳转
     - 节点6 可选第 3 元素为条件表达式（非空字符串）
  5. 选项表达式 / 条件引用格式抽查（f.c<页号>=<序号>、f.c<页号> == <序号>）

用法：python3 tools/validate_qlwh.py
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCN_DIR = os.path.join(ROOT, "src", "common", "scn")
BG_DIR = os.path.join(ROOT, "src", "common", "bg")
CH_DIR = os.path.join(ROOT, "src", "common", "ch")
EV_DIR = os.path.join(ROOT, "src", "common", "ev")
GAME_TXT = os.path.join(ROOT, "src", "common", "game.txt")

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def ev_ext(name):
    return ".jpg" if name.startswith("ev") else ".png"


def main():
    # 1. game.txt
    if not os.path.isfile(GAME_TXT):
        err("缺少 game.txt")
        sys.exit(1)
    with open(GAME_TXT, encoding="utf-8") as fh:
        game = json.load(fh)
    scns = game.get("scenarios", {}).get("main", [])
    if len(scns) != 112:
        err("场景数量应为 112，实际 %d" % len(scns))
    id_set = set()
    for s in scns:
        if s["id"] in id_set:
            err("场景 id 重复: %s" % s["id"])
        id_set.add(s["id"])
        p = os.path.join(SCN_DIR, s["path"])
        if not os.path.isfile(p):
            err("场景文件缺失: %s" % s["path"])

    # 2. 遍历 chunk
    files = sorted(glob.glob(os.path.join(SCN_DIR, "chunk*.txt")))
    if len(files) != 112:
        err("chunk 文件数量应为 112，实际 %d" % len(files))
    bg_refs, ch_refs, ev_refs = set(), set(), set()
    label_locs = {}  # (chunkId, label) -> ok
    total_nodes = 0
    cond_re = re.compile(r"^f\.c\d+ == \d+(\s*&&\s*f\.c\d+ == \d+)*$")
    exp_re = re.compile(r"^f\.c\d+=\d+$")
    opt_count = 0
    for f in files:
        cid = re.search(r"chunk(\d+)\.txt$", f).group(1)
        with open(f, encoding="utf-8") as fh:
            arr = json.load(fh)
        if not isinstance(arr, list):
            err("chunk%s 不是 JSON 数组" % cid)
            continue
        total_nodes += len(arr)
        labels = {}
        valid_types = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        for i, n in enumerate(arr):
            if not isinstance(n, list) or len(n) < 2:
                err("chunk%s[%d] 节点结构非法: %s" % (cid, i, n))
                continue
            t = n[0]
            if t not in valid_types:
                err("chunk%s[%d] 节点类型非法: %s" % (cid, i, t))
                continue
            if t == 0:
                lab = n[1]
                if lab in labels:
                    err("chunk%s 标签重复: %s" % (cid, lab))
                labels[lab] = i
            elif t == 2:
                bg_refs.add(n[1])
            elif t == 3:
                if len(n) >= 4 and isinstance(n[3], list):
                    for ch in n[3]:
                        if isinstance(ch, list) and len(ch) >= 1:
                            ch_refs.add(ch[0])
                if not isinstance(n[1], str) or not isinstance(n[2], str):
                    err("chunk%s[%d] 对话节点字段非法" % (cid, i))
            elif t == 4:
                for opt in n[1]:
                    if len(opt) < 3:
                        err("chunk%s[%d] 选项结构非法: %s" % (cid, i, opt))
                        continue
                    opt_count += 1
                    if not exp_re.match(opt[2]):
                        warn("chunk%s[%d] 选项表达式非常规: %s" % (cid, i, opt[2]))
                    if len(opt) >= 4 and opt[3] not in (None, "",):
                        warn("chunk%s[%d] 选项带条件（原版无）: %s" % (cid, i, opt[3]))
            elif t == 5:
                if n[1] is not None:
                    ev_refs.add(n[1])
            elif t == 6:
                if len(n) >= 3 and n[2] not in (None, "") and not cond_re.match(n[2]):
                    warn("chunk%s[%d] 条件跳转表达式非常规: %s" % (cid, i, n[2]))
            elif t == 7:
                if n[1] != "*":
                    ch_refs.add(n[1])
        label_locs[cid] = labels

    # 3. 跳转目标解析（收集后再查）
    cross_ids = id_set
    for f in files:
        cid = re.search(r"chunk(\d+)\.txt$", f).group(1)
        with open(f, encoding="utf-8") as fh:
            arr = json.load(fh)
        labels = label_locs[cid]
        for i, n in enumerate(arr):
            if n[0] == 4:
                for opt in n[1]:
                    tgt = opt[1]
                    if "@" in tgt:
                        sc, lab = tgt.split("@", 1)
                        if sc not in cross_ids or lab not in label_locs.get(sc, {}):
                            err("chunk%s[%d] 选项跨块目标不可达: %s" % (cid, i, tgt))
                    elif tgt not in labels:
                        err("chunk%s[%d] 选项目标标签缺失: %s" % (cid, i, tgt))
            elif n[0] == 6:
                tgt = n[1]
                if "gameend" in tgt.lower() or "endrecollection" in tgt.lower():
                    continue
                if "@" in tgt:
                    sc, lab = tgt.split("@", 1)
                    if sc not in cross_ids or lab not in label_locs.get(sc, {}):
                        err("chunk%s[%d] 跨块跳转目标不可达: %s" % (cid, i, tgt))
                elif tgt not in labels:
                    err("chunk%s[%d] 跳转目标标签缺失: %s" % (cid, i, tgt))

    # 4. 资源存在性
    bg_files = set(os.listdir(BG_DIR))
    ch_files = set(os.listdir(CH_DIR))
    ev_files = set(os.listdir(EV_DIR))
    for b in sorted(bg_refs):
        if b + ".jpg" not in bg_files:
            err("背景缺失: bg/%s.jpg" % b)
    for c in sorted(ch_refs):
        if c + ".png" not in ch_files:
            err("立绘缺失: ch/%s.png" % c)
    for e in sorted(ev_refs):
        if e + ev_ext(e) not in ev_files:
            err("事件图缺失: ev/%s%s" % (e, ev_ext(e)))

    print("== 内容包校验 ==")
    print("  场景: %d | 节点: %d | 选项: %d | 背景引用: %d | 立绘引用: %d | 事件图引用: %d"
          % (len(scns), total_nodes, opt_count, len(bg_refs), len(ch_refs), len(ev_refs)))
    print("  错误: %d | 警告: %d" % (len(errors), len(warnings)))
    for e in errors[:30]:
        print("  [ERR] " + e)
    for w in warnings[:10]:
        print("  [WARN] " + w)
    if errors:
        print("校验未通过")
        sys.exit(1)
    print("校验通过")


if __name__ == "__main__":
    main()
