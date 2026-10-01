import os
import json
import traceback
import sys

from enum import IntEnum

class EventType(IntEnum):
    LABEL = 0  # 标签/跳转点 [0, "label_name"]
    CHAPTER_TITLE = 1  # 章节标题 [1, "章节标题"]
    BACKGROUND = 2  # 背景切换 [2, "bg_name"]
    DIALOGUE = 3  # 对话 [3, "说话人", "内容", [立绘列表]] #立绘列表可空
    SELECT = 4  # 选项 [4, [["文字", "跳转", "表达式"]]]
    EV = 5  # 事件CG [5, "ev_img_name"]
    NEXT = 6  # 跳转至（下一章？） [6, "target_label"]


def to_arrays(raw_data):
    output = []

    # 状态记录
    last_bg = None
    last_character_state = None
    last_title = None
    last_ev = None

    # 获取scenes场景列表
    scenes = raw_data.get("scenes", []) if isinstance(raw_data, dict) else []

    # 遍历每个场景
    for scene in scenes:
        # 标签/跳转点 -> [0, "label_name"]
        if "label" in scene and scene["label"]:
            output.append([EventType.LABEL, scene["label"]])

        # 提取章节标题 -> [1, "章节标题"]
        title = scene.get("title")
        if title and title != last_title:
            output.append([EventType.CHAPTER_TITLE, title])
            last_title = title

        # 解析每个场景下的texts
        texts_blocks = scene.get("texts", [])
        for line in texts_blocks:
            if not isinstance(line, list) or len(line) < 6:
                continue
            
            # 读取原始json，示例：
            # [
            #   "女学生",                                                        # Index0 角色名
            #   "女子",                                                           # Index1 貌似是别名？           
            #   "「那个……保科君，有空么」(因不明原因，部分人名汉化后显示改不了，请见谅）",   # Index2 对话内容
            #   ...,                                                             # Index3 貌似是CV，省略
            #   208,                                                             # Index4 未知数字   
            #   {"data": [ ["stage", ...], ["bgm", ...] ], ...}                  # Index5 控制命令，（包含背景、立绘等）                 
            # ],
            speaker = line[0] or ""
            message = line[2] or ""
            command_dict = line[5]

            current_characters = []

            # 读取控制命令，提取背景 立绘信息
            if isinstance(command_dict, dict):
                # 示例
                # {
	            #   "data": [], "env": {}，"meswinchange": "", "showdate": {}
                # }
                
                # 读取data
                for cmd in command_dict.get("data", []):
                    if not isinstance(cmd, list) or len(cmd) < 3:
                        continue

                    cmd_type = cmd[1]   
                    params  = cmd[2] or {}

                    # 背景
                    if cmd_type == "stage":
                        current_bg = (
                            params.get("redraw", {}).get("imageFile", {}).get("file")
                        )

                        # 处理与写入背景切换 -> [2, "bg_name"]
                        if current_bg and current_bg != last_bg:
                            output.append([EventType.BACKGROUND, current_bg])
                            last_bg = current_bg

                    # 事件
                    if cmd_type == "event":
                        current_ev_img = (
                            params.get("redraw", {}).get("imageFile", {}).get("file")
                        )

                        # 处理与写入事件CG -> [5, "ev_img_name"]
                        if current_ev_img != last_ev:
                            output.append([EventType.EV, current_ev_img])
                            last_ev = current_ev_img

                    # 立绘
                    if cmd_type == "character":
                        if params .get("showmode") == 0:
                            continue

                        name = params .get("name")
                        redraw = params.get("redraw", {})
                        opts = redraw.get("imageFile", {}).get("options", {})
                        if name:
                            # 立绘数组: [姓名, 位置, 表情, 服装]
                            current_characters.append(
                                [
                                    name,
                                    redraw.get("posName", "中"),
                                    opts.get("face", ""),
                                    opts.get("dress", ""),
                                ]
                            )

            # 处理对话
            character_to_save = None
            if current_characters != last_character_state:
                character_to_save = current_characters
                last_character_state = current_characters

            # 只有当有说话人、有话或者立绘变了才写入文件 -> [3, "说话人", "内容", [立绘列表](可空)]
            if speaker or message or character_to_save is not None:
                dialog = [EventType.DIALOGUE, speaker, message]
                # 只在有立绘时在对话尾部附加
                if character_to_save is not None:
                    dialog.append(character_to_save)

                output.append(dialog)

        # 处理选项 -> [4, [["文字", "跳转", "表达式"]]]
        selects = scene.get("selects", [])
        if selects and isinstance(selects, list):
            select_list = []

            for line in selects:
                if "text" not in line:
                    continue

                # 提取 target 或 tag
                target = line.get("target") or line.get("tag") or ""

                # 与上文补全跳转一致，强制补上 *
                if target and not target.startswith("*"):
                    target = "*" + target

                select_list.append([line.get("text", ""), target, line.get("exp", "")])

            if select_list:
                output.append([EventType.SELECT, select_list])

        # 处理跳转 -> [6, "target_label"]
        nexts = scene.get("nexts", [])
        if nexts and isinstance(nexts, list):
            for line in nexts:
                target = line.get("target") or line.get("tag")

                if target:
                    # 如果不为空且不以 * 开头，则强制补上，有时target与实际节点有偏差
                    if not target.startswith("*"): target = "*" + target

                    output.append([EventType.NEXT, target])
                    break

    return output


def batch_process():
    input_dir, output_dir = get_args()
    if not input_dir or not output_dir:
        return
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 遍历输入文件夹
    for root, _, files in os.walk(input_dir):
        for file in files:
            # 忽略resx.json结尾与非.json结尾的文件
            if file.endswith("resx.json") or not file.endswith(".json"):
                continue

            # 忽略特定文件
            ignoreList = ["charvoice", "classlist", "scenelist"]
            skip_file = False
            for ignore in ignoreList:
                if ignore in file:
                    print(f"跳过: {file}")
                    skip_file = True
                    break
            if skip_file:
                continue

            # 构建输入输出文件路径，为后缀拼上txt
            input_file_path = os.path.join(root, file)
            output_file_path = os.path.join(
                output_dir, os.path.splitext(file)[0] + ".txt"
            )

            try:
                with open(input_file_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)

                compact_data = to_arrays(raw_data)

                # 压缩与写入文件
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(
                        compact_data, f, ensure_ascii=False, separators=(",", ":")
                    )

                print(f"转换成功: {file}")
            except Exception:
                print(f"转换失败: {file}\n{traceback.format_exc()}")


def get_args():
    # 获取命令行参数
    if len(sys.argv) < 3 or len(sys.argv) > 5:
        print("用法：python convert_script.py <输入路径> <输出路径>")
        return None, None

    # 处理路径参数，去除多余的引号和空格
    input_dir = sys.argv[1].strip().strip('"')
    output_dir = sys.argv[2].strip().strip('"')
    return input_dir, output_dir


if __name__ == "__main__":
    batch_process()
