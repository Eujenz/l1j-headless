import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
legacy_path = r"C:\Users\p0282768\Documents\Gemini\Lineage182c"
drop_sql = os.path.join(legacy_path, "db", "lineage", "monster_item_drop.sql")
items_sql = os.path.join(legacy_path, "db", "lineage", "items.sql")

items_dict = {}
with open(items_sql, 'r', encoding='utf-8-sig', errors='replace') as f:
    for line in f:
        if line.startswith("INSERT INTO `items`"):
            m = re.search(r"VALUES\s*\((.*)\);?", line)
            if m:
                tokens = [t.strip(" '\"") for t in m.group(1).split(",")]
                items_dict[tokens[0]] = tokens[1]

target_mids = {'1','2','3','4','5','6','7','8','9','10','11','12','13','14','18','55'}
print("TI Monsters Drops:")
with open(drop_sql, 'r', encoding='utf-8-sig', errors='replace') as f:
    for line in f:
        if line.startswith("INSERT INTO `monster_item_drop`"):
            m = re.search(r"VALUES\s*\((.*)\);?", line)
            if m:
                tokens = [t.strip(" '\"") for t in m.group(1).split(",")]
                uid, name, monid, itemid, cmin, cmax, spec, chance = tokens[:8]
                if monid in target_mids:
                    item_name = items_dict.get(itemid, f"Item {itemid}")
                    print(f"MonID={monid:3} Name={name:10} Item={item_name:12} (id={itemid}) Count=[{cmin}-{cmax}] Chance={chance}")
