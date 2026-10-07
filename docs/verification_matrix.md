# L1J-HEADLESS 驗證矩陣與職責切分規範 (Verification Matrix)

本文件定義 L1J Headless 專案中「**自動化腳本自行驗證**」與「**Agent / 人工語意驗證**」的清晰邊界、執行工具、驗收標準與對抗審查機制。

---

## 1. 雙軌驗證架構 (Dual-Track Verification)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        雙軌驗證體系架構                                │
├───────────────────────────────────┬────────────────────────────────────┤
│   自動化腳本驗證 (Deterministic)  │   Agent / 人工驗證 (Semantic/Feel) │
│   - 機器可精確度量                │   - 需源碼考古與人工判斷           │
│   - 回歸防禦、效能預算、公式比對  │   - 真偽查證、手感體感、防偽測試   │
│   - 觸發時機：每次 Commit、CI     │   - 觸發時機：Level 2 核心改動     │
└───────────────────────────────────┴────────────────────────────────────┘
```

---

## 2. 軌道一：腳本自行驗證項目 (Automated Verification)

由自動化測試腳本執行，**不需要人工或 Agent 肉眼逐行審查**，指標必須 100% 通過（Green）。

| 類別 | 驗證範疇 | 驗證目標與指標 | 對應測試腳本 / 指令 |
| :--- | :--- | :--- | :--- |
| **數值與公式** | 6 維屬性、AC、MR、負重 | 總值計算、敏捷 AC 階梯、精神魔防、負重 30 階條公式 | `python -m unittest tests/test_player_operation.py` |
| **戰鬥與時序** | 攻擊/移動間隔、冷卻時間 | 騎士單手劍 920ms、走速 640ms/480ms，冷卻未滿禁止攻擊 | `python -m unittest tests/test_combat.py` |
| **地圖與導航** | 障礙碰撞、地圖邊界、A* 尋路 | SBM 地圖阻擋判定正確、合法走步、跨地圖傳送點切換 | `python -m unittest tests/test_map_decoder.py` |
| **契約與分層** | 操作隊列、執行路徑 | 手動與自動化全數走 `PlayerOperation -> Controller` | `python -m unittest tests/test_controller.py` |
| **裝備約束** | 14 格固定槽位互斥 | 單手盾與雙手武器互斥、雙戒指依序配戴、部位防具單一 | `python -m unittest tests/test_equipment.py` |
| **效能預算** | GUI 渲染與 Snapshot 時間 | Snapshot 生成 $< 5\text{ms}$，Canvas 重繪 $\approx 12\text{FPS}$，無主線程阻塞 | `python -m unittest tests/test_player_ui_performance.py` |
| **全系統回歸** | 全場景完整驗證 | 180+ 項回歸測試全數通過，無 Regression | `python -m unittest discover tests` |

---

## 3. 軌道二：Agent / 人工語意驗證項目 (Semantic Verification)

此類項目無法單憑 `assert` 判定真偽，必須由 Agent 或人類依據 Ground Truth 嚴格查核。

| 審查維度 | 核心核查點 | 為什麼不能單靠腳本？ | 核查標準與基準來源 |
| :--- | :--- | :--- | :--- |
| **規則真偽 (Ground Truth)** | 新增/修改的數值與機制是否真實存在於 1.82c？ | 腳本只確認 `code == test`，無法得知該數值是否為 AI 憑空捏造。 | 必須調閱 `Lineage182c` 具體檔案路徑與行號（如 `CheckSpeed.java`、`PcInventory.java`）。 |
| **防偽測試 (Anti-Fabrication)** | 測試中的 Invariant 是否被偷偷放水修改？ | AI 容易同時修改代碼與測試，包裝為假綠燈。 | 檢查測試變更是否更動了 `CONFIRMED_CANONICAL` 斷言，若有必須有源碼反證。 |
| **架構不變量 (Layer Invariant)** | UI 是否直接侵入 Native World 內部狀態？ | 測試可能忽略封裝破壞（例如在 UI 直接改 `actor.hp`）。 | 確保 Manual 與 Automation 100% 透過 `PlayerOperation` 統一出口。 |
| **遊戲體感 (Game Feel)** | 角色放置遊玩時是否有「卡點、發呆、笨重感」？ | 數值正確不代表操作流暢。 | 實際執行 `python mvp.py` 觀察 3~5 分鐘狩獵節奏、轉向與喝水反應。 |
| **UI 語意與清晰度** | 繁體中文化是否徹底、數值顏色警示是否合乎直覺？ | 腳本無法評判使用者理解成本與視覺雜訊。 | 人眼檢視顏色反饋（綠/橘/紅負重條、血條扣減動態飄字）。 |

---

## 4. 變更審查分級矩陣 (Change Classification Matrix)

任何變更在 Commit 前，依此矩陣決定審查路徑：

```text
┌────────────────────────────────────────────────────────┐
│                      變更分級決策樹                    │
└───────────────────────────┬────────────────────────────┘
                            │
               變更是否觸及核心遊戲規則？
              (數值/時序/公式/限制/分層邊界)
                            │
            ┌───────────────┴───────────────┐
            │ 是                            │ 否
            ↓                               ↓
       【Level 2】                     【Level 1】
  強制啟動 Auditor Subagent        腳本自行驗證即可
    進行對抗性證據審查             (單元測試 100% 通過即放行)
```

### 🟢 Level 1：免對抗審查（腳本自行驗證）
* 純 UI 排版、字型、配色調整。
* UI 繁體中文文案潤飾。
* 效能 Profile 探針與快取最佳化（不改變對外行為）。
* 註解、文件格式調整。
* **驗收標準**：`python -m unittest discover tests` 全通即可 Commit。

### 🔴 Level 2：強制對抗審查（啟動 Auditor Subagent）
* 修改攻擊速度、移動速度、施法延遲或動作幀數（Timing）。
* 修改戰鬥公式、傷害計算、AC/MR 折算、命中率或掉落率。
* 修改道具效果、職業限制（例如：勇敢藥水、精靈餅乾限制）。
* 修改 14 格裝備位規則或負重懲罰門檻。
* 修改 `Controller`、`PlayerOperation` 或跨層執行路徑。
* 修改或刪除任何現有標註 `LEGACY_OBSERVED` 的測試或常數。
* **驗收標準**：
  1. 腳本全數 PASS。
  2. **Auditor Subagent** 依據 `Lineage182c` 查核並簽署審查通過報告（審查報告格式見後述）。

---

## 5. Auditor Subagent 標準審查報告模板

當觸發 Level 2 審查時，Auditor 必須輸出以下格式的審查報告：

```markdown
### [AUDIT] Level 2 對抗性審查報告
- **審查項目**：[例如：勇敢藥水職業限制與加速倍率]
- **變更檔案**：[例如：native_engine/model.py:135-155]
- **Ground Truth 核對**：
  - 引用來源：`Lineage182c/src/lineage/world/object/instance/ItemPotionInstance.java:120`
  - 原始碼吻合度：[PASS / FAIL - 說明是否一致]
- **防偽測試檢查**：
  - 測試是否有放水修改：[無放水 / 發現偽造 - 說明]
- **四層架構規範**：
  - 是否繞過 Controller / PlayerOperation：[合規 / 違規]
- **審查結論**：[APPROVED / REJECTED]
```
