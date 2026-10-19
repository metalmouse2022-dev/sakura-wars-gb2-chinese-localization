# -*- coding: utf-8 -*-
"""
单条、等长、只改正文实验 + PyBoy 运行时日志

用法：
    python exp_single_entry.py build      # 生成 4 个实验 ROM
    python exp_single_entry.py run A      # 运行并输出日志

实验对象：第 1 章第 5 条
    ROM 0x104072  slot 14 字节
    原始：83 54 FF FF 0D 92 71 76 72 52 6D 9F 0D 00
      A 基线（当前汉化版）
      B 等长、只改正文（全假名，FF FF / 0D / 00 原样）
      C 恢复原始日文
      D 中文，但 ！ 仍用 FF FF，并用 0x10 空格补齐到 14 字节
"""
import os
import sys
import json
import hashlib

BASE = "Sakura Taisen GB2 - Chinese_Fixed.gbc"
SRC = "Sakura Taisen GB2 - Thunderbolt Sakusen (Japan)(Sega)(32Mb).gbc"
OFF = 0x104072
SLOT = 14

ORIG = bytes.fromhex("83 54 FF FF 0D 92 71 76 72 52 6D 9F 0D 00")
# 等长、只改正文：保留 FF FF / 0D / 00 的位置
KANA = bytes.fromhex("83 55 FF FF 0D 93 72 77 73 53 6E 90 0D 00")
assert len(ORIG) == len(KANA) == SLOT


def build():
    base = open(BASE, "rb").read()
    variants = {"A": None, "B": KANA, "C": ORIG}
    for name, data in variants.items():
        rom = bytearray(base)
        if data is not None:
            rom[OFF:OFF + SLOT] = data
        open(f"exp_{name}.gbc", "wb").write(rom)
        print("built", f"exp_{name}.gbc", data.hex(" ") if data else "(baseline)")

    # D：中文，保留 FF FF，空格补齐
    cm = json.load(open("translations/char_map_fixed2.json", encoding="utf-8"))
    char_map = {c: (v["H"], v["L"]) for c, v in cm.items()}
    body = bytearray()
    for ch in "呼":
        h, l = char_map[ch]
        body += bytes([l]) if h == 0 else bytes([h, l])
    body += b"\xff\xff\x0d"
    for ch in "終於到了":
        h, l = char_map[ch]
        body += bytes([l]) if h == 0 else bytes([h, l])
    body += b"\x0d"
    assert len(body) <= SLOT - 1, (len(body), SLOT)
    body += b"\x10" * (SLOT - 1 - len(body)) + b"\x00"
    rom = bytearray(base)
    rom[OFF:OFF + SLOT] = body
    open("exp_D.gbc", "wb").write(rom)
    print("built exp_D.gbc", body.hex(" "))


def run(name, presses=48, log_path=None):
    from pyboy import PyBoy
    rom = f"exp_{name}.gbc"
    pb = PyBoy(rom, window="null", sound=False)

    def tick(n):
        for _ in range(n):
            pb.tick(1, render=False)

    def snap():
        c6 = bytes(pb.memory[0xC6C3 + i] for i in range(48))
        c9 = bytes(pb.memory[0xC9D5 + i] for i in range(48))
        return {
            "pc": pb.register_file.PC,
            "c6": c6.split(b"\x00")[0].hex(" "),
            "c9": c9.split(b"\x00")[0].hex(" "),
        }

    tick(1600)
    pb.button_press("down"); tick(15); pb.button_release("down"); tick(30)
    pb.button_press("a"); tick(15); pb.button_release("a"); tick(120)

    lines = []
    prev = None
    for k in range(presses):
        pb.button_press("a")
        for _ in range(8): pb.tick(1, render=False)
        pb.button_release("a")
        best6 = best9 = ""
        pc_at = 0
        for _ in range(40):
            pb.tick(1, render=False)
            c6 = bytes(pb.memory[0xC6C3 + i] for i in range(48)).split(b"\x00")[0]
            c9 = bytes(pb.memory[0xC9D5 + i] for i in range(48)).split(b"\x00")[0]
            if len(c6) > len(best6):
                best6 = c6.hex(" "); pc_at = pb.register_file.PC
            if len(c9) > len(best9):
                best9 = c9.hex(" ")
        s = {"pc": pc_at, "c6": best6, "c9": best9}
        sig = (s["c9"], s["c6"])
        mark = ""
        if prev is not None and sig != prev:
            mark = "  <-- 变化"
        prev = sig
        lines.append(f"{k:02d} PC={s['pc']:04X} C9D5=[{s['c9']}] C6C3=[{s['c6']}]{mark}")

    pb.stop()
    out = "\n".join(lines)
    if log_path:
        open(log_path, "w", encoding="utf-8").write(out + "\n")
    return lines


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "run":
        name = sys.argv[2]
        log = f"exp_log_{name}.txt"
        lines = run(name, log_path=log)
        print("\n".join(lines))
        print("saved", log)
