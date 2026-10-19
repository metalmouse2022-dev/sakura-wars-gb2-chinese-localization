# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 地下城与出击剧情提取器 (Dungeon & Sortie Text Dumper)
负责提取:
- Bank 0x60 ~ 0x6F (16 个 Bank)
- Bank 0x90 ~ 0x94 (5 个 Bank)
提取结果存放在 translations/dungeon/ 目录下
"""
import os
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

ROM_PATH = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
OUTPUT_DIR = "translations/dungeon"

def load_rom():
    with open(ROM_PATH, "rb") as f:
        return f.read()

def load_1byte_table(rom):
    tbl_offset = 0x08355A
    chars = {}
    for i in range(256):
        b = rom[tbl_offset + i * 2 : tbl_offset + i * 2 + 2]
        try:
            ch = b.decode('shift-jis')
            if ch != '×':
                chars[i] = ch
        except:
            pass
    return chars

def dump_dungeon_bank(rom, bank_num, tbl):
    b_start = bank_num * 0x4000
    b_data = rom[b_start : b_start + 0x4000]
    entries = []
    i = 0
    length = len(b_data)

    while i < length:
        # 跳过开头的 0x00 填充
        if b_data[i] == 0:
            i += 1
            continue

        start_off = i
        tokens = []
        has_kana = False
        text_char_count = 0

        while i < length:
            b = b_data[i]
            if b == 0:
                i += 1
                break
            elif b == 0x0D:
                tokens.append("\n")
                i += 1
            elif b == 0x08:
                tokens.append("<NAME>")
                text_char_count += 1
                i += 1
            elif b in tbl:
                c = tbl[b]
                tokens.append(c)
                text_char_count += 1
                if '\u3040' <= c <= '\u30ff':
                    has_kana = True
                i += 1
            elif 0x20 <= b <= 0x7E:
                tokens.append(chr(b))
                text_char_count += 1
                i += 1
            else:
                tokens.append(f"<{b:02X}>")
                i += 1

        raw_text = "".join(tokens)
        orig_byte_len = i - start_off  # 包含结尾 0x00 的字节长度
        # 只要包含假名且字符数>=2，判定为有效台词
        if has_kana and text_char_count >= 2:
            entries.append({
                "bank": f"0x{bank_num:02X}",
                "rom_offset": f"0x{b_start + start_off:06X}",
                "bank_offset": f"0x{start_off:04X}",
                "cpu_addr": f"0x{0x4000 + start_off:04X}",
                "orig_len": orig_byte_len,
                "text": raw_text
            })

    return entries

def save_dungeon_file(bank_num, entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fname = f"dungeon_bank_{bank_num:02X}.txt"
    fpath = os.path.join(OUTPUT_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"# 樱花大战GB2 汉化底稿: 地下城与出击剧情 (Bank 0x{bank_num:02X})\n")
        f.write(f"# 本文件条目数: {len(entries)}\n")
        f.write("# 规则: 在 CN: 下方直接输入中文译文。换行为实际换行，保留 <NAME> 等控制标签。\n")
        f.write("=" * 60 + "\n\n")

        for idx, entry in enumerate(entries, 1):
            f.write(f"# [{idx:04d}] [ROM: {entry['rom_offset']}] [Bank: {entry['bank']}:{entry['bank_offset']}] [CPU: {entry['cpu_addr']}] [OrigLen: {entry['orig_len']}]\n")
            for line in entry['text'].split('\n'):
                f.write(f"JP: {line}\n")
            f.write("CN: \n\n")

def main():
    print("=" * 60)
    print("【樱花大战GB2 - 地下城与出击剧情全量提取工具】")
    rom = load_rom()
    tbl = load_1byte_table(rom)
    print(f"假名码表加载完成: 共 {len(tbl)} 个有效字符")

    target_banks = list(range(0x60, 0x70)) + list(range(0x90, 0x95))
    total_dialogues = 0

    for b in target_banks:
        entries = dump_dungeon_bank(rom, b, tbl)
        save_dungeon_file(b, entries)
        total_dialogues += len(entries)
        print(f"  - Bank 0x{b:02X}: 导出 {len(entries)} 条台词 -> translations/dungeon/dungeon_bank_{b:02X}.txt")

    print("=" * 60)
    print(f"全部提取完成！共 21 个 Bank，总计 {total_dialogues} 条地下城台词已导出至 {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
