# Scenario 007.1 — Playtest & Authenticity Audit Report

**Generated**: 2026-10-01  
**Target Repository**: `Eujenz/l1j-headless`  
**Reference Repository**: `Eujenz/182c` (Commit: `7eeacbc`)  
**Scope**: Codebase Authenticity Audit, Fidelity Gap Analysis & Human Playtest Preparation

---

## 0. Executive Summary

本文件是在 Scenario 007 自動化認證通過後，針對當前 Headless Runtime 進行的深度技術審查報告。
本階段嚴格遵守規範：**禁止擴充未認證之新系統（無 NPC、無 Quest、無 Spell、無大型背包），專注於核心模擬之真實度（Fidelity）、邊界語義（Semantics）與人類遊玩感官審計（Playtest Audit）。**

---

## 1. 核心系統技術稽核 (Technical Audit)

### A. Spawn Collision Validation (怪物生成碰撞檢驗)
- **Legacy 考古對照**：
  Legacy `MonsterSpawnTable.java` (L128-151) 在讀取 `monster_spawnlist` 進行怪物的隨機落點計算時，會以 `do { ... } while (c < 50)` 進行最多 50 次重試：
  每次候選座標均透過 `WorldMap.getInstance().IsThroughObject(...)` 檢查周圍 8 個方向是否為可站立/非牆壁磁磚；若 50 次嘗試皆失敗（`c >= 50`），該隻怪物**直接放棄生成（Dropped）**。
- **Native 實作稽核與修正**：
  在本次 S007.1 審查中，我們為 `PopulationManager.initialize_population()` 補上了 real `WorldMapGrid` 碰撞驗證：
  候選座標會透過 `map_grid.is_in_bounds(cand_x, cand_y)` 及 `can_move(grid, cand_x, cand_y, h)` 檢查至少有一方向可行（非全阻擋靜態牆體）。
- **實證結果**：
  在種子 `777777` 下，Map 0 與 Map 1 的 182 隻怪物全部在 50 次重試內成功找到合法且可站立的幾何位置，0 隻掉出地圖或生成於靜態牆壁中。
- **分類判定**：`LEGACY_OBSERVED`（邏輯已完整還原 Legacy 重試上限與碰撞過濾語義）。

---

### B. Spawn Random vs. `loc_size` (`random` 欄位語義區分)
- **Legacy 考古對照**：
  在 Legacy `monster_spawnlist.sql` 中，同時存在 `loc_size` 與 `random` 欄位：
  - `loc_size`（整數）：決定**初始伺服器啟動**時怪物分佈的矩形半徑（`x ± loc_size`, `y ± loc_size`）。若 `loc_size == 0`，代表以地圖全圖邊界（`MAP.get_locX1()` ~ `MAP.get_locX2()`）隨機分佈。
  - `random`（字串/布林值）：在 `MonsterSpawnTable.java:105` 載入為 `mon.setSpawnRandom("true".equalsIgnoreCase(rs.getString("random")))`，用於控制**怪物死亡後 Respawn** 的位置策略（true 代表重新在全範圍隨機散佈，false 代表在 Home 點原處生成）。
- **Native 現狀與限制 (Limitation)**：
  - Native 已完整重現 `loc_size > 0` 與 `loc_size == 0` 的初始散佈幾何語義。
  - 由於目前 MVP 獵殺流程中怪物死亡後採確定性 Despawn（未啟動 MMO 常駐 Respawn 背景排程），`random` 欄位目前在 Native Runtime **尚未參與死亡重生運算**。
- **分類判定**：
  - 初始生成：`LEGACY_OBSERVED`
  - Respawn Random：`KNOWN LIMITATION (DEFERRED)`

---

### C. `agro` vs. `attack` (主動追擊與反擊語義)
- **Legacy 考古對照**：
  Legacy `MonsterTable.java:57, 62` 分別載入：
  - `agro`: `mon.setAgro((rs.getInt("agro") == 1))`
  - `attack`: `mon.setAttack((rs.getInt("attack") == 1))`
  在 `MonsterInstance.java:317`：
  ```java
  if (getMon().isAttack() && FightStart())
  ```
  - `attack == 1`：怪物具有自主搜尋攻擊目標的 AI 能力。
  - `agro == 1`：怪物具有主動敵意（在 `FightStart()` 中 12 格範圍內主動索敵）。
  - 若 `attack == 0`（如妖魔、侏儒、青蛙、漂浮之眼）：怪物不會主動發動 `FightStart()` 搜尋玩家；但當玩家主動發動攻擊時，只要怪物的 `min_dmg/max_dmg > 0`，怪物依然會進入戰鬥反擊！
- **Native 實作對照**：
  - `EncounterSystem.check_encounter()` 依據 `agro` 判定怪物是否會向路過的玩家主動發動突襲。
  - `CanonicalCombat` 與 `GameSession._run_auto_combat()` 則確保所有受到攻擊且具備傷害力的怪物（不論被動主動）皆會依 Legacy 傷害公式進行反擊。
- **分類判定**：`LEGACY_OBSERVED`

---

### D. Encounter Radius (遭遇檢測半徑)
- **Legacy 考古對照**：
  Legacy `MonsterInstance.java:184` 使用 `getDistance(o.getX(), o.getY(), o.getMap(), 12)` 作為怪物感知玩家的最大視距（約 1 個螢幕半徑）。
- **Native 實作分類**：
  - `radius = 2`（切比雪夫近身接觸距離）：
    用於旅行途中（`_travel_encounter_hook`）路過怪物身邊的即時接觸檢測。
    分類標記：`CONTROLLED_SUBSTITUTION`（為防止長途行軍被過遠怪物頻繁打斷所採取的局部感知抽象，非 Legacy 原始 12 格全螢幕視距）。
  - `hunt radius = 20`：
    用於玩家抵達狩獵區後，搜尋視線內目標怪物的宏觀搜索半徑。
    分類標記：`MODERN_DESIGN`（玩家自動索敵意圖的高層級輔助，方便連續獵殺）。

---

### E. Travel Encounter (行軍途中遭遇中斷與恢復)
- **Native 實作架構**：
  在 `WorldRouteExecutor.execute_with_encounter_hook` 與 `AutonomousNavigator.goto_with_hook` 中：
  1. 玩家由起點開始執行 A* 步進。
  2. 每移動一格，觸發 `encounter_hook()`。
  3. 若周圍 2 格內有怪物，立刻暫停移動，進入 `_run_auto_combat()`。
  4. 戰鬥結束、怪物死亡、玩家獲取 EXP 並處理可能的 LevelUp 後，**不會傳送或跳步**，而是維持在當前格子，繼續執行剩餘的導航步進。
  5. 抵達傳送點 (32477, 32851) 時觸發 `PortalTriggered`，原子轉移至地監 1F (32669, 32802)，再繼續第二段地監內導航至目標點。
- **分類判定**：`DERIVED_CANONICAL`

---

### F. Critical Equipment Audit (裝備與 items.sql 欄位審計)

透過對 `db/lineage/items.sql` 的比對，當前裝備系統支援度如下：

| 欄位名稱 | Legacy 意義 | Native 支援狀態 | 備註說明 |
| :--- | :--- | :--- | :--- |
| `dmg_small` | 對小型怪傷害上限 | ✅ **SUPPORTED** | 完整納入 `CanonicalCombat` 武器骰 |
| `dmg_large` | 對大型怪傷害上限 | ✅ **SUPPORTED** | 完整納入 `CanonicalCombat` 武器骰 |
| `enchant` | 強化等級 (+0~+9) | ✅ **SUPPORTED** | 完整反映在命中補正與傷害基底 |
| `bless` | 祝福狀態 (0:封印 1:一般 2:祝福) | ✅ **SUPPORTED** | S001 認證保留 |
| `weapon_type` | 武器類型 | ✅ **SUPPORTED** | 識別 Slot 11 武器裝備 |
| `add_hit` | 武器額外命中加成 | ❌ **UNSUPPORTED** | **KNOWN GAP**：尚未計入 `HitFigure` |
| `add_dmg` | 武器額外固定傷害 | ❌ **UNSUPPORTED** | **KNOWN GAP**：尚未計入 `DmgWeaponFigure` |
| `two_hand` | 雙手武器標記 | ❌ **UNSUPPORTED** | **KNOWN GAP**：盾牌系統尚未開放，目前不影響 |
| `add_str/dex/con` | 裝備力量/敏捷/體質加成 | ❌ **UNSUPPORTED** | **KNOWN GAP**：角色數值尚未聯動裝備屬性 |
| `safe_enchant` | 安定值 | ❌ **UNSUPPORTED** | 強化系統不在 MVP 範圍 |

> **誠實聲明**：目前 Native 裝備系統僅完整保證 `dmg_small`、`dmg_large`、`enchant`、`bless` 與武器更換帶來的傷害變化。不得宣稱「100% 完整 Legacy 裝備系統」。

---

### G. Progression Audit (經驗值與升級審計)
- **ExpTable 門檻**：
  `1: 20`, `2: 45`, `3: 80`, `4: 630`, `5: 1296`。100% 來自 Legacy `exp.sql` 的 `cumulative_bonus` 欄位。
- **升級 HP 成長**：
  Legacy 騎士公式為 `max(6, con - 9) + rand(1, 6)`。Native 使用確定性 PRNG 取樣，並在升級當下重現 Legacy 之「HP 完全恢復至新 MaxHP」機制。
- **分類判定**：`LEGACY_OBSERVED`（門檻與滿血機制）+ `CONTROLLED_SUBSTITUTION`（RNG 取樣採 NativeRng 確定性種子）。

---

### H. Differential Claim Audit (差分宣稱精確化)
- **審計修正**：
  `scenario_007_differential.py` 的 Level 5 測試項原先命名為「Autonomous Simulation Outcome」。經審查，其預期數值（Lv3, 112 EXP, 7 kills）是由合約模擬定義之期望基準，而非由未經修飾的 Legacy Java Server 所輸出。
- **修正措施**：
  已將 Level 5 正式改名為：
  **`Level 5: Canonical Scenario Outcome & Contract Validation`**
  明確向審查者傳達此項為「針對確定性合約狀態之端到端驗證」，避免誤導為「與 Java MMO Server 之黑箱即時對齊」。

---

## 2. 已知真實度落差總整理 (Known Fidelity Gaps)

1. **怪物移動追擊 AI (Monster Pursuit AI)**：
   目前怪物在生成後維持於固定坐標等待接觸或遭遇，尚未具備主動走向玩家的每 tick 自主巡邏/追擊 AI（Legacy 使用 `MonsterInstance.toFight()` 每 tick 向目標尋路移動）。
2. **武器額外加成 (`add_hit` / `add_dmg`)**：
   `items.sql` 中的額外命中與額外傷害尚未進入 `CanonicalCombat`。
3. **視野感知半徑 (Aggro Radius)**：
   行軍遭遇採用切比雪夫 2 格近身感知，非 Legacy 之 12 格全螢幕視距。
4. **Respawn 排程**：
   目前擊殺後採即時 Despawn，未實作長態計時重生隊列。

---

## 3. Human Playtest 準備與指引

CLI 入口點已完成全面準備，預設直接啟動真實 S007 路徑，並支援隨機種子覆寫：

```bash
# 1. 互動遊玩入口（預設 S007 話島世界）
python mvp.py

# 2. 指定確定性種子遊玩
python mvp.py --seed 777777

# 3. 觀看完整端到端獵殺示範
python mvp.py --demo --s007 --seed 777777
```

使用者進行 Playtest 的具體操作流程與反思題目，請參閱根目錄之 [`PLAYTEST.md`](file:///c:/Users/p0282768/Documents/l1j-headless/PLAYTEST.md)。
