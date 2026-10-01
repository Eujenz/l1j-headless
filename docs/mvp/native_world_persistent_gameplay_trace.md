# L1J 1.82 Multi-Actor Persistent Native World Gameplay Trace (MVP-03)

## 1. 執行概要 (Executive Summary)

- **執行模式**: In-Process Native Headless World Simulation (Multi-Actor Autonomous Scheduler)
- **隨機種子 (Deterministic Seed)**: `777777`
- **地圖**: Map 0 (Talking Island Surface)
- **虛擬時間跨度 (Virtual Time)**: `600000 ms` (10.0 simulated minutes)
- **終止原因**: `SIMULATION_TIME_REACHED`
- **怪物擊殺數**: `44 kills`
- **怪物重生次數 (Respawns)**: `44 times`
- **角色最終等級與經驗**: `Lv4 (EXP: 636)`
- **角色最終血量**: `128/128 HP`
- **總造成傷害**: `573 dmg`
- **總承受傷害**: `44 dmg`
- **拾取道具數量**: `0 items`

---

## 2. 核心機制驗證 (Core Mechanics Validated)

### 2.1 Multi-Actor Concurrency & Autonomous Monster AI
- 玩家與多隻怪物共存於同一虛擬地圖。
- 怪物具備自主 AI：在感知或受擊時鎖定目標，以 `modespeed(0)` 追擊、以 `modespeed(1)` 攻擊。
- 怪物攻擊與反擊不再由玩家 step 內部同步呼叫，而是獨立排程於 `VirtualClock` 之 `Scheduler` 佇列。

### 2.2 Monster Respawn Lifecycle
- 怪物陣亡後即時觸發 `despawn`，並在 `Scheduler` 註冊重生事件。
- 重生事件到期後，透過 `PopulationManager.respawn_monster` 於有效座標重生滿血怪物。

### 2.3 Natural HP/MP Regeneration Event
- 伺服器世界每 10,000 ms (`HpMpTimer.java:48-73`) 觸發獨立定時回血事件（`HP_REGEN`），角色自然回復 5 HP。

### 2.4 Dynamic PC Action Timing Resolution
- PC 攻擊間隔不再寫死固定常數，而是由 `Player GFX + Action + Weapon` 動態解析（GFX 48 女騎士單手劍 = 920ms，GFX 61 男騎士單手劍 = 880ms）。

---

## 3. 代表性日誌節錄 (Representative Event Trace Snippets)

```text
[T=000000] PLAYER SPAWN: Arthur (Lv1 HP:100/100) at Map 0 (32477, 32875) with Long Sword
[T=000000] MOVE: Advanced to (32476, 32876) heading=5
[T=000030] MONSTER MOVE: Orc advanced to (32475, 32877) pursuing Player
[T=000640] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=000640] DAMAGE RESOLVED: Player→Orc: HIT for 1 dmg (IMMEDIATE) | Target HP: 5/6
[T=000830] MONSTER ATTACK: Orc→Player for 4 dmg | Player HP: 96/100
[T=001560] ATTACK TRIGGERED: Player attacks Orc (HP: 5/6)
[T=001560] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 5/6
[T=002150] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 96/100
[T=002480] ATTACK TRIGGERED: Player attacks Orc (HP: 5/6)
[T=002480] DAMAGE RESOLVED: Player→Orc: HIT for 5 dmg (IMMEDIATE) | Target HP: 0/6
[T=002480] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 5)
[T=003400] MOVE: Advanced to (32477, 32875) heading=1
[T=004040] MOVE: Advanced to (32477, 32874) heading=0
[T=004680] MOVE: Advanced to (32477, 32873) heading=0
[T=005320] MOVE: Advanced to (32477, 32872) heading=0
[T=005350] MONSTER MOVE: Orc advanced to (32478, 32871) pursuing Player
[T=005960] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=005960] DAMAGE RESOLVED: Player→Orc: HIT for 6 dmg (IMMEDIATE) | Target HP: 0/6
[T=005960] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 10)
[T=006880] MOVE: Advanced to (32478, 32871) heading=1
[T=007520] MOVE: Advanced to (32479, 32870) heading=1
[T=007550] MONSTER MOVE: Orc advanced to (32480, 32869) pursuing Player
[T=008160] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=008160] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 6/6
[T=008350] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 96/100
[T=009080] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=009080] DAMAGE RESOLVED: Player→Orc: MISS for 0 dmg (IMMEDIATE) | Target HP: 6/6
[T=009670] MONSTER ATTACK: Orc→Player for 0 dmg | Player HP: 96/100
[T=010000] HP_REGEN: Player recovered 5 HP -> HP: 100/100
[T=010000] ATTACK TRIGGERED: Player attacks Orc (HP: 6/6)
[T=010000] DAMAGE RESOLVED: Player→Orc: HIT for 3 dmg (IMMEDIATE) | Target HP: 3/6
[T=010920] ATTACK TRIGGERED: Player attacks Orc (HP: 3/6)
[T=010920] DAMAGE RESOLVED: Player→Orc: HIT for 4 dmg (IMMEDIATE) | Target HP: 0/6
[T=010920] MONSTER DIED: Orc slain! Granted +5 EXP (Total EXP: 15)
[T=011840] MOVE: Advanced to (32478, 32869) heading=7
[T=012480] MOVE: Advanced to (32478, 32868) heading=0
[T=012510] MONSTER MOVE: Slime advanced to (32482, 32857) pursuing Player
[T=013120] MOVE: Advanced to (32478, 32867) heading=0
[T=013310] MONSTER MOVE: Slime advanced to (32481, 32858) pursuing Player
...
[中間省略數百筆巡邏、交戰、拾取與重生事件]...
[T=565880] ATTACK TRIGGERED: Player attacks Goblin (HP: 9/9)
[T=565880] DAMAGE RESOLVED: Player→Goblin: HIT for 7 dmg (IMMEDIATE) | Target HP: 2/9
[T=566030] MONSTER ATTACK: Goblin→Player for 0 dmg | Player HP: 128/128
[T=566800] ATTACK TRIGGERED: Player attacks Goblin (HP: 2/9)
[T=566800] DAMAGE RESOLVED: Player→Goblin: HIT for 6 dmg (IMMEDIATE) | Target HP: 0/9
[T=566800] MONSTER DIED: Goblin slain! Granted +5 EXP (Total EXP: 636)
[T=567720] PATROL: Roaming (32510, 32899) heading=4
[T=568360] PATROL: Roaming (32510, 32900) heading=4
[T=569000] PATROL: Roaming (32510, 32901) heading=4
[T=569640] PATROL: Roaming (32509, 32900) heading=7
[T=569800] RESPAWN: Orc respawned at (32492, 32861) HP: 6/6
[T=570280] PATROL: Roaming (32508, 32899) heading=7
[T=570920] PATROL: Roaming (32507, 32898) heading=7
[T=571560] PATROL: Roaming (32506, 32899) heading=5
[T=572200] PATROL: Roaming (32505, 32900) heading=5
[T=572840] PATROL: Roaming (32504, 32901) heading=5
[T=573480] PATROL: Roaming (32503, 32902) heading=5
[T=574120] PATROL: Roaming (32502, 32903) heading=5
[T=574760] PATROL: Roaming (32503, 32903) heading=2
[T=575400] PATROL: Roaming (32504, 32903) heading=2
[T=576040] PATROL: Roaming (32503, 32903) heading=6
[T=576680] PATROL: Roaming (32502, 32903) heading=6
[T=577320] PATROL: Roaming (32501, 32903) heading=6
[T=577960] PATROL: Roaming (32501, 32902) heading=0
[T=578600] PATROL: Roaming (32501, 32901) heading=0
[T=579240] PATROL: Roaming (32502, 32901) heading=2
[T=579600] RESPAWN: Orc respawned at (32503, 32871) HP: 6/6
[T=579880] PATROL: Roaming (32503, 32901) heading=2
[T=580520] PATROL: Roaming (32504, 32901) heading=2
[T=581160] PATROL: Roaming (32505, 32901) heading=2
[T=581800] PATROL: Roaming (32506, 32900) heading=1
[T=582440] PATROL: Roaming (32507, 32899) heading=1
[T=583080] PATROL: Roaming (32507, 32900) heading=4
[T=583720] PATROL: Roaming (32507, 32901) heading=4
[T=585000] PATROL: Roaming (32506, 32901) heading=6
[T=585640] PATROL: Roaming (32505, 32901) heading=6
[T=586280] PATROL: Roaming (32504, 32901) heading=6
[T=586920] PATROL: Roaming (32503, 32900) heading=7
[T=587560] PATROL: Roaming (32502, 32899) heading=7
[T=588200] PATROL: Roaming (32502, 32898) heading=0
[T=588840] PATROL: Roaming (32502, 32897) heading=0
[T=589480] PATROL: Roaming (32502, 32896) heading=0
[T=590120] PATROL: Roaming (32502, 32895) heading=0
[T=590760] PATROL: Roaming (32501, 32894) heading=7
[T=591400] PATROL: Roaming (32500, 32893) heading=7
[T=592040] PATROL: Roaming (32499, 32892) heading=7
[T=592680] PATROL: Roaming (32498, 32891) heading=7
[T=593320] PATROL: Roaming (32497, 32890) heading=7
[T=593960] PATROL: Roaming (32496, 32889) heading=7
[T=594600] MOVE: Advanced to (32497, 32888) heading=1
[T=595240] MOVE: Advanced to (32498, 32887) heading=1
[T=595880] MOVE: Advanced to (32499, 32886) heading=1
[T=596520] MOVE: Advanced to (32500, 32885) heading=1
[T=596800] RESPAWN: Goblin respawned at (32491, 32888) HP: 9/9
[T=597160] MOVE: Advanced to (32499, 32886) heading=5
[T=597800] MOVE: Advanced to (32498, 32887) heading=5
[T=598440] MOVE: Advanced to (32497, 32888) heading=5
[T=599080] MOVE: Advanced to (32496, 32888) heading=6
[T=599720] MOVE: Advanced to (32495, 32888) heading=6
[T=600000] SESSION END: Reason=SIMULATION_TIME_REACHED | Kills=44 | Level=4 | EXP=636 | VirtualTime=600000ms
```
