# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 全量结构化文本提取器 (Structured Full Text Dumper)
分类导出：
1. 主线剧情章节 (translations/story/chapter_01.txt ~ chapter_14.txt)
2. 战斗与台词 (translations/battle/skills_and_items.txt, battle_dialogues.txt, mecha_units.txt)
3. 系统与菜单 (translations/system/chapter_titles.txt, system_menus.txt, item_events.txt)
4. 地图与探索 (translations/exploration/exploration_events.txt)
5. 全量汇总底稿 (translations/master_dialogue.txt)
"""
import os
import sys
import json
import re

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

ROM_PATH = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
OUTPUT_DIR = "translations"

def load_rom():
    with open(ROM_PATH, "rb") as f:
        return f.read()

def build_1byte_table(rom):
    """构建位于 Bank 0x20 (ROM 0x83500) 的 1-Byte 假名码表 (>= 0x3C 为有效文字)"""
    tbl = {}
    table_base = 0x83500
    for i in range(0x3C, 256):
        pos = table_base + i * 2
        raw = rom[pos:pos+2]
        try:
            char = raw.decode('cp932')
            if char != '×':
                tbl[i] = char
        except:
            pass
    return tbl

def dump_1byte_script_bank(bank_num, bank_data, tbl):
    """解析 1-byte 格式的主线剧情 Bank，完整保留控制代码 <XX> 和换行符"""
    entries = []
    i = 0
    length = len(bank_data)

    while i < length:
        # 跳过开头的连续 0x00
        while i < length and bank_data[i] == 0:
            i += 1
        if i >= length:
            break

        start_offset = i
        tokens = []
        text_char_count = 0

        while i < length:
            b = bank_data[i]
            if b == 0x00:
                i += 1
                break
            elif b == 0x0D:
                tokens.append("\n")
                i += 1
            elif b in tbl:
                tokens.append(tbl[b])
                text_char_count += 1
                i += 1
            elif b == 0x10:
                # 0x10 是全角空格/间距
                tokens.append("　")
                i += 1
            else:
                # 控制代码保留为 <XX>
                tokens.append(f"<{b:02X}>")
                i += 1

        # 只要该串包含至少 2 个有效文字字符，即判定为剧情对话
        if text_char_count >= 2:
            raw_text = "".join(tokens).strip()
            # 滤除纯控制码或过短噪点
            if any('\u3040' <= c <= '\u30ff' for c in raw_text):
                entries.append({
                    "bank": f"0x{bank_num:02X}",
                    "rom_offset": f"0x{bank_num * 0x4000 + start_offset:06X}",
                    "bank_offset": f"0x{start_offset:04X}",
                    "format": "1-Byte-Script",
                    "text": raw_text
                })

    return entries

def is_clean_japanese(txt):
    """过滤二进制噪点，仅保留真实有意义的日文台词/菜单"""
    jp_kana = sum(1 for c in txt if '\u3040' <= c <= '\u30ff')
    jp_kanji = sum(1 for c in txt if '\u4e00' <= c <= '\u9fff')
    jp_punct = sum(1 for c in txt if c in '、。！？～『』「」…（）\r\n 　・：／↑↓＋－０１２３４５６７８９')
    total = len(txt)
    if total < 2: return False
    valid = jp_kana + jp_kanji + jp_punct
    if jp_kana >= 2 and (valid / total) >= 0.5:
        return True
    if (jp_kana + jp_kanji) >= 2 and (valid / total) >= 0.6:
        return True
    return False

def dump_sjis_bank(bank_num, bank_data, min_len=2):
    """提取 Bank 内的标准 Shift-JIS 字符串"""
    pattern = re.compile(rb'((?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e]|\r|\n){%d,}\x00)' % min_len)
    entries = []
    for m in pattern.finditer(bank_data):
        raw = m.group(1)[:-1]
        try:
            txt = raw.decode('cp932')
            if is_clean_japanese(txt):
                clean_txt = txt.strip('\x00')
                entries.append({
                    "bank": f"0x{bank_num:02X}",
                    "rom_offset": f"0x{bank_num * 0x4000 + m.start():06X}",
                    "bank_offset": f"0x{m.start():04X}",
                    "format": "Shift-JIS",
                    "text": clean_txt
                })
        except:
            pass
    return entries

def save_text_file(filepath, title, entries):
    """将文本条目保存为标准的翻译工作底稿格式"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# 樱花大战GB2 汉化底稿: {title}\n")
        f.write(f"# 本文件条目数: {len(entries)}\n")
        f.write("# 规则: 在 CN: 下方直接输入中文译文。请保留 <XX> 控制标签与换行。\n")
        f.write("=" * 60 + "\n\n")

        for idx, entry in enumerate(entries, 1):
            f.write(f"# [{idx:04d}] [ROM: {entry['rom_offset']}] [Bank: {entry['bank']}:{entry['bank_offset']}]\n")
            lines = entry['text'].split('\n')
            for l in lines:
                f.write(f"JP: {l}\n")
            f.write("CN: \n\n")

def main():
    print("=" * 60)
    print("【樱花大战GB2 - 全量结构化文本提取工具】")
    rom = load_rom()
    tbl = build_1byte_table(rom)
    print(f"1-Byte 码表加载完成: 共 {len(tbl)} 个有效字符")

    all_master_entries = []

    # 1. 提取主线剧情 (Bank 0x41 ~ 0x4E -> 第 1 章 ~ 第 14 章)
    print("\n[1/4] 正在提取主线剧情 (第1章 ~ 第14章)...")
    for chapter_idx, bank_num in enumerate(range(0x41, 0x4F), 1):
        b_data = rom[bank_num * 0x4000 : (bank_num + 1) * 0x4000]
        entries = dump_1byte_script_bank(bank_num, b_data, tbl)
        ch_name = f"chapter_{chapter_idx:02d}"
        ch_title = f"第 {chapter_idx:02d} 章 主线剧情 (Bank 0x{bank_num:02X})"
        save_text_file(os.path.join(OUTPUT_DIR, "story", f"{ch_name}.txt"), ch_title, entries)
        all_master_entries.extend(entries)
        print(f"  - {ch_title}: {len(entries)} 条台词")

    # 2. 提取战斗与角色系统文本
    print("\n[2/4] 正在提取战斗技能、道具与角色台词...")
    battle_targets = [
        (0x11, "skills_and_items.txt", "战斗技能与道具名 (Bank 0x11)"),
        (0x1E, "mecha_units.txt", "光武机体与装备数据 (Bank 0x1E)"),
        (0x1F, "battle_dialogues.txt", "角色出击/胜利战斗台词 (Bank 0x1F)")
    ]
    for bank_num, fname, title in battle_targets:
        b_data = rom[bank_num * 0x4000 : (bank_num + 1) * 0x4000]
        entries = dump_sjis_bank(bank_num, b_data)
        save_text_file(os.path.join(OUTPUT_DIR, "battle", fname), title, entries)
        all_master_entries.extend(entries)
        print(f"  - {title}: {len(entries)} 条文本")

    # 3. 提取系统UI、主线标题与事件
    print("\n[3/4] 正在提取章节标题、系统UI与剧情分支...")
    system_targets = [
        (0xC1, "chapter_titles.txt", "主线章节标题与主界面 (Bank 0xC1)"),
        (0x1B, "system_events_1b.txt", "日常系统对话与分支 A (Bank 0x1B)"),
        (0x1C, "system_events_1c.txt", "日常系统对话与分支 B (Bank 0x1C)"),
        (0x24, "item_events.txt", "道具拾取与任务提示 (Bank 0x24)")
    ]
    for bank_num, fname, title in system_targets:
        b_data = rom[bank_num * 0x4000 : (bank_num + 1) * 0x4000]
        entries = dump_sjis_bank(bank_num, b_data)
        save_text_file(os.path.join(OUTPUT_DIR, "system", fname), title, entries)
        all_master_entries.extend(entries)
        print(f"  - {title}: {len(entries)} 条文本")

    # 4. 提取大地图探索事件 (Bank 0x30 ~ 0x34)
    print("\n[4/4] 正在提取大地图与探索交互事件 (Bank 0x30 ~ 0x34)...")
    explore_entries = []
    for bank_num in range(0x30, 0x35):
        b_data = rom[bank_num * 0x4000 : (bank_num + 1) * 0x4000]
        entries = dump_sjis_bank(bank_num, b_data)
        explore_entries.extend(entries)
    save_text_file(os.path.join(OUTPUT_DIR, "exploration", "exploration_events.txt"), "大地图探索事件 (Bank 0x30-0x34)", explore_entries)
    all_master_entries.extend(explore_entries)
    print(f"  - 大地图探索事件: {len(explore_entries)} 条文本")

    # 5. 输出汇总 master 文件
    master_txt_file = os.path.join(OUTPUT_DIR, "master_dialogue.txt")
    save_text_file(master_txt_file, "全游戏主线与系统总底稿汇总", all_master_entries)

    print("\n" + "=" * 60)
    print("【导出全部完毕！】")
    print(f"全游戏有效文本总计: {len(all_master_entries)} 条")
    print(f"文本存放目录: {OUTPUT_DIR}/")
    print("  ├── story/        (主线 1~14 章剧情，如 chapter_01.txt)")
    print("  ├── battle/       (战斗台词、道具、招式、光武机体)")
    print("  ├── system/       (章节标题、系统UI、日常分支)")
    print("  ├── exploration/  (大地图探索NPC对话)")
    print("  └── master_dialogue.txt (包含上述全部内容的单文件总表)")
    print("=" * 60)

if __name__ == "__main__":
    main()
