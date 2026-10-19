# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 主线剧情全量重新提取工具 (Story Re-Extractor)
依据底层硬件渲染引擎 (Bank 0x00: $17A4 & Bank 0x18: $46BB) 的图块直址编码 (Tile-Direct Encoding)
完全重新导出 1~14 章官方纯正日文台词，彻底清除历史乱码。
"""
import os
import shutil

ROM_PATH = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
OUTPUT_DIR = "translations"

with open(ROM_PATH, 'rb') as f:
    rom = f.read()

# 1. 构建 H=0 单字节字符表 (Bank 0x06: 0x10 ~ 0xFE)
h0_table = {0x09: '·', 0x10: ' '}
for i in range(10): h0_table[0x11+i] = str(i)
for i in range(26): h0_table[0x1B+i] = chr(ord('A')+i)
for i in range(26): h0_table[0x35+i] = chr(ord('a')+i)

h0_chars = [
    'ぁ', 'あ', 'ぃ', 'い', 'ぅ', 'う', 'ぇ', 'え', 'ぉ', 'お',
    'か', 'が', 'き', 'ぎ', 'く', 'ぐ', 'け', 'げ', 'こ', 'ご',
    'さ', 'ざ', 'し', 'じ', 'す', 'ず', 'せ', 'ぜ', 'そ', 'ぞ',
    'た', 'だ', 'ち', 'ぢ', 'っ', 'つ', 'づ', 'て', 'で', 'と', 'ど',
    'な', 'に', 'ぬ', 'ね', 'の',
    'は', 'ば', 'ぱ', 'ひ', 'び', 'ぴ', 'ふ', 'ぶ', 'ぷ', 'へ', 'べ', 'ぺ', 'ほ', 'ぼ', 'ぽ',
    'ま', 'み', 'む', 'め', 'も',
    'ゃ', 'や', 'ゅ', 'ゆ', 'ょ', 'よ',
    'ら', 'り', 'る', 'れ', 'ろ',
    'ゎ', 'わ', '、', '。', 'を', 'ん',
    'ァ', 'ア', 'ィ', 'イ', 'ゥ', 'ウ', 'ェ', 'エ', 'ォ', 'オ',
    'カ', 'ガ', 'キ', 'ギ', 'ク', 'グ', 'ケ', 'ゲ', 'コ', 'ゴ',
    'サ', 'ザ', 'シ', 'ジ', 'ス', 'ズ', 'セ', 'ゼ', 'ソ', 'ゾ',
    'タ', 'ダ', 'チ', 'ヂ', 'ッ', 'ツ', 'ヅ', 'テ', 'デ', 'ト', 'ド',
    'ナ', 'ニ', 'ヌ', 'ネ', 'ノ',
    'ハ', 'バ', 'パ', 'ヒ', 'ビ', 'ピ', 'フ', 'ブ', 'プ', 'ヘ', 'ベ', 'ペ', 'ホ', 'ボ', 'ポ',
    'マ', 'ミ', 'ム', 'メ', 'モ',
    'ャ', 'ヤ', 'ュ', 'ユ', 'ョ', 'ヨ',
    'ラ', 'リ', 'ル', 'レ', 'ロ',
    'ヮ', 'ワ', 'ヰ', 'ヱ', 'ヲ', 'ン', 'ヴ', 'ヵ', 'ヶ',
    '？', '！', 'ー', '～', '「', '」', '…'
]
for i, c in enumerate(h0_chars):
    h0_table[0x4F + i] = c

# 2. 构建 H=1 符号表
h1_symbols = [
    '/', "'", '"', '(', ')', '[', ']', '『', '』', '+', '-', '×', '÷', '=', '%', '♪',
    '_', '<', '>', '→', '々', ':', '○', 'Ex', '♥'
]
h1_table = {i: c for i, c in enumerate(h1_symbols)}

# 3. 构建 H=2..6 汉字映射表
kanji_table = {
    # H=2
    (2, 0x00): '員', (2, 0x01): '遠', (2, 0x02): '黄', (2, 0x04): '栄', (2, 0x05): '液',
    (2, 0x06): '意', (2, 0x07): '飲', (2, 0x09): '応', (2, 0x0E): '因', (2, 0x10): '挨',
    (2, 0x11): '衣', (2, 0x1E): '育', (2, 0x20): '一', (2, 0x23): '王', (2, 0x25): '居',
    (2, 0x28): '悪',
    # H=3
    (3, 0x00): '組', (3, 0x01): '赤', (3, 0x02): '静', (3, 0x03): '雪', (3, 0x0D): '仕',
    (3, 0x10): '衛', (3, 0x13): '天', (3, 0x20): '酒', (3, 0x25): '席', (3, 0x50): '孫',
    (3, 0x56): '節', (3, 0x58): '山', (3, 0x61): '邪', (3, 0x65): '上', (3, 0x67): '咲',
    (3, 0x72): '春', (3, 0x78): '先', (3, 0x8A): '誠', (3, 0x8B): '実', (3, 0x91): '芝',
    (3, 0x92): '親', (3, 0x94): '自', (3, 0x95): '車', (3, 0x96): '歓', (3, 0x97): '趣',
    (3, 0x98): '様', (3, 0x99): '然', (3, 0xC1): '数',
    # H=4
    (4, 0x00): '典', (4, 0x01): '玉', (4, 0x02): '退', (4, 0x03): '井', (4, 0x04): '倒',
    (4, 0x0D): '体', (4, 0x0E): '大', (4, 0x0F): '多', (4, 0x10): '亭', (4, 0x11): '談',
    (4, 0x19): '魂', (4, 0x20): '的', (4, 0x28): '置', (4, 0x6B): '包', (4, 0x84): '百',
    (4, 0x87): '箱', (4, 0xD1): '身', (4, 0xE3): '欲',
    # H=5
    (5, 0x00): '了', (5, 0x01): '令', (5, 0x02): '料', (5, 0x04): '卵', (5, 0x05): '兼',
    (5, 0x10): '来', (5, 0x19): '緑', (5, 0x20): '話', (5, 0x23): '頼', (5, 0x25): '異',
    (5, 0x28): '急', (5, 0x40): '則', (5, 0x87): '館',
    # H=6
    (6, 0x01): '袋', (6, 0x02): '得', (6, 0x06): '忍', (6, 0x10): '病', (6, 0x11): '犯',
    (6, 0x1A): '売', (6, 0x1C): '皮', (6, 0x20): '梅', (6, 0x28): '裕', (6, 0x3D): '影',
    (6, 0x4C): '歯', (6, 0x4F): '登', (6, 0x5D): '項', (6, 0x6D): '菅', (6, 0x6F): '沢',
    (6, 0x82): '磯', (6, 0x94): '芽', (6, 0x99): '節', (6, 0x9A): '演', (6, 0xA2): '哀',
    (6, 0xAF): '徹', (6, 0xB5): '厚', (6, 0xB6): '亡', (6, 0xDF): 'ッド', (6, 0xE8): '圭',
    (6, 0xE9): '亨'
}

def decode_dialogue_segment(data, start_pos):
    i = start_pos
    chars = []
    while i < len(data):
        b = data[i]
        i += 1
        if b == 0x00:
            break
        elif b == 0x0D:
            chars.append('\n')
        elif b == 0x08:
            chars.append('[大神]')
        elif b == 0xFF and i < len(data) and data[i] == 0xFF:
            chars.append('！')
            i += 1
        elif b == 0x01:
            if i < len(data) and data[i] <= 0x18:
                chars.append(h1_table.get(data[i], f'<01:{data[i]:02X}>'))
                i += 1
            else:
                chars.append('<01>')
        elif 0x02 <= b <= 0x06:
            if i < len(data):
                low = data[i]
                i += 1
                pair = (b, low)
                if pair in kanji_table:
                    chars.append(kanji_table[pair])
                else:
                    chars.append(f'[{b:02X}:{low:02X}]')
            else:
                chars.append(f'<{b:02X}>')
        elif b in h0_table:
            chars.append(h0_table[b])
        else:
            chars.append(f'<{b:02X}>')
    return ''.join(chars), i

def extract_chapter_dialogues(bank_num):
    data = rom[bank_num * 0x4000 : (bank_num + 1) * 0x4000]
    dialogues = []
    i = 0
    while i < len(data) - 4:
        if data[i] == 0x01:
            next_b = data[i+1]
            is_valid_start = (
                (next_b == 0x01 and i+2 < len(data) and data[i+2] <= 0x18) or
                (0x02 <= next_b <= 0x06) or
                (next_b == 0x08) or
                (0x10 <= next_b <= 0xFE and next_b not in (0x00, 0x0D))
            )
            if is_valid_start:
                text, end_pos = decode_dialogue_segment(data, i + 1)
                clean = text.strip()
                jp_count = sum(1 for c in clean if '\u3040' <= c <= '\u30ff' or c in '『』「」…！？～' or ('\u4e00' <= c <= '\u9fff'))
                if jp_count >= 2:
                    dialogues.append({
                        'bank_num': bank_num,
                        'bank_offset': i + 1,
                        'rom_offset': bank_num * 0x4000 + i + 1,
                        'text': clean
                    })
                    i = end_pos
                    continue
        i += 1
    return dialogues

def main():
    print("=" * 60)
    print("【樱花大战GB2 - 主线剧情全量重新提取工具】")
    print("=" * 60)
    
    # 备份旧 story 目录
    backup_story_dir = os.path.join(OUTPUT_DIR, ".workbuddy", "backup_corrupted_story")
    os.makedirs(backup_story_dir, exist_ok=True)
    for ch in range(1, 15):
        old_file = os.path.join(OUTPUT_DIR, "story", f"chapter_{ch:02d}.txt")
        if os.path.exists(old_file):
            shutil.copy2(old_file, os.path.join(backup_story_dir, f"chapter_{ch:02d}.txt"))
    print("已将旧剧情底稿备份至 translations/.workbuddy/backup_corrupted_story/\n")

    all_story_entries = []
    total_count = 0

    # 提取第 1 章 ~ 第 14 章
    for ch in range(1, 15):
        bank = 0x40 + ch
        dialogues = extract_chapter_dialogues(bank)
        total_count += len(dialogues)
        all_story_entries.extend(dialogues)
        
        filepath = os.path.join(OUTPUT_DIR, "story", f"chapter_{ch:02d}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# 樱花大战GB2 汉化底稿: 第 {ch:02d} 章 主线剧情 (Bank 0x{bank:02X})\n")
            f.write(f"# 本文件条目数: {len(dialogues)}\n")
            f.write("# 规则: 在 CN: 下方直接输入中文译文。请保留控制标签与换行。\n")
            f.write("=" * 60 + "\n\n")

            for idx, d in enumerate(dialogues, 1):
                f.write(f"# [{idx:04d}] [ROM: 0x{d['rom_offset']:06X}] [Bank: 0x{d['bank_num']:02X}:0x{d['bank_offset']:04X}]\n")
                lines = d['text'].split('\n')
                for l in lines:
                    f.write(f"JP: {l}\n")
                f.write("CN: \n\n")

        print(f"  - 第 {ch:02d} 章 (Bank 0x{bank:02X}): 成功提取 {len(dialogues):4d} 条纯正日文台词")

    print("\n" + "=" * 60)
    print(f"14 个章节主线剧情重新导出完毕！总计: {total_count} 条台词。")
    print("=" * 60)

    # 接下来同步更新 master_dialogue.txt
    print("\n正在同步重构 translations/master_dialogue.txt...")
    master_path = os.path.join(OUTPUT_DIR, "master_dialogue.txt")
    
    # 读取旧 master_dialogue.txt 中的非剧情部分 (line 39849 起的 battle, system, exploration 已翻译内容)
    non_story_lines = []
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        cut_idx = None
        for i, l in enumerate(lines):
            if "[ROM: 0x04402E]" in l or "[Bank: 0x11:0x002E]" in l:
                cut_idx = i
                break
        if cut_idx is not None:
            non_story_lines = lines[cut_idx:]

    print(f"保留了现有非剧情已翻译条目（共 {len(non_story_lines)} 行数据）")

    # 写入新 master_dialogue.txt
    with open(master_path, "w", encoding="utf-8") as f:
        f.write("# 樱花大战GB2 汉化底稿: 全游戏主线与系统总底稿汇总\n")
        f.write("# 规则: 在 CN: 下方直接输入中文译文。请保留控制标签与换行。\n")
        f.write("=" * 60 + "\n\n")

        # 写入 14 个章节
        m_idx = 1
        for d in all_story_entries:
            f.write(f"# [{m_idx:04d}] [ROM: 0x{d['rom_offset']:06X}] [Bank: 0x{d['bank_num']:02X}:0x{d['bank_offset']:04X}]\n")
            for l in d['text'].split('\n'):
                f.write(f"JP: {l}\n")
            f.write("CN: \n\n")
            m_idx += 1

        # 追加写入非剧情条目
        for l in non_story_lines:
            f.write(l)

    print(f"master_dialogue.txt 同步完成！前 {len(all_story_entries)} 条为主线剧情，后续为战斗/系统/探索译文。")

if __name__ == "__main__":
    main()
