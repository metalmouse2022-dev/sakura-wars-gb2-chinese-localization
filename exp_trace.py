# -*- coding: utf-8 -*-
"""
通用运行时追踪器：对任意 ROM 跑同一串按键，记录每一帧的
    PC / ROM bank / 脚本读取地址(HL→绝对 ROM) / 0xC6C3 / 0xC9D5

用法：
    python exp_trace.py <rom路径> <标签> [按键次数]

ROM bank 判定：取 HL 指向的窗口 16 字节，到 ROM 全部 bank 的同偏移处比对，
命中即该 bank（无需 hook 84 处 ld [$2000],A，开销极低且精确）。
"""
import os
import re
import sys

# ---- 1-byte 码表（用于把 0xC6C3 里的内容粗略还原成可读文字）----
_src = open("inject_fixed2.py", encoding="utf-8").read()
_m = re.search(r"H0_CHARS\s*=\s*\[(.*?)\]", _src, re.S)
H0_CHARS = re.findall(r"'([^'])'", _m.group(1))
TBL = {0x4F + i: c for i, c in enumerate(H0_CHARS)}
TBL[0x0D] = "\n"
TBL[0x10] = " "
TBL[0x08] = "[大神]"


def decode1(bs):
    """把 1-byte script 缓冲区粗略还原（日文原版可用；汉化版汉字页显示成 H:LL）"""
    out = []
    i = 0
    while i < len(bs):
        b = bs[i]
        if b == 0x00:
            break
        if b == 0xFF:
            out.append("!"); i += 1; continue
        if 0x01 <= b <= 0x07:
            if i + 1 < len(bs):
                out.append("<%02X:%02X>" % (b, bs[i + 1])); i += 2; continue
            i += 1; continue
        if b == 0x09:
            i += 1; continue          # 引擎插入的分隔
        out.append(TBL.get(b, "{%02X}" % b))
        i += 1
    return "".join(out)


def run(rom_path, tag, presses=60, log_path=None):
    from pyboy import PyBoy
    rom = open(rom_path, "rb").read()
    pb = PyBoy(rom_path, window="null", sound=False)

    # 解码循环 hook：ROM 0x0606BB → bank 0x18, addr 0x06BB
    last_hl = [0]
    hits = [0]

    def on_dec(_ctx):
        hits[0] += 1
        last_hl[0] = pb.register_file.HL

    try:
        pb.hook_register(0x18, 0x06BB, on_dec, None)
    except Exception as e:
        print("hook 失败:", e)

    def bank_of(hl, win):
        if not (0x4000 <= hl < 0x8000):
            return None, None
        off = (hl - 0x4000)
        for b in range(len(rom) // 0x4000):
            base = b * 0x4000 + off
            if rom[base:base + len(win)] == win:
                return b, base
        return None, None

    def tick(n):
        for _ in range(n):
            pb.tick(1, render=False)

    tick(1600)                                   # 开机 + 标题画面
    pb.button_press("down"); tick(15); pb.button_release("down"); tick(30)
    pb.button_press("a");    tick(15); pb.button_release("a");    tick(120)
    # 若还有菜单层，再按一次 A
    pb.button_press("a");    tick(15); pb.button_release("a");    tick(120)

    lines = []
    seen = []
    prev = None
    for k in range(presses):
        pb.button_press("a")
        for _ in range(6):
            pb.tick(1, render=False)
        pb.button_release("a")

        best = (b"", b"", 0, 0, "", -1)
        for _ in range(44):
            pb.tick(1, render=False)
            c6 = bytes(pb.memory[0xC6C3 + i] for i in range(64)).split(b"\x00")[0]
            c9 = bytes(pb.memory[0xC9D5 + i] for i in range(64)).split(b"\x00")[0]
            if len(c6) > len(best[0]):
                hl = last_hl[0]
                win = bytes(pb.memory[hl + i] for i in range(16)) if 0x4000 <= hl < 0x8000 else b""
                bk, base = bank_of(hl, win)
                best = (c6, c9, pb.register_file.PC, hl,
                        ("%02X:%04X" % (bk, base)) if bk is not None else "?",
                        bk if bk is not None else -1)

        c6, c9, pc, hl, absrom, bk = best
        mark = ""
        if prev is not None and (c6, c9) != prev:
            mark = "  <<<"
        prev = (c6, c9)
        if c6 and (not seen or seen[-1] != c6):
            seen.append(c6)
        lines.append(
            "%02d PC=%04X bank=%-3s HL=%04X ABS=%-8s C6C3=[%s]%s\n      C9D5=[%s]\n      TXT=%s"
            % (k, pc, ("%02X" % bk) if bk >= 0 else "?", hl, absrom,
               c6.hex(" "), mark, c9.hex(" "), decode1(c6))
        )

    pb.stop()
    head = [
        "ROM   : %s" % rom_path,
        "TAG   : %s" % tag,
        "hook  : 0x18:0x06BB 命中 %d 次" % hits[0],
        "不同对话屏数: %d" % len(seen),
        "-" * 70,
    ]
    out = "\n".join(head + lines)
    if log_path:
        open(log_path, "w", encoding="utf-8").write(out + "\n")
    print("\n".join(head))
    print("hook 命中 %d 次, 不同对话屏 %d" % (hits[0], len(seen)))
    return out


if __name__ == "__main__":
    rom = sys.argv[1]
    tag = sys.argv[2]
    presses = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    run(rom, tag, presses, log_path="trace_%s.txt" % tag)
    print("saved trace_%s.txt" % tag)
