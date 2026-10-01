# L1J 1.82 Headless Auto-Hunt Vertical Slice: Gameplay Trace

> **場景驗證**：
> 本文件記錄 Headless Bot 在真實 L1J 1.82 地圖（TI Dungeon 1F）進行自主探索、尋路、戰鬥（即時傷害結算）、擊殺、經驗獲得、升級、掉落與自動拾取的完整端到端 Gameplay 追蹤日誌。

## 1. 核心驗證指標 (Verification Metrics)

| 指標 | 驗證數值 | 規格與證據來源 |
| :--- | :--- | :--- |
| **執行模式** | 純虛擬時間 (Virtual Time) | `native_engine.temporal.VirtualClock` (0 秒 real waiting) |
| **移動時序** | 640 ms / step | `canonical_timing_spec.md` (PC Base Walk) |
| **攻擊時序** | 880 ms / attack | `canonical_timing_spec.md` (Knight Sword Interval) |
| **傷害時序** | T = 0 (IMMEDIATE) | `canonical_timing_spec.md` (Immediate Damage Resolution) |
| **戰鬥公式** | 182 HitFigure & DmgSystem | `native_engine.combat.CanonicalCombat` |
| **掉落來源** | 1.82 `monster_item_drop.sql` | `native_engine.bot.drop.DropSystem` |
| **地圖數據** | Real Map 1 (128x128 binary tiles) | S004 / S005 WorldMapGrid |

## 2. 完整遊戲追蹤日誌 (Complete Execution Trace)

```text
=================================================================
   L1J 1.82 HEADLESS AUTO-HUNT VERTICAL SLICE (AUTONOMOUS BOT)   
=================================================================
 Target Map     : Map 1 (TI Dungeon 1F)
 Kill Target    : 3 kills
 Max Virtual Time: 600000 ms (10.0 simulated minutes)
 Seed           : 777777
-----------------------------------------------------------------
[T=000000] PLAYER SPAWN: Arthur (Lv1 HP:100/100) at Map 1 (32671, 32804) with Long Sword

[STARTING AUTONOMOUS HUNTING SESSION IN VIRTUAL TIME]
[T=000000] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 35/35)
[T=000000] DAMAGE RESOLVED: Player→Floating Eye: HIT for 1 dmg (IMMEDIATE) | Target HP: 34/35
[T=000000] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=000880] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 34/35)
[T=000880] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 34/35
[T=000880] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=001760] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 34/35)
[T=001760] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 34/35
[T=001760] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=002640] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 34/35)
[T=002640] DAMAGE RESOLVED: Player→Floating Eye: HIT for 4 dmg (IMMEDIATE) | Target HP: 30/35
[T=002640] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=003520] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 30/35)
[T=003520] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 30/35
[T=003520] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=004400] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 30/35)
[T=004400] DAMAGE RESOLVED: Player→Floating Eye: HIT for 6 dmg (IMMEDIATE) | Target HP: 24/35
[T=004400] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=005280] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 24/35)
[T=005280] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 24/35
[T=005280] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=006160] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 24/35)
[T=006160] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 24/35
[T=006160] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=007040] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 24/35)
[T=007040] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 24/35
[T=007040] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=007920] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 24/35)
[T=007920] DAMAGE RESOLVED: Player→Floating Eye: HIT for 9 dmg (IMMEDIATE) | Target HP: 15/35
[T=007920] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=008800] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 15/35)
[T=008800] DAMAGE RESOLVED: Player→Floating Eye: HIT for 1 dmg (IMMEDIATE) | Target HP: 14/35
[T=008800] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=009680] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 14/35)
[T=009680] DAMAGE RESOLVED: Player→Floating Eye: HIT for 1 dmg (IMMEDIATE) | Target HP: 13/35
[T=009680] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=010560] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 13/35)
[T=010560] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 13/35
[T=010560] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=011440] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 13/35)
[T=011440] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 13/35
[T=011440] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=012320] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 13/35)
[T=012320] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 13/35
[T=012320] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=013200] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 13/35)
[T=013200] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 13/35
[T=013200] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=014080] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 13/35)
[T=014080] DAMAGE RESOLVED: Player→Floating Eye: HIT for 6 dmg (IMMEDIATE) | Target HP: 7/35
[T=014080] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=014960] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 7/35)
[T=014960] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 7/35
[T=014960] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=015840] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 7/35)
[T=015840] DAMAGE RESOLVED: Player→Floating Eye: HIT for 2 dmg (IMMEDIATE) | Target HP: 5/35
[T=015840] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=016720] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 5/35)
[T=016720] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 5/35
[T=016720] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=017600] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 5/35)
[T=017600] DAMAGE RESOLVED: Player→Floating Eye: MISS for 0 dmg (IMMEDIATE) | Target HP: 5/35
[T=017600] COUNTER-ATTACK: Floating Eye→Player for 0 dmg | Player HP: 100/100
[T=018480] ATTACK TRIGGERED: Player attacks Floating Eye (HP: 5/35)
[T=018480] DAMAGE RESOLVED: Player→Floating Eye: HIT for 6 dmg (IMMEDIATE) | Target HP: 0/35
[T=018480] MONSTER DIED: Floating Eye slain! Granted +50 EXP (Total EXP: 50)
[T=018480] LEVEL UP: Ding! Lv1 → Lv2! MaxHP increased to 109
[T=018480] GROUND DROP: Floating Eye dropped 漂浮之眼肉 x1 at (32672, 32805)
[T=019360] MOVE: Advanced to (32672, 32805) heading=3
[T=020000] LOOT: Picked up 漂浮之眼肉 x1 -> Added to Inventory
[T=020200] MOVE: Advanced to (32671, 32806) heading=5
[T=020840] ATTACK TRIGGERED: Player attacks Zombie (HP: 40/40)
[T=020840] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 40/40
[T=020840] COUNTER-ATTACK: Zombie→Player for 1 dmg | Player HP: 108/109
[T=021720] ATTACK TRIGGERED: Player attacks Zombie (HP: 40/40)
[T=021720] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 40/40
[T=021720] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 108/109
[T=022600] ATTACK TRIGGERED: Player attacks Zombie (HP: 40/40)
[T=022600] DAMAGE RESOLVED: Player→Zombie: HIT for 2 dmg (IMMEDIATE) | Target HP: 38/40
[T=022600] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 108/109
[T=023480] ATTACK TRIGGERED: Player attacks Zombie (HP: 38/40)
[T=023480] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 38/40
[T=023480] COUNTER-ATTACK: Zombie→Player for 7 dmg | Player HP: 101/109
[T=024360] ATTACK TRIGGERED: Player attacks Zombie (HP: 38/40)
[T=024360] DAMAGE RESOLVED: Player→Zombie: HIT for 5 dmg (IMMEDIATE) | Target HP: 33/40
[T=024360] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 101/109
[T=025240] ATTACK TRIGGERED: Player attacks Zombie (HP: 33/40)
[T=025240] DAMAGE RESOLVED: Player→Zombie: HIT for 8 dmg (IMMEDIATE) | Target HP: 25/40
[T=025240] COUNTER-ATTACK: Zombie→Player for 3 dmg | Player HP: 98/109
[T=026120] ATTACK TRIGGERED: Player attacks Zombie (HP: 25/40)
[T=026120] DAMAGE RESOLVED: Player→Zombie: HIT for 1 dmg (IMMEDIATE) | Target HP: 24/40
[T=026120] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 98/109
[T=027000] ATTACK TRIGGERED: Player attacks Zombie (HP: 24/40)
[T=027000] DAMAGE RESOLVED: Player→Zombie: HIT for 4 dmg (IMMEDIATE) | Target HP: 20/40
[T=027000] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 98/109
[T=027880] ATTACK TRIGGERED: Player attacks Zombie (HP: 20/40)
[T=027880] DAMAGE RESOLVED: Player→Zombie: HIT for 8 dmg (IMMEDIATE) | Target HP: 12/40
[T=027880] COUNTER-ATTACK: Zombie→Player for 5 dmg | Player HP: 93/109
[T=028760] ATTACK TRIGGERED: Player attacks Zombie (HP: 12/40)
[T=028760] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 12/40
[T=028760] COUNTER-ATTACK: Zombie→Player for 3 dmg | Player HP: 90/109
[T=029640] ATTACK TRIGGERED: Player attacks Zombie (HP: 12/40)
[T=029640] DAMAGE RESOLVED: Player→Zombie: HIT for 10 dmg (IMMEDIATE) | Target HP: 2/40
[T=029640] COUNTER-ATTACK: Zombie→Player for 5 dmg | Player HP: 85/109
[T=030520] ATTACK TRIGGERED: Player attacks Zombie (HP: 2/40)
[T=030520] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 2/40
[T=030520] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 85/109
[T=031400] ATTACK TRIGGERED: Player attacks Zombie (HP: 2/40)
[T=031400] DAMAGE RESOLVED: Player→Zombie: HIT for 7 dmg (IMMEDIATE) | Target HP: 0/40
[T=031400] MONSTER DIED: Zombie slain! Granted +37 EXP (Total EXP: 87)
[T=031400] LEVEL UP: Ding! Lv2 → Lv3! MaxHP increased to 118
[T=032280] MOVE: Advanced to (32670, 32805) heading=7
[T=032920] MOVE: Advanced to (32669, 32804) heading=7
[T=033560] MOVE: Advanced to (32668, 32803) heading=7
[T=034200] MOVE: Advanced to (32667, 32802) heading=7
[T=034840] ATTACK TRIGGERED: Player attacks Zombie (HP: 40/40)
[T=034840] DAMAGE RESOLVED: Player→Zombie: HIT for 1 dmg (IMMEDIATE) | Target HP: 39/40
[T=034840] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 118/118
[T=035720] ATTACK TRIGGERED: Player attacks Zombie (HP: 39/40)
[T=035720] DAMAGE RESOLVED: Player→Zombie: HIT for 5 dmg (IMMEDIATE) | Target HP: 34/40
[T=035720] COUNTER-ATTACK: Zombie→Player for 5 dmg | Player HP: 113/118
[T=036600] ATTACK TRIGGERED: Player attacks Zombie (HP: 34/40)
[T=036600] DAMAGE RESOLVED: Player→Zombie: HIT for 3 dmg (IMMEDIATE) | Target HP: 31/40
[T=036600] COUNTER-ATTACK: Zombie→Player for 9 dmg | Player HP: 104/118
[T=037480] ATTACK TRIGGERED: Player attacks Zombie (HP: 31/40)
[T=037480] DAMAGE RESOLVED: Player→Zombie: HIT for 9 dmg (IMMEDIATE) | Target HP: 22/40
[T=037480] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 104/118
[T=038360] ATTACK TRIGGERED: Player attacks Zombie (HP: 22/40)
[T=038360] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 22/40
[T=038360] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 104/118
[T=039240] ATTACK TRIGGERED: Player attacks Zombie (HP: 22/40)
[T=039240] DAMAGE RESOLVED: Player→Zombie: HIT for 4 dmg (IMMEDIATE) | Target HP: 18/40
[T=039240] COUNTER-ATTACK: Zombie→Player for 4 dmg | Player HP: 100/118
[T=040120] ATTACK TRIGGERED: Player attacks Zombie (HP: 18/40)
[T=040120] DAMAGE RESOLVED: Player→Zombie: HIT for 6 dmg (IMMEDIATE) | Target HP: 12/40
[T=040120] COUNTER-ATTACK: Zombie→Player for 4 dmg | Player HP: 96/118
[T=041000] ATTACK TRIGGERED: Player attacks Zombie (HP: 12/40)
[T=041000] DAMAGE RESOLVED: Player→Zombie: HIT for 6 dmg (IMMEDIATE) | Target HP: 6/40
[T=041000] COUNTER-ATTACK: Zombie→Player for 6 dmg | Player HP: 90/118
[T=041880] ATTACK TRIGGERED: Player attacks Zombie (HP: 6/40)
[T=041880] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 6/40
[T=041880] COUNTER-ATTACK: Zombie→Player for 3 dmg | Player HP: 87/118
[T=042760] ATTACK TRIGGERED: Player attacks Zombie (HP: 6/40)
[T=042760] DAMAGE RESOLVED: Player→Zombie: HIT for 5 dmg (IMMEDIATE) | Target HP: 1/40
[T=042760] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 87/118
[T=043640] ATTACK TRIGGERED: Player attacks Zombie (HP: 1/40)
[T=043640] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 1/40
[T=043640] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 87/118
[T=044520] ATTACK TRIGGERED: Player attacks Zombie (HP: 1/40)
[T=044520] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 1/40
[T=044520] COUNTER-ATTACK: Zombie→Player for 3 dmg | Player HP: 84/118
[T=045400] ATTACK TRIGGERED: Player attacks Zombie (HP: 1/40)
[T=045400] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 1/40
[T=045400] COUNTER-ATTACK: Zombie→Player for 1 dmg | Player HP: 83/118
[T=046280] ATTACK TRIGGERED: Player attacks Zombie (HP: 1/40)
[T=046280] DAMAGE RESOLVED: Player→Zombie: MISS for 0 dmg (IMMEDIATE) | Target HP: 1/40
[T=046280] COUNTER-ATTACK: Zombie→Player for 0 dmg | Player HP: 83/118
[T=047160] ATTACK TRIGGERED: Player attacks Zombie (HP: 1/40)
[T=047160] DAMAGE RESOLVED: Player→Zombie: HIT for 6 dmg (IMMEDIATE) | Target HP: 0/40
[T=047160] MONSTER DIED: Zombie slain! Granted +37 EXP (Total EXP: 124)
[T=047160] SESSION END: Reason=KILL_LIMIT_REACHED | Kills=3 | Level=3 | EXP=124 | VirtualTime=47160ms

=================================================================
                    BOT SESSION COMPLETED                        
=================================================================
 Termination Reason : KILL_LIMIT_REACHED
 Total Monsters Slain: 3
 Final Character Lv  : Lv3 (EXP: 124)
 Final Character HP  : 83/118
 Virtual Time Elapsed: 47160 ms (47.16 simulated seconds)
 Total Damage Dealt  : 126
 Total Damage Taken  : 59
 Items Looted (1): 漂浮之眼肉 x1
=================================================================
 OVERALL STATUS: PASS (MVP-01 VERTICAL SLICE VALIDATED)
=================================================================
```
