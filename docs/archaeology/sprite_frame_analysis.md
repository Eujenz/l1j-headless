# L1J 1.82 Legacy Server — `sprite_frame.sql` 深度考古分析

## 1. 來源基本資料 (Source Identity)

- **檔案路徑**: `C:\Users\p0282768\Documents\Gemini\Lineage182c\db\lineage\sprite_frame.sql`
- **資料庫專案**: Lineage 1.82c (`Eujenz/182c`)
- **生成日期戳記**: `2014/8/7 9:28:45` (MySQL Data Transfer Export)
- **版本層級**: **1.82c (L1J 1.82c Server / Database Ground Truth)**
- **證據分類**: `LEGACY_OBSERVED` (PRIMARY_DATA_AUTHORITY)
- **資料規模**:
  - 總資料列數: 281 筆 `INSERT INTO` 記錄
  - 唯一 GFX 數量: 63 個外觀 ID (包含王、騎、妖、法四大職業男女角色及主要怪物)
  - GFX ID 涵蓋範圍: 0 至 2323
  - 動作 ID 種類: 14 種主要動作編號

---

## 2. 實際 SQL Schema (Actual SQL Schema)

```sql
CREATE TABLE `sprite_frame` (
  `name` varchar(255) NOT NULL DEFAULT '',
  `gfx` int(10) unsigned NOT NULL DEFAULT '0',
  `action` int(10) unsigned NOT NULL DEFAULT '0',
  `action_name` varchar(255) NOT NULL DEFAULT '',
  `frame` int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`gfx`,`action`),
  KEY `id` (`gfx`),
  KEY `type` (`name`)
) ENGINE=MyISAM AUTO_INCREMENT=388 DEFAULT CHARSET=utf8;
```

---

## 3. 欄位語意分析 (Field Semantics)

| 欄位名稱 | 實際型別 | 代表意義 | 考古實證分析 |
| :--- | :--- | :--- | :--- |
| `name` | `varchar(255)` | 角色/怪物/外形中文名稱 | 供管理與查閱用（如「王子」、「女騎士」、「高侖石頭怪」），Java 運行期未直接使用。 |
| `gfx` | `int(10) unsigned` | 外形 GFX / Sprite ID | 伺服器角色與怪物外形識別碼，在 Java `SprTable` 中做為 Map 的查詢主鍵 (Key)。 |
| `action` | `int(10) unsigned` | 動作編號 (Action ID) | 與客戶端動畫 Action ID 嚴格對應（0 為移動、1 為空手攻擊、5 為單手劍攻擊等）。 |
| `action_name` | `varchar(255)` | 動作名稱敘述 | 如 `walk`, `attack`, `attack sword`, `spell direction` 等，輔助人類判讀。 |
| **`frame`** | **`int(10) unsigned`** | **動作基準時長 (毫秒 ms)** | **核心發現：名稱雖為 `frame`，但數值不是幀數，而是該動作的基礎持續時長（毫秒 ms）！** |

### `frame` 數值分佈實證：
- 最小值: `480` ms (某些特殊快速動作)
- 最大值: `2280` ms
- 平均值: `874.0` ms
- 標準 PC 角色步行時長 (`walk`): 一律為 **`640` ms**

---

## 4. 代表性資料範例 (Sample Records)

### 4.1 玩家角色範例 (PC Classes)

```sql
-- 王子 (GFX 0)
INSERT INTO `sprite_frame` VALUES ('王子', '0', '0', 'walk', '640');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '1', 'attack', '840');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '4', 'walk sword', '640');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '5', 'attack sword', '1000');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '20', 'walk bow', '640');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '21', 'attack bow', '1600');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '18', 'spell direction', '880');
INSERT INTO `sprite_frame` VALUES ('王子', '0', '19', 'spell no direction', '800');

-- 女騎士 (GFX 48)
INSERT INTO `sprite_frame` VALUES ('女騎士', '48', '0', 'walk', '640');
INSERT INTO `sprite_frame` VALUES ('女騎士', '48', '1', 'attack', '1000');
INSERT INTO `sprite_frame` VALUES ('女騎士', '48', '5', 'attack sword', '920');
INSERT INTO `sprite_frame` VALUES ('女騎士', '48', '21', 'attack bow', '1840');

-- 女妖精 (GFX 37)
INSERT INTO `sprite_frame` VALUES ('女妖精', '37', '0', 'walk', '640');
INSERT INTO `sprite_frame` VALUES ('女妖精', '37', '1', 'attack', '800');
INSERT INTO `sprite_frame` VALUES ('女妖精', '37', '5', 'attack sword', '760');
INSERT INTO `sprite_frame` VALUES ('女妖精', '37', '21', 'attack bow', '960');
```

### 4.2 怪物與變身範例 (Monster / Polymorph)

```sql
-- 骷髏 (GFX 30)
INSERT INTO `sprite_frame` VALUES ('骷髏', '30', '0', 'walk', '640');
INSERT INTO `sprite_frame` VALUES ('骷髏', '30', '1', 'attack', '920');

-- 漂浮之眼 (GFX 29)
INSERT INTO `sprite_frame` VALUES ('漂浮之眼', '29', '0', 'move', '960');
INSERT INTO `sprite_frame` VALUES ('漂浮之眼', '29', '1', 'attack', '1720');

-- 高侖石頭怪 (GFX 49)
INSERT INTO `sprite_frame` VALUES ('高侖石頭怪', '49', '0', 'walk', '1280');
INSERT INTO `sprite_frame` VALUES ('高侖石頭怪', '49', '1', 'attack', '1920');

-- 人形僵屍 (GFX 52)
INSERT INTO `sprite_frame` VALUES ('人形僵屍', '52', '0', 'walk', '1640');
INSERT INTO `sprite_frame` VALUES ('人形僵屍', '52', '1', 'attack', '1040');
```

---

## 5. Java Consumer 實證分析 (Java Consumers)

經全面搜尋，1.82c 伺服器代碼中精確定位到以下三層使用架構：

```text
Database: sprite_frame.sql
       ↓ (SELECT * FROM sprite_frame)
net.database.SprTable.java (靜態快取與分類查詢)
       ↓ (getMoveSpeed / getAttackSpeed)
net.check.CheckSpeed.java (動作週期驗證與外掛檢測)
       ↓ (checkInterval)
net.world.instance.PcInstance.java (toMove, Attack, AttackBow)
net.world.instance.skill.PcSkill.java (SPELL_DIR, SPELL_NODIR)
```

### 5.1 `SprTable.java` (`net.database.SprTable`)
- **啟動加載**: 在伺服器啟動時由 `Server.java:126` 呼叫 `SprTable.getInstance()`。
- **欄位讀取與轉換**:
  ```java
  int actid = rs.getInt("action");
  int speed = rs.getInt("frame"); // 明確讀取為 speed (毫秒)!
  ```
- **四類速度分類映射**:
  1. `moveSpeed`: Action ID `0, 4, 11, 20, 24, 40, 46, 50`
  2. `attackSpeed`: Action ID `1, 5, 12, 21, 25, 30, 31, 41, 47, 51`
  3. `dirSpellSpeed`: Action ID `18` (定向施法)
  4. `nodirSpellSpeed`: Action ID `19` (無定向施法)
- **回退機制 (Fallback Policy)**:
  若特定武器動作無資料，`getMoveSpeed` 回退至 `action = 0` (普通移動)；`getAttackSpeed` 回退至 `action = 1` (空手攻擊)。

### 5.2 `CheckSpeed.java` (`net.check.CheckSpeed`)
- **武器與動作映射數學規律**:
  - 移動判定動作: `pc.getGfxMode()` (如 0, 4, 11, 20...)
  - 攻擊判定動作: `pc.getGfxMode() + 1`！
    ```java
    SprTable.getInstance().getAttackSpeed(this._pc.getGfx(), this._pc.getGfxMode() + 1);
    ```
    實證證明：**攻擊動作編號恆為該武器移動模式編號 + 1**。
- **狀態時間修正係數 (Haste / Brave / Slow)**:
  ```java
  if (this._pc.isSpeed())  // 一段加速 (綠色藥水 / 通暢氣脈)
      interval = (int)(interval * 0.75D); // 縮短 25% (速度提升 1.33x)
  if (this._pc.isBrave())  // 二段加速 (勇敢藥水 / 精靈餅乾)
      interval = (int)(interval * 0.75D); // 再縮短 25%
  if (this._pc.isSlow())   // 緩速術 (Slow)
      interval = (int)(interval / 0.75D); // 延長為 1.33x
  ```

---

## 6. Client 3.80 (`TW13081901`) 交叉比對 (Cross-Reference)

將 `sprite_frame.sql` (1.82 Server) 與 `TW13081901.sqlite` (3.80 Client) 交叉檢索比對，得到重要實證結論：

| GFX | 名稱 | Action | 動作類型 | 1.82 Server `frame` (ms) | 3.80 Client 總幀數 (frames) | 單幀等效毫秒 (ms/frame) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | 王子 | 0 | walk | **640** | 4 | **160.0** |
| 0 | 王子 | 1 | attack | **840** | 7 | 120.0 |
| 0 | 王子 | 5 | attack sword | **1000** | 6 | 166.7 |
| 0 | 王子 | 21 | attack bow | **1600** | 10 | 160.0 |
| **48** | 女騎士 | 0 | walk | **640** | 4 | **160.0** |
| 48 | 女騎士 | 5 | attack sword | **920** | 7 | 131.4 |
| 48 | 女騎士 | 21 | attack bow | **1840** | 11 | 167.3 |
| **37** | 女妖精 | 0 | walk | **640** | 4 | **160.0** |
| 37 | 女妖精 | 5 | attack sword | **760** | 9 | 84.4 |
| 37 | 女妖精 | 21 | attack bow | **960** | 9 | 106.7 |
| **49** | 高侖石頭怪 | 0 | walk | **1280** | 4 | **320.0** (剛好是 160×2) |
| 49 | 高侖石頭怪 | 1 | attack | **1920** | 9 | 213.3 |
| **52** | 人形僵屍 | 0 | walk | **1640** | 6 | 273.3 |

### 交叉分析發現：
1. **動作代碼與武器分類 100% 吻合**：1.82 Server 的 `action` 與 3.80 Client 的 `action_id` 完全對應。
2. **PC 移動速度具有統一基準**：所有玩家職業的行走動作均為 4 幀、640 ms，即標準基準幀速為 **160 ms / frame** (相當於 6.25 FPS 的循環動畫)。
3. **攻擊動作因職業與武器具備高度異質性**：
   - 妖精拿弓攻速為 960 ms；騎士拿弓則為 1840 ms (近兩倍時間)。
   - 騎士拿單手劍為 920 ms；王子拿單手劍為 1000 ms。
4. **版本隔離警告**：3.80 客戶端中的後期 GFX 顯式標註的 `110.framerate(...)`（例如 36 或 59）是客戶端 DirectDraw/DirectX 動畫播放器的 timer 參數，**絕非 1.82 伺服器端的動作間隔**。

---

## 7. 追溯性結論 (Provenance Summary)

```yaml
claim: "L1J 1.82 伺服器端將 sprite_frame.sql 的 frame 欄位定義為動作間隔 (毫秒)，PC 基礎移動間隔為 640ms，攻擊動作間隔由 GFX 與武器模式決定 (760ms ~ 1840ms)。"
source: "legacy-db-lineage-sql / legacy-server-182c"
version: "1.82c"
layer: "database + server"
classification: "LEGACY_OBSERVED"
target_version: "1.82"
raw_evidence: "sprite_frame.sql:L14-L309, SprTable.java:L40-L140, CheckSpeed.java:L86-L108"
confirmed_by: "Eujenz/182c"
```

---

## 8. 已確認之關係 (Confirmed Relationships)

1. **`sprite_frame.frame` ＝ 動作間隔（毫秒 ms）**，不是幀數。
2. **移動 Action ID ＝ `GfxMode`**；**攻擊 Action ID ＝ `GfxMode + 1`**。
3. **PC 基礎步行時間 ＝ 640 ms / 格**。
4. **加速狀態縮減比例**：一段加速與二段加速分別以 `× 0.75` 縮短動作間隔。
5. **武器攻速差**：1.82 伺服器從資料庫層級即為各職業設定了精確的武器攻擊動作耗時，妖精弓 (960ms) 與騎士弓 (1840ms) 的巨大差距是設計中的原生設定。

---

## 9. 未知事項與證據邊界 (Unknowns & Evidence Boundaries)

1. **怪物主動行動間隔 (Monster Autonomous Cadence)**:
   - **已於 Phase B Task 2 徹底查明**：怪物完全不使用 `sprite_frame.sql`，詳見 [Monster Timing 深度考古分析](file:///c:/Users/p0282768/Documents/l1j-headless/docs/archaeology/monster_timing_analysis.md)。
2. **未列入資料庫之 GFX**:
   `sprite_frame.sql` 僅有 63 筆 GFX，主要涵蓋 PC 各職業外觀與代表性怪物變身。對於不在表內的 GFX，PC 端檢測走 `SpeedHackChecker.java` 舊版 switch-case 或回退。

---

## 10. 是否產生新的 `DERIVED_CANONICAL` 證據？

**是。**
透過 `sprite_frame.sql` (Database) 與 `SprTable.java` / `CheckSpeed.java` (Server Source) 交叉比對，正式確立：
> **`DERIVED_CANONICAL_TIMING_BASE_1_82`**:
> - 角色基礎步速基準 (Movement Cadence): **`640 ms`**
> - 角色狀態加速倍率 (Haste Multiplier): **`0.75`** (即時長為原時長的 75%)
> - 角色攻擊基準時間 (Attack Cadence): **依據 GFX 與武器模式自 `sprite_frame.sql` 精確取得** (例：王子劍 1000ms, 妖精弓 960ms, 騎士劍 920ms)。

---

## 11. 怪物時間機制與動作語義考古連結 (Further Archaeology)

- 怪物時間機制與 `MonAi` 30ms 輪詢循環深度分析：
  [docs/archaeology/monster_timing_analysis.md](file:///c:/Users/p0282768/Documents/l1j-headless/docs/archaeology/monster_timing_analysis.md)
- 怪物 `modespeed` 與 `client/list.spr` (40ms 刻度) 深度分析：
  [docs/archaeology/monster_modespeed_analysis.md](file:///c:/Users/p0282768/Documents/l1j-headless/docs/archaeology/monster_modespeed_analysis.md)
- 動作時序語義（即時傷害結算 vs 動作冷卻間隔）：
  [docs/archaeology/action_timing_semantics.md](file:///c:/Users/p0282768/Documents/l1j-headless/docs/archaeology/action_timing_semantics.md)
- 結論判定：**`SPRITE_FRAME_PC_ONLY`** (怪物與玩家時間系統完全隔離) 且 **`DAMAGE_TIMING = IMMEDIATE`** (傷害結算即時無前搖)。
