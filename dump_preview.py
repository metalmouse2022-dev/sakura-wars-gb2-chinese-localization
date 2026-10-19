# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 初探文本与数据结构提取脚本
"""
import sys
import os
import re

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

ROM_PATH = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
OUTPUT_REPORT = "dump_preview.txt"

def analyze_rom():
    if not os.path.exists(ROM_PATH):
        print(f"ROM 未找到: {ROM_PATH}")
        return

    with open(ROM_PATH, "rb") as f:
        rom = f.read()

    report_lines = []
    def log(msg=""):
        try:
            print(msg)
        except:
            print(msg.encode('utf-8', errors='replace').decode('gbk', errors='replace'))
        report_lines.append(msg)

    log("=" * 60)
    log("【1. ROM 基本信息】")
    title = rom[0x134:0x143].decode('latin1', errors='replace')
    log(f"游戏标题: {title.strip()}")
    log(f"ROM 大小: {len(rom)} 字节 ({len(rom) // 1024} KB / {len(rom) // (1024*1024)} MB)")
    log(f"总 Bank 数量: {len(rom) // 0x4000} 个 (0x00 ~ 0xFF)")

    log("\n" + "=" * 60)
    log("【2. Bank 0x11: 道具/招式技能数据库提取预览】")
    # Bank 0x11 包含固定宽度的道具与招式数据
    b11_start = 0x11 * 0x4000
    b11 = rom[b11_start:b11_start + 0x4000]
    
    # 提取技能/道具名 (前16字节为Shift-JIS字符串，含全角空格填充)
    items = []
    for offset in range(0x0000, 0x1000, 32):
        record = b11[offset:offset+32]
        name_raw = record[:16]
        try:
            name = name_raw.decode('cp932').strip('\x00 　')
            if name and all(ord(c) >= 32 for c in name):
                items.append((offset, name, record[16:].hex()))
        except:
            pass

    log(f"在 Bank 0x11 识别到固定结构记录 {len(items)} 条，示例展示前 15 条：")
    for off, name, extra in items[:15]:
        log(f"  [偏移 0x{off:04X}] 名称: {name:<12} | 属性数据: {extra[:24]}...")

    log("\n" + "=" * 60)
    log("【3. Bank 0x1F: 剧情/战斗台词脚本提取预览】")
    # Bank 0x1F 包含带角色分支指令的战斗台词与对话
    b1f_start = 0x1F * 0x4000
    b1f = rom[b1f_start:b1f_start + 0x4000]

    dialogues = []
    pattern = re.compile(rb'((?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e]){4,}\x00)')
    for m in pattern.finditer(b1f):
        raw = m.group(1)[:-1]
        try:
            text = raw.decode('cp932')
            if any(ord(c) > 0x3000 for c in text):
                prefix_start = max(0, m.start() - 4)
                ctrl_bytes = b1f[prefix_start:m.start()].hex()
                cpu_addr = 0x4000 + m.start()
                dialogues.append((m.start(), cpu_addr, ctrl_bytes, text))
        except:
            pass

    log(f"在 Bank 0x1F 识别到独立剧情/台词文本 {len(dialogues)} 句，示例展示：")
    for off, cpu_addr, ctrl, text in dialogues[:12]:
        log(f"  [ROM 0x{b1f_start+off:06X} | CPU 0x{cpu_addr:04X}] 前置控制码: {ctrl} | 台词: {text}")

    log("\n" + "=" * 60)
    log("【4. 文本引擎特征总结】")
    log("1. 编码格式: 核心文本采用标准 Shift-JIS (CP932) 双字节编码。")
    log("2. 文本寻址: 脚本中包含 16位 CPU 地址 (0x4000~0x7FFF 映射当前 Bank)。")
    log("3. 分支指令: 发现了角色分支条件选择码 (如 2D CA [角色ID] [指针] 0B)。")
    log("4. 控制代码: 台词前包含控制序列 (例如 1D 05 xx 用于控制肖像/音效/延时)。")
    log("=" * 60)

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(report_lines))
    print(f"\n完整报告已保存至: {OUTPUT_REPORT}")

if __name__ == "__main__":
    analyze_rom()
