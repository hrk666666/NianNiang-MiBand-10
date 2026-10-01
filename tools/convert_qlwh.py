#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_qlwh.py — 《千恋＊万花》小米手环移植版 → Sanoba VN 引擎 v1.1 内容包转换器

输入：
  - 上游 qlwh 仓库（hezdaaa/qlwh-mibandported）的 src/common/script/scriptData*.txt
  - 上游 detail.ux 中 branchConfig 的 noNextPages / end（自动解析）
  - 上游资源目录 bcgi/ cimg/ evig/

输出（写入本项目 src/）：
  - src/common/scn/chunk001.txt … chunk112.txt   剧本（节点 v1.1，JSON 数组）
  - src/common/game.txt                          内容包配置
  - src/common/bg/ src/common/ch/ src/common/ev/ 资源

转换规则（与上游翻页导航逐条对应）：
  - 顺序页:  page N 的下一节点 = 页 N+1 的内容（上游 readProgress++）
  - 选项页:  co/c1..c5 + c1t..c5t  → 节点 4；选中时执行 f.c<页号>=<选项序号>（对应上游 recordChoice）
  - 合流页:  noNextPages[N]=T  → 节点 6 跳转（跳过上游分支合流前的其他分支内容）
  - 隐藏路由: hiddenPages[N]    → 条件节点 6（[6, "target", "cond"]）+ 无条件兜底跳转
  - 结局页:  end[N]             → [6, "*gameend"]
  - 章节:    s="[CHAPTERx-y]"   → 节点 1
  - 背景:    b 变化时 → 节点 2（bg 目录）
  - 立绘:    c 存在 → 对话节点第 4 字段 [["c","center","change"]]；c 消失 → 节点 7 fadeout
  - 事件图:  cg → 节点 5（ev*/sd*/ef_*/アイテム_*/画面_* 统一映射到 ev 目录，扩展名按前缀区分）
"""

import glob
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QLWH = os.path.abspath(os.path.join(ROOT, "..", "repo1-qlwh"))

SCRIPT_DIR = os.path.join(QLWH, "src", "common", "script")
DETAIL_UX = os.path.join(QLWH, "src", "pages", "detail", "detail.ux")
BCGI = os.path.join(QLWH, "src", "common", "bcgi")
CIMG = os.path.join(QLWH, "src", "common", "cimg")
EVIG = os.path.join(QLWH, "src", "common", "evig")

OUT_SCN = os.path.join(ROOT, "src", "common", "scn")
OUT_BG = os.path.join(ROOT, "src", "common", "bg")
OUT_CH = os.path.join(ROOT, "src", "common", "ch")
OUT_EV = os.path.join(ROOT, "src", "common", "ev")
OUT_GAME = os.path.join(ROOT, "src", "common", "game.txt")

CHUNK_SIZE = 500
GAME_ID = "senren-banka"
GAME_TITLE = "千恋＊万花"
GAME_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 1. 读取上游剧本
# ---------------------------------------------------------------------------
def load_pages():
    files = sorted(
        glob_script_files(),
        key=lambda f: int(re.search(r"scriptData(\d+)\.txt$", f).group(1)),
    )
    pages = {}
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            pages.update(json.load(fh))
    # 校验编号连续
    keys = [int(k) for k in pages.keys()]
    assert min(keys) == 1 and max(keys) == 55901 and len(keys) == 55901, (
        "剧本页数不完整: %d 页" % len(keys)
    )
    return pages


def glob_script_files():
    return glob.glob(os.path.join(SCRIPT_DIR, "scriptData*.txt"))


def chunk_of(page):
    return (page - 1) // CHUNK_SIZE + 1


# ---------------------------------------------------------------------------
# 2. 从 detail.ux 解析分支规则
# ---------------------------------------------------------------------------
def extract_js_object(text, key):
    """解析 `key: { ... },` 形式的 JS 对象字面量（数字键/字符串值），返回 dict[str,str]。"""
    m = re.search(r"\b%s\s*:\s*\{" % key, text)
    if not m:
        return {}
    i = text.index("{", m.start())
    depth = 0
    j = i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = text[i + 1 : j]
    out = {}
    # 键可能带引号（"114": "124"）也可能不带（9180 : "END"）
    for pm in re.finditer(r'"?(\d+)"?\s*:\s*"([^"]*)"', body):
        out[pm.group(1)] = pm.group(2)
    return out


def load_branch_rules():
    with open(DETAIL_UX, "r", encoding="utf-8") as fh:
        text = fh.read()
    no_next_raw = extract_js_object(text, "noNextPages")
    end_raw = extract_js_object(text, "end")
    no_next = {int(k): int(v) for k, v in no_next_raw.items() if int(v) != int(k)}
    end = {int(k): v for k, v in end_raw.items()}
    # 死路由修复：页 5925（钓鱼分支结尾）被上游 noNextPages 错误配置为跳 6325，
    # 导致中间的 5926 选项页（「就是不行/既然你都这么说了……」）永远不可达，
    # flag c5926 永不被赋值 → 芳乃线（需 c5926==1）与蕾娜线（需 c5926==2）成为死路由。
    # 移除该规则后：钓鱼分支 5925 → 5926 选项 →（c5926 赋值）→ 5927/6030 → 6029/6130 → 6322 合流。
    no_next.pop(5925, None)
    return no_next, end


# hiddenPages 条件路由（手工翻译自 detail.ux 中的 JS 函数，逐条核对过）
HIDDEN_PAGES = {
    # 6411: if(choice[5912]===3) return 6412(丛雨好感度剧情); else return 6505
    6411: [("f.c5912 == 3", 6412), (None, 6505)],
    # 7813: if(choice[5912]===2) return 7814(茉子好感度剧情); else return 7978
    7813: [("f.c5912 == 2", 7814), (None, 7978)],
    # 8460: 蕾娜线 → 39501（蕾娜线第 4 章开头，山中战斗）；否则 8461
    # 上游配置为 31160（共通线中段安晴讨论会），跳转后纯线性播到丛雨线结局 077，蕾娜线不可达。
    8460: [("f.c5504 == 1 && f.c5912 == 1 && f.c5926 == 2", 39501), (None, 8461)],
    # 9130: 芳乃线 → 9182；茉子线 → 19002；否则 9131
    9130: [
        ("f.c5504 == 2 && f.c5912 == 1 && f.c5926 == 1 && f.c8418 == 1", 9182),
        ("f.c5504 == 2 && f.c5912 == 2", 19002),
        (None, 9131),
    ],
    # 9165: 丛雨线 → 28137；小春&芦花线 → 48623；否则 9166
    9165: [
        ("f.c5504 == 2 && f.c5912 == 3 && f.c6390 == 2", 28137),
        ("f.c109 == 1 && f.c5504 == 2 && f.c7337 == 2", 48623),
        (None, 9166),
    ],
    # 51814: 小春 → 51815；芦花 → 51889（都不是 → 顺序进入 51815）
    51814: [("f.c51359 == 1", 51815), ("f.c51359 == 2", 51889)],
}


# ---------------------------------------------------------------------------
# 3. 资源清单
# ---------------------------------------------------------------------------
def listdir(d):
    return set(os.listdir(d)) if os.path.isdir(d) else set()


def ev_resolve(name):
    """节点 5 名称 → ev 目录文件名（扩展名按前缀区分）"""
    if name.startswith("ev"):
        return name + ".jpg"
    return name + ".png"


# ---------------------------------------------------------------------------
# 4. 主转换
# ---------------------------------------------------------------------------
def main():
    print("== 千恋＊万花 → VN v1.1 转换 ==")
    pages = load_pages()
    no_next, end = load_branch_rules()
    print("  剧本页数: %d | noNextPages 规则: %d | 结局页: %d"
          % (len(pages), len(no_next), len(end)))

    # 选项页 / 隐藏页 / 合流目标 / 结局 集合
    choice_pages = []
    for pid, p in pages.items():
        if p.get("co"):
            choice_pages.append(int(pid))
    choice_pages.sort()
    hidden_keys = set(HIDDEN_PAGES.keys())

    # 校验：选项页与 noNext / hidden 不重叠（上游逻辑里同一页不会同时命中）
    for pid in choice_pages:
        assert pid not in no_next, "选项页同时是 noNext: %d" % pid
        assert pid not in hidden_keys, "选项页同时是 hidden: %d" % pid
    # 6411 同时存在于 noNext 与 hidden：上游 nextPage 先查 hiddenPages，其 else 分支
    # 已等价于 noNext（6411→6505），因此转换时对 hidden 页跳过 noNext 节点。
    overlap = set(no_next.keys()) & hidden_keys
    for pid in sorted(overlap):
        print("  注: %d 同时命中 noNext 与 hidden（hidden 优先，跳过 noNext 节点）" % pid)

    # 需要的标签：选项目标 / 合流目标 / 隐藏路由目标
    labels_needed = set()
    for pid in pages:
        p = pages[pid]
        for i in range(1, 6):
            t = p.get("c%dt" % i)
            if t:
                labels_needed.add(int(t))
    labels_needed.update(no_next.values())
    for _, rules in HIDDEN_PAGES.items():
        for _, target in rules:
            labels_needed.add(target)

    def jump_label(page):
        c = chunk_of(page)
        if c == current_chunk[0]:
            return "*p%d" % page
        return "%03d@*p%d" % (c, page)

    # 资源存在性预检查
    evig_files = listdir(EVIG)
    bcgi_files = listdir(BCGI)
    cimg_files = listdir(CIMG)

    # 转换：逐块生成节点
    chunks = {}
    current_chunk = [1]
    last_bg = [None]
    last_ev = [None]
    last_char = [None]
    missing_ev = {}
    missing_bg = {}
    missing_ch = {}
    chapter_markers = 0
    skipped_item = 0
    total_nodes = 0

    for c in range(1, 113):
        current_chunk[0] = c
        nodes = []
        start = (c - 1) * CHUNK_SIZE + 1
        chunk_end = min(c * CHUNK_SIZE, 55901)
        for pid in range(start, chunk_end + 1):
            p = pages[str(pid)]
            if pid in labels_needed:
                nodes.append([0, "*p%d" % pid])
            s = p.get("s", "")
            t = p.get("t", "")
            # 背景（变化时）
            b = p.get("b")
            if b and b != last_bg[0]:
                if (b + ".jpg") not in bcgi_files:
                    missing_bg[b] = missing_bg.get(b, 0) + 1
                nodes.append([2, b])
                last_bg[0] = b
            # 章节标记
            m = re.fullmatch(r"\[(CHAPTER[^\]]*)\]", s or "")
            if m and not t:
                nodes.append([1, m.group(1)])
                chapter_markers += 1
                continue
            # 事件图（cg）
            cg = p.get("cg")
            if cg:
                name = cg[:-4] if cg.endswith(".png") or cg.endswith(".jpg") else cg
                fname = ev_resolve(name)
                if fname in evig_files:
                    nodes.append([5, name])
                    last_ev[0] = name
                else:
                    missing_ev[name] = missing_ev.get(name, 0) + 1
                    if name != last_ev[0]:
                        nodes.append([5, None])
                        last_ev[0] = None
                    skipped_item += 1
            elif last_ev[0] is not None:
                nodes.append([5, None])
                last_ev[0] = None
            # 对话（选项页无正文时跳过——选项页只显示选项浮层）
            ch = p.get("c")
            is_choice = bool(p.get("co"))
            if is_choice and not s and not t:
                pass
            elif ch:
                key = ch
                fname = key + ".png"
                if fname.lower() not in {x.lower() for x in cimg_files}:
                    missing_ch[ch] = missing_ch.get(ch, 0) + 1
                nodes.append([3, s, t, [[key, "center", "change"]]])
                last_char[0] = key
            else:
                if last_char[0] is not None:
                    nodes.append([7, "*", "center", "fadeout"])
                    last_char[0] = None
                nodes.append([3, s, t])
            # 选项
            if p.get("co"):
                opts = []
                for i in range(1, 6):
                    label = p.get("c%d" % i)
                    target = p.get("c%dt" % i)
                    if label:
                        opts.append([label, jump_label(int(target)), "f.c%d=%d" % (pid, i)])
                if opts:
                    nodes.append([4, opts])
                else:
                    skipped_item += 1
            # 合流跳转（noNextPages；hidden 页跳过——上游 hidden 优先且其兜底等价）
            if pid in no_next and pid not in hidden_keys:
                nodes.append([6, jump_label(no_next[pid])])
            # 隐藏路由（条件跳转 + 兜底）
            if pid in hidden_keys:
                for cond, target in HIDDEN_PAGES[pid]:
                    node = [6, jump_label(target)]
                    if cond:
                        node.append(cond)
                    nodes.append(node)
            # 结局
            if pid in end:
                name = re.sub(r"[^A-Za-z0-9]", "", end[pid])
                nodes.append([6, "*gameend_%s" % (name or "end")])
        chunks[c] = nodes
        total_nodes += len(nodes)

    # 写出 scn 文件
    os.makedirs(OUT_SCN, exist_ok=True)
    for c, nodes in chunks.items():
        path = os.path.join(OUT_SCN, "chunk%03d.txt" % c)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(nodes, fh, ensure_ascii=False, separators=(",", ":"))

    # 写出 game.txt
    scenario_list = [
        {"id": "%03d" % c, "path": "chunk%03d.txt" % c} for c in range(1, 113)
    ]
    game = {
        "id": GAME_ID,
        "title": GAME_TITLE,
        "version": GAME_VERSION,
        "engine": {"format": "vn-1.1", "minRuntime": "1.0"},
        "initialState": {"flags": {}},
        "resources": {
            "base": "/common",
            "dirs": {"bg": "bg", "sd": "sd", "ev": "ev", "ch": "ch", "audio": "audio"},
        },
        "scenarios": {"main": scenario_list},
        "routes": {},
    }
    with open(OUT_GAME, "w", encoding="utf-8") as fh:
        json.dump(game, fh, ensure_ascii=False, indent=2)

    # 资源搬运
    print("  搬运资源…")
    copied = {"bg": 0, "ch": 0, "ev": 0}
    for fn in sorted(bcgi_files):
        if fn.endswith(".jpg"):
            shutil.copy2(os.path.join(BCGI, fn), os.path.join(OUT_BG, fn))
            copied["bg"] += 1
    for fn in sorted(cimg_files):
        if fn.endswith(".png"):
            # 立绘键名按剧本 c 字段规范化（剧本用 ev703_cutin，文件为 EV703_cutin）
            shutil.copy2(os.path.join(CIMG, fn), os.path.join(OUT_CH, fn))
            copied["ch"] += 1
            if fn == "EV703_cutin.png":
                shutil.copy2(os.path.join(CIMG, fn), os.path.join(OUT_CH, "ev703_cutin.png"))
                copied["ch"] += 1
    for fn in sorted(evig_files):
        if fn.endswith((".jpg", ".png")):
            shutil.copy2(os.path.join(EVIG, fn), os.path.join(OUT_EV, fn))
            copied["ev"] += 1

    print("== 转换完成 ==")
    print("  节点总数: %d | 章节标记: %d | 选项页: %d"
          % (total_nodes, chapter_markers, len(choice_pages)))
    print("  资源: bg=%d ch=%d ev=%d" % (copied["bg"], copied["ch"], copied["ev"]))
    if missing_bg:
        print("  ⚠ 剧本引用的背景缺失: %s" % sorted(missing_bg.items())[:10])
    if missing_ch:
        print("  ⚠ 剧本引用的立绘缺失: %s" % sorted(missing_ch.items())[:10])
    if missing_ev:
        print("  ⚠ 剧本引用的事件图缺失(已跳过节点): %d 个不同名, 例: %s"
              % (len(missing_ev), sorted(missing_ev.items())[:10]))
    print("  scn: %d 个文件 → %s" % (len(chunks), OUT_SCN))
    print("  game.txt → %s" % OUT_GAME)


if __name__ == "__main__":
    main()
