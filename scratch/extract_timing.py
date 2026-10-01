import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
legacy_root = r'C:\Users\p0282768\Documents\Gemini\Lineage182c\db\lineage'

mid_to_data = {}
with open(os.path.join(legacy_root, 'monster.sql'), 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # INSERT INTO `monster` VALUES ('1', '漂浮之眼', '$4', '53', ...
        m = re.search(r"VALUES\s*\(\s*'(\d+)',\s*'([^']*)',\s*'([^']*)',\s*'(\d+)'", line)
        if m:
            mid_to_data[int(m.group(1))] = (m.group(2), int(m.group(4)))

spr_timing = {}
with open(os.path.join(legacy_root, 'sprite_frame.sql'), 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # INSERT INTO `sprite_frame` VALUES ('王子', '0', '0', 'walk', '640');
        m = re.search(r"VALUES\s*\(\s*'([^']*)',\s*'(\d+)',\s*'(\d+)',\s*'([^']*)',\s*'(\d+)'\)", line)
        if m:
            gfx = int(m.group(2))
            act = int(m.group(3))
            act_name = m.group(4)
            ftime = int(m.group(5))
            if gfx not in spr_timing:
                spr_timing[gfx] = {}
            spr_timing[gfx][act] = (act_name, ftime)

# Male Knight (gfx 61)
print("=== PLAYER (Male Knight GFX 61) ===")
for act, (aname, ms) in spr_timing.get(61, {}).items():
    print(f"  Action {act} ({aname}): {ms}ms")

target_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 18, 55]
print("\n=== MONSTERS TIMING ===")
for tid in target_ids:
    name, gfx = mid_to_data.get(tid, ('Unknown', 0))
    tinfo = spr_timing.get(gfx, {})
    w_info = tinfo.get(0, ('walk', 800))
    a_info = tinfo.get(1, ('attack', 1200))
    print(f"ID {tid:2d}: {name:<12} (GFX {gfx:<4}) -> walk={w_info[1]:4d}ms, attack={a_info[1]:4d}ms")
