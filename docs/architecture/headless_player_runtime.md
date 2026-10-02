# Headless Player Runtime Architecture

## 1. 系統定位與架構層級

`HeadlessPlayerRuntime` 是 L1J Headless Runtime 的核心外觀層 (Facade Layer)。
它的核心職責是：在不依賴 Legacy Java Server、GUI 遊戲客戶端、JVM、Legacy MySQL 或網路協定的前提下，封裝並提供一個可由玩家即時觀察、介入控制、且隨時可切換自動化輔助 (Helper) 的 Native Runtime。

```text
┌────────────────────────────────────────────────────────┐
│                   User Interface                       │
│    (Desktop Tkinter GUI / Interactive CLI / Scripts)   │
└──────────────────────────┬─────────────────────────────┘
                           │  Snapshot Polling & Commands
                           ▼
┌────────────────────────────────────────────────────────┐
│               HeadlessPlayerRuntime (Facade)           │
│  - Background Worker Thread (run_loop)                 │
│  - Thread-Safe Operations Queue (manual_queue)         │
│  - Runtime State Snapshot Generation                   │
│  - Dynamic Speed Control & Live Config Updates         │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
      Manual Operations          Perception & Helper Policy
               │                          │
               ▼                          ▼
┌────────────────────────────────────────────────────────┐
│                     HeadlessBot                        │
│             (Unified Controller Layer)                 │
│         execute_player_operation(PlayerOperation)      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│               Native L1J World Engine                  │
│   Map / Actor / Monster / Combat / Item / Town / Economy│
└────────────────────────────────────────────────────────┘
```

---

## 2. 核心特性

### 2.1 執行緒安全與背景循環 (Background Worker)
* `HeadlessPlayerRuntime` 內建背景工作執行緒，驅動時鐘 (`RealTimeClock` 或 `VirtualClock`) 與排程器 (`Scheduler`)。
* 透過重入鎖 (`threading.RLock`) 保證在多執行緒環境下讀取狀態快照與輸入手動操作的安全性。

### 2.2 狀態快照機制 (`PlayerRuntimeSnapshot`)
* UI 與外界控制器不直接持有或修改遊戲引擎內部的 `Actor` 或 `World` 物件。
* 每次由 `take_snapshot()` 產生一份不可變的純量/字典快照，包含：
  - 玩家數值：HP/MP、最大 HP/MP、等級、經驗值、座標與地圖編號。
  - 狀態標誌：死亡、麻痺、中毒、輔助暫停狀態。
  - 背包清單：物品編號、名稱、數量、裝備狀態。
  - 週遭怪物：名稱、當前 HP/最大 HP、距離、座標。
  - 當前目標與戰鬥狀態。
  - 獵場目的地與各模組開關狀態。
  - 運作統計與即時活動日誌。

### 2.3 動態速度調節 (Speed Scaling)
* 支援由玩家隨時動態調整遊戲節奏（0.5x, 1.0x, 2.0x, 5.0x, 10.0x, 甚至 Instant）。
* 底層透過 `RealTimeClock.set_time_scale(speed)` 平滑切換，無須重新啟動世界或重設狀態。

### 2.4 即時配置更新 (Live In-Game Config Updates)
* 玩家在遊戲進行中隨時可修改藥水閾值、逃脫血量、補給數量或啟閉特定輔助模組。
* 呼叫 `update_config(new_config)` 後立即生效，完全保留玩家當前所在位置、戰鬥與背包進度。

---

## 3. 手動操作佇列 (Manual Operations Queue)

當玩家透過 UI 發出操作時（如點擊移動、指定目標、攻擊、喝水、使用卷軸）：
1. 外觀層建立對應的 `PlayerOperation`（例如 `MOVE_STEP`, `ATTACK`, `USE_ITEM`）。
2. 將操作排入 `bot.enqueue_manual_operation(op)`。
3. 在下一個時鐘動作判定週期（Action Gate），Controller 優先消耗手動佇列中的操作，直接在原生世界中執行。
4. 手動操作與自動化操作皆完整記錄於 `operations_count` 與 `trace_log` 中。
