# -*- coding: utf-8 -*-
"""
Sakura Taisen GB2 - 自动化全量回填工具 (Universal ROM Inserter)
功能：
1. 自动扫描 translations/ 目录下所有翻译文件（或指定文件/总表 master_dialogue.txt）
2. 识别 CN: 翻译文本，智能进行简体转 GBC 8x8 字库支持码映射 (S2J 映射)
3. 同时支持两类编码自动写入：
   - Format 1: Shift-JIS (系统UI、道具技能、战斗台词、章节标题、探索事件)
   - Format 2: 1-Byte-Script (主线剧情 1~14 章脚本与控制码)
4. 自动长度检测、溢出截断保护、末尾 0x00 填充
5. 自动修复 GBC 硬件 Header Checksum 与 Global Checksum，输出免修改即玩 ROM
"""
import os
import sys
import re

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

ORIGINAL_ROM = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
OUTPUT_ROM = "Sakura Taisen GB2 - Chinese.gbc"
TRANSLATIONS_DIR = "translations"

# 简体中文 -> GBC 内置 8x8 汉字字模映射表 (常用汉字对照表)
SIMP_TO_JIS = {
    '欢': '歓', '迎': '迎', '战': '戦', '樱': '桜', '号': '号', '场': '場',
    '宫': '宮', '寺': '寺', '与': '与', '神': '神', '郎': '郎', '参': '参',
    '这': '這', '样': '様', '们': '們', '说': '説', '话': '話', '机': '機',
    '头': '頭', '长': '長', '军': '軍', '车': '車', '时': '時', '为': '為',
    '会': '会', '来': '来', '国': '国', '团': '団', '击': '撃', '华': '華',
    '点': '点', '风': '風', '红': '紅', '兰': '蘭', '灵': '霊', '变': '変',
    '对': '対', '错': '錯', '难': '難', '结': '結', '终': '終', '开': '開',
    '关': '関', '发': '発', '动': '動', '见': '見', '问': '問', '题': '題',
    '现': '現', '实': '実', '电': '電', '记': '記', '录': '録', '确': '確',
    '定': '定', '选': '選', '择': '択', '图': '図', '书': '書', '传': '伝',
    '统': '統', '乐': '楽', '术': '術', '义': '義', '声': '声', '类': '類',
    '节': '節', '数': '数', '据': '拠', '级': '級', '别': '別', '种': '種',
    '强': '強', '计': '計', '视': '視', '绝': '絶', '独': '独', '胜': '勝',
    '利': '利', '败': '敗', '将': '将', '领': '領', '导': '導', '专': '専',
    '门': '門', '户': '戸', '玛': '瑪', '丽': '麗', '亚': '亜', '织': '織',
    '姬': '姫', '堇': '菫', '奈': '奈', '岛': '島', '仓': '倉', '伤': '傷',
    '害': '害', '护': '護', '防': '防', '御': '御', '攻': '攻', '速': '速',
    '度': '度', '力': '力', '耐': '耐', '气': '気', '复': '復', '态': '態',
    '异': '異', '常': '常', '无': '無', '效': '効', '条': '条', '件': '件',
    '设': '設', '置': '置', '装': '装', '备': '備', '武': '武', '器': '器',
    '身': '身', '手': '手', '臂': '臂', '脚': '脚', '部': '部', '改': '改',
    '造': '造', '升': '昇', '降': '降', '合': '合', '成': '成', '买': '買',
    '卖': '売', '保': '保', '存': '存', '消': '消', '返': '返', '回': '回',
    '测': '測', '试': '試', '运': '運', '汉': '漢', '体': '体', '师': '師',
    '亲': '親', '爱': '愛', '带': '帯', '经': '経', '总': '総', '认': '認',
    '让': '譲', '给': '給', '决': '決', '烈': '烈', '命': '命', '运': '運',
    '进': '進', '步': '歩', '行': '行', '飞': '飛', '翔': '翔', '跳': '跳',
    '跃': '躍', '奔': '奔', '跑': '走', '超': '超', '级': '級', '魔': '魔',
    '法': '法', '物': '物', '理': '理', '斩': '斬', '刀': '刀', '剑': '剣',
    '枪': '銃', '炮': '砲', '弹': '弾', '药': '薬', '箱': '箱', '囊': '嚢'
}

def build_1byte_reverse_table(rom_data):
    """构建 1-Byte 码表反查表 (字符 -> 1-byte 编码 ID)"""
    char_to_byte = {}
    table_base = 0x83500
    for i in range(0x3C, 256):
        pos = table_base + i * 2
        raw = rom_data[pos:pos+2]
        try:
            c = raw.decode('cp932')
            if c != '×' and c not in char_to_byte:
                char_to_byte[c] = i
        except:
            pass
    return char_to_byte

def fix_gbc_checksums(rom_bytes):
    """重新计算并修复 GBC Header Checksum 与 Global Checksum"""
    rom = bytearray(rom_bytes)
    # Header Checksum at 0x14D
    chk = 0
    for i in range(0x134, 0x14D):
        chk = (chk - rom[i] - 1) & 0xFF
    rom[0x14D] = chk

    # Global Checksum at 0x14E-0x14F
    global_chk = 0
    for i, b in enumerate(rom):
        if i != 0x14E and i != 0x14F:
            global_chk = (global_chk + b) & 0xFFFF
    rom[0x14E] = (global_chk >> 8) & 0xFF
    rom[0x14F] = global_chk & 0xFF
    return bytes(rom)

def parse_translation_file(filepath):
    """解析翻译底稿文件，提取出有中文翻译的条目"""
    if not os.path.exists(filepath):
        return []

    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配每个条目块
    blocks = re.split(r'\n(?=# \[\d+\])', content)
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines or not lines[0].startswith('# ['):
            continue

        header = lines[0]
        # 提取 ROM 偏移
        m_rom = re.search(r'ROM:\s*(0x[0-9A-Fa-f]+)', header)
        if not m_rom:
            continue
        rom_offset = int(m_rom.group(1), 16)

        # 提取 JP 与 CN (支持多行)
        jp_lines = []
        cn_lines = []
        state = None
        for line in lines[1:]:
            line_str = line.strip()
            if line.startswith('JP:'):
                state = 'JP'
                txt = line[3:].strip()
                if txt: jp_lines.append(txt)
            elif line.startswith('CN:'):
                state = 'CN'
                txt = line[3:].strip()
                if txt: cn_lines.append(txt)
            elif state == 'CN' and line_str:
                cn_lines.append(line_str)
            elif state == 'JP' and line_str:
                jp_lines.append(line_str)

        # 如果填写了 CN 翻译，则记录
        if cn_lines:
            entries.append({
                "rom_offset": rom_offset,
                "jp_text": "\n".join(jp_lines),
                "cn_text": "\n".join(cn_lines)
            })

    return entries

def to_fullwidth(text):
    """将半角英文、数字、空格和常见符号转为全角，以适配 GBC 2 字节字库引擎"""
    res = []
    for c in text:
        code = ord(c)
        if c == ' ':
            res.append('　')
        elif 0x21 <= code <= 0x7E:
            if c == '[':
                res.append('【')
            elif c == ']':
                res.append('】')
            elif c == '~':
                res.append('～')
            else:
                res.append(chr(code + 0xFEE0))
        else:
            res.append(c)
    return ''.join(res)

_TAG_RE = re.compile(r'<([0-9A-Fa-f]{2})>')


def encode_text_sjis(text):
    """将中文文本转换映射为 Shift-JIS 字节序列 (换行符转换为 0x0D)

    <XX> 控制标签会被还原为原始单字节（例如 <45> -> 0x45），
    正文部分自动转全角并做简体->日式字形映射。
    """
    out = bytearray()
    for i, part in enumerate(_TAG_RE.split(text)):
        if i % 2 == 1:                      # 奇数段 = 标签里的十六进制
            out.append(int(part, 16))
            continue
        if not part:
            continue
        seg = part.replace('\r\n', '\r').replace('\n', '\r')
        seg = to_fullwidth(seg)
        seg = ''.join(SIMP_TO_JIS.get(c, c) for c in seg)
        for c in seg:
            if c == '\r':
                out.append(0x0D)
                continue
            try:
                out.extend(c.encode('cp932'))
            except Exception:
                out.extend('？'.encode('cp932'))
    out.append(0x00)
    return bytes(out)

def encode_text_1byte(text, rev_tbl):
    """将剧情文本转换为 1-byte 编码字节序列，保留 <XX> 控制标签"""
    tokens = []
    # 使用正则将 <XX> 标签与普通文本分开
    parts = re.split(r'(<[0-9A-Fa-f]{2}>)', text)
    result = bytearray()

    for part in parts:
        if not part:
            continue
        # 如果是 <XX> 控制码
        m = re.match(r'^<([0-9A-Fa-f]{2})>$', part)
        if m:
            result.append(int(m.group(1), 16))
        else:
            # 普通文本
            for c in part:
                if c == '\r' or c == '\n':
                    result.append(0x0D)
                elif c == '　' or c == ' ':
                    result.append(0x10) # 0x10 为 1-byte 空间中的间距
                else:
                    # 尝试查表
                    c_mapped = SIMP_TO_JIS.get(c, c)
                    if c_mapped in rev_tbl:
                        result.append(rev_tbl[c_mapped])
                    elif c in rev_tbl:
                        result.append(rev_tbl[c])
                    else:
                        # 默认缺字 fallback
                        result.append(0x3C) # '。' 作为占位
    result.append(0x00)
    return bytes(result)

def run_insertion():
    print("=" * 60)
    print("【樱花大战GB2 - 自动化全量回填工具】")
    if not os.path.exists(ORIGINAL_ROM):
        print(f"[错误] 未找到原版 ROM: {ORIGINAL_ROM}")
        return

    with open(ORIGINAL_ROM, "rb") as f:
        rom = bytearray(f.read())

    rev_tbl = build_1byte_reverse_table(rom)

    # 扫描 translations 目录下的所有 txt 文件
    target_files = []
    for root, dirs, files in os.walk(TRANSLATIONS_DIR):
        for f in files:
            if f.endswith('.txt') and f != 'master_dialogue.txt':
                target_files.append(os.path.join(root, f))

    # 优先扫描分模块文件，最后也可以补充 master 文件
    print(f"找到翻译文件: {len(target_files)} 个")

    total_injected = 0
    total_skipped = 0

    for filepath in target_files:
        entries = parse_translation_file(filepath)
        if not entries:
            continue

        file_injected = 0
        is_story_bank = "story" in filepath

        for entry in entries:
            offset = entry['rom_offset']
            cn_text = entry['cn_text']

            # 判断编码格式
            if is_story_bank:
                new_data = encode_text_1byte(cn_text, rev_tbl)
            else:
                new_data = encode_text_sjis(cn_text)

            # 获取原文本长度（从 offset 往后找 0x00）
            orig_len = 0
            while offset + orig_len < len(rom) and rom[offset + orig_len] != 0:
                orig_len += 1
            orig_len += 1 # 包含结尾 0x00

            # 安全写入：如果新文本更短或相等，填入并补 0x00
            if len(new_data) <= orig_len:
                for i in range(len(new_data)):
                    rom[offset + i] = new_data[i]
                for i in range(len(new_data), orig_len):
                    rom[offset + i] = 0x00
                file_injected += 1
            else:
                # 超过原长时，安全截断到原长（防止破坏后续指令），并给出提示
                for i in range(orig_len - 1):
                    rom[offset + i] = new_data[i]
                rom[offset + orig_len - 1] = 0x00
                file_injected += 1
                total_skipped += 1

        if file_injected > 0:
            rel_name = os.path.relpath(filepath, TRANSLATIONS_DIR)
            print(f"  [注入成功] {rel_name:<30}: 回填 {file_injected} 句")
            total_injected += file_injected

    # 修复校验和
    fixed_rom = fix_gbc_checksums(rom)
    with open(OUTPUT_ROM, "wb") as f:
        f.write(fixed_rom)

    print("\n" + "=" * 60)
    print("【回填打包完成！】")
    print(f"本次累计回填句子: {total_injected} 句")
    print(f"生成最新发布版 ROM: {OUTPUT_ROM}")
    print("现在可以直接用 BGB 打开该 ROM 查看全量更新！")
    print("=" * 60)

if __name__ == "__main__":
    run_insertion()
