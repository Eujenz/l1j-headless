# Client 3.80 資產考古 — TW13081901.txt

## 1. 資料源基本身份 (Identity Metadata)

- **Source ID**: `legacy-client-tw13081901`
- **Product**: Lineage (天堂)
- **Layer**: Client (客戶端動作/精靈動畫資料表)
- **Client Version**: **3.80** (臺灣版本)
- **Target Version**: **1.83 / 1.82**
- **Classification**: `LEGACY_CLIENT_OBSERVED_3_80`
- **Applicability**: `CROSS_VERSION_AUXILIARY`
- **Runtime Dependency**: `false` (嚴禁在遊戲執行期直接讀取)
- **File Metrics**:
  - 檔案大小: 7,412,363 bytes (~7.07 MB)
  - 總行數: 155,202 行
  - 總 GFX 區塊數: 22,536 個
  - SHA256: `ddcbd759d4124877768990db505a8b1f7b7cbba23e7e78fe7e3fafd4bda356fe`

---

## 2. 跨版本邊界規範 (Cross-Version Isolation)

> [!IMPORTANT]
> **3.80 Client 資料 ≠ 1.83 / 1.82 Canonical 數值！**
> `TW13081901.txt` 是在 3.80 時代的客戶端定義檔。雖然它保留了大量自 1.82 以來的 GFX 編號與動作序列，但：
> 1. 嚴禁僅憑檔案中的 `110.framerate(36)` 就直接判定為「1.83 伺服器判定攻擊間隔為 36ms 或 36 FPS」。
> 2. 任何動作時長必須與 1.82 伺服器端資料庫 (`sprite_frame.sql`) 及速度驗證碼 (`CheckSpeed.java`, `SprTable.java`) 進行交叉驗證 (`DERIVED_CANONICAL`)，否則只能保留為 `CROSS_VERSION_AUXILIARY` 或 `UNKNOWN`。

---

## 3. 核心考古價值 (Archaeological Value)

此檔案提供了客戶端視覺表現的權威結構：
1. **GFX 與 Sprite 的對應關係**：如 `#18315 56 tw xiaolongbao monster`，確立 GFX 18315 使用 Sprite 56。
2. **動作與武器分支 (Weapon-Specific Actions)**：
   - 清楚區分通用攻擊 (`attack`) 與各類武器特化動作：
     - `attack sword` (Action 5)
     - `attack axe` (Action 12)
     - `attack bow` (Action 21)
     - `attack spear` (Action 25)
     - `attack staff` (Action 41)
     - `attack dagger` (Action 47)
     - `attack largesword` (Action 51)
     - `attack double sword` (Action 55)
     - `attack claw` (Action 59)
     - `attack shuriken` (Action 63)
     - `attack chainsword` (Action 84)
3. **幀數與關鍵幀結構 (Frame Sequence)**：
   - 包含每種動作的總幀數（如 6 幀、8 幀、18 幀）。
   - 標記傷害判定點或音效觸發點（如序列中的 `!` 驚嘆號）。
4. **關聯性參照 (References)**：
   - `shadow` (影子 GFX 編號)
   - `clothes` (裝飾與部件 GFX)
   - `type` (實體型別標籤)
