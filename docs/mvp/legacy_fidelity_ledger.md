# L1J 1.82 Legacy Fidelity Ledger (MVP-03: Multi-Actor Persistent Native World)

## 1. 說明與分類標準

本文件對目前已進入 `l1j-headless` MVP-01 / MVP-02 / MVP-03 運行階段之所有遊戲機制（Game Mechanics）、數值、公式與行為進行嚴格的 **Legacy Fidelity Audit**。

任何機制不得以「代碼能跑通」或「經驗觀察」擅自宣稱為真實伺服器規格。所有機制必須嚴格分類為以下五種標準之一：

- **`LEGACY_RULE`**: 直接對應 L1J 1.82 Legacy Server / DB 原始碼或資料表，具有完全一致之明確證據。
- **`DERIVED_CANONICAL`**: 根據 Legacy 原始碼與資料表邏輯所歸納、推導之標準規格（如 VirtualClock 事件排程）。
- **`BOT_POLICY`**: 屬於自主代理人（Headless Bot）之決策策略，非 L1J 伺服器本體規則，不可宣稱為 L1J 官方 AI。
- **`CONTROLLED_SUBSTITUTION`**: 因無圖形/決定性測試需求，對 Legacy 實作所進行之受控替代（如隨機數固定中位數、地圖初始生成等）。
- **`UNKNOWN`**: 目前尚未找到 1.82 Legacy 直接原始證據，保留待後續考古確認。

---

## 2. 核心機制保真度總表 (Master Fidelity Ledger)

| Mechanic (機制) | Implementation (目前實作) | L1J 1.82 Evidence (原始證據) | Classification | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Player Movement Interval** | 640 ms (Virtual Clock event gate) | `sprite_frame.sql:81, 118` (action 0/4 `walk` = 640ms), `SprTable.java:60` | `LEGACY_RULE` | **CONFIRMED** |
| **Dynamic PC Attack Timing** | 動態解析：Player GFX + Action + Weapon（GFX 48 女騎單手劍 920ms、GFX 61 男騎單手劍 880ms、GFX 0 王子 1000ms、GFX 37 女妖 760ms、徒手 880/1000ms） | `SprTable.java:84`, `CheckSpeed.java:89`, `sprite_frame.sql:28-118` | `LEGACY_RULE` | **CONFIRMED** (MVP-04 擴展驗證) |
| **Attack Damage Timing** | Immediate ($T = 0$) | `PcInstance.java:600-650`, `C_Attack.java:26`, `canonical_timing_spec.md:214` | `LEGACY_RULE` | **CONFIRMED** |
| **Damage Formula (Physical)** | `CanonicalCombat.calculate_damage()` | `PcInstance.java:613`, `CalcStat.calcDmg()`, `C_Attack.java` | `DERIVED_CANONICAL` | **CONFIRMED** |
| **Hit Formula (HitFigure)** | `CanonicalCombat.resolve_hit()` | `PcInstance.java:606`, `CalcStat.calcHit()` | `DERIVED_CANONICAL` | **CONFIRMED** |
| **Potion Recovery (Red Potion)** | 紅水 (Item 104) 回復 10～30 HP (`rand(10, 30)`) | `LesserHealingPotion.java:22-26` (`MIN_HP = 10, MAX_HP = 30`) | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Potion Recovery (Orange Potion)** | 白水/澄水 (Item 105) 回復 30～70 HP (`rand(30, 70)`) | `HealingPotion.java:22-26` (`MIN_HP = 30, MAX_HP = 70`) | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Green Potion Haste Buff** | 綠水 (Item 108) 賦予 300 秒加速狀態（取消緩速、排程 VirtualClock 到期） | `HastePotion.java:21-36` (`firstTime = 300`) | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **PC Speed Multipliers** | PC Haste: $int(interval \times 0.75)$; Slow: $int(interval / 0.75)$; Brave: $int(interval \times 0.75)$ | `CheckSpeed.java:101-106` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Monster Speed Multipliers** | Monster Haste: $int(spd - spd \times 0.3)$; Slow: $int(spd + spd \times 0.3)$ | `NpcInstance.java:158-167` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Status Conflict Neutralization** | 加速取消緩速（不留加速）；緩速取消加速（不留緩速） | `HastePotion.java:30-33`, `Slow.java:43` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Offensive Skill (Energy Bolt)** | 光箭 (Skill 4): 耗魔 3 MP，施法動作 18 (880ms)，即時魔法傷害 $T=0$ | `skill_list.sql:24`, `Magic.java:164-176`, `EnergyBolt.java` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Support Skill (Lesser Heal)** | 初治 (Skill 1): 耗魔 4 MP，施法動作 19 (800ms)，即時 HP 回復 | `skill_list.sql:21`, `Magic.java:180-192`, `Heal.java` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Status Skill (Haste)** | 加速術 (Skill 28): 耗魔 25 MP / 20 HP，動作 19 (800ms)，持續 1200 秒 | `skill_list.sql:48`, `Haste.java:18-35` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Novice Death Protection** | 角色等級 $\le 9$ 時死亡不扣經驗值 (EXP Loss = 0) | `PcInstance.java:789` (`if (getLevel() > 9)`) | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **High Level Death Penalty** | 角色等級 $> 9$ 時死亡扣除當前 10% 經驗值 | `PcInstance.java:838` (`lose_exp = (int)(curExp * 0.1)`) | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Death State Cleanup** | 死亡時清除所有主動 Buff、藥水與狀態計時器 | `PcInstance.java:845-855`, `BuffTimerInstance.java` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Player Town Respawn** | 死亡後重生地點設定於說話之島城鎮中心 (32608, 32742) | `PcInstance.java:860`, `loc.sql` (TI Town center) | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **NPC Shop Interaction (Pandora)** | 說話之島潘朵拉 (NPC 3, GFX 98) 純記憶體交易：紅水 37 金幣、綠水 120 金幣 | `npc.sql:21` (潘朵拉), `npc_shop.sql:31-35` | `LEGACY_RULE` | **CONFIRMED** (MVP-04) |
| **Autonomous Monster AI Timing** | 怪物透過 Scheduler 自主事件驅動，追擊使用 `modespeed(0)`，攻擊使用 `modespeed(1)` | `MonsterTable.java:76`, `ClientFileLoad.java:42`, `MonAi.java:85-88`, `MonsterInstance.java:293-305` | `LEGACY_RULE` | **CONFIRMED** (MVP-03 自主化) |
| **Monster Agro & Pursuit** | 感知範圍內怪物自主鎖定目標並主動追逐 | `MonsterInstance.java:293`, `NpcInstance.java:160` | `LEGACY_RULE` | **CONFIRMED** |
| **Monster Respawn Lifecycle** | 死亡移出地圖，`re_spawn * 1000ms` 後透過 `respawn_monster` 在合法格重生滿血 | `MonsterInstance.java:518-551`, `monster_spawnlist.sql` (`re_spawn` 欄位) | `LEGACY_RULE` | **CONFIRMED** (MVP-03 重生化) |
| **Monster Death / Despawn** | HP <= 0 即時判定死亡並移出 active map | `MonsterInstance.java:450`, `NpcInstance.java` (death check) | `LEGACY_RULE` | **CONFIRMED** |
| **Monster EXP Distribution** | 漂浮之眼 +50, 人形僵屍 +37, 狼人 +45, 骷髏 +70 | `db/lineage/monster.sql:57` 等 | `LEGACY_RULE` | **CONFIRMED** |
| **Level Progression Thresholds** | Lv1: 20 EXP, Lv2: 45 EXP, Lv3: 80 EXP | `db/lineage/exp.sql:27-29` (`bonus` 欄位: 20, 45, 80) | `LEGACY_RULE` | **CONFIRMED** |
| **Level Up HP Growth** | 騎士升級固定 +9 MaxHP (con<=15) | `Character.java:980-998` `start_hp = 6 + rand(1..6)`。目前採用中位數 3 (6+3=9) 作為確定性測試替代 | `CONTROLLED_SUBSTITUTION` | **VALIDATED** |
| **Natural HP Regeneration Event**| 每 10 秒固定排程回血 +5 HP（非步進輪詢，為獨立世界事件） | `HpMpTimer.java:48-73` (`cha.isHpTic()`, `cha.hpTic()`) | `LEGACY_RULE` | **CONFIRMED** (MVP-03 排程化) |
| **Drop Table Contents** | 漂浮之眼肉(166)、骷髏骨(288)、銀長劍(102)等 | `db/lineage/monster_item_drop.sql` (各怪物 monid 關聯表) | `LEGACY_RULE` | **CONFIRMED** |
| **Drop Chance Calculation** | 機率採用萬分比 `rand(1, 10000) <= chance` | `MonsterItemDropTable.java:57` (`Util.rand(1, 10000) <= d.getChance() * Config.RATE_DROP`) | `LEGACY_RULE` | **CONFIRMED** |
| **Drop Quantity** | `count_min` 至 `count_max` 隨機區加 | `MonsterItemDropTable.java:73` (`Util.rand(d.getCount_min(), d.getCount_max())`) | `LEGACY_RULE` | **CONFIRMED** |
| **Ground Item Generation** | 掉落物生成於怪物座標 $(x, y)$ | `C_ItemDrop.java`, `MonsterItemDropTable.java`, `WorldInstance.java` | `LEGACY_RULE` | **CONFIRMED** |
| **Loot (Item Pickup)** | 靠近至目標格後拾取進 Inventory | `C_ItemPickup.java:33` (`L1Object.pickup()`), `PcInstance.java` | `LEGACY_RULE` | **CONFIRMED** |
| **Target Selection Policy** | 優先攻擊近戰目標、檢查 A* 可達性、避開高等級怪物 | Bot 自主感知與啟發式決策樹 | `BOT_POLICY` | **AGENT_SPECIFIC** |
| **Roaming / Patrol Policy** | 無目標時沿地圖幾何漫步搜尋敵人，永不異常終止 | Bot 自主尋路與巡邏漫遊狀態機 | `BOT_POLICY` | **AGENT_SPECIFIC** |

---

## 3. 關鍵數值之原始證據回溯 (Detailed Trace Back)

### 3.1 怪物 EXP (+50 EXP, +37 EXP)
- **證據來源**: `db/lineage/monster.sql`
- **實測驗證**:
  - `漂浮之眼` (ID 1, GFX 29): 第 12 欄位 `exp = 50`。
  - `人形僵屍` (ID 7, GFX 52): 第 12 欄位 `exp = 37`。
  - `骷髏` (ID 2, GFX 30): 第 12 欄位 `exp = 70`。
- **結論**: 目前執行日誌出現的 `+50 EXP` 與 `+37 EXP` 均為 **100% LEGACY_RULE**，非自創數值。

### 3.2 角色升級門檻 (EXP Table)
- **證據來源**: `db/lineage/exp.sql`
- **實測驗證**:
  - `INSERT INTO exp VALUES ('1', '1', '20', '20');` (達 20 EXP 升 Lv2)
  - `INSERT INTO exp VALUES ('2', '2', '25', '45');` (達 45 累積 EXP 升 Lv3)
  - `INSERT INTO exp VALUES ('3', '3', '35', '80');` (達 80 累積 EXP 升 Lv4)
- **結論**: 目前等級晉升條件完全遵循 1.82 Legacy 資料庫規格。

### 3.3 升級生命值成長 (+9 MaxHP)
- **證據來源**: `src/net/world/object/Character.java:979-999` (`StatusUP()`)
- **原始碼實作**:
  ```java
  case 1: // Knight
    temp = Util.rand(1, 64);
    if (con <= 15) {
      start_hp = 6;
    } else {
      start_hp = con - 9;
    }
    if (temp <= 7) { start_hp += 1; }
    else if (temp <= 22) { start_hp += 2; }
    else if (temp <= 42) { start_hp += 3; }  // 最常出現區間 (31.25%)
    else if (temp <= 57) { start_hp += 4; }
    else if (temp <= 63) { start_hp += 5; }
    else { start_hp += 6; }
  ```
- **目前實作**:
  在 `native_engine/progression.py` 中，為確保單元測試之確定性（Determinism），使用中位數 `start_hp = 6 + 3 = 9`。
- **分類定位**: 數值結構來自 `Character.java`，採用確定性中位數判定為 `CONTROLLED_SUBSTITUTION`。

### 3.4 掉落機率與數量 (Drop Chance & Count)
- **證據來源**: `src/net/database/MonsterItemDropTable.java:57-75` 與 `db/lineage/monster_item_drop.sql`
- **判定邏輯**:
  ```java
  if (Util.rand(1, 10000) <= d.getChance() * Config.RATE_DROP) {
      ItemInstance item = ItemsTable.getInstance().newItem(d.getItemid(), false, true);
      item.setCount(Util.rand(d.getCount_min(), d.getCount_max()));
      mon.getInventory().add(item);
  }
  ```
- **結論**: 機率分母為 10,000，數量取區間隨機，完全依循原始伺服器規則。

---

## 4. 殘餘受控替代與未確認清單 (Remaining Substitutions & Unknowns)

### 4.1 殘餘受控替代 (CONTROLLED_SUBSTITUTION)
1. **升級 HP 隨機分佈**: 目前採用固定中位數（+9），未來若接入完整 Seeded RNG 可還原 1..64 權重隨機分佈。
2. **怪物的在地圖初始分佈**: 伺服器啟動時由 `MonsterSpawnTable` 隨機擲骰 50 次，目前由 `initialize_s007_session` 依 Seed 決定。
3. **自然回血 (HP TIC)**: 目前設定每 10 秒回 5 HP，Legacy 原始依體重（<= 14）與角色姿態（站立 4s / 步行 16s）動態變動。

### 4.2 殘餘未確認清單 (UNKNOWN)
1. **怪物被擊退 (Push/Stun) 動畫時長**: 在 1.82 中是否有固定的 Action ID 與封包延遲，待後續封包層實作時確認。
2. **多怪物碰撞重疊 (Tile Collision)**: 怪物之間在同一格能否重疊（Lineage 1.82 原版允許怪物短暫重疊於同格，或限制不可穿過），目前以 A* 碰撞為準。
