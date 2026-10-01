# 男娘恋爱物语 · 小米手环移植版（Band）

《男娘恋爱物语》（Ren'Py 中文校园恋爱喜剧 v1.0）的小米手环移植版。

基于 [hrk_ 的 Senren-Banka-MiBand-10](https://github.com/hrk666666/Senren-Banka-MiBand-10) VN 引擎（VN-1.1，三槽位立绘 / 多档存档 / 快进 / 内容包解耦）移植，JSC 字节码打包。

## 分支说明

| 分支 | 适配 | 说明 |
|------|------|------|
| `main` | 小米手环 10 胶囊屏（designWidth 212） | 本分支 |
| `pro` | 小米手环 10 Pro / 9 Pro / 8 Pro 方屏（336×480） | `git checkout pro` |
| `auto` | 胶囊屏 / 方屏自适应（单包通用） | `git checkout auto` |

## 内容

- 13 场景完整剧本（约 2 万字，含英/日翻译行），4 结局：报警结局 / 关系破裂 / 室友结局 / 真结局
- 30 张分层立绘（240×480，64 色量化 PNG）、15 张 CG、16 张背景（336×480 JPEG）
- 存档 / 读档、快进、打字机、隐藏文本、亮度保持等引擎能力全量启用
- 最终 RPK 约 1.28MB

## 构建

```bash
npm ci
npm run release        # = aiot release --enable-jsc，产物在 dist/*.rpk
```

模拟器部署：

```bash
echo Y | timeout 120 aiot start --start-page 'pages/index'
```

## 授权

- 引擎与移植代码：GNU GPL v3.0（作者 hrk_）
- 《男娘恋爱物语》内容版权归原作者所有，请勿用于商业用途

## 剧本 / 资源转换

`tools/` 下为可复现的转换脚本：`convert_nn.py`（rpy→vn-1.1 剧本）、`compose_assets.py`（立绘合成与量化压缩）、`apply_ui.py`（三版本 UI 修改）。
