import os
import re
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')
legacy_path = r"C:\Users\p0282768\Documents\Gemini\Lineage182c"

monster_sql = os.path.join(legacy_path, "db", "lineage", "monster.sql")
fields = [
    "uid", "name", "name_id", "gfx", "level", "hp", "mp", "min_dmg", "max_dmg",
    "ac", "mr", "exp", "lawful", "size", "die", "tribal_id", "agro", "poly",
    "item_pick", "tameable", "runtype", "attack", "areaatk", "resurrection",
    "tough_skin", "undead", "drop_adena"
]

target_ids = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '18', '55'}
monsters_data = {}

with open(monster_sql, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        if line.startswith("INSERT INTO `monster`"):
            m = re.search(r"VALUES\s*\((.*)\);?", line)
            if m:
                content = m.group(1)
                tokens = [p.strip(" '\"") for p in content.split(",")]
                if len(tokens) >= len(fields):
                    d = dict(zip(fields, tokens[:len(fields)]))
                    if d["uid"] in target_ids:
                        monsters_data[d["uid"]] = d

for mid in sorted(monsters_data.keys(), key=lambda x: int(x)):
    d = monsters_data[mid]
    print(f"ID={d['uid']:3} Name={d['name']:12} Lvl={d['level']:2} HP={d['hp']:4} AC={d['ac']:3} Dmg=[{d['min_dmg']:2}-{d['max_dmg']:2}] Exp={d['exp']:5} Agro={d['agro']} Undead={d['undead']} Atk={d['attack']}")
