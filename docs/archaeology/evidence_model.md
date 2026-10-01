# Legacy Evidence Corpus & Provenance Model

## 1. 核心原則 (Core Philosophy)

在 `l1j-headless` 中，世界的行為規則必須建立在明確的歷史證據之上。
我們嚴格區分**「世界規則的歷史證據」(Legacy Evidence)** 與 **「系統實作的外部架構參考」(Architecture Reference)**。

```text
Legacy Evidence
       ↓
Archaeology / Evidence Index
       ↓
Evidence Classification
       ↓
Canonical Contract
       ↓
Native World Rules
       ↓
Headless Game Runtime
       ↓
Autonomous Agent
```

---

## 2. 證據分類法 (Evidence Classification Taxonomy)

每一個被納入專案或引用的陳述（Claim），必須標註以下精確分類之一：

| 分類代碼 | 說明 | 範例 / 適用情境 |
| :--- | :--- | :--- |
| `LEGACY_OBSERVED` | 1.82/1.83 官方或代表性 Server 源碼或資料庫直接證明 | `CharacterStatDice.java` 決定骰點；`exp.sql` 等級門檻 |
| `LEGACY_CLIENT_OBSERVED` | Client 檔案或資產直接觀察到的數據 | `TW13081901.txt` 中的 Action 結構、幀數序列 |
| `CROSS_VERSION_AUXILIARY` | 跨版本輔助資訊（如 3.80 client），供啟發但**不可**直接視為 1.83 canonical | 3.80 的 `framerate(36)` 僅為輔助線索 |
| `DERIVED_CANONICAL` | 由多項相互驗證的 Legacy 證據共同支撐的抽象結論 | 由 `sprite_frame.sql` 與 `CheckSpeed.java` 共同確定的動作間隔 |
| `CONTROLLED_SUBSTITUTION` | 原生端為了確定性或無頭化所做的受控替換 | 確定性 PRNG 初始座標放置代替隨機啟動 |
| `MODERN_DESIGN` | 為了 Headless Runtime 或 AI Agent 所設計的新架構 | `SimulationClock`、`TaskScheduler`、`TargetSelector` |
| `INFERRED` | 強力推論或合理假說，但尚無直接代碼證實 | 特殊怪物的索敵行為猜想 |
| `UNKNOWN` | 目前證據不足，保留未知，絕不任意虛構數值 | 某些未公開動作的真實伺服器驗收窗口 |
| `EXTERNAL_ARCHITECTURE_REFERENCE` | 外部開源專案僅供 Agent/Task 架構參考，**絕非 L1J 規則** | OpenKore 的 `AI::CoreLogic`、`Task::Route` |

> [!WARNING]
> **嚴格禁止將 `EXTERNAL_ARCHITECTURE_REFERENCE` 標示為 `LEGACY_OBSERVED`！**
> OpenKore 是 Ragnarok Online 的外掛機器人架構參考，絕不可作為天堂（Lineage）的世界規則或時間尺度依據。

---

## 3. 證據來源層級 (Evidence Source Hierarchy)

專案中的歷史來源清單與 SHA256 雜湊碼統一由以下檔案管理：
- `legacy/manifests/legacy_sources.json`
- `legacy/manifests/source_hashes.json`

層級優先順序：
1. **`SERVER_1.82`**：Lineage 1.82c Java 伺服器源碼與資料庫匯出檔 (`Eujenz/182c`)。
2. **`MAP_1.82`**：解碼的地圖幾何與穿透性二進位快取 (`maps.csv`, `0.data`, `1.data`)。
3. **`CLIENT_3.80`**：3.80 臺灣客戶端動畫與精靈定義檔 (`TW13081901.txt`)，定位為跨版本輔助線索。
4. **`EXTERNAL_REFERENCE`**：外部軟體架構參考 (`OpenKore`)。

---

## 4. 追溯性契約 (Provenance Contract)

所有自 Legacy 來源提取出的結論必須包含以下元數據結構：
```yaml
claim: "結論陳述"
source: "legacy-source-id"
version: "3.80 / 1.82c"
layer: "client / server / database"
classification: "LEGACY_CLIENT_OBSERVED_3_80 / DERIVED_CANONICAL"
target_version: "1.83"
raw_evidence: "檔案路徑:行號範圍"
sha256: "來源檔案之雜湊碼"
notes: "相關背景說明"
```
