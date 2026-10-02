# Player UI Architecture (MVP-06)

## 1. 設計哲學與技術選型

* **技術選型**：純原生 Python 標準函式庫 `tkinter`。
  - 無外部龐大相依（如 PyQt、Electron、React、Node.js）。
  - 在任何標準 Python 3 環境下開箱即用，原生效能極高。
  - 支援無介面測試（Headless Unit Testing via `root.withdraw()`）。
* **單向資料流 (Unidirectional Data Flow)**：
  - UI 僅作為觀察與輸入媒介。
  - UI **絕不直接改動遊戲記憶體與物件**。
  - 所有操作經由 `PlayerViewModel` 封裝成 `PlayerOperation` 送往 `HeadlessPlayerRuntime`。
  - UI 週期性（預設 100ms）向 Runtime 抓取 `PlayerRuntimeSnapshot` 進行單向更新。

---

## 2. 視窗元件配置 (UI Layout)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        L1J Headless Player Client                      │
├───────────────────────────────────┬────────────────────────────────────┤
│           Player HUD              │         Helper Control Bar         │
│  Arthur (Knight) Lv 3             │  Status: [ACTIVE]  Speed: [1.0x v] │
│  HP: [====================] 120/120│  [Pause / Resume Helper]           │
│  MP: [==========          ]  10/20 │  [⚙ Configure Helper Rules]        │
│  Adena: 2,500 | Pos: 32671, 32804  │  Dest: Talking Island Dungeon 1F   │
├───────────────────────────────────┴────────────────────────────────────┤
│                           Main Workspace                               │
│ ┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────────┐ │
│ │   Nearby Monsters    │ │  Manual Actions  │ │      Inventory       │ │
│ │ - Skeleton (120/120) │ │      [ ▲ ]       │ │ Red Potion x45       │ │
│ │ - Werewolf (80/80)   │ │  [ ◄ ] [ ▼ ] [ ►]│ │ Orange Potion x10    │ │
│ │ - Goblin (45/45)     │ │                  │ │ Teleport Scroll x5   │ │
│ │                      │ │ [ Attack Target] │ │ Katana (Equipped)    │ │
│ │ [Target Selected]    │ │ [ Drink Red Pot] │ │ Leather Armor        │ │
│ │ [Attack Selected]    │ │ [ Use Escape]    │ │                      │ │
│ └──────────────────────┘ └──────────────────┘ └──────────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│                       Real-Time Activity Monitor                       │
│ [12.4s] [Arthur] MOVE_STEP to (32672, 32804)                          │
│ [13.2s] [Arthur] ATTACK Skeleton (Dealt 12 dmg, Target HP: 108/120)   │
│ [14.0s] [Arthur] USE_ITEM Red Potion (+30 HP)                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 元件說明

### 3.1 狀態列 (Player HUD)
* 玩家名稱、職業、等級、經驗值比例。
* HP 與 MP 彩色進度條（HP 依比例在綠色、黃色與紅色間動態切換）。
* 目前座標、地圖與金幣 (Adena) 餘額。

### 3.2 輔助狀態與控制 (Helper Control Bar)
* **Helper 狀態燈號**：綠色 `[ACTIVE]` 或黃色 `[PAUSED]`。
* **[Pause / Resume Helper]**：一鍵切換自動化與手動模式。
* **[⚙ Configure Helper Rules]**：開啟多頁標籤設定對話框。
* **獵場目的地下拉選單**：即時切換目標獵場（如說話之島地監 1F 或說話之島地表）。
* **遊戲倍速下拉選單**：支援 0.5x 至 10.0x 及極速 Instant 即時變速。

### 3.3 互動工作區 (Main Workspace)
* **Nearby Monsters**：列出感知半徑內所有存活怪物與血量，支援點選後進行 `Target Selected` 或 `Attack Selected`。
* **Manual D-Pad & Action Buttons**：提供手動移動方向鍵（上、下、左、右）與常用手動按鍵（攻擊、喝水、使用回卷）。
* **Inventory**：列出背包所有物品與裝備狀態，支援雙擊使用。

### 3.4 即時日誌 (Activity Monitor)
* 滾動日誌區，即時顯示戰鬥、移動、拾取、補給與地圖切換事件。

---

## 4. 設定面板 (Config Panel)

提供獨立對話框，分為三大設定分頁：
1. **General & Modules**：輔助模組各別開關（自動選怪、自動攻擊、自動移動、自動喝水、自動回城、自動補給、自動拾取等）。
2. **Potions & Emergency**：各類補血藥水 HP 百分比門檻與緊急回城卷軸觸發 HP 百分比。
3. **Return & Resupply**：回城條件（藥水不足、負重超標）與潘朵拉 (Pandora) 補給目標清單。
4. **Profile 管理**：支援一鍵套用至當前遊戲、載入 JSON 設定檔與另存新設定檔。
