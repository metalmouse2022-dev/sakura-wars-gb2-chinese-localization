# -*- coding: utf-8 -*-
"""
Sync translated story chapters into master_dialogue.txt
"""
import re
import os

def sync_master():
    story_trans = {}
    for ch in range(1, 15):
        fn = f"translations/story/chapter_{ch:02d}.txt"
        if not os.path.exists(fn):
            continue
        with open(fn, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = content.split("# [")
        for b in blocks[1:]:
            lines = b.splitlines()
            header = lines[0]
            m = re.search(r"\[ROM:\s*(0x[0-9A-Fa-f]+)\]", header)
            if not m:
                continue
            rom_addr = m.group(1).upper()
            cns = []
            found_cn = False
            for l in lines:
                if l.startswith("CN:"):
                    found_cn = True
                    val = l[3:].strip()
                    if val:
                        cns.append(val)
                elif found_cn and not l.startswith("JP: ") and not l.startswith("#") and not l.startswith("="):
                    if l.strip():
                        cns.append(l.strip())
            if cns:
                story_trans[rom_addr] = cns

    print(f"Loaded {len(story_trans)} translated dialogue entries from story chapters.")

    master_path = "translations/master_dialogue.txt"
    with open(master_path, "r", encoding="utf-8") as f:
        master_lines = f.readlines()

    output_lines = []
    i = 0
    cur_rom_addr = None
    synced_count = 0

    while i < len(master_lines):
        line = master_lines[i]
        output_lines.append(line)

        if line.startswith("# ["):
            m = re.search(r"\[ROM:\s*(0x[0-9A-Fa-f]+)\]", line)
            if m:
                cur_rom_addr = m.group(1).upper()
            else:
                cur_rom_addr = None
        elif line.startswith("CN:") and cur_rom_addr in story_trans:
            cns = story_trans[cur_rom_addr]
            output_lines.pop() # remove current CN:
            output_lines.append(f"CN: {cns[0]}\n")
            for sub in cns[1:]:
                output_lines.append(f"{sub}\n")
            synced_count += 1
            # Skip any existing subsequent CN lines until blank line or next entry
            while i + 1 < len(master_lines) and not master_lines[i+1].startswith("# [") and not master_lines[i+1].startswith("JP: ") and not master_lines[i+1].startswith("CN:") and master_lines[i+1].strip() != "" and not master_lines[i+1].startswith("="):
                i += 1
            cur_rom_addr = None
        i += 1

    with open(master_path, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

    print(f"Synced {synced_count} entries into master_dialogue.txt successfully.")

if __name__ == "__main__":
    sync_master()
