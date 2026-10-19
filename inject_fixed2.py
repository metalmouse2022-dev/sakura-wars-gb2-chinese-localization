# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 修正版全量汉化注入器 v2 (inject_fixed2.py)

在 inject_fixed.py 基础上重做字库分配：

问题：旧版把最常用的 176 个汉字塞进 H=0 的 0x4F..0xFE，
      这块正是游戏原有的假名/标点字模。起名界面「なまえ / せいべつ」
      用的是 1-byte 文本 + 这套 8x8 字模，于是全变成乱码。

修正：
1. H=0 整页（ASCII/假名/标点）原样保留，不写入任何新字模；
   文本里出现的假名与标点直接映射回原有槽位。
2. 新汉字只写入 H=1 0x19..0xFF、H=2..7 全页，共 1,767 格。
   剧情全文需要 1,769 格，余下 2 字借用页 1 的 ♪ ♥ 两个符号槽
   （剧情文本从不使用这两个符号）。
3. 其余逻辑（多行读取、菜单横幅、署名、校验和）沿用 v1。
"""
import os
import re
import sys
import json
import zhconv
from collections import Counter
from PIL import Image, ImageFont, ImageDraw

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SOURCE_ROM = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
FINAL_ROM = os.environ.get("OUT_ROM", "Sakura Taisen GB2 - Chinese_Fixed.gbc")
FONT_PATH = "C:/Windows/Fonts/simsun.ttc"

STORY_FILES = [f"translations/story/chapter_{i:02d}.txt" for i in range(1, 15)]
NON_STORY_FILES = []  # 8x8 非剧情文本全部移交 inject_dungeon.py 注入（支持小点阵 8x8 动态简体重定向字库，彻底消除？乱码与溢出）


DROP_TAGS = set()
TAG_RE = re.compile(r'<([0-9A-Fa-f]{2})>')
NAME_RE = re.compile(r'\[大神\]')
PAIR_RE = re.compile(r'\[([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\]')

# 游戏原有 1-byte 单字节字表（H=0，0x4F 起）。
# 起名界面「なまえ／せいべつ／おとこ／おんな／はい／いいえ」全部是平假名，
# 因此必须保留：平假名 + 标点。片假名与英文字母的槽位让给常用汉字（1 字节编码）。
H0_CHARS = [
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
H0_MAP = {c: (0, 0x4F + i) for i, c in enumerate(H0_CHARS)}

# 保留给日文 UI 的单字节字（平假名 + 标点），不得占用
KEEP_H0 = set(H0_CHARS[0:79]) | {'、', '。', 'を', 'ん', '？', '！', 'ー', '～', '「', '」'}

# Preserve Japanese title-menu glyphs in the H0 katakana area. The previous
# pool accidentally reused these IDs for Chinese glyphs, corrupting “プロローグ”.
PRESERVE_MENU_H0 = {'プ', 'ロ', 'グ'}
PRESERVE_H0_SLOTS = {H0_MAP[c] for c in KEEP_H0 | PRESERVE_MENU_H0}
# Only unused H=0 codes are available as a compact fallback. Chapter heading
# glyphs stay in the full-height story pages.
ONE_BYTE_POOL = [s for s in [(0, 0x9D + i) for i in range(0xF7 - 0x9D)]
                 if s not in PRESERVE_H0_SLOTS]
FORCE_STORY_16 = set('第一章光武登上三笠')
UI_ONE_BYTE_CHARS = '姓名性别请选择主角这样可以吗是否男女'
FORCE_H0 = set('见屁次逃跑波奇网球画漫草拉金饭歌滚士斯') | set(UI_ONE_BYTE_CHARS)



# ---------------------------------------------------------------- 读取底稿
def read_blocks(path, is_story=False):
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
        if is_story:
            full_cn = zhconv.convert(full_cn, 'zh-hans')
            full_cn = full_cn.replace('康娜', '神奈')
        out.append((off, full_cn))
    return out


# ---------------------------------------------------------------- 字库
def build_char_map(texts):
    counter = Counter()
    for s in texts:
        s = NAME_RE.sub('', s)
        s = TAG_RE.sub('', s)
        s = PAIR_RE.sub('', s)
        for c in s:
            if c not in '\r\n':
                counter[c] += 1

    char_map = {' ': (0, 0x10)}
    for i in range(10):
        char_map[str(i)] = (0, 0x11 + i)

    # Only reserve original kana/punctuation slots that actually occur in the
    # story corpus. Preloading every Japanese glyph wastes scarce 16x16 slots
    # when the CN translation contains mostly Chinese characters.
    for c, slot in H0_MAP.items():
        if c in KEEP_H0 and c in counter:
            char_map[c] = slot

    pool = list(ONE_BYTE_POOL)
    for c in sorted(FORCE_H0):
        if c in counter and c not in char_map and pool:
            char_map[c] = pool.pop(0)

    # 剩余字符按频率分配：先占 1 字节槽（字母/片假名），再占 2 字节页
    rest = [c for c, _ in counter.most_common() if c not in char_map]

    for c in rest:
        if c in FORCE_STORY_16:
            continue
        if not pool:
            break
        char_map[c] = pool.pop(0)
    rest = [c for c in rest if c not in char_map]
    for c, slot in zip(rest, pool):
        char_map[c] = slot
    rest = rest[len(pool):]

    slots = [(1, l) for l in range(0x19, 0x100)]
    slots += [(h, l) for h in range(2, 8) for l in range(1, 0x100)]  # L=0 会产生 0x00，必须避开
    for c, slot in zip(rest, slots):
        char_map[c] = slot

    overflow = rest[len(slots):]

    return char_map, overflow, len(counter)


_ARK_FONT = None
_SIMSUN_FONT = None


def is_ark_missing(char):
    global _ARK_FONT
    im = Image.new('L', (12, 12), 0)
    d = ImageDraw.Draw(im)
    d.text((0, 0), char, fill=255, font=_ARK_FONT)
    # Ark's tofu .notdef box has all 4 corners lit
    return (im.getpixel((0, 0)) > 64 and im.getpixel((11, 0)) > 64 and 
            im.getpixel((0, 11)) > 64 and im.getpixel((11, 11)) > 64)


def render_tile(char, font=None, thresh=100):
    global _ARK_FONT, _SIMSUN_FONT
    if _ARK_FONT is None:
        _ARK_FONT = ImageFont.truetype('fonts/ark-12px/ark-pixel-12px-monospaced-zh_hans.ttf', 12)
        _SIMSUN_FONT = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 12)

    box = Image.new('L', (8, 16), 0)
    if char == '一':
        for y in (7, 8):
            for x in range(1, 7):
                box.putpixel((x, y), 255)
    elif char == '…':
        for y in (7, 8):
            for x in (1, 3, 5):
                box.putpixel((x, y), 255)
    else:
        use_font = _SIMSUN_FONT if is_ark_missing(char) else _ARK_FONT
        im = Image.new('L', (12, 12), 0)
        d = ImageDraw.Draw(im)
        d.text((0, 0), char, fill=255, font=use_font)
        c11 = im.crop((0, 0, 11, 12))
        res = c11.resize((7, 12), Image.BILINEAR)
        box.paste(res, (0, 2))

    b = bytearray(16)
    for y in range(16):
        bits = 0
        for x in range(8):
            if box.getpixel((x, y)) > thresh:
                bits |= (1 << (7 - x))
        b[y] = bits
    return bytes(b)


# ---------------------------------------------------------------- 剧情编码
def encode_story(text, char_map):
    out = bytearray()
    toks = re.split(r'(\[大神\]|<[0-9A-Fa-f:]+>|\[[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\]|\n)', text)
    for tok in toks:
        if not tok:
            continue
        if tok == '[大神]':
            out.append(0x08)
        elif tok == '\n':
            out.append(0x0D)
        elif TAG_RE.fullmatch(tok):
            if tok in DROP_TAGS:
                continue
            out.append(int(tok[1:3], 16))
        elif tok.startswith('<01:') and tok.endswith('>'):
            out.extend([0x01, int(tok[4:-1], 16)])
        elif PAIR_RE.fullmatch(tok):
            h, l = tok[1:-1].split(':')
            out.extend([int(h, 16), int(l, 16)])
        else:
            for c in tok:
                if c in char_map:
                    h, l = char_map[c]
                    if h == 0:
                        out.append(l)
                    else:
                        out.extend([h, l])
                else:
                    out.append(0x10)
    out.append(0x00)
    return bytes(out)


def story_slot(rom, off, limit=4000):
    i = off
    while i < len(rom) and i - off < limit:
        b = rom[i]
        if b == 0x00:
            return i - off + 1
        if b <= 0x07 or b == 0x0A:
            i += 2
        else:
            i += 1
    raise ValueError('string not terminated at 0x%06X' % off)


def combine_prefix_and_body(prefix, body):
    if not prefix:
        return body
    if body.startswith(prefix):
        return body
    for k in range(len(prefix), 0, -1):
        if body.startswith(prefix[-k:]):
            return prefix[:-k] + body
    return prefix + body


def encode_story_with_context(text, char_map, prefix=b'', suffix=b''):
    enc = encode_story(text, char_map)
    body = enc[:-1]
    # Story slots can start with interpreter commands (e.g. 01 01, 1E 0B...,
    # which select speaker or perform transitions).
    # Keep these commands intact, merging any matching prefix from text.
    body = combine_prefix_and_body(prefix, body)
    # 0D flushes the final dialogue line before the slot terminator. Preserve
    # the source's trailing line break while keeping any padding before it.
    if suffix and not body.endswith(suffix):
        body += suffix
    return body + b'\x00'


def fit_story(text, slot_len, char_map, prefix=b'', suffix=b''):
    enc = encode_story_with_context(text, char_map, prefix, suffix)
    if len(enc) <= slot_len:
        return text, enc, 0
    lines = [l for l in text.split('\n')]
    for p in ['。', '！', '？', '…', '～', '、', '，', ',', '.']:
        for i in range(len(lines)):
            if lines[i].endswith(p):
                lines[i] = lines[i][:-1]
                t = '\n'.join(lines)
                e = encode_story_with_context(t, char_map, prefix, suffix)
                if len(e) <= slot_len:
                    return t, e, 0
    guard = 0
    while guard < 400:
        guard += 1
        t = '\n'.join(lines)
        e = encode_story_with_context(t, char_map, prefix, suffix)
        if len(e) <= slot_len:
            return t, e, 0
        idx = max(range(len(lines)), key=lambda i: len(lines[i])) if lines else 0
        if not lines or len(lines[idx]) <= 1:
            break
        lines[idx] = lines[idx][:-1]
    t = '\n'.join(lines)
    fitted_enc = encode_story_with_context(t, char_map, prefix, suffix)
    return t, fitted_enc, len(fitted_enc) - slot_len


# ---------------------------------------------------------------- 非剧情编码
def encode_sjis(text):
    out = bytearray()
    toks = re.split(r'(<[0-9A-Fa-f]{2}>|\n|\r)', text)
    for tok in toks:
        if not tok:
            continue
        if tok in ('\n', '\r'):
            out.append(0x0D)
            continue
        m = TAG_RE.fullmatch(tok)
        if m:
            out.append(int(m.group(1), 16))
            continue
        for c in tok:
            try:
                out.extend(c.encode('cp932'))
            except UnicodeEncodeError:
                out.extend('？'.encode('cp932'))
    return bytes(out)


def patch_name_ui(rom, char_map):
    # These prompts are a separate one-byte kana table, outside the extracted
    # Shift-JIS dialogue files. Use dedicated one-byte Chinese glyphs and keep
    # each original field width/control boundary intact.
    fields = [
        (0x0C468B, 15, '请选择主角性别。'),
        (0x0C469F, 3, '男'),
        (0x0C46A5, 3, '女'),
        (0x0C46AE, 14, '这样可以吗？'),
        (0x0C46C1, 3, '是'),
        (0x0C46C7, 3, '否'),
        (0x0C46D0, 3, '姓名'),
        (0x0C46DF, 4, '性别'),
    ]
    for off, width, text in fields:
        codes = bytearray()
        for ch in text:
            if ch == ' ':
                codes.append(0x10)
            elif ch == '？':
                codes.append(0xF9)  # 原生 Bank 0x06 精修问号
            elif ch == '。':
                codes.append(0x9F)  # 原生句号
            elif ch in char_map:
                h, l = char_map[ch]
                if h != 0:
                    raise ValueError(f'name UI character {ch} is not mapped to one byte: (H={h}, L={hex(l)})')
                codes.append(l)
            else:
                raise ValueError(f'name UI character is not in char_map: {ch}')
        if len(codes) > width:
            raise ValueError('name UI field overflow at 0x%06X' % off)
        rom[off:off + width] = codes + b'\x10' * (width - len(codes))

    if '男' in char_map and '女' in char_map:
        rom[0x0C46EE:0x0C46EE + 4] = bytes([char_map['男'][1], 0x00, 0x00, 0x00])
        rom[0x0C46F2:0x0C46F2 + 4] = bytes([char_map['女'][1], 0x00, 0x00, 0x00])


def render_ark12_string_2bpp_tiles(text, total_w, total_h, x_offset=0, y_offset=2):
    font = ImageFont.truetype('fonts/ark-12px/ark-pixel-12px-monospaced-zh_hans.ttf', 12)
    im = Image.new('L', (total_w, total_h), 255)
    d = ImageDraw.Draw(im)
    d.text((x_offset, y_offset), text, fill=0, font=font)
    
    num_tiles = total_w // 8
    tiles_list = []
    for t in range(num_tiles):
        top = bytearray(16)
        bot = bytearray(16)
        tx = t * 8
        for y in range(8):
            m = 0
            for x in range(8):
                if im.getpixel((tx + x, y)) < 128:
                    m |= (1 << (7 - x))
            top[y * 2] = m
            top[y * 2 + 1] = m
        for y in range(8):
            m = 0
            for x in range(8):
                if im.getpixel((tx + x, 8 + y)) < 128:
                    m |= (1 << (7 - x))
            bot[y * 2] = m
            bot[y * 2 + 1] = m
        tiles_list.append((bytes(top), bytes(bot)))
    return tiles_list


def patch_name_screen_tiles(rom):
    # 1. 键盘瓦片映射 (Bank 0x3A:0x55AD)
    d_map, comp_len_map = decompress(rom, 0x3A, 0x55AD)
    new_map = bytearray(d_map)

    # 行 15: 按钮上半部分
    # Col 2, 3, 4: 汉字 (3瓦片: 0x88, 0x8A, 0xB6)
    new_map[15 * 32 + 2] = 0x88
    new_map[15 * 32 + 3] = 0x8A
    new_map[15 * 32 + 4] = 0xB6
    new_map[15 * 32 + 5] = 0x81

    # Col 6, 7: ABC (2瓦片: 0x90, 0x92)
    new_map[15 * 32 + 6] = 0x90
    new_map[15 * 32 + 7] = 0x92
    new_map[15 * 32 + 8] = 0x81
    new_map[15 * 32 + 9] = 0x81

    # Col 10, 11, 12: 删除 (3瓦片: 0x8C, 0x8E, 0x94)
    new_map[15 * 32 + 10] = 0x8C
    new_map[15 * 32 + 11] = 0x8E
    new_map[15 * 32 + 12] = 0x94
    new_map[15 * 32 + 13] = 0x81
    new_map[15 * 32 + 14] = 0x81

    # Col 15, 16, 17, 18: 决定 (4瓦片: 0x96, 0x98, 0x9A, 0x9C)
    new_map[15 * 32 + 15] = 0x96
    new_map[15 * 32 + 16] = 0x98
    new_map[15 * 32 + 17] = 0x9A
    new_map[15 * 32 + 18] = 0x9C

    # 行 16: 按钮下半部分
    new_map[16 * 32 + 2] = 0x89
    new_map[16 * 32 + 3] = 0x8B
    new_map[16 * 32 + 4] = 0xB7
    new_map[16 * 32 + 5] = 0x81

    new_map[16 * 32 + 6] = 0x91
    new_map[16 * 32 + 7] = 0x93
    new_map[16 * 32 + 8] = 0x81
    new_map[16 * 32 + 9] = 0x81

    new_map[16 * 32 + 10] = 0x8D
    new_map[16 * 32 + 11] = 0x8F
    new_map[16 * 32 + 12] = 0x95
    new_map[16 * 32 + 13] = 0x81
    new_map[16 * 32 + 14] = 0x81

    new_map[16 * 32 + 15] = 0x97
    new_map[16 * 32 + 16] = 0x99
    new_map[16 * 32 + 17] = 0x9B
    new_map[16 * 32 + 18] = 0x9D

    # 行 18..21: 输入法模式切换备份行 (更新为汉字 0x88, 0x8A, 0xB6，防止切页时冲掉)
    new_map[18 * 32 + 0] = 0x88
    new_map[18 * 32 + 1] = 0x8A
    new_map[18 * 32 + 2] = 0xB6
    new_map[18 * 32 + 3] = 0x81

    new_map[19 * 32 + 0] = 0x89
    new_map[19 * 32 + 1] = 0x8B
    new_map[19 * 32 + 2] = 0xB7
    new_map[19 * 32 + 3] = 0x81

    new_map[20 * 32 + 0] = 0x88
    new_map[20 * 32 + 1] = 0x8A
    new_map[20 * 32 + 2] = 0xB6
    new_map[20 * 32 + 3] = 0x81

    new_map[21 * 32 + 0] = 0x89
    new_map[21 * 32 + 1] = 0x8B
    new_map[21 * 32 + 2] = 0xB7
    new_map[21 * 32 + 3] = 0x81

    comp_map = compress(new_map)
    assert len(comp_map) <= comp_len_map, f'Map overflow: {len(comp_map)} > {comp_len_map}'
    b_map = 0x3A * 0x4000 + (0x55AD - 0x4000)
    rom[b_map : b_map + len(comp_map)] = comp_map
    rom[b_map + len(comp_map) : b_map + comp_len_map] = b'\x00' * (comp_len_map - len(comp_map))

    # 2. 写入 Ark12 图块数据 (Bank 0x39:0x4EB7 -> 重定向至空闲 Bank 0x0E:0x4000)
    d_tiles, comp_len_tiles = decompress(rom, 0x39, 0x4EB7)
    new_tiles = bytearray(d_tiles)

    def put_tile(tile_id, top_data, bot_data):
        off = (tile_id - 0x80) * 16
        new_tiles[off : off + 16] = top_data
        new_tiles[off + 16 : off + 32] = bot_data

    # 顶栏「姓名」(Ark12 跨 3 瓦片 24px)
    tiles_xm = render_ark12_string_2bpp_tiles('姓名', 24, 16, x_offset=0, y_offset=2)
    put_tile(0xB0, tiles_xm[0][0], tiles_xm[0][1])
    put_tile(0xB2, tiles_xm[1][0], tiles_xm[1][1])
    put_tile(0xB4, tiles_xm[2][0], tiles_xm[2][1])

    # 底栏「汉字」(Ark12 跨 3 瓦片 24px)
    tiles_hz = render_ark12_string_2bpp_tiles('汉字', 24, 16, x_offset=0, y_offset=2)
    put_tile(0x88, tiles_hz[0][0], tiles_hz[0][1])
    put_tile(0x8A, tiles_hz[1][0], tiles_hz[1][1])
    put_tile(0xB6, tiles_hz[2][0], tiles_hz[2][1])

    # 底栏「删除」(Ark12 跨 3 瓦片 24px)
    tiles_sc = render_ark12_string_2bpp_tiles('删除', 24, 16, x_offset=0, y_offset=2)
    put_tile(0x8C, tiles_sc[0][0], tiles_sc[0][1])
    put_tile(0x8E, tiles_sc[1][0], tiles_sc[1][1])
    put_tile(0x94, tiles_sc[2][0], tiles_sc[2][1])

    # 底栏「决定」(Ark12 居中跨 4 瓦片 32px)
    tiles_jd = render_ark12_string_2bpp_tiles('决定', 32, 16, x_offset=4, y_offset=2)
    put_tile(0x96, tiles_jd[0][0], tiles_jd[0][1])
    put_tile(0x98, tiles_jd[1][0], tiles_jd[1][1])
    put_tile(0x9A, tiles_jd[2][0], tiles_jd[2][1])
    put_tile(0x9C, tiles_jd[3][0], tiles_jd[3][1])

    comp_tiles = compress(new_tiles)
    
    # 写入至完全空闲的 Bank 0x0E:0x4000
    RELOC_BANK = 0x0E
    RELOC_ADDR = 0x4000
    reloc_rom_off = RELOC_BANK * 0x4000 + (RELOC_ADDR - 0x4000)
    rom[reloc_rom_off : reloc_rom_off + len(comp_tiles)] = comp_tiles

    # 修补 Bank 31:0x42AB..0x42B4 的解压调用指针
    call_off = 0x31 * 0x4000 + (0x42AB - 0x4000)
    assert rom[call_off + 2] in (0x39, RELOC_BANK)
    rom[call_off + 2] = RELOC_BANK
    rom[call_off + 7] = RELOC_ADDR & 0xFF
    rom[call_off + 8] = (RELOC_ADDR >> 8) & 0xFF

    print('[*] 起名界面顶栏（姓名）与底栏按钮（汉字/ABC/删除/决定）采用完整 Ark12 写入 Bank 0x0E:0x4000 (%d 字节)' % len(comp_tiles))


def encode_choice_text(text, char_map):
    res = bytearray()
    for ch in text:
        if ch == ' ':
            res.append(0x10)
        elif ch in char_map:
            h, l = char_map[ch]
            if h == 0:
                res.append(l)
            else:
                res.extend([h, l])
        else:
            res.append(0x10)
    return res


def pad_choice_text(text, max_len, char_map):
    raw = encode_choice_text(text, char_map)
    assert len(raw) <= max_len - 1, f'{text} overflow: {len(raw)} > {max_len - 1}'
    return raw + b'\x10' * (max_len - 1 - len(raw)) + b'\x00'


def patch_all_choices(rom, char_map):
    with open('translations/all_choices_data.json', 'r', encoding='utf-8') as f:
        all_choices = json.load(f)
    print('[*] 正在安全注入全篇 166 处限时选项 (Bank 0x41 ~ 0x4D)...')
    for c_idx, (c_off, opts) in enumerate(all_choices, 1):
        assert rom[c_off] == 0x0A and rom[c_off+1] == 0x16, f'Choice {c_idx} header error at 0x{c_off:06X}'
        timer = rom[c_off+2]
        n_opt = rom[c_off+3]
        assert n_opt == len(opts), f'Choice {c_idx} opt count mismatch: {n_opt} != {len(opts)}'
        cur = c_off + 4
        for o_idx, (text, slot, prep) in enumerate(opts):
            end = rom.find(b'\x00', cur)
            orig_slot = end - cur + 1
            assert orig_slot == slot, f'Choice {c_idx} Opt {o_idx} slot mismatch: orig {orig_slot} != def {slot}'
            assert rom[cur + slot] == o_idx, f'Choice {c_idx} Opt {o_idx} ID mismatch: {rom[cur+slot]} != {o_idx}'
            pad = pad_choice_text(text, slot, char_map) if not prep else (
                b'\x10' + pad_choice_text(text, slot - 1, char_map)
            )
            assert len(pad) == slot, f'Choice {c_idx} Opt {o_idx} len mismatch: {len(pad)} != {slot}'
            rom[cur:cur + slot] = pad
            cur += slot + 1
    print('[*] 全剧 166 处限时选项全部安全注入完成（100% 保持分支跳转表与选项ID）')


def truncate_sjis(raw, limit):
    if len(raw) <= limit:
        return raw
    cut = limit
    i = 0
    while i < cut:
        b = raw[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            if i + 1 < cut:
                i += 2
            else:
                cut -= 1
                break
        else:
            i += 1
    return raw[:cut]


# ---------------------------------------------------------------- 菜单图块
def decompress(data, bank, addr):
    pos = bank * 0x4000 + (addr - 0x4000) if bank > 0 else addr
    start = pos
    n = data[pos] | (data[pos + 1] << 8)
    pos += 2
    out = bytearray()
    prev = 0
    for _ in range(n):
        cmd = data[pos]; pos += 1
        if (cmd & 0x80) == 0:
            for _ in range(cmd + 1):
                prev ^= data[pos]; out.append(prev); pos += 1
        else:
            cnt = cmd - 0x7E
            arg = data[pos]; pos += 1
            for _ in range(cnt):
                prev ^= arg
                out.append(prev)
    return bytes(out), pos - start


def compress(data):
    out = bytearray([0, 0])
    packets = 0
    pos = 0
    prev = 0
    while pos < len(data):
        best_run = 0
        if pos + 1 < len(data):
            a = data[pos]
            b = data[pos + 1]
            if prev == b:
                run = 0
                while pos + run < len(data) and run < 128:
                    expected = a if (run % 2 == 0) else b
                    if data[pos + run] != expected:
                        break
                    run += 1
                if run >= 2:
                    best_run = run
        if best_run >= 2:
            cmd = 0x7E + best_run
            arg = data[pos] ^ prev
            out.append(cmd)
            out.append(arg)
            for _ in range(best_run):
                prev ^= arg
            pos += best_run
            packets += 1
            continue
        lit = []
        while pos < len(data) and len(lit) < 128:
            if len(lit) > 0 and pos + 2 < len(data):
                if data[pos] == data[pos + 1] and prev == data[pos]:
                    break
                if data[pos + 1] == data[pos - 1] and data[pos] == data[pos + 2]:
                    break
            b = data[pos]
            lit.append(b ^ prev)
            prev = b
            pos += 1
        cmd = len(lit) - 1
        out.append(cmd)
        out.extend(lit)
        packets += 1
    out[0] = packets & 0xFF
    out[1] = (packets >> 8) & 0xFF
    return bytes(out)


def patch_menu_banners(rom):
    decomp_orig, comp_len = decompress(rom, 0x39, 0x44FB)
    new_decomp = bytearray(decomp_orig)
    sp_blank = bytearray(decomp_orig[0x22 * 16 : 0x24 * 16])

    font_path = 'fonts/xiaodianzhen/xiaodianzhen-8px.ttf'
    font8 = ImageFont.truetype(font_path, 8)

    def make_sprite(ch):
        sp = bytearray(sp_blank)
        if not ch:
            return bytes(sp)
        im = Image.new('1', (8, 8), 0)
        d = ImageDraw.Draw(im)
        d.text((0, 0), ch, fill=1, font=font8)
        for y in range(8):
            sy = 4 + y
            off = sy * 2 if sy < 8 else 16 + (sy - 8) * 2
            for x in range(8):
                if im.getpixel((x, y)):
                    # 文字前景色：颜色 2 (b1=0, b2=1)
                    sp[off] &= ~(1 << (7 - x))
                    sp[off + 1] |= (1 << (7 - x))
        return bytes(sp)

    # 1. 序章 (Sprite 06, 08, 0A, 0C)
    new_decomp[0x06 * 16 : 0x08 * 16] = sp_blank
    new_decomp[0x08 * 16 : 0x0A * 16] = make_sprite('序')
    new_decomp[0x0A * 16 : 0x0C * 16] = make_sprite('章')
    new_decomp[0x0C * 16 : 0x0E * 16] = sp_blank

    # 2. 新游戏 (Sprite 0E, 10, 12, 14, 16)
    new_decomp[0x0E * 16 : 0x10 * 16] = sp_blank
    new_decomp[0x10 * 16 : 0x12 * 16] = make_sprite('新')
    new_decomp[0x12 * 16 : 0x14 * 16] = make_sprite('游')
    new_decomp[0x14 * 16 : 0x16 * 16] = make_sprite('戏')
    new_decomp[0x16 * 16 : 0x18 * 16] = sp_blank

    # 3. 继续游戏 (Sprite 18, 1A, 1C, 1E, 20)
    new_decomp[0x18 * 16 : 0x1A * 16] = make_sprite('继')
    new_decomp[0x1A * 16 : 0x1C * 16] = make_sprite('续')
    new_decomp[0x1C * 16 : 0x1E * 16] = make_sprite('游')
    new_decomp[0x1E * 16 : 0x20 * 16] = make_sprite('戏')
    new_decomp[0x20 * 16 : 0x22 * 16] = sp_blank

    comp = compress(new_decomp)
    assert len(comp) <= comp_len, f'Banner stream overflow: {len(comp)} > {comp_len}'
    b_base = 0x39 * 0x4000 + (0x44FB - 0x4000)
    rom[b_base : b_base + len(comp)] = comp
    rom[b_base + len(comp) : b_base + comp_len] = b'\x00' * (comp_len - len(comp))

    # Metasprite 调整：解绑 Sprite 0 对 Tile 0x08 的复用，实现「序」「章」居中对齐
    rom[0x0D0BB4] = 0x0A
    rom[0x0D0BC0] = 0x0C
    print('[*] 标题菜单横幅（序章/新游戏/继续游戏）小点阵高清化写入 Bank 0x39:0x44FB (%d/%d 字节)' % (len(comp), comp_len))


def patch_status_and_strategy_ui(rom):
    """
    汉化状态界面与策略界面：
    1. 横幅标题（未压缩 2bpp 瓦片）：
       - ROM 0x318600：状态横幅「状态」
       - ROM 0x318900：策略横幅「策略」
    2. 属性与选项瓦片（Bank 0x36:0x6084 压缩图块）：
       - すばやさ -> 敏捷
       - こうげき -> 攻击
       - ぼうぎょ -> 防御
       - たいきゅう -> 耐久
       - きりょく -> 气力
       - みぎて -> 右手
       - ひだりて -> 左手
       - ボディ -> 机体
       - レベル -> 等级
       - ふつうのじょうたい -> 普通状态
    """
    print('[*] 正在汉化状态界面与策略界面 (横幅与属性图块)...')
    ark_font_path = 'fonts/ark-12px/ark-pixel-12px-monospaced-zh_hans.ttf'
    if not os.path.exists(ark_font_path):
        ark_font_path = FONT_PATH
    font12 = ImageFont.truetype(ark_font_path, 12)

    def patch_banner_text(off, text, num_tiles, x_offset):
        w = num_tiles * 8
        h = 16
        im = Image.new('1', (w, h), 0)
        d = ImageDraw.Draw(im)
        d.text((x_offset, 2), text, fill=1, font=font12)

        for c in range(num_tiles):
            t_top = 1 + c
            t_bot = 17 + c
            top_bytes = bytearray(rom[off + t_top * 16 : off + (t_top + 1) * 16])
            bot_bytes = bytearray(rom[off + t_bot * 16 : off + (t_bot + 1) * 16])
            for y in range(5, 8):
                top_bytes[y * 2] = 0
                top_bytes[y * 2 + 1] = 0
                for x in range(8):
                    if im.getpixel((c * 8 + x, y)):
                        top_bytes[y * 2] |= (1 << (7 - x))
                        top_bytes[y * 2 + 1] |= (1 << (7 - x))
            for y in range(0, 7):
                bot_bytes[y * 2] = 0
                bot_bytes[y * 2 + 1] = 0
                for x in range(8):
                    if im.getpixel((c * 8 + x, 8 + y)):
                        bot_bytes[y * 2] |= (1 << (7 - x))
                        bot_bytes[y * 2 + 1] |= (1 << (7 - x))
            rom[off + t_top * 16 : off + (t_top + 1) * 16] = top_bytes
            rom[off + t_bot * 16 : off + (t_bot + 1) * 16] = bot_bytes

    # 状态横幅: 5 个文字瓦片 (40px), 居中 x_offset=8
    patch_banner_text(0x318600, '状态', 5, 8)
    # 清理状态横幅右边框瓦片 (Tile 6 与 Tile 22) 左侧 4 列原日文字模残余
    for y in range(5, 8):
        for x in range(4):
            rom[0x318600 + 6 * 16 + y * 2] &= ~(1 << (7 - x))
            rom[0x318600 + 6 * 16 + y * 2 + 1] &= ~(1 << (7 - x))
    for y in range(0, 7):
        for x in range(4):
            rom[0x318600 + 22 * 16 + y * 2] &= ~(1 << (7 - x))
            rom[0x318600 + 22 * 16 + y * 2 + 1] &= ~(1 << (7 - x))

    # 策略横幅: 4 个文字瓦片 (32px), 居中 x_offset=4
    patch_banner_text(0x318900, '策略', 4, 4)

    # 背包横幅: 8 个文字瓦片 (64px), 居中 x_offset=20
    patch_banner_text(0x318300, '背包', 8, 20)
    # 清理背包横幅右边框瓦片 (Tile 9 与 Tile 25) 左侧 7 列原日文字模残余
    for y in range(5, 8):
        for x in range(7):
            rom[0x318300 + 9 * 16 + y * 2] &= ~(1 << (7 - x))
            rom[0x318300 + 9 * 16 + y * 2 + 1] &= ~(1 << (7 - x))
    for y in range(0, 7):
        for x in range(7):
            rom[0x318300 + 25 * 16 + y * 2] &= ~(1 << (7 - x))
            rom[0x318300 + 25 * 16 + y * 2 + 1] &= ~(1 << (7 - x))

    # 胶囊装备槽标签「左」「右」汉化
    def patch_capsule_5tiles(off, start_tile, text):
        im = Image.new('1', (40, 16), 0)
        d = ImageDraw.Draw(im)
        d.text((14, 2), text, fill=1, font=font12)
        for c in range(5):
            t_top = start_tile + c
            t_bot = start_tile + 16 + c
            top_bytes = bytearray(rom[off + t_top * 16 : off + (t_top + 1) * 16])
            bot_bytes = bytearray(rom[off + t_bot * 16 : off + (t_bot + 1) * 16])
            x_range = range(3, 8) if c == 0 else (range(0, 6) if c == 4 else range(8))
            for y in range(5, 8):
                for x in x_range:
                    top_bytes[y * 2] &= ~(1 << (7 - x))
                    top_bytes[y * 2 + 1] &= ~(1 << (7 - x))
                    if im.getpixel((c * 8 + x, y)):
                        top_bytes[y * 2] |= (1 << (7 - x))
                        top_bytes[y * 2 + 1] |= (1 << (7 - x))
            for y in range(0, 7):
                for x in x_range:
                    bot_bytes[y * 2] &= ~(1 << (7 - x))
                    bot_bytes[y * 2 + 1] &= ~(1 << (7 - x))
                    if im.getpixel((c * 8 + x, 8 + y)):
                        bot_bytes[y * 2] |= (1 << (7 - x))
                        bot_bytes[y * 2 + 1] |= (1 << (7 - x))
            rom[off + t_top * 16 : off + (t_top + 1) * 16] = top_bytes
            rom[off + t_bot * 16 : off + (t_bot + 1) * 16] = bot_bytes

    def patch_capsule_right(off, start_tile, text):
        im = Image.new('1', (40, 16), 0)
        d = ImageDraw.Draw(im)
        d.text((14, 2), text, fill=1, font=font12)
        for c in range(5):
            t_top = start_tile + c
            t_bot = start_tile + 16 + c
            top_bytes = bytearray(rom[off + t_top * 16 : off + (t_top + 1) * 16])
            bot_bytes = bytearray(rom[off + t_bot * 16 : off + (t_bot + 1) * 16])
            x_range = range(3, 8) if c == 0 else (range(0, 6) if c == 4 else range(8))
            for y in range(3, 8):
                for x in x_range:
                    top_bytes[y * 2] &= ~(1 << (7 - x))
                    top_bytes[y * 2 + 1] &= ~(1 << (7 - x))
                    if im.getpixel((c * 8 + x, y)):
                        top_bytes[y * 2] |= (1 << (7 - x))
                        top_bytes[y * 2 + 1] |= (1 << (7 - x))
            for y in range(0, 3):
                for x in x_range:
                    bot_bytes[y * 2] &= ~(1 << (7 - x))
                    bot_bytes[y * 2 + 1] &= ~(1 << (7 - x))
                    if im.getpixel((c * 8 + x, 8 + y)):
                        bot_bytes[y * 2] |= (1 << (7 - x))
                        bot_bytes[y * 2 + 1] |= (1 << (7 - x))
            rom[off + t_top * 16 : off + (t_top + 1) * 16] = top_bytes
            rom[off + t_bot * 16 : off + (t_bot + 1) * 16] = bot_bytes

    patch_capsule_5tiles(0x318300, 11, '左')
    patch_capsule_right(0x317100, 8, '右')
    patch_capsule_right(0x317A00, 8, '右')
    for b_off in [0x317700, 0x316E00, 0x317400]:
        patch_capsule_5tiles(b_off, 11, '左')

    # 2. 属性与选项瓦片 (Bank 0x36:0x6084)
    decomp_orig, comp_len = decompress(rom, 0x36, 0x6084)
    new_decomp = bytearray(decomp_orig)

    font8_path = 'fonts/xiaodianzhen/xiaodianzhen-8px.ttf'
    font8 = ImageFont.truetype(font8_path, 8)

    def render_8x8_1bpp(ch):
        if not ch or ch == ' ':
            return bytes(16)
        img = Image.new('1', (8, 8), 0)
        d = ImageDraw.Draw(img)
        d.text((0, 0), ch, font=font8, fill=1)
        res = bytearray()
        for y in range(8):
            b = 0
            for x in range(8):
                if img.getpixel((x, y)):
                    b |= (1 << (7 - x))
            res.append(b)
            res.append(b)  # 2bpp, plane 0 == plane 1
        return bytes(res)

    tile_replacements = {
        # 敏捷
        13: '敏', 14: '捷', 5: ' ', 6: ' ', 7: ' ',
        # 攻击
        16: '攻', 17: '击', 18: ' ', 19: ' ',
        # 防御
        20: '防', 21: '御', 22: ' ', 23: ' ',
        # 耐久
        27: '耐', 28: '久', 29: ' ', 30: ' ', 31: ' ',
        # 气力
        9: '气', 10: '力', 11: ' ', 12: ' ',
        # 右手
        35: '右', 36: '手', 37: ' ',
        # 左手
        38: '左', 39: '手', 40: ' ',
        # 机体
        43: '机', 44: '体', 45: ' ',
        # 等级
        46: '等', 47: '级', 63: ' ',
        # 普通状态 (Tile 54..62)
        54: ' ', 55: ' ', 56: '普', 57: '通', 58: '状', 59: '态', 60: ' ', 61: ' ', 62: ' '
    }

    for t_idx, ch in tile_replacements.items():
        new_decomp[t_idx * 16 : (t_idx + 1) * 16] = render_8x8_1bpp(ch)

    comp = compress(new_decomp)
    assert len(comp) <= comp_len, f'UI tiles stream overflow: {len(comp)} > {comp_len}'
    b_base = 0x36 * 0x4000 + (0x6084 - 0x4000)
    rom[b_base : b_base + len(comp)] = comp
    rom[b_base + len(comp) : b_base + comp_len] = b'\x00' * (comp_len - len(comp))

    print('[*] 状态与策略界面（横幅「状态/策略」与各项属性/装备/状态标签）汉化完成 (%d/%d 字节)' % (len(comp), comp_len))



# ---------------------------------------------------------------- 主流程
def main():
    with open(SOURCE_ROM, 'rb') as f:
        rom = bytearray(f.read())
    print('[*] 载入原版 ROM: %d 字节' % len(rom))

    story_entries = []
    for f in STORY_FILES:
        if os.path.exists(f):
            story_entries.extend(read_blocks(f, is_story=True))
    non_story_entries = []
    for f in NON_STORY_FILES:
        if os.path.exists(f):
            non_story_entries.extend(read_blocks(f, is_story=False))
    # 扫描识别 Bank 0x41 ~ 0x4D 全部 166 处限时选项 Choice 范围，禁止主剧情循环写入这些选项槽破坏跳转表
    choice_spans = []
    p = 0x104000
    while p < 0x138000 - 4:
        if rom[p] == 0x0A and rom[p+1] == 0x16:
            timer = rom[p+2]
            n_opt = rom[p+3]
            cur = p + 4
            valid = True
            for i in range(n_opt):
                end = rom.find(b'\x00', cur)
                if end == -1 or end > cur + 50:
                    valid = False; break
                cur = end + 1
                if cur < 0x138000 and rom[cur] == i:
                    cur += 1
            if valid and 1 <= n_opt <= 5:
                choice_spans.append((p, cur))
                p = cur
                continue
        p += 1
    print('[*] 识别受保护限时选项 Choice 区域: %d 处' % len(choice_spans))

    # 过滤掉落在 Choice 范围内的条目
    filtered_story = []
    choice_conflict_count = 0
    for off, text in story_entries:
        if any(s <= off < e for s, e in choice_spans):
            choice_conflict_count += 1
            continue
        filtered_story.append((off, text))
    if choice_conflict_count > 0:
        print('[*] 成功从主剧情循环隔离 %d 条限时选项条目（防止覆盖分支跳转表）' % choice_conflict_count)

    all_text = [t for _, t in filtered_story]
    # 将全篇 166 处限时选项专用文本加入字库统计
    with open('translations/all_choices_data.json', 'r', encoding='utf-8') as f:
        all_choices_data = json.load(f)
    for _, opts in all_choices_data:
        for t, _, _ in opts:
            all_text.append(t)
    # 将起名与性别界面所需的单字节中文字符加入字库统计与映射
    all_text.extend(list(UI_ONE_BYTE_CHARS))
    char_map, overflow, unique = build_char_map(all_text)
    print('[*] 全文去重字符 %d，映射 %d，溢出 %d' % (unique, len(char_map), len(overflow)))
    for ch in UI_ONE_BYTE_CHARS:
        assert ch in char_map and char_map[ch][0] == 0, f'{ch} is not in H=0! ({char_map.get(ch)})'
    if overflow:
        print('[!] 未分配字符:', ''.join(overflow))
    with open('translations/char_map_fixed2.json', 'w', encoding='utf-8') as f:
        json.dump({c: {'H': h, 'L': l} for c, (h, l) in char_map.items()}, f, ensure_ascii=False, indent=2)

    font = ImageFont.truetype(FONT_PATH, 8)
    pool = set(ONE_BYTE_POOL)
    story_slots = [(1, l) for l in range(0x19, 0x100)]
    story_slots += [(h, l) for h in range(2, 8) for l in range(1, 0x100)]
    tiles = 0
    for c, (h, l) in char_map.items():
        if h == 0 and (h, l) not in pool and c != '…':
            continue                      # 平假名/标点/数字：保留原字模
        bank = 0x06 + (h >> 2)
        off = bank * 0x4000 + (((h & 3) << 8 | l) * 16)
        rom[off:off + 16] = render_tile(c, font)
        tiles += 1
    print('[*] 写入字模 %d 个（平假名/标点原样保留）' % tiles)

    # 名字/性别选择界面弹窗与标签汉化注入
    patch_name_ui(rom, char_map)
    patch_name_screen_tiles(rom)
    print('[*] 名字/性别界面弹窗与键盘图块（姓名/汉字/ABC/删除/决定）汉化完成')

    truncated = []
    SKIP_STORY = os.environ.get('SKIP_STORY') == '1'
    FONT_ONLY = os.environ.get('FONT_ONLY') == '1'
    for off, text in ([] if (SKIP_STORY or FONT_ONLY) else filtered_story):
        if not text.strip():
            continue
        slot = story_slot(rom, off)
        source_slot = rom[off:off + slot]
        prefix_end = 0
        while prefix_end < slot - 1 and source_slot[prefix_end] != 0:
            b = source_slot[prefix_end]
            if (0x4F <= b <= 0xFE) or b == 0x08:
                break
            prefix_end += 1
        prefix = source_slot[:prefix_end]
        suffix_start = slot - 2
        while suffix_start >= prefix_end and source_slot[suffix_start] == 0x0D:
            suffix_start -= 1
        suffix = source_slot[suffix_start + 1:slot - 1]
        fitted, enc, over = fit_story(text, slot, char_map, prefix, suffix)
        if over > 0 or fitted != text:
            truncated.append((off, slot, len(enc), text, fitted))
        if len(enc) > slot:
            enc = enc[:slot - 1] + b'\x00'
        # Keep the terminator at the original offset. Place padding before any
        # trailing 0D line-break control so the next script command stays aligned.
        body = enc[:-1]
        if suffix and body.endswith(suffix):
            body = body[:-len(suffix)] + b'\x10' * (slot - len(enc)) + suffix
        else:
            body += b'\x10' * (slot - len(enc))
        body += b'\x00'
        assert len(body) == slot
        rom[off:off + slot] = body
    print('[*] 剧情注入完成，其中 %d 条因槽位不足被压缩' % len(truncated))
    with open('translations/story_truncated_fixed2.txt', 'w', encoding='utf-8') as f:
        for off, slot, ln, orig, fit in truncated:
            f.write('0x%06X slot=%d used=%d\n  原: %s\n  改: %s\n\n' %
                    (off, slot, ln, orig.replace('\n', '/'), fit.replace('\n', '/')))

    ns_count = 0
    for off, text in non_story_entries:
        if not text.strip():
            continue
        n = 0
        while rom[off + n] != 0:
            n += 1
        slot = n + 1
        raw = encode_sjis(text)
        raw = truncate_sjis(raw, slot - 1)
        rom[off:off + len(raw)] = raw
        rom[off + len(raw)] = 0x00
        if len(raw) + 1 < slot:
            rom[off + len(raw) + 1:off + slot] = b'\x00' * (slot - len(raw) - 1)
        ns_count += 1
    print('[*] 非剧情注入 %d 条' % ns_count)

    # 标题画面开始菜单横幅（Bank 0x39:0x44FB，含序章、新游戏、继续游戏及对齐补丁）
    patch_menu_banners(rom)

    # 状态与策略界面汉化（横幅「状态/策略」与各项属性/装备/状态标签）
    patch_status_and_strategy_ui(rom)


    # 空存档提示
    empty = '暫無資料'.encode('cp932') + b'\x00'
    assert len(empty) <= 10
    rom[0x307A24:0x307A24 + len(empty)] = empty
    rom[0x307A24 + len(empty):0x307A2E] = b'\x00' * (10 - len(empty))

    # 序章署名
    sig = bytes([0x45]) + 'ｍｅｔａｌｍｏｕｓｅ\r漢化'.encode('cp932') + b'\x00'
    rom[0x0CC3E9:0x0CC3E9 + len(sig)] = sig
    rom[0x0CC3E9 + len(sig):0x0CC3E9 + 54] = b'\x00' * (54 - len(sig))

    # 全篇 166 处限时选项定长安全汉化注入（保持分支跳转表与选项ID）
    patch_all_choices(rom, char_map)

    # 第一章标题：暂不写入。
    # 该标题卡用的是 16x16 字库（H=8..15，512 字固定集合），
    # 汉字若不在集合内会画出碎片乱码（实机图 5）。等扩 16x16 字库后再译。
    # title = '～第一章～\r『光武、立於三笠！』'.encode('cp932') + b'\x00'
    # rom[0x307AFE:0x307AFE + len(title)] = title

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

    with open(FINAL_ROM, 'wb') as f:
        f.write(rom)
    print('[★] 生成: %s  header=0x%02X global=0x%04X' % (FINAL_ROM, chk, g))

    out_copy = 'outputs/Sakura Taisen GB2 - Chinese_Fixed.gbc'
    if os.path.abspath(FINAL_ROM) != os.path.abspath(out_copy):
        with open(out_copy, 'wb') as f:
            f.write(rom)
        print('[★] 同步副本: %s' % out_copy)


if __name__ == '__main__':
    main()
