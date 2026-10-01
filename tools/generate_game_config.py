#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_game_config.py — 从 legacy constants.js 的 SCN_LIST 生成内容包 game.txt

用法：
    python3 tools/generate_game_config.py

产物：
    src/common/game.txt   （内容包：场景清单 + 路线规则 + 初始变量）

说明：
    旧版把"游戏内容"(101 个剧本清单、分线规则)硬编码在 constants.js 里，
    引擎无法复用。本脚本把这些内容抽到 game.txt，引擎只读配置。
    路线映射（与旧版 getNextScn/determineRoute 行为等价）：
      - 020_xxx 并入对应个人线列表开头 → 列表内顺序推进
      - 019 章节结束 → flagRoute（好感度最高者进线，全0/并列走 fallback=020_meguru）
"""
import json
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSTANTS = os.path.join(ROOT, "src", "common", "constants.js")
OUT = os.path.join(ROOT, "src", "common", "game.txt")

# 019 分线的 flag → 目标场景 映射（与旧 determineRoute/getNextScn 等价）
FLAG_ROUTE_019 = [
    {"id": "nene",    "flag": "nen_flag", "next": "020_nene"},
    {"id": "meguru",  "flag": "meg_flag", "next": "020_meguru"},
    {"id": "tsumugi", "flag": "tsu_flag", "next": "020_tsumugi"},
    {"id": "akogare", "flag": "tou_flag", "next": "020_akogare"},
    {"id": "wakana",  "flag": "wak_flag", "next": "500"},
]


def extract_scn_list(src_text):
    """提取 SCN_LIST = { listName: [ {id,path}, ... ] } """
    m = re.search(r"export const SCN_LIST\s*=\s*(\{.*?\n\})", src_text, re.S)
    if not m:
        raise SystemExit("未找到 SCN_LIST")
    body = m.group(1)

    lists = {}
    # 分组：  name: [ ... ]
    for group in re.finditer(r"([A-Za-z_]\w*)\s*:\s*\[(.*?)\n\s*\]", body, re.S):
        name, items_src = group.group(1), group.group(2)
        items = []
        for it in re.finditer(r'id\s*:\s*"([^"]+)"\s*,\s*path\s*:\s*"([^"]+)"', items_src):
            items.append({"id": it.group(1), "path": it.group(2)})
        if items:
            lists[name] = items
    return lists


def restructure(lists):
    """020_xxx 从 common 并入对应线开头；common 只留 001-019 顺序场景"""
    route_map = {"020_nene": "nene", "020_meguru": "meguru",
                 "020_tsumugi": "tsumugi", "020_akogare": "akogare"}
    common = []
    heads = {k: [] for k in route_map.values()}

    for item in lists.get("common", []):
        if item["id"] in route_map:
            heads[route_map[item["id"]]].append(item)
        else:
            common.append(item)

    out = {"common": common}
    for name in ["nene", "meguru", "tsumugi", "akogare", "wakana"]:
        out[name] = heads.get(name, []) + lists.get(name, [])
    return out


def build_config(lists):
    scenarios = restructure(lists)
    # 文件名大小写归一化：以 src/common/scn/ 实际文件名为准（旧 SCN_LIST 的 path 大小写不可靠）
    scn_dir = os.path.join(ROOT, "src", "common", "scn")
    if os.path.isdir(scn_dir):
        actual = {}
        for fn in os.listdir(scn_dir):
            if fn.endswith(".txt"):
                actual[fn.lower()] = fn
        for items in scenarios.values():
            for item in items:
                low = item["path"].lower()
                if low in actual and actual[low] != item["path"]:
                    item["path"] = actual[low]
    return {
        "id": "sanoba-witch",
        "title": "魔女的夜宴",
        "version": "1.0.0",
        "engine": {"format": "vn-1.1", "minRuntime": "1.0"},
        "initialState": {"flags": {}},
        "resources": {
            "base": "/common",
            "dirs": {"bg": "bg", "sd": "sd", "ev": "ev", "ch": "ch", "audio": "audio"}
        },
        "scenarios": scenarios,
        "routes": {
            "019": {
                "type": "flagRoute",
                "targets": FLAG_ROUTE_019,
                "fallback": "020_meguru"
            }
        }
    }


def main():
    with open(CONSTANTS, "r", encoding="utf-8") as f:
        src = f.read()
    lists = extract_scn_list(src)
    total = sum(len(v) for v in lists.values())
    config = build_config(lists)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 校验：id 唯一
    ids = []
    for items in config["scenarios"].values():
        ids += [i["id"] for i in items]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        raise SystemExit("ID 重复: " + str(dup))

    print(f"生成 {OUT}")
    print(f"  提取列表: {total} 个场景 → 重组后 {len(ids)} 个")
    for name, items in config["scenarios"].items():
        print(f"    {name}: {len(items)} 个 ({items[0]['id']} .. {items[-1]['id']})")
    print("  routes: 019 → flagRoute (nene/meguru/tsumugi/akogare/wakana), fallback=020_meguru")


if __name__ == "__main__":
    main()
