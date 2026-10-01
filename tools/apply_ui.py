#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一修改三版本 UI：manifest / constants / scriptRuntime / index / about / 媒体查询"""
import json, re, sys, os

BASE = "/home/user/Doubao/chats/38445140291631362/build"

def patch_file(path, pairs):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    for old, new in pairs:
        if old not in s:
            print(f"  [WARN] 未找到: {old[:60]} in {path}")
            continue
        s = s.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)

def patch_manifest(version):
    pkg = {"band": "com.hrk.nianniang.band", "pro": "com.hrk.nianniang.bandp", "auto": "com.hrk.nianniang.bandauto"}[version]
    path = f"{BASE}/{version}/src/manifest.json"
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d["package"] = pkg
    d["name"] = "男娘恋爱物语"
    d["versionName"] = "1.0.0"
    d["versionCode"] = 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f"{version}: manifest -> {pkg}")

def patch_constants(version):
    path = f"{BASE}/{version}/src/common/constants.js"
    patch_file(path, [
        ('export const CLEARS_KEY = "qlwh_clears"', 'export const CLEARS_KEY = "nn_clears"'),
        # AFTER_STORIES 置空
        ('''export const AFTER_STORIES = [
  { name: "芳乃", scn: "037", from: 553 },
  { name: "茉子", scn: "056", from: 57 },
  { name: "丛雨", scn: "077", from: 498 },
  { name: "蕾娜", scn: "097", from: 321 },
  { name: "小春", scn: "107", from: 728 },
  { name: "芦花", scn: "111", from: 789 }
]''', 'export const AFTER_STORIES = []'),
        ('// 场景分块：chunk001.txt … chunk112.txt（《千恋＊万花》55901 页剧本，每块 500 页）',
         '// 场景分块：chunk001.txt … chunk013.txt（《男娘恋爱物语》13 场景剧本）'),
    ])

def patch_runtime(version):
    path = f"{BASE}/{version}/src/engine/scriptRuntime.js"
    patch_file(path, [
        ('''const END_LINE_NAMES = {
  "gameend_yoshinoend": "芳乃",
  "gameend_makoend": "茉子",
  "gameend_murasameend": "丛雨",
  "gameend_renaend": "蕾娜",
  "gameend_koharuend": "小春",
  "gameend_rokaend": "芦花"
}''', '''const END_LINE_NAMES = {
  "gameend_badend1": "报警结局",
  "gameend_badend2": "关系破裂",
  "gameend_normalend": "室友结局",
  "gameend_trueend": "真结局"
}'''),
        ('''const HIDDEN_OPTION_JUMPS = {
  "*p8424": true  // 共通线 8418 页"还是别说多余的话比较好"→ 小春/芦花线
}''', 'const HIDDEN_OPTION_JUMPS = {}'),
    ])

def patch_index(version):
    path = f"{BASE}/{version}/src/pages/index/index.ux"
    # 标题
    patch_file(path, [
        ('<text class="header-title">千恋＊万花</text>', '<text class="header-title">男娘恋爱物语</text>'),
        # 移除后日谈入口
        ('''      <div class="item" @click="routeAfterStory">
        <text class="itemtext">后日谈</text>
        <image class="arrow" src="/common/images/enter.png"></image>
      </div>
''', ''),
        # 移除后日谈弹窗
        ('''    <!-- 后日谈选择 -->
    <div class="confirm-overlay" if="{{ showAfterStory }}">
      <div class="after-dialog">
        <text class="confirm-title">后日谈</text>
        <text class="confirm-message">通关对应主线后解锁</text>
        <scroll scroll-y="true" class="after-list">
          <div
            class="after-item {{ clears.indexOf(item.name) !== -1 ? '' : 'after-item-locked' }}"
            for="{{item in afterStoryList}}"
            @click="startAfterStory(item.name)"
          >
            <text class="after-item-text">{{ item.name }}线</text>
            <text class="after-item-state">{{ clears.indexOf(item.name) !== -1 ? '可阅读' : '未解锁' }}</text>
          </div>
        </scroll>
        <div class="confirm-buttons">
          <div class="confirm-btn confirm-btn-cancel" @click="closeAfterStory">
            <text class="confirm-btn-text">返回</text>
          </div>
        </div>
      </div>
    </div>

''', ''),
        ('<text class="itemtext">关于本篇</text>', '<text class="itemtext">关于本作</text>'),
    ])
    # 移除 JS 中后日谈相关（routeAfterStory/closeAfterStory/startAfterStory 方法体 + 数据字段）
    patch_file(path, [
        ('''    showAfterStory: false,
    afterStoryList: AFTER_STORIES,
''', ''),
        ('''
  routeAfterStory() {
    if (this.isNavigating) return
    this.isNavigating = true
    this.vibrateIfEnabled()
    this.showAfterStory = true
    this.navTimer = setTimeout(() => { this.isNavigating = false }, 2000)
  },

  closeAfterStory() {
    this.showAfterStory = false
  },

  startAfterStory(name) {
    const item = this.afterStoryList.find((i) => i.name === name)
    if (!item) return
    if (this.clears.indexOf(name) === -1) {
      prompt.showToast({ message: "未解锁：先通关「" + name + "」线" })
      return
    }
    if (this.isNavigating) return
    this.isNavigating = true
    this.vibrateIfEnabled()
    this.showAfterStory = false
    this.$app.$def.globalGameState = {
      _fromAfterStory: { scn: item.scn, from: item.from }
    }
    router.push({ uri: "/pages/game" })
    this.navTimer = setTimeout(() => { this.isNavigating = false }, 2000)
  },
''', ''),
    ])

def patch_about(version):
    dev = {"band": "Band 9/10/11", "pro": "Band 9 Pro/10 Pro/8 Pro", "auto": "胶囊屏/方屏 自适应"}[version]
    path = f"{BASE}/{version}/src/pages/about/about.ux"
    patch_file(path, [
        ('<text class="app-name">千恋＊万花</text>', '<text class="app-name">男娘恋爱物语</text>'),
        (f'<text class="app-version">Band 9/10/11 · v{{{{ appVersion }}}}</text>',
         f'<text class="app-version">{dev} · v{{{{ appVersion }}}}</text>'),
        ('<text class="info-value">内容版权归原厂商（SAGA PLANETS）所有，请勿用于商业用途</text>',
         '<text class="info-value">内容版权归原作者所有，请勿用于商业用途</text>'),
    ])

def patch_rect(version):
    """Pro/Auto 加 about/data/settings 方屏媒体查询（参照上游 pro 分支）"""
    if version == "band":
        return
    # about
    path = f"{BASE}/{version}/src/pages/about/about.ux"
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "@media (shape: rect)" not in s:
        s += '''
/* 方形屏（手环 10 Pro / 9 Pro / 8 Pro，336x480） */
@media (shape: rect) {
  .header {
    top: 13px;
    height: 28px;
  }
  .header-title {
    font-size: 16px;
  }
  .list {
    top: 48px;
    bottom: 10px;
  }
  .card {
    padding: 9px 11px;
    border-radius: 13px;
  }
  .app-icon {
    width: 30px;
    height: 30px;
    border-radius: 15px;
    margin-right: 9px;
  }
  .app-name {
    font-size: 14px;
  }
  .app-version {
    font-size: 10px;
  }
  .info-label {
    font-size: 11px;
    margin-bottom: 2px;
  }
  .info-value {
    font-size: 12px;
  }
  .arrow {
    width: 15px;
    height: 15px;
  }
}
'''
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"{version}: about.ux rect 适配已加")
    # settings
    path = f"{BASE}/{version}/src/pages/settings/settings.ux"
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "@media (shape: rect)" not in s:
        s += '''
/* 方形屏（手环 10 Pro / 9 Pro / 8 Pro，336x480） */
@media (shape: rect) {
  .header {
    top: 13px;
    height: 28px;
  }
  .header-title {
    font-size: 16px;
  }
  .list {
    top: 48px;
    bottom: 100px;
  }
  .item {
    min-height: 35px;
    margin-bottom: 5px;
    padding: 6px 10px;
    border-radius: 16px;
  }
  .item-title {
    font-size: 12px;
  }
  .item-desc {
    font-size: 11px;
  }
  .bottom-bar {
    bottom: 82px;
  }
  .reset-btn {
    height: 30px;
    border-radius: 15px;
  }
  .reset-btn-text {
    font-size: 13px;
  }
  .preview-panel {
    bottom: 10px;
    height: 60px;
    border-radius: 13px;
    padding: 8px;
  }
}
'''
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"{version}: settings.ux rect 适配已加")
    # data
    path = f"{BASE}/{version}/src/pages/data/data.ux"
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if "@media (shape: rect)" not in s:
        s += '''
/* 方形屏（手环 10 Pro / 9 Pro / 8 Pro，336x480） */
@media (shape: rect) {
  .header {
    top: 13px;
    height: 28px;
  }
  .header-title {
    font-size: 16px;
  }
  .list {
    top: 48px;
    bottom: 45px;
  }
  .card {
    min-height: 40px;
    margin-bottom: 5px;
    padding: 8px 10px;
    border-radius: 13px;
  }
  .card-title {
    font-size: 12px;
  }
  .card-desc {
    font-size: 10px;
    line-height: 13px;
  }
  .card-date {
    font-size: 9px;
  }
  .status-icon {
    width: 15px;
    height: 15px;
  }
  .card-empty {
    height: 25px;
  }
  .empty-icon {
    width: 15px;
    height: 15px;
    margin-right: 5px;
  }
  .footer {
    bottom: 10px;
    height: 30px;
    border-radius: 15px;
  }
  .footer-text {
    font-size: 13px;
  }
  .confirm-dialog {
    padding: 13px 10px;
    border-radius: 13px;
  }
  .confirm-title {
    font-size: 13px;
    margin-bottom: 6px;
  }
  .confirm-message {
    font-size: 10px;
    line-height: 14px;
    margin-bottom: 12px;
  }
  .confirm-btn {
    height: 26px;
    margin: 0 3px;
    border-radius: 13px;
  }
  .confirm-btn-text {
    font-size: 11px;
  }
}
'''
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"{version}: data.ux rect 适配已加")

def main():
    for v in ["band", "pro", "auto"]:
        print(f"== {v} ==")
        patch_manifest(v)
        patch_constants(v)
        patch_runtime(v)
        patch_index(v)
        patch_about(v)
        patch_rect(v)

if __name__ == "__main__":
    main()
