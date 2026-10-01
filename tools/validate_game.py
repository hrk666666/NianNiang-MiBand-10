#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_game.py — 内容包校验器

校验对象：
  - src/common/game.txt       内容包配置（场景清单/routes/resources）
  - src/common/scn/*.txt      全部剧本（节点语法）
  - 资源引用（bg/sd/ev 文件是否存在；ch/audio 缺失仅警告——内容包尚未提供）

用法：
    python3 tools/validate_game.py            # 全量校验
    python3 tools/validate_game.py --strict   # 警告也报错（CI 用）

节点规范（v1.1）：
    0 标签 [0, str]
    1 章节 [1, str]
    2 背景 [2, str]
    3 对话 [3, str, str, list?]
    4 选项 [4, list[list[str, str, str?, str?]]]
    5 事件CG [5, str]
    6 跳转 [6, str]
    7 立绘 [7, str, "left|center|right", "fadein|fadeout|change"]
    8 音乐 [8, str, "bgm|se", "loop|once"]
    9 特效 [9, str, int|str?]
    10 变量 [10, str]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCN_DIR = os.path.join(ROOT, "src", "common", "scn")
GAME_TXT = os.path.join(ROOT, "src", "common", "game.txt")
BG_DIR = os.path.join(ROOT, "src", "common", "bg")
SD_DIR = os.path.join(ROOT, "src", "common", "sd")
EV_DIR = os.path.join(ROOT, "src", "common", "ev")

CH_SLOTS = {"left", "center", "right"}
CH_ACTIONS = {"fadein", "fadeout", "change"}
# 存量 KRKR 立绘位置（FreeMote 转换产物）：中文位置 + 百分比
LEGACY_CH_POS = {
    "出", "中", "顔", "立", "左", "左中", "左奥", "左近", "左外",
    "右", "右中", "右奥", "右近", "右外", "消",
}
AUDIO_KINDS = {"bgm", "se"}
AUDIO_MODES = {"loop", "once"}
FX_NAMES = {"whiteflash", "blackout", "fadein", "fadeout", "vibrate"}


def is_ch_position(v):
    if v in CH_SLOTS or v in LEGACY_CH_POS:
        return True
    return bool(re.fullmatch(r"\d+%", v))

errors = []
warnings = []
_warned_ev = False


def err(msg, scn=None, idx=None):
    loc = f"{scn}@{idx}" if scn is not None else ""
    errors.append(f"  ✗ [{loc}] {msg}")


def warn(msg, scn=None):
    warnings.append(f"  ⚠ [{scn}] {msg}")


def check_node(node, scn, idx):
    if not isinstance(node, list) or not node:
        err("节点必须是非空数组", scn, idx)
        return
    t = node[0]
    if not isinstance(t, int) or t < 0 or t > 10:
        err(f"未知节点类型: {t!r}", scn, idx)
        return

    if t == 0:  # 标签
        if not isinstance(node[1], str):
            err("标签节点 [0, \"label\"] 第2项须为字符串", scn, idx)
    elif t == 1:  # 章节
        if not isinstance(node[1], str):
            err("章节节点 [1, \"标题\"] 第2项须为字符串", scn, idx)
    elif t == 2:  # 背景
        if not isinstance(node[1], str) or not node[1]:
            err("背景节点 [2, \"bg_name\"] 名称不能为空", scn, idx)
    elif t == 3:  # 对话
        if len(node) < 3 or not isinstance(node[1], str) or not isinstance(node[2], str):
            err("对话节点须为 [3, \"说话人\", \"内容\", 立绘列表?]", scn, idx)
        if len(node) > 3 and node[3] is not None:
            if not isinstance(node[3], list):
                err("对话第4字段（立绘列表）须为数组", scn, idx)
            else:
                for item in node[3]:
                    if not isinstance(item, list) or not item or not isinstance(item[0], str):
                        err("立绘项须为 [\"角色_表情\", \"位置\", \"动作\"] 或存量 [\"角色名\", \"位置\", \"表情号\", \"服装\"]", scn, idx)
                    elif len(item) > 1 and not is_ch_position(item[1]):
                        err(f"立绘位置 {item[1]!r} 非法（left/center/right 或存量 出/中/左/右/百分比）", scn, idx)
                    elif len(item) > 2 and item[1] in CH_SLOTS and item[2] not in CH_ACTIONS:
                        err(f"新格式立绘动作 {item[2]!r} 非法（fadein/fadeout/change）", scn, idx)
    elif t == 4:  # 选项
        if not isinstance(node[1], list) or not node[1]:
            err("选项节点须为 [4, [[\"文字\",\"跳转\",\"表达式\",\"条件?\"], ...]]", scn, idx)
        else:
            for opt in node[1]:
                if not isinstance(opt, list) or len(opt) < 2 or not isinstance(opt[0], str) or not isinstance(opt[1], str):
                    err("选项项须为 [\"文字\", \"跳转标签\", \"表达式?\", \"条件?\"]", scn, idx)
    elif t == 5:  # 事件CG / SD / 道具（存量转换产物）
        # 存量数据：null 表示清空；sdXXX/evXXX 图片；item_* 道具图（旧引擎忽略，仅日志）
        if node[1] is not None and not isinstance(node[1], str):
            err(f"事件CG {node[1]!r} 须为字符串或 null", scn, idx)
    elif t == 6:  # 跳转
        if not isinstance(node[1], str):
            err("跳转节点 [6, \"target_label\"] 第2项须为字符串", scn, idx)
    elif t == 7:  # 立绘（v1.1 新格式）
        if not isinstance(node[1], str) or not node[1]:
            err("立绘节点 [7, \"角色_表情\", 位置, 动作] 第2项不能为空", scn, idx)
        if len(node) > 2 and not is_ch_position(node[2]):
            err(f"立绘位置 {node[2]!r} 非法（left/center/right 或存量位置）", scn, idx)
        if len(node) > 3 and node[2] in CH_SLOTS and node[3] not in CH_ACTIONS:
            err(f"立绘动作 {node[3]!r} 非法（fadein/fadeout/change）", scn, idx)
    elif t == 8:  # 音乐
        if not isinstance(node[1], str) or not node[1]:
            err("音乐节点 [8, \"曲名\", kind, mode] 第2项不能为空", scn, idx)
        if len(node) > 2 and node[2] not in AUDIO_KINDS:
            err(f"音乐类型 {node[2]!r} 非法（bgm/se）", scn, idx)
        if len(node) > 3 and node[3] not in AUDIO_MODES:
            err(f"音乐模式 {node[3]!r} 非法（loop/once）", scn, idx)
    elif t == 9:  # 特效
        if not isinstance(node[1], str) or node[1] not in FX_NAMES:
            err(f"特效 {node[1]!r} 非法（{sorted(FX_NAMES)}）", scn, idx)
    elif t == 10:  # 变量
        if not isinstance(node[1], str) or not node[1]:
            err("变量节点 [10, \"f.x = 1, f.y++\"] 指令不能为空", scn, idx)


def check_jumps(script, scn):
    """校验同场景内跳转标签是否存在；跨场景/缺失目标仅警告（旧引擎跳过继续）"""
    labels = {n[1] for n in script if isinstance(n, list) and n[0] == 0 and isinstance(n[1], str)}
    for i, n in enumerate(script):
        if not isinstance(n, list):
            continue
        if n[0] == 6 and isinstance(n[1], str):
            if n[1] not in labels and "@" not in n[1]:
                warn(f"跳转目标 {n[1]!r} 在本场景内不存在，运行时将跳过（跨场景请用 scnId@label）", scn)
        if n[0] == 4:
            for opt in n[1] if isinstance(n[1], list) else []:
                if isinstance(opt, list) and len(opt) > 1 and isinstance(opt[1], str):
                    if opt[1] not in labels and "@" not in opt[1]:
                        warn(f"选项跳转目标 {opt[1]!r} 在本场景内不存在，运行时将跳过", scn)


def check_resources(script, scn):
    """资源文件存在性（bg/sd 严格，ch/audio 仅警告）"""
    global _warned_ev
    for i, n in enumerate(script):
        if not isinstance(n, list):
            continue
        if n[0] == 2 and isinstance(n[1], str):
            p = os.path.join(BG_DIR, n[1] + ".jpg")
            if not os.path.exists(p):
                err(f"背景资源缺失: {n[1]}.jpg", scn, i)
        if n[0] == 5 and isinstance(n[1], str) and n[1].startswith("sd"):
            p = os.path.join(SD_DIR, n[1] + ".jpg")
            if not os.path.exists(p):
                err(f"SD 图缺失: {n[1]}.jpg", scn, i)
        if n[0] == 5 and isinstance(n[1], str) and n[1].startswith("ev"):
            if not os.path.isdir(EV_DIR) and not _warned_ev:
                _warned_ev = True
                warn("ev 目录不存在（EV 渲染层未启用，可接受）", scn)
        if n[0] == 7 and isinstance(n[1], str):
            p = os.path.join(ROOT, "src", "common", "ch", n[1] + ".png")
            if not os.path.exists(p):
                warn(f"立绘资源缺失（内容包未提供，可接受）: ch/{n[1]}.png", scn)


_warned_ev = False


def main():
    strict = "--strict" in sys.argv

    if not os.path.exists(GAME_TXT):
        err("game.txt 不存在，先运行 tools/generate_game_config.py")
        sys.exit(1)

    with open(GAME_TXT, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 内容包结构
    scenarios = cfg.get("scenarios", {})
    ids = []
    for list_name, items in scenarios.items():
        for it in items:
            ids.append(it.get("id"))
            path = os.path.join(SCN_DIR, it.get("path", ""))
            if not os.path.exists(path):
                err(f"剧本文件缺失: {it.get('path')}")

    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        err(f"场景 ID 重复: {sorted(dup)}")

    # routes 引用的场景必须存在
    for scn_id, route in (cfg.get("routes") or {}).items():
        if scn_id not in ids:
            err(f"routes 起始场景 {scn_id} 不在 scenarios 中")
        if route.get("type") == "flagRoute":
            for t in route.get("targets", []):
                if t.get("next") not in ids:
                    err(f"flagRoute 目标 {t.get('next')} 不在 scenarios 中")
            if route.get("fallback") not in ids:
                err(f"flagRoute fallback {route.get('fallback')} 不在 scenarios 中")

    # 剧本逐文件校验
    total_nodes = 0
    for list_name, items in scenarios.items():
        for it in items:
            scn_path = os.path.join(SCN_DIR, it["path"])
            if not os.path.exists(scn_path):
                continue
            with open(scn_path, "r", encoding="utf-8") as f:
                text = f.read()
            try:
                script = json.loads(text)
            except json.JSONDecodeError as e:
                err(f"JSON 解析失败: {e}", it["id"])
                continue
            if not isinstance(script, list):
                err("剧本根必须是数组", it["id"])
                continue
            total_nodes += len(script)
            for i, node in enumerate(script):
                check_node(node, it["id"], i)
            check_jumps(script, it["id"])
            check_resources(script, it["id"])

    print("==== 内容包校验 ====")
    print(f"  场景数: {len(ids)}  剧本节点总数: {total_nodes}")
    if errors:
        print(f"\n错误 {len(errors)} 个:")
        for e in errors:
            print(e)
        print("\n校验未通过")
        sys.exit(1)

    print(f"  错误: 0")
    print(f"  警告: {len(warnings)} 个")
    for w in warnings:
        print(w)
    if strict and warnings:
        print("\n--strict 模式下警告视为失败")
        sys.exit(1)
    print("\n校验通过 ✓")


if __name__ == "__main__":
    main()
