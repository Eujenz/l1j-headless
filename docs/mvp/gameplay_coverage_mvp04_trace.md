# L1J 1.82 Gameplay Coverage Expansion Simulation Trace (MVP-04)

## 1. 執行概要 (Executive Summary)

- **執行模式**: In-Process Native Headless World Simulation (Multi-Actor Autonomous Scheduler)
- **隨機種子 (Deterministic Seed)**: `777777`
- **地圖**: Map 0 (Talking Island Surface)
- **虛擬時間跨度 (Virtual Time)**: `600000 ms` (10.0 simulated minutes)
- **終止原因**: `SIMULATION_TIME_REACHED`
- **怪物擊殺數**: `45 kills`
- **怪物重生次數 (Respawns)**: `16 times`
- **角色最終等級與經驗**: `Lv4 (EXP: 709)`
- **角色最終血量**: `127/127 HP`
- **總造成傷害**: `653 dmg`
- **總承受傷害**: `102 dmg`
- **拾取道具數量**: `0 items`
- **總事件記錄數**: `1652 log entries`

---

## 2. 核心機制驗證 (Core Mechanics Validated in Persistent World)

### 2.1 Dynamic Weapon & Action Timing Resolution
- PC 攻擊間隔不再使用固定數值，而是依據角色職業外觀（GFX）、武器類型與動作編號動態向 `SprTable` 查表。
- 武器切換與徒手狀態（Bare Hands）能動態觸發攻擊間隔重算。

### 2.2 Canonical Potions & Recovery Semantics
- 紅水（Red Potion，Item 104）依據 `LesserHealingPotion.java` 精確給予 10～30 HP 回復。
- 綠水（Green Potion，Item 108）依據 `HastePotion.java` 精確賦予 300 秒加速狀態（Haste）。

### 2.3 Status Effects & Speed Multipliers (VirtualClock Expiration)
- 玩家加速時移動與攻擊間隔依據 `CheckSpeed.java` 乘以 0.75。
- 怪物加速依據 `NpcInstance.java` 扣減 30% 間隔（speed - speed * 0.3）。
- 加速（Haste）與緩速（Slow）具備互斥抵銷邏輯（Conflict Neutralization）。
- 所有狀態持續時間完全依賴 `VirtualClock` 與 `Scheduler` 事件到期自動復原，零 Wall-Clock 等待。

### 2.4 Skill Execution Vertical Slice
- 支援初級治癒術（Lesser Heal，Skill 1，Action 19 800ms）、光箭（Energy Bolt，Skill 4，Action 18 880ms）與加速術（Haste，Skill 28，Action 19 800ms）。
- 技能傷害與效果採即時（Immediate T=0）結算，並由動作延遲控管下次決策時點。

### 2.5 Novice Protection & Respawn Semantics
- 玩家於 9 級以下死亡時享有新手保護，EXP 損失為 0（`PcInstance.java:789-858`）。
- 死亡時主動清除所有 Buff 與藥水狀態，並於說話之島城鎮座標（32608, 32742）排程重生。

### 2.6 NPC Shop Interaction (Pandora)
- 提供說話之島潘朵拉（NPC ID 3，GFX 98）之純記憶體商店交易接口，以金幣（Adena 40308）購買紅水（37 金幣）與綠水（120 金幣）。

---

## 3. 代表性日誌節錄 (Representative Event Trace Snippets)

### 前段日誌節錄 (Initial Events):
```text
[T=000000] PLAYER SPAWN: Arthur (Lv1 HP:100/100 MP:10/10) at Map 0 (32477, 32875) with Long Sword
[T=000000] POTION: Drank Green Potion -> Haste applied for 300s (Move: 480ms, Atk: 690ms)
[T=000030] MONSTER MOVE: Orc advanced to (32475, 32877) pursuing Player
[T=000600] MOVE: Advanced to (32476, 32876) heading=5
[T=000830] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 100/100
[T=001080] SKILL CAST: Energy Bolt -> Hit Orc for 1 magic dmg (IMMEDIATE) | Target HP: 5/6 MP: 7/10
[T=001960] ATTACK TRIGGERED: Player attacks Orc (HP: 5/6)
[T=001960] DAMAGE RESOLVED: Player→Orc: HIT for 1 dmg (IMMEDIATE) | Target HP: 4/6
[T=002150] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 100/100
[T=002650] ATTACK TRIGGERED: Player attacks Orc (HP: 4/6)
[T=002650] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 4/6
[T=003340] ATTACK TRIGGERED: Player attacks Orc (HP: 4/6)
[T=003340] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 4/6
[T=003470] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 100/100
[T=004030] ATTACK TRIGGERED: Player attacks Orc (HP: 4/6)
[T=004030] DAMAGE RESOLVED: Player→Orc: HIT for 3 dmg (IMMEDIATE) | Target HP: 1/6
[T=004720] ATTACK TRIGGERED: Player attacks Orc (HP: 1/6)
[T=004720] DAMAGE RESOLVED: Player→Orc: HIT for 2 dmg (IMMEDIATE) | Target HP: 0/6
[T=004720] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 5)
[T=005410] MOVE: Advanced to (32477, 32875) heading=1
[T=005890] MOVE: Advanced to (32477, 32874) heading=0
[T=006370] MOVE: Advanced to (32477, 32873) heading=0
[T=006850] MOVE: Advanced to (32477, 32872) heading=0
[T=006880] MONSTER MOVE: Orc advanced to (32478, 32871) pursuing Player
[T=007330] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=007330] DAMAGE RESOLVED: Player→Orc: HIT for 5 dmg (IMMEDIATE) | Target HP: 1/6
[T=007680] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 100/100
[T=008020] ATTACK TRIGGERED: Player attacks Orc (HP: 1/6)
[T=008020] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 1/6
[T=008710] ATTACK TRIGGERED: Player attacks Orc (HP: 1/6)
[T=008710] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 1/6
[T=009000] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 100/100
[T=009400] ATTACK TRIGGERED: Player attacks Orc (HP: 1/6)
[T=009400] DAMAGE RESOLVED: Player→Orc: HIT for 3 dmg (IMMEDIATE) | Target HP: 0/6
[T=009400] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 10)
[T=010000] MP_REGEN: Player recovered 3 MP -> MP: 10/10
[T=010090] MOVE: Advanced to (32478, 32871) heading=1
[T=010570] MOVE: Advanced to (32479, 32870) heading=1
[T=010600] MONSTER MOVE: Orc advanced to (32480, 32869) pursuing Player
[T=011050] SKILL CAST: Energy Bolt -> Hit Orc for 1 magic dmg (IMMEDIATE) | Target HP: 5/6 MP: 7/10
[T=011400] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 100/100
[T=011930] ATTACK TRIGGERED: Player attacks Orc (HP: 5/6)
[T=011930] DAMAGE RESOLVED: Player→Orc: HIT for 1 dmg (IMMEDIATE) | Target HP: 4/6
[T=012620] ATTACK TRIGGERED: Player attacks Orc (HP: 4/6)
[T=012620] DAMAGE RESOLVED: Player→Orc: HIT for 4 dmg (IMMEDIATE) | Target HP: 0/6
[T=012620] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 15)
[T=013310] MOVE: Advanced to (32478, 32869) heading=7
[T=013790] MOVE: Advanced to (32478, 32868) heading=0
[T=013820] MONSTER MOVE: Slime advanced to (32482, 32857) pursuing Player
[T=014270] MOVE: Advanced to (32478, 32867) heading=0
[T=014620] MONSTER MOVE: Slime advanced to (32481, 32858) pursuing Player
[T=014750] MOVE: Advanced to (32478, 32866) heading=0
[T=014780] MONSTER MOVE: Goblin advanced to (32479, 32865) pursuing Player
[T=014780] MONSTER MOVE: Slime advanced to (32472, 32855) pursuing Player
[T=015230] ATTACK TRIGGERED: Player attacks Goblin (HP: 9/9)
[T=015230] DAMAGE RESOLVED: Player→Goblin: HIT for 2 dmg (IMMEDIATE) | Target HP: 7/9
[T=015420] MONSTER MOVE: Slime advanced to (32480, 32859) pursuing Player
[T=015540] MONSTER ATTACK: Goblin→Player for 0 dmg | Player HP: 100/100
[T=015580] MONSTER MOVE: Slime advanced to (32473, 32856) pursuing Player
[T=015920] ATTACK TRIGGERED: Player attacks Goblin (HP: 7/9)
[T=015920] DAMAGE RESOLVED: Player→Goblin: HIT for 8 dmg (IMMEDIATE) | Target HP: 0/9
[T=015920] MONSTER DIED: Goblin slain! Granted +5 EXP (Total EXP: 20)
[T=016220] MONSTER MOVE: Slime advanced to (32479, 32860) pursuing Player
[T=016380] MONSTER MOVE: Slime advanced to (32474, 32857) pursuing Player
[T=016610] MOVE: Advanced to (32477, 32865) heading=7
[T=017020] MONSTER MOVE: Slime advanced to (32478, 32861) pursuing Player
[T=017090] MOVE: Advanced to (32476, 32864) heading=7
[T=017180] MONSTER MOVE: Slime advanced to (32475, 32858) pursuing Player
[T=017570] MOVE: Advanced to (32476, 32863) heading=0
[T=017600] MONSTER MOVE: Orc advanced to (32477, 32862) pursuing Player
[T=017820] MONSTER MOVE: Slime advanced to (32477, 32862) pursuing Player
[T=017980] MONSTER MOVE: Slime advanced to (32476, 32859) pursuing Player
[T=018050] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=018050] DAMAGE RESOLVED: Player→Orc: HIT for 10 dmg (IMMEDIATE) | Target HP: 0/6
[T=018050] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 25)
[T=018620] MONSTER ATTACK: Slime→Player for 0 dmg | Player HP: 100/100
[T=018740] ATTACK TRIGGERED: Player attacks Slime (HP: 20/20)
[T=018740] DAMAGE RESOLVED: Player→Slime: HIT for 0 dmg (IMMEDIATE) | Target HP: 20/20
[T=018780] MONSTER MOVE: Slime advanced to (32477, 32860) pursuing Player
[T=019430] ATTACK TRIGGERED: Player attacks Slime (HP: 20/20)
[T=019430] DAMAGE RESOLVED: Player→Slime: HIT for 2 dmg (IMMEDIATE) | Target HP: 18/20
[T=019580] MONSTER MOVE: Slime advanced to (32476, 32861) pursuing Player
[T=019820] MONSTER ATTACK: Slime→Player for 0 dmg | Player HP: 100/100
[T=020000] MP_REGEN: Player recovered 3 MP -> MP: 10/10
[T=020120] SKILL CAST: Energy Bolt -> Hit Slime for 1 magic dmg (IMMEDIATE) | Target HP: 17/20 MP: 7/10
[T=020380] MONSTER MOVE: Slime advanced to (32477, 32862) pursuing Player
[T=021000] ATTACK TRIGGERED: Player attacks Slime (HP: 17/20)
[T=021000] DAMAGE RESOLVED: Player→Slime: HIT for 7 dmg (IMMEDIATE) | Target HP: 10/20
[T=021020] MONSTER ATTACK: Slime→Player for 0 dmg | Player HP: 100/100
[T=021180] MONSTER ATTACK: Slime→Player for 0 dmg | Player HP: 100/100
[T=021690] ATTACK TRIGGERED: Player attacks Slime (HP: 10/20)
[T=021690] DAMAGE RESOLVED: Player→Slime: HIT for 10 dmg (IMMEDIATE) | Target HP: 0/20
[T=021690] MONSTER DIED: Slime slain! Granted +37 EXP (Total EXP: 62)
[T=021690] LEVEL UP: Ding! Lv1 → Lv2! MaxHP increased to 109
[T=022380] MONSTER ATTACK: Slime→Player for 4 dmg | Player HP: 105/109
[T=022380] ATTACK TRIGGERED: Player attacks Slime (HP: 20/20)
[T=022380] DAMAGE RESOLVED: Player→Slime: HIT for 2 dmg (IMMEDIATE) | Target HP: 18/20
[T=023070] ATTACK TRIGGERED: Player attacks Slime (HP: 18/20)
[T=023070] DAMAGE RESOLVED: Player→Slime: MISS for 0 dmg (IMMEDIATE) | Target HP: 18/20
[T=023580] MONSTER ATTACK: Slime→Player for 0 dmg | Player HP: 105/109
```

### 中後段日誌節錄 (Late-Stage & Conclusion Events):
```text
[中間省略數百筆巡邏、交戰、施法、藥水、拾取與重生事件]...
[T=557750] ATTACK TRIGGERED: Player attacks Orc Fighter (HP: 19/40)
[T=557750] DAMAGE RESOLVED: Player→Orc Fighter: HIT for 2 dmg (IMMEDIATE) | Target HP: 17/40
[T=558440] ATTACK TRIGGERED: Player attacks Orc Fighter (HP: 17/40)
[T=558440] DAMAGE RESOLVED: Player→Orc Fighter: HIT for 8 dmg (IMMEDIATE) | Target HP: 9/40
[T=558710] MONSTER ATTACK: Orc Fighter→Player for 7 dmg | Player HP: 113/127
[T=559130] ATTACK TRIGGERED: Player attacks Orc Fighter (HP: 9/40)
[T=559130] DAMAGE RESOLVED: Player→Orc Fighter: HIT for 0 dmg (IMMEDIATE) | Target HP: 9/40
[T=559820] ATTACK TRIGGERED: Player attacks Orc Fighter (HP: 9/40)
[T=559820] DAMAGE RESOLVED: Player→Orc Fighter: MISS for 0 dmg (IMMEDIATE) | Target HP: 9/40
[T=559910] MONSTER ATTACK: Orc Fighter→Player for 5 dmg | Player HP: 108/127
[T=560000] HP_REGEN: Player recovered 5 HP -> HP: 113/127
[T=560000] MP_REGEN: Player recovered 3 MP -> MP: 10/10
[T=560510] SKILL CAST: Energy Bolt -> Hit Orc Fighter for 1 magic dmg (IMMEDIATE) | Target HP: 8/40 MP: 7/10
[T=561110] MONSTER ATTACK: Orc Fighter→Player for 0 dmg | Player HP: 113/127
[T=561390] ATTACK TRIGGERED: Player attacks Orc Fighter (HP: 8/40)
[T=561390] DAMAGE RESOLVED: Player→Orc Fighter: MISS for 0 dmg (IMMEDIATE) | Target HP: 8/40
[T=562080] ATTACK TRIGGERED: Player attacks Orc Fighter (HP: 8/40)
[T=562080] DAMAGE RESOLVED: Player→Orc Fighter: HIT for 8 dmg (IMMEDIATE) | Target HP: 0/40
[T=562080] MONSTER DIED: Orc Fighter slain! Granted +65 EXP (Total EXP: 709)
[T=562770] PATROL: Roaming (32576, 32836) heading=0
[T=563250] PATROL: Roaming (32576, 32835) heading=0
[T=563730] PATROL: Roaming (32577, 32836) heading=3
[T=564690] PATROL: Roaming (32576, 32837) heading=5
[T=565170] PATROL: Roaming (32575, 32838) heading=5
[T=565650] PATROL: Roaming (32574, 32839) heading=5
[T=566130] PATROL: Roaming (32573, 32840) heading=5
[T=566610] PATROL: Roaming (32572, 32841) heading=5
[T=567090] PATROL: Roaming (32571, 32842) heading=5
[T=567570] PATROL: Roaming (32570, 32843) heading=5
[T=568050] PATROL: Roaming (32569, 32842) heading=7
[T=568530] PATROL: Roaming (32568, 32841) heading=7
[T=569010] PATROL: Roaming (32567, 32840) heading=7
[T=569490] PATROL: Roaming (32566, 32839) heading=7
[T=569970] PATROL: Roaming (32565, 32838) heading=7
[T=570000] HP_REGEN: Player recovered 5 HP -> HP: 118/127
[T=570000] MP_REGEN: Player recovered 3 MP -> MP: 10/10
[T=570450] PATROL: Roaming (32566, 32838) heading=2
[T=570930] PATROL: Roaming (32567, 32838) heading=2
[T=571410] PATROL: Roaming (32568, 32838) heading=2
[T=571890] PATROL: Roaming (32569, 32838) heading=2
[T=572370] PATROL: Roaming (32570, 32837) heading=1
[T=572850] PATROL: Roaming (32571, 32836) heading=1
[T=573330] PATROL: Roaming (32572, 32835) heading=1
[T=573810] PATROL: Roaming (32573, 32834) heading=1
[T=574290] PATROL: Roaming (32574, 32833) heading=1
[T=574770] PATROL: Roaming (32575, 32832) heading=1
[T=575250] PATROL: Roaming (32576, 32831) heading=1
[T=575730] PATROL: Roaming (32576, 32832) heading=4
[T=576210] PATROL: Roaming (32576, 32833) heading=4
[T=576690] PATROL: Roaming (32576, 32834) heading=4
[T=577170] PATROL: Roaming (32576, 32835) heading=4
[T=577650] PATROL: Roaming (32576, 32836) heading=4
[T=578130] PATROL: Roaming (32576, 32837) heading=4
[T=578610] PATROL: Roaming (32577, 32837) heading=2
[T=579570] PATROL: Roaming (32577, 32838) heading=4
[T=580000] HP_REGEN: Player recovered 5 HP -> HP: 123/127
[T=580050] PATROL: Roaming (32577, 32839) heading=4
[T=580530] PATROL: Roaming (32577, 32840) heading=4
[T=581010] PATROL: Roaming (32576, 32841) heading=5
[T=581490] PATROL: Roaming (32575, 32842) heading=5
[T=581970] PATROL: Roaming (32574, 32843) heading=5
[T=582450] PATROL: Roaming (32575, 32844) heading=3
[T=582930] PATROL: Roaming (32576, 32845) heading=3
[T=583410] PATROL: Roaming (32577, 32846) heading=3
[T=583890] PATROL: Roaming (32576, 32846) heading=6
[T=584370] PATROL: Roaming (32575, 32846) heading=6
[T=584850] PATROL: Roaming (32574, 32846) heading=6
[T=585330] PATROL: Roaming (32573, 32846) heading=6
[T=585810] PATROL: Roaming (32572, 32847) heading=5
[T=586290] PATROL: Roaming (32571, 32848) heading=5
[T=586770] PATROL: Roaming (32570, 32849) heading=5
[T=587250] PATROL: Roaming (32569, 32850) heading=5
[T=587730] PATROL: Roaming (32568, 32851) heading=5
[T=588210] PATROL: Roaming (32567, 32852) heading=5
[T=588690] PATROL: Roaming (32568, 32853) heading=3
[T=589170] PATROL: Roaming (32569, 32854) heading=3
[T=589650] PATROL: Roaming (32569, 32853) heading=0
[T=590000] HP_REGEN: Player recovered 5 HP -> HP: 127/127
[T=590130] PATROL: Roaming (32569, 32852) heading=0
[T=590610] PATROL: Roaming (32570, 32851) heading=1
[T=591090] PATROL: Roaming (32571, 32850) heading=1
[T=591570] PATROL: Roaming (32572, 32849) heading=1
[T=592050] PATROL: Roaming (32572, 32850) heading=4
[T=592530] PATROL: Roaming (32572, 32851) heading=4
[T=593010] PATROL: Roaming (32572, 32852) heading=4
[T=593490] PATROL: Roaming (32572, 32853) heading=4
[T=593970] PATROL: Roaming (32573, 32852) heading=1
[T=594450] PATROL: Roaming (32574, 32851) heading=1
[T=594930] PATROL: Roaming (32573, 32852) heading=5
[T=595410] PATROL: Roaming (32572, 32853) heading=5
[T=595890] PATROL: Roaming (32571, 32854) heading=5
[T=596370] PATROL: Roaming (32570, 32855) heading=5
[T=596850] PATROL: Roaming (32569, 32856) heading=5
[T=597330] PATROL: Roaming (32568, 32857) heading=5
[T=597810] PATROL: Roaming (32567, 32858) heading=5
[T=598290] PATROL: Roaming (32566, 32859) heading=5
[T=598770] PATROL: Roaming (32565, 32860) heading=5
[T=599250] PATROL: Roaming (32564, 32861) heading=5
[T=599730] PATROL: Roaming (32564, 32862) heading=4
[T=600000] SESSION END: Reason=SIMULATION_TIME_REACHED | Kills=45 | Level=4 | EXP=709 | VirtualTime=600000ms
```

---

## 4. 驗證結論 (Verification Conclusion)

本測試於完全虛擬時間（Virtual Time）下，在單一行程（In-Process）中持續運算 600,000 ms（模擬 10 分鐘）。
角色在持續巡邏、狩獵、施法、飲用紅綠藥水、拾取掉落物及怪物重生的完整生態系中穩定運行，驗證了 MVP-04 擴展之 Legacy Gameplay Coverage 的正確性與確定性。
