# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 地下城与出击文本注入与 8x8 字体补丁器 (Dungeon Injector & 8x8 Font Patcher)
功能:
1. 批量将 xiaodianzhen-8px (小点阵 8px) 注入到 ROM Bank 08~0B (6,902 个汉字字模)
2. 建立简体独占字 (如 达、这、样、么、们、让、话、说 等) 到未用字槽位的重定向表
3. 读取 translations/dungeon/ 下的已翻译文本并注入到对应 Bank (支持原位覆盖与自由扩展)
"""
import os
import sys
import re
import zhconv
from PIL import Image, ImageFont, ImageDraw

ROM_IN = "outputs/Sakura Taisen GB2 - Chinese_Fixed.gbc"
if not os.path.exists(ROM_IN):
    ROM_IN = "Sakura Taisen GB2 - Chinese_Fixed.gbc"
ROM_OUT = "outputs/Sakura Taisen GB2 - Chinese_Fixed.gbc"
SOURCE_ROM = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
FONT_PATH = "fonts/xiaodianzhen/xiaodianzhen-8px.ttf"

NON_STORY_FILES = [
    'translations/battle/skills_and_items.txt',
    'translations/battle/mecha_units.txt',
    'translations/battle/battle_dialogues.txt',
    'translations/system/chapter_titles.txt',
    'translations/system/item_events.txt',
    'translations/system/system_events_1b.txt',
    'translations/system/system_events_1c.txt',
    'translations/exploration/exploration_events.txt',
]


def render_8x8_glyph(ch, font):
    img = Image.new('1', (8, 8), 0)
    d = ImageDraw.Draw(img)
    d.text((0, 0), ch, font=font, fill=1)
    if not any(img.get_flattened_data()):
        return None
    res = bytearray()
    for y in range(8):
        b = 0
        for x in range(8):
            if img.getpixel((x, y)):
                b |= (1 << (7 - x))
        res.append(b)
    return bytes(res)

def get_shift_jis_glyph_map(rom):
    """
    解析 Bank 0B 中的 0x5990 和 0x5B10 表，
    构建 (lead, trail) -> rom_offset 字典
    """
    b0B = rom[0x0B * 0x4000 : 0x0C * 0x4000]
    mapping = {}

    for lead in range(0x81, 0x100):
        if 0xA0 <= lead <= 0xDF:
            continue
        row = lead & 0x7F
        off_5990 = 0x5990 - 0x4000 + row * 3
        if off_5990 + 2 >= len(b0B):
            continue
        count = b0B[off_5990]
        if count == 0:
            continue
        ptr = (b0B[off_5990 + 2] << 8) | b0B[off_5990 + 1]
        trail_list_cpu = 0x5990 + ptr
        trail_list_off = trail_list_cpu - 0x4000

        for i in range(count):
            trail = b0B[trail_list_off + i]
            trail_addr = trail_list_cpu + i
            glyph_idx = trail_addr - 0x5B10
            rom_pos = 0x020000 + glyph_idx * 8
            mapping[(lead, trail)] = (glyph_idx, rom_pos)

    return mapping

def patch_8x8_font(rom, font, sjis_map):
    """
    将 xiaodianzhen-8px 批量写入 Bank 08~0B
    """
    print("[1/3] 正在将 xiaodianzhen-8px 批量写入 Bank 08~0B...")
    replaced = 0
    kept = 0

    for (lead, trail), (glyph_idx, rom_pos) in sjis_map.items():
        if rom_pos + 8 > len(rom):
            continue
        try:
            ch = bytes([lead, trail]).decode('cp932')
            glyph = render_8x8_glyph(ch, font)
            if glyph:
                rom[rom_pos : rom_pos + 8] = glyph
                replaced += 1
            else:
                kept += 1
        except:
            kept += 1

    print(f"  - 8x8 字库替换完成: {replaced} 个汉字更新为小点阵，{kept} 个特殊符号保留原版系统字模")

def collect_used_cp932_codes(translations_dir="translations"):
    """
    扫描 translations 目录下所有翻译文件，收集所有实际使用到的 Shift-JIS 双字节码，
    确保重定向池绝对不会覆盖任何已被翻译使用的汉字字模。
    """
    used = set()
    if not os.path.exists(translations_dir):
        return used
    for root, dirs, files in os.walk(translations_dir):
        for f in files:
            if f.endswith(".txt") or f.endswith(".json"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fp:
                        content = fp.read()
                    for ch in content:
                        try:
                            b = ch.encode("cp932")
                            if len(b) == 2:
                                used.add((b[0], b[1]))
                        except:
                            pass
                except Exception:
                    pass
    return used

def build_simplified_char_mapper(rom, font, sjis_map):
    """
    建立简体独占字 (Shift-JIS 原生不存在的汉字) 到罕用字槽位的重定向表
    使用 Lead 0x98 (罕用汉字区) 进行重定向，同时过滤掉所有底稿已使用的 Shift-JIS 汉字。
    """
    used_sjis = collect_used_cp932_codes()
    print(f"  - 收集到底稿已使用的 Shift-JIS 双字节字符: {len(used_sjis)} 个")

    pool = []
    for (lead, trail), (glyph_idx, rom_pos) in sjis_map.items():
        if (lead, trail) in used_sjis:
            continue
        if 0x98 <= lead <= 0x9F and trail >= 0x40:
            pool.append((lead, trail, rom_pos))

    print(f"  - 简体重定向扩展池安全可用容量: {len(pool)} 个槽位")
    return pool

def parse_dungeon_txt(fpath):
    """
    解析 translations/dungeon/dungeon_bank_XX.txt 中的有效翻译
    """
    if not os.path.exists(fpath):
        return []

    entries = []
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.split("# [")
    for b in blocks[1:]:
        lines = b.strip().split("\n")
        header = lines[0]
        # 解析 [0329] [ROM: 0x1822E9] [Bank: 0x60:0x22E9] [CPU: 0x62E9] [OrigLen: 30]
        m = re.search(r"ROM:\s*(0x[0-9A-Fa-f]+).*?Bank:\s*(0x[0-9A-Fa-f]+):(0x[0-9A-Fa-f]+).*?CPU:\s*(0x[0-9A-Fa-f]+).*?OrigLen:\s*(\d+)", header)
        if not m:
            continue
        rom_off = int(m.group(1), 16)
        bank_num = int(m.group(2), 16)
        bank_off = int(m.group(3), 16)
        cpu_addr = int(m.group(4), 16)
        orig_len = int(m.group(5))

        cn_lines = []
        is_cn = False
        for l in lines[1:]:
            if l.startswith("CN:"):
                is_cn = True
                val = l[3:].strip()
                if val:
                    cn_lines.append(val)
            elif is_cn and l.startswith("JP:"):
                is_cn = False
            elif is_cn:
                cn_lines.append(l.strip())

        cn_text = "\n".join(cn_lines).strip()
        if cn_text:
            entries.append({
                "rom_offset": rom_off,
                "bank": bank_num,
                "bank_offset": bank_off,
                "cpu_addr": cpu_addr,
                "orig_len": orig_len,
                "cn_text": cn_text
            })

    return entries

def to_fullwidth(ch):
    code = ord(ch)
    if 0x21 <= code <= 0x7E:
        return chr(code + 0xFEE0)
    elif code == 0x20:
        return '　'
    elif ch == '·':
        return '・'
    return ch

def truncate_8x8(raw, limit):
    if len(raw) <= limit:
        return raw
    max_body = limit - 1
    i = 0
    valid_len = 0
    while i < len(raw) - 1:
        b = raw[i]
        step = 2 if ((0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC)) else 1
        if i + step > max_body:
            break
        i += step
        valid_len = i
    return raw[:valid_len] + b'\x00'

def read_blocks(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    out = []
    for b in re.split(r'\n(?=# \[\d+\])', content):
        if not b.startswith('# ['):
            continue
        m = re.search(r'ROM:\s*(0x[0-9A-Fa-f]+)', b.split('\n')[0])
        if not m:
            continue
        off = int(m.group(1), 16)
        lines = b.split('\n')
        cn = []
        in_cn = False
        for l in lines[1:]:
            if l.startswith('CN:'):
                in_cn = True
                cn.append(l[3:].lstrip(' '))
            elif in_cn:
                if l.startswith(('JP:', '#', '=')):
                    break
                cn.append(l)
        full_cn = '\n'.join(cn).strip('\r\n')
        full_cn = zhconv.convert(full_cn, 'zh-hans')
        full_cn = full_cn.replace('康娜', '神奈')
        out.append((off, full_cn))
    return out

def encode_dungeon_string(text, get_char_fn):
    """
    将中文翻译字符串编码为地下城/系统引擎可识别的字节序列:
    - 换行符: 0x0D (支持空行垂直对齐)
    - <NAME>: 0x08
    - 标签: <XX> (16进制单字节控制符)
    - 汉字/符号: get_char_fn 动态映射 (8x8 小点阵字库)
    - 半角英数转全角双字节，避免与单字节假名冲突
    - 结尾: 0x00
    """
    norm = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = norm.split('\n')
    res = bytearray()
    for idx, l in enumerate(lines):
        if idx > 0:
            res.append(0x0D)  # 换行符
        i = 0
        while i < len(l):
            if l[i:i+6] == "<NAME>":
                res.append(0x08)
                i += 6
            elif l[i] == '<' and i + 3 < len(l) and l[i+3] == '>':
                try:
                    b_val = int(l[i+1:i+3], 16)
                    res.append(b_val)
                    i += 4
                    continue
                except ValueError:
                    pass
                ch = to_fullwidth(l[i])
                lead, trail = get_char_fn(ch)
                res.extend([lead, trail])
                i += 1
            elif l[i] == '…':
                res.extend([0x81, 0x63])
                i += 1
            elif l[i] == '·':
                res.extend([0x81, 0x45])
                i += 1
            else:
                ch = to_fullwidth(l[i])
                lead, trail = get_char_fn(ch)
                res.extend([lead, trail])
                i += 1

    res.append(0x00)  # 结束符
    return bytes(res)

def main():
    print("=" * 60)
    print("【樱花大战GB2 - 地下城文本注入与 8x8 字体管线】")
    if not os.path.exists(ROM_IN):
        print(f"错误: 找不到输入 ROM: {ROM_IN}")
        return

    with open(ROM_IN, "rb") as f:
        rom = bytearray(f.read())

    font = ImageFont.truetype(FONT_PATH, 8)
    sjis_map = get_shift_jis_glyph_map(rom)

    # 1. 批量将 xiaodianzhen-8px 写入 Bank 08~0B
    patch_8x8_font(rom, font, sjis_map)

    # 2. 建立简体独占字重定向池
    pool = build_simplified_char_mapper(rom, font, sjis_map)
    custom_map = {}
    pool_idx = 0

    def get_or_create_custom_char(ch):
        nonlocal pool_idx
        if ch in custom_map:
            return custom_map[ch]
        # 尝试标准 cp932
        try:
            b = ch.encode('cp932')
            if len(b) == 2:
                return (b[0], b[1])
        except:
            pass
        # 需要重定向到 pool
        if pool_idx >= len(pool):
            raise RuntimeError("重定向池已耗尽！")
        lead, trail, rom_pos = pool[pool_idx]
        pool_idx += 1
        # 将 ch 的 8x8 字模写入 rom_pos
        glyph = render_8x8_glyph(ch, font)
        if glyph:
            rom[rom_pos : rom_pos + 8] = glyph
        custom_map[ch] = (lead, trail)
        return (lead, trail)

    # 3. 扫描 translations/dungeon/ 下全部文本
    dungeon_dir = "translations/dungeon"
    txt_files = [f for f in os.listdir(dungeon_dir) if f.startswith("dungeon_bank_") and f.endswith(".txt")]
    txt_files.sort()

    total_injected = 0
    print(f"\n[2/3] 正在扫描并注入地下城翻译文本 (共 {len(txt_files)} 个文件)...")

    for fname in txt_files:
        fpath = os.path.join(dungeon_dir, fname)
        entries = parse_dungeon_txt(fpath)
        if not entries:
            continue

        injected_in_file = 0
        for e in entries:
            encoded = encode_dungeon_string(e["cn_text"], get_or_create_custom_char)
            # 原位覆盖判断
            if len(encoded) <= e["orig_len"]:
                pad = e["orig_len"] - len(encoded)
                final_bytes = encoded + b"\x00" * pad
                rom[e["rom_offset"] : e["rom_offset"] + e["orig_len"]] = final_bytes
                injected_in_file += 1
            else:
                # 若略微超出，尝试截断结尾冗余或发出提示
                print(f"  警告: [{fname}] ROM 0x{e['rom_offset']:06X} 译文长度 {len(encoded)} 超出原槽位 {e['orig_len']}，跳过")

        if injected_in_file > 0:
            print(f"  - [{fname}]: 成功注入 {injected_in_file} 条台词")
            total_injected += injected_in_file

    # 3.2 注入非剧情系统文本 (8 个文件，包含战斗、系统与大地图探索)
    print(f"\n[2.5/3] 正在扫描并注入非剧情系统文本 (8 个文件)...")
    with open(SOURCE_ROM, "rb") as f:
        clean_rom = f.read()

    total_non_story = 0
    for fpath in NON_STORY_FILES:
        entries = read_blocks(fpath)
        if not entries:
            continue
        injected_in_file = 0
        for off, text in entries:
            if not text.strip():
                continue
            n = 0
            while clean_rom[off + n] != 0:
                n += 1
            slot = n + 1

            encoded = encode_dungeon_string(text, get_or_create_custom_char)
            if len(encoded) > slot:
                text_stripped = text.rstrip(' 　\t')
                encoded_stripped = encode_dungeon_string(text_stripped, get_or_create_custom_char)
                if len(encoded_stripped) <= slot:
                    encoded = encoded_stripped
                else:
                    encoded = truncate_8x8(encoded_stripped, slot)

            rom[off : off + len(encoded)] = encoded
            if len(encoded) < slot:
                rom[off + len(encoded) : off + slot] = b'\x00' * (slot - len(encoded))
            injected_in_file += 1

        print(f"  - [{os.path.basename(fpath)}]: 成功注入 {injected_in_file} 条")
        total_non_story += injected_in_file

    # 3.5 注入策略界面底部说明文 (ROM 0x301DF2, 槽位长度 71 字节)
    strat_help_text = "配合搭档与装备的武器\n随时切换不同策略。"
    strat_encoded = encode_dungeon_string(strat_help_text, get_or_create_custom_char)
    if len(strat_encoded) <= 71:
        rom[0x301DF2 : 0x301DF2 + len(strat_encoded)] = strat_encoded
        rom[0x301DF2 + len(strat_encoded) : 0x301DF2 + 71] = b"\x00" * (71 - len(strat_encoded))
        print("  - [UI] 成功注入策略界面底部说明文 (ROM 0x301DF2)")
    else:
        print(f"  警告: 策略界面底部说明文超出长度限制 ({len(strat_encoded)} > 71)")

    print(f"\n[3/3] 动态映射了 {len(custom_map)} 个简体独占汉字到扩展槽位")

    # 4. 修复 Header Checksum 与 Global Checksum
    chk = 0
    for i in range(0x134, 0x14D):
        chk = (chk - rom[i] - 1) & 0xFF
    rom[0x14D] = chk
    g = 0
    for i, b in enumerate(rom):
        if i not in (0x14E, 0x14F):
            g = (g + b) & 0xFFFF
    rom[0x14E] = (g >> 8) & 0xFF
    rom[0x14F] = g & 0xFF

    os.makedirs(os.path.dirname(ROM_OUT), exist_ok=True)
    with open(ROM_OUT, "wb") as f:
        f.write(rom)

    root_rom = "Sakura Taisen GB2 - Chinese_Fixed.gbc"
    if os.path.abspath(ROM_OUT) != os.path.abspath(root_rom):
        with open(root_rom, "wb") as f:
            f.write(rom)
        print(f"  - 同步副本: {root_rom}")

    print("=" * 60)
    print(f"【地下城与系统文本 8x8 注入完成！】")
    print(f"累计注入地下城台词: {total_injected} 条")
    print(f"累计注入非剧情台词: {total_non_story} 条")
    print(f"产物保存至: {ROM_OUT}")

if __name__ == "__main__":
    main()
