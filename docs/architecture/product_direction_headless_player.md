# 產品方向與最高架構依據：Headless Player ≈ Real Legacy L1J Player + Configurable Automation

本文件為 `l1j-headless` 專案所有後續開發與架構設計的**最高層級依據**。

---

## 1. 核心產品目標

> **在不依賴 Legacy Java Server、Legacy Client、JVM、GUI Client、Legacy MySQL Runtime、Live Network Protocol 的情況下，讓 Native Headless Player 以盡可能接近真實 L1J 1.82 玩家操作、邏輯與遊玩體驗的方式進行遊戲。**

Headless 與真實 Legacy 玩家最大的差別只有：

> **原本需要玩家反覆手動操作的狩獵行為，可以由玩家透過 UI / Configuration 設定自動執行。**

概念上等同：

```text
Real L1J Player
+
Legacy-compatible helper / bot configuration
```

而不是：

```text
Generic AI Agent
```

也不是：

```text
Game Strategy Optimizer
```

---

## 2. 核心架構流程

```text
Legacy L1J Behavior (Eujenz/182c)
        ↓
Native L1J World
        ↓
Headless Player
        ↓
Player Operation (Action Model)
        ↓
Configurable Automation (Helper / Policy)
        ↓
Continuous Gameplay
```

---

## 3. 四層架構定義 (The Four Layers)

### Layer 1 — Legacy Evidence
* **Canonical 來源**：`Eujenz/182c`
* **範疇**：
  * Legacy gameplay rules
  * Legacy data & sql
  * Legacy timing & animations
  * Legacy item behavior
  * Legacy NPC behavior & shop catalog
  * Legacy map behavior & portals
  * Legacy combat formulas & dice rolls
  * Legacy death & respawn coordinates
  * Legacy economy & drop rates
* **原則**：所有可驗證的 L1J 1.82 行為優先從此層取得。不得自行發明現代數值或猜想。

### Layer 2 — Native L1J World
* **職責**：以純 Python / Native In-Process 形式，忠實執行 L1J 1.82 的世界規則。
* **包含元件**：
  * World, Map, Collision Grid
  * Movement, Pathfinding (A* with line-of-sight)
  * Monster AI, Spawning, Aggro
  * Combat, Damage calculation, Weapon speed
  * Skills, Spells
  * Items, Inventory, Weight
  * Drops, EXP, Level progression
  * Status, HP/MP Regeneration
  * Potion consumption & cooldowns
  * NPC, Shop, Economy
  * Death, Respawn, Teleportation
  * Virtual Temporal Runtime (Deterministic Virtual Clock)
* **原則**：這些機制只能表達 L1J 1.82 Legacy semantics，不包含任何玩家個人偏好或策略決策。

### Layer 3 — Player Operation
* **職責**：描述「一個真實玩家可以對 L1J 世界做什麼」。
* **定位**：這**不是 AI**，而是 **Player Action Model**。
* **基本操作集合**：
  * `MOVE` (走步、尋路)
  * `ATTACK` (選取目標並近戰/遠攻)
  * `SELECT_TARGET` (視野內怪物選取)
  * `CAST_SKILL` (施放法術)
  * `USE_ITEM` (雙擊使用藥水、卷軸)
  * `LOOT` (拾取地表掉落物)
  * `TALK_NPC` (與 NPC 對話)
  * `BUY` / `SELL` (商店交易)
  * `TRAVEL` / `TELEPORT` (地圖走動、使用瞬卷、穿越傳送門)
  * `EQUIP` / `UNEQUIP` (更換裝備)

### Layer 4 — Configurable Automation
* **職責**：玩家決定哪些 Player Operation 要由系統自動執行。
* **定位**：等同經典的天堂外掛 / 輔助工具（例如參考成熟外掛專案架構如 `r0ptik/L1J-3.8-launcher` 的設定思維），讓玩家配置自動化條件：
  * 喝水規則（如 HP < 70% 喝紅水，HP < 40% 喝澄水，指定冷卻時間）
  * 緊急逃跑（如 HP < 20% 使用回城卷軸）
  * 回城補給（如紅水 < 10 瓶或負重過重時回城）
  * 商店採購（回村後至指定 NPC 補滿紅水至 50 瓶、綠水至 20 瓶）
  * 狩獵出發（補給完成自動前往指定地圖繼續狩獵）

---

## 4. 關鍵設計戒律 (Core Tenets)

1. **Automation 不等於 Optimization**：
   * 禁止設計任何「自動尋找最高 EXP」、「自動計算最高利潤」、「自動尋找最佳地圖/職業」、「動態最佳化喝水」等 AI 最佳化演算法。
   * 玩家自己設定選擇，Native World 忠實運算與執行。
2. **入不敷出與失敗是合法的遊戲結果**：
   * 狩獵賺得的金幣少於買藥水的支出（如 Earned = 235, Spent = 1110, Net = -875）是完全正常的遊戲體驗。
   * 絕不因此修改 drop rate、shop price、potion effect 或 monster stats。
   * 絕不讓 Bot 自動改寫策略去「救」玩家。
   * 玩家因配置不當導致死亡、破產、虧損或效率低落，完全屬於合法真實的遊戲產出。
3. **絕對禁止策略硬編碼 (No Hardcoding)**：
   * 禁止在 Engine 內寫入 `if red_potions < 3: return_town()` 或 `if hp < 25: use_escape_scroll()`。
   * 所有判斷必須由 Config 載入並進行規則比對。
4. **驗證以 Virtual Duration 為核心**：
   * 驗證不再以「殺滿 N 隻怪」為終點，而是以「連續執行 30 分鐘 / 1 小時 / 8 小時虛擬時間」為真實遊玩標準，觀察其持續性、回城補給、死亡復原等綜合運作狀態。
5. **最終檢驗原則**：
   > **「這個功能是在讓 Native Headless Player 更接近一個真實 L1J 1.82 玩家，還是在讓我們自己發明一個新的 AI 遊戲？」**
   * 若是前者：繼續。
   * 若是後者：停止，重新評估。

---

## 5. 一句話核心定義

> **L1J Headless = 一個沒有 Legacy Client / JVM 的 Native L1J 1.82 玩家；唯一額外能力，是玩家可以透過設定把原本手動進行的狩獵操作自動化。**
