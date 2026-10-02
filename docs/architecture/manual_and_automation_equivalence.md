# Manual and Automation Equivalence Contract

## 1. 核心設計原則

在 L1J Headless 中，最高層級的架構原則是：

> **手動操作與自動化操作必須享有完全相同、不可被繞過的原生執行路徑與 Legacy 規則驗證。**

手動玩家並不是神，無法無視遊戲世界的冷卻時間 (Action Gate)、障礙物阻擋 (Map Obstacles)、背包存量或負重限制；而自動化輔助規則 (Helper) 也不擁有任何特權 API。兩者皆被嚴格限制在 `PlayerOperation` 抽象與 `HeadlessBot.execute_player_operation()` 的單一入口之中。

---

## 2. 雙軌等價執行路徑

```text
[Human Player via UI]                   [Helper Policy Engine]
        │                                         │
        │ Click Move / Attack / Potion            │ Observe & Evaluate Rules
        ▼                                         ▼
Construct PlayerOperation               Construct PlayerOperation
        │                                         │
        ▼                                         ▼
enqueue_manual_operation(op)            decide_next_action(...)
        │                                         │
        └─────────────────┬───────────────────────┘
                          │
                          ▼
            HeadlessBot.step() [Action Gate]
                          │
                          ▼
            execute_player_operation(op)
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
Movement Rules      Combat Rules        Item/Town Rules
(Obstacle/Passable) (Hit/Dmg/Cooldown)  (Inventory/Weight)
       │                  │                  │
       └──────────────────┴──────────────────┘
                          │
                          ▼
                  Native L1J World
```

---

## 3. 等價性不變式 (Invariants)

1. **單一入口點 (Single Chokepoint)**：
   不論操作來源是真人點擊 GUI 還是策略引擎判定，所有動作一律包裝為 `PlayerOperation(type, ...)` 並送入 `execute_player_operation(op)`。UI 絕對不具備直接改動角色數值或世界狀態的權限。

2. **時鐘與節奏約束 (Timing Invariance)**：
   手動發送的攻擊與移動同樣受到 Native Engine 的動作間隔 (Action Cooldowns / Action Gate) 約束。如果在攻擊冷卻中手動點擊攻擊，動作將在冷卻結束後於下一個有效 Action Gate 排程執行，無法違規超速。

3. **物理與規則約束 (Rule Invariance)**：
   - 手動移動如果點選不可通行的障礙或牆壁，同樣會觸發碰撞判定失敗而無法前進。
   - 手動使用藥水如果背包數量為 0，操作將無法生效。
   - 死亡或麻痺狀態下手動操作同樣會被引擎拒絕。

4. **度量與審計一致性 (Metric Invariance)**：
   手動操作與自動化操作共同計入 `operations_count`（例如 `MOVE_STEP`, `ATTACK`, `USE_ITEM`），並產生相同格式的即時追蹤日誌 (`trace_log`)。
