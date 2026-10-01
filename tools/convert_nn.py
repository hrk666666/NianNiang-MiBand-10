#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《男娘恋爱物语》Ren'Py rpy → vn-1.1 节点格式转换器
输入: _analyze/男娘恋爱物语_移植素材包/01_剧本/script/scenes/scene_1_*.rpy
输出: build/src/common/scn/chunk001.txt ~ chunk013.txt + game.txt

节点格式 (与 Senren-Banka 引擎一致):
  [0,"label"] 标签  [1,"章节"]  [2,"bg"]  [3,"说话人","文本",[立绘]]  [4,[选项]]
  [5,"ev"]  [6,"跳转"]  [7,"角色_表情","位置","动作"]  [8,"曲名","bgm","loop"]  [9,"blackout"]
"""
import os, re, json, sys

SRC_DIR = "/home/user/Doubao/chats/38445140291631362/_analyze/男娘恋爱物语_移植素材包/01_剧本/script/scenes"
OUT_DIR = "/home/user/Doubao/chats/38445140291631362/build/src/common/scn"

# 角色显示名映射
SPEAKER_MAP = {
    "mei": "小美", "fei": "李飞", "shen": "周星文", "shen2": "？？？",
    "mei2": "？？？", "fei2": "？？？", "meire": "小美", "feire": "李飞", "mei3": "王帅",
}

# 位置映射
POS_MAP = {"center3": "center", "center3_in": "center", "center3_out": "center",
           "right3": "right", "right32": "right", "center3_in, in_blur": "center",
           "center3, from_in_blur": "center", "center3, no_blur": "center"}

BG_MAP = {
    "bg gate": "bg_gate", "bg ground": "bg_ground", "bg room": "bg_room",
    "bg room dark": "bg_room_dark", "bg street2": "bg_street2",
    "bg tea": "bg_tea", "bg classroom": "bg_classroom",
    "bg resturant": "bg_resturant", "bg gym": "bg_gym", "bg lake": "bg_lake",
    "bg museum": "bg_museum", "bg street2 night": "bg_street2_night",
    "bg tea night": "bg_tea_night", "bg room night": "bg_room_night",
    "white": "bg_white", "black": "bg_black",
}

# CG 表情 -> 合成文件名（scene_1_4 中 no2 叠 blush1、air 叠 blush2）
EV_MAP = {
    "meicg1 no2": "evmeicg1_no2", "meicg1 cute": "evmeicg1_cute",
    "meicg1 no3": "evmeicg1_no3", "meicg1 no": "evmeicg1_no",
    "meicg1 cute2": "evmeicg1_cute2", "meicg1 air": "evmeicg1_air",
    "meicg1 cute3": "evmeicg1_cute3", "meicg1 cute4": "evmeicg1_cute4",
    "meicg1 air2": "evmeicg1_air2", "meicg1_gallery": "evmeicg1_gallery",
    "meicg2 wut": "evmeicg2_wut", "meicg2 kiss": "evmeicg2_kiss",
    "meicg2 wut2": "evmeicg2_wut2", "meicg2 worry": "evmeicg2_worry",
    "meicg2 smile": "evmeicg2_smile",
}

def is_skip_line(s):
    """需要整行跳过的指令"""
    return (s.startswith("pause") or s.startswith("winhide") or s.startswith("clockout")
            or s.startswith("camera") or s.startswith("window auto")
            or s.startswith("$") or s.startswith("call phone") or s.startswith("call normal")
            or s.startswith("call screen") or s.startswith("play sound") or s.startswith("play music")
            or s.startswith("stop music") or s.startswith("with") or s.startswith("nvl")
            or s.startswith("window") or s.startswith("#") or s.startswith("return")
            or s == "pass")

def parse_rpy(path):
    nodes = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    i = 0
    n = len(lines)
    cur_show = None  # 当前屏幕上立绘 (key)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        indent = len(raw) - len(raw.lstrip())

        # 跳过 if _preferences.language 块（含缩进子块）
        if s.startswith("if _preferences.language") or s.startswith("if renpy"):
            # 跳到与 if 相同缩进的下一行
            while i < n:
                nxt = lines[i + 1] if i + 1 < n else ""
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                i += 1
            i += 1
            continue
        if s.startswith("elif _preferences") or s.startswith("else:"):
            while i < n:
                nxt = lines[i + 1] if i + 1 < n else ""
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                i += 1
            i += 1
            continue

        # 标签
        m = re.match(r'^label\s+([\w_]+):', s)
        if m:
            nodes.append([0, m.group(1)])
            i += 1
            continue

        # 章节日期 call day ("...")
        m = re.match(r'^call day \("([^"]+)"\)', s)
        if m:
            nodes.append([1, m.group(1)])
            i += 1
            continue

        # scene 背景
        m = re.match(r'^scene\s+(.+)$', s)
        if m:
            target = m.group(1).strip()
            # 去掉 at/with 后缀
            target = re.split(r'\s+(?:at|with)\s+', target)[0]
            if target.startswith("meicg"):
                evkey = target
                if evkey in EV_MAP:
                    # 清立绘
                    if cur_show:
                        nodes.append([7, "*", "center", "fadeout"])
                        cur_show = None
                    nodes.append([5, EV_MAP[evkey]])
            elif target in BG_MAP:
                if cur_show:
                    nodes.append([7, "*", "center", "fadeout"])
                    cur_show = None
                nodes.append([2, BG_MAP[target]])
            i += 1
            continue

        # show mei/fei X at pos / hide mei
        m = re.match(r'^show\s+(mei|fei)\s+(\S+)(?:\s+at\s+([\w,\s]+))?', s)
        if m and m.group(2) != "with":
            key = f"{m.group(1)}_{m.group(2)}"
            pos = POS_MAP.get(m.group(3).strip() if m.group(3) else "center3", "center")
            # 检查是否是 'with' 开头的误判（show mei with dissolve）
            if key.endswith("_with"):
                i += 1
                continue
            nodes.append([7, key, pos, "change"])
            cur_show = key
            i += 1
            continue

        m = re.match(r'^hide\s+(mei|fei)\s*(?:with\s+\w+)?', s)
        if m:
            nodes.append([7, "*", "center", "fadeout"])
            cur_show = None
            i += 1
            continue

        # show meicg1 X（CG 分层）→ 事件 CG
        m = re.match(r'^show\s+(meicg1\s+\w+)', s)
        if m:
            evkey = m.group(1).replace("_m_blush", "").strip()
            if evkey in EV_MAP:
                if cur_show:
                    nodes.append([7, "*", "center", "fadeout"])
                    cur_show = None
                nodes.append([5, EV_MAP[evkey]])
            i += 1
            continue
        m = re.match(r'^show\s+(meicg2\s+\w+)', s)
        if m:
            evkey = m.group(1).strip()
            if evkey in EV_MAP:
                if cur_show:
                    nodes.append([7, "*", "center", "fadeout"])
                    cur_show = None
                nodes.append([5, EV_MAP[evkey]])
            i += 1
            continue

        # show 其他（tea_chair/tea_desk/memory/phone/black/white）→ 忽略
        m = re.match(r'^show\s+(\w+)', s)
        if m:
            i += 1
            continue

        # hide 其他 → 忽略
        m = re.match(r'^hide\s+(\w+)', s)
        if m:
            i += 1
            continue

        # blackout 特效
        if s == "blackout":
            nodes.append([9, "blackout"])
            i += 1
            continue

        # menu 块
        if s.startswith("menu:"):
            i += 1
            options = []
            # 跳过 menu 标题行（"……" 等不以冒号结尾的引号行）
            while i < n:
                opt = lines[i].strip()
                if opt and not opt.endswith(':'):
                    i += 1
                    continue
                break
            while i < n:
                opt_raw = lines[i]
                opt = opt_raw.strip()
                if not opt:
                    i += 1
                    continue
                opt_indent = len(opt_raw) - len(opt_raw.lstrip())
                if opt_indent <= indent:
                    break
                m = re.match(r'^"([^"]*)":\s*$', opt)
                if m:
                    label_text = m.group(1)
                    # 找 jump / pass
                    j = i + 1
                    target = None
                    while j < n:
                        sub = lines[j].strip()
                        sub_indent = len(lines[j]) - len(lines[j].lstrip())
                        if sub_indent <= opt_indent:
                            break
                        mj = re.match(r'^jump\s+([\w_]+)', sub)
                        if mj:
                            target = mj.group(1)
                            break
                        if sub == "pass":
                            break
                        j += 1
                    options.append([label_text, target or "", ""])
                    i = j
                    continue
                i += 1
            if options:
                nodes.append([4, options])
            continue

        # jump
        m = re.match(r'^jump\s+([\w_]+)', s)
        if m:
            nodes.append([6, m.group(1)])
            i += 1
            continue

        # 对话：说话人 "..." 或 旁白 "..."
        m = re.match(r'^(mei|fei|shen|shen2|mei2|fei2|meire|feire|mei3)\s+(.+)$', s)
        if m:
            text = m.group(2).strip().strip('"')
            speaker = SPEAKER_MAP.get(m.group(1), "???")
            nodes.append([3, speaker, text])
            i += 1
            continue

        if s.startswith('"') and s.endswith('"') or (s.startswith('"') and len(s) > 1):
            text = s.strip().strip('"')
            nodes.append([3, "", text])
            i += 1
            continue

        if is_skip_line(s):
            i += 1
            continue

        i += 1
    return nodes

def cross_scene(node, scene_id):
    """把场景内 jump 转成跨场景跳转"""
    if node[0] == 6 and node[1]:
        t = node[1]
        m = re.match(r'^scene_1_(\d+)$', t)
        if m:
            return [6, f"{int(m.group(1)):03d}@{t}"]
        # 结局
        if t in ("end_1_4_1", "end_1_4_2", "end_1_11_1"):
            return [6, f"013@{t}"]
        if t == "ad_menu":
            return None
    return node

def postprocess(nodes, scene_id):
    """跨场景跳转 + 结尾处理"""
    out = []
    for node in nodes:
        x = cross_scene(node, scene_id)
        if x is not None:
            out.append(x)
    return out

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    scene_ids = ["001", "002", "003", "004", "005", "006", "007", "008", "009", "010", "011", "012", "013"]
    # 场景文件: scene_1_1.rpy ... scene_1_13.rpy
    chunk_files = {}
    for i, sid in enumerate(scene_ids, start=1):
        fn = f"scene_1_{i}.rpy"
        path = os.path.join(SRC_DIR, fn)
        if not os.path.exists(path):
            print(f"缺失: {fn}")
            continue
        nodes = parse_rpy(path)
        nodes = postprocess(nodes, sid)
        chunk_files[sid] = nodes

    # chunk013 需要包含三个结局（scene_1_13.rpy 里的 end_1_4_1/end_1_4_2/end_1_11_1）
    # 结局尾部加 gameend
    end_targets = {"end_1_4_1": "gameend_badend1", "end_1_4_2": "gameend_badend2", "end_1_11_1": "gameend_normalend"}

    for sid, nodes in chunk_files.items():
        if sid == "012":
            # 真结局：ad_menu 广告段（Steam 商店页）不适用于手环，截断，结尾加 gameend_trueend
            out = []
            stop = False
            for node in nodes:
                if node[0] == 0 and node[1] == "ad_menu":
                    stop = True
                if stop:
                    continue
                if node[0] == 6 and node[1] == "ad_menu":
                    continue
                out.append(node)
            out.append([6, "*gameend_trueend"])
            chunk_files[sid] = out

        if sid == "013":
            # 结局块：每个结局标签尾部补 gameend
            out = []
            cur_end = None
            for node in nodes:
                if node[0] == 0 and node[1] in end_targets:
                    # 上一个结局尾部补 gameend
                    if cur_end:
                        out.append([6, f"*{end_targets[cur_end]}"])
                    cur_end = node[1]
                    out.append(node)
                    continue
                if node[0] == 0:
                    if cur_end:
                        out.append([6, f"*{end_targets[cur_end]}"])
                    cur_end = None
                    out.append(node)
                    continue
                out.append(node)
            if cur_end:
                out.append([6, f"*{end_targets[cur_end]}"])
            chunk_files[sid] = out

    # 写 chunk 文件
    for sid in scene_ids:
        nodes = chunk_files.get(sid, [])
        with open(os.path.join(OUT_DIR, f"chunk{sid}.txt"), "w", encoding="utf-8") as f:
            json.dump(nodes, f, ensure_ascii=False, separators=(",", ":"))
        print(f"chunk{sid}.txt: {len(nodes)} 节点")

    # game.txt 配置
    game = {
        "title": "男娘恋爱物语",
        "id": "nikoyuri",
        "scenarioBase": "chunk",
        "scenarios": {
            "main": [{"id": sid, "path": f"chunk{sid}.txt"} for sid in scene_ids]
        },
        "resources": {"base": "/common", "dirs": {"bg": "bg", "sd": "sd", "ev": "ev", "ch": "ch", "audio": "audio"}}
    }
    with open(os.path.join(OUT_DIR, "..", "game.txt"), "w", encoding="utf-8") as f:
        json.dump(game, f, ensure_ascii=False, indent=2)
    print("game.txt 已生成")

if __name__ == "__main__":
    main()
