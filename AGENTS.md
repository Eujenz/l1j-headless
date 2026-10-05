# L1J-HEADLESS AGENT RULES & ARCHAEOLOGY-FIRST PROTOCOL

## 1. 核心產品本質與最高原則
- **L1J Headless = 沒有 Legacy Client / JVM 的 Native L1J 1.82 玩家；唯一額外能力，是玩家可以透過設定，把原本手動進行的狩獵操作自動化。**
- 本專案的世界規則唯一真實基準（Ground Truth）是：`C:/Users/p0282768/Documents/Gemini/Lineage182c`（L1J 1.82 Legacy Server Java 源碼、SQL 資料庫與 bytecode）以及 `docs/archaeology/` 考證文件。
- **嚴禁使用任何一般通用 RPG、天堂 2、其他手遊或未經考證的個人直覺/印象來推測或改寫 L1J 1.82 的遊戲規則。**

---

## 2. 防幻覺機制：強制證據先行協議 (Evidence-First Verification Gate)

為杜絕任何 AI 幻覺與憑空捏造規則，所有 Agent 在執行此專案時必須嚴格遵守以下四項鐵律：

### 鐵律一：無實證不推論 (Zero-Assumption Ground Truth)
- 凡涉及「數值、公式、道具效果、狀態倍率、職業限制、時序 (Timing/Cadence/Interval)、冷卻、技能封包、地圖座標與怪物行為」：
  - **嚴禁**憑記憶或預訓練常識直接作答或改寫程式碼。
  - **在寫下任何程式碼修改或斷言之前，必須先以工具（`view_file` 或 `run_command` grep/Select-String）調閱並引用本地 Legacy Ground Truth (`Gemini/Lineage182c` 或 `docs/archaeology/`) 的具體檔案路徑、行號與程式碼片段。**

### 鐵律二：反既有考古代碼倒退 (Anti-Regression on Archaeological Code)
- 本專案既有 Native 代碼中許多邏輯（例如 `effective_move_speed_ms`、`SprTable`、`CheckSpeed` 延遲、`CombatEngine` 公式）已在先前階段經由考古確認。
- 若既有 Native 代碼已經有特定實作，**絕不允許因直覺或懷疑而隨意刪除**。
- 若要修改或刪除既有 Native 規則，**必須先提出具體相反的 Legacy 182c 源碼實證**（明確證明既有實作與 1.82c 源碼衝突），否則視為違規改動。

### 鐵律三：嚴禁在測試中偽造規則 (No Fabricated Test Invariants)
- 單元測試中的 docstring 若標註 `Legacy L1J Invariant` 或 `CONFIRMED_CANONICAL`，**必須附帶真實出處檔案與行號**（例如 `CheckSpeed.java:101-106`、`PotionofBravery.java:30`）。
- 嚴禁為了讓測試通過，同時修改測試與程式碼，將 AI 幻覺包裝為測試通過的「假既定事實」。

### 鐵律四：工作區與 Git 規範
- Git Commit Author 一律嚴格保持：`Eujenz <p2030m@gmail.com>`。
- 遵循四大分層架構：`Layer 1 Evidence -> Layer 2 Native World -> Layer 3 Player Operation -> Layer 4 Configurable Automation`。
- 手動與自動化走完全相同執行路徑（Manual / Helper -> PlayerOperation -> Controller -> Native World）。
