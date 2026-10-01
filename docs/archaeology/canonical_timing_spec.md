# L1J 1.82 Canonical Timing Specification (權威時序規範)

> **版本定位與文件性質**：
> 本文件為 L1J 1.82 Legacy Server（`Eujenz/182c`）之**唯一權威 Canonical Timing Specification**。
> 本文件收斂 `sprite_frame_analysis.md`、`monster_timing_analysis.md`、`monster_modespeed_analysis.md` 與 `action_timing_semantics.md` 之所有實證，作為後續 Phase C Temporal Runtime 開發的唯一契約依據。
> **在 Phase C 實作中，任何未收錄於本文件、或被標記為禁止假設（MUST NOT assume）的項目，皆不得出現在 Runtime 核心邏輯中。**

---

## 1. 絕對版本邊界與權威層級 (Version Boundaries & Evidence Hierarchy)

### 1.1 版本劃分原則
1. **Canonical Target (唯一世界規則基準)**：
   - **`SERVER_1.82` (`Eujenz/182c`)**：本專案唯一的世界規則與伺服器邏輯 Ground Truth。包含 Java 源碼、Bytecode 與 MySQL 資料庫。
2. **Auxiliary Reference (跨版本輔助參考)**：
   - **`CLIENT_3.80` (`TW13081901.txt`)**：僅供驗證動畫結構、幀序列特徵與 GFX/Action 映射，**絕對禁止**將 Client 3.80 之 FPS 或幀數直接反推為 1.82 Server 之判定間隔。
3. **External Architecture Reference (外部架構參考)**：
   - **`OpenKore`**：僅供參考 Headless Agent Runtime 的任務切換、狀態機與隊列管理架構，**絕對禁止**將 OpenKore（Ragnarok Online）之遊戲規則或封包延遲當作 L1J 之行為依據。

### 1.2 證據分類定義 (Evidence Classification)
| 分類代碼 | 定義與判定標準 | 允許作為 Phase C 依據 |
| :--- | :--- | :--- |
| **`CONFIRMED_CANONICAL`** | 在 L1J 1.82 伺服器源碼、字節碼或資料庫中具備直接、明確且一致之實證。 | **YES** |
| **`DERIVED_CANONICAL`** | 由 `CONFIRMED_CANONICAL` 機制經數學或系統調度特性嚴格推導而得（如輪詢量化區間）。 | **YES** (需載明推導邊界) |
| **`INFERRED`** | 符合源碼觀測但缺乏直接指令級實證，屬高合理性推論。 | **CONDITIONAL** (需預留擴充) |
| **`UNKNOWN`** | 源碼無直接記錄、存在衝突或僅存於客戶端封閉實作（如 DirectDraw 內部幀鎖定）。 | **NO** (禁止假設固定值) |
| **`CROSS_VERSION_AUXILIARY`** | 源自 Client 3.80 等外部版本之輔助觀察。 | **NO** (僅供對比，不可入核心) |
| **`EXTERNAL_ARCHITECTURE_REFERENCE`** | 源自 OpenKore 等外部代理專案之架構概念。 | **NO** (僅供設計模式參考) |

---

## 2. Canonical Timing 核心詞彙表 (Canonical Timing Vocabulary)

為消除語義模糊，統一規範以下 11 項核心時序名詞：

### 2.1 Animation Duration (動畫時長)
- **定義**：客戶端圖形引擎將特定 GFX 的特定動作從第 0 幀播放至最後一幀的視覺呈現時間。
- **證據來源**：`client/list.spr`, `TW13081901.txt`
- **分類**：`CROSS_VERSION_AUXILIARY` / `CONFIRMED_CANONICAL` (僅限於 list.spr 標註之序列)
- **規範數值**：依外觀而異（如 1.82 list.spr 中單位總和 $\times 40\text{ ms}$）。
- **適用範圍**：客戶端畫面呈現與純視覺同步。
- **What it does NOT mean**：**絕對不代表伺服器端攻擊判定或傷害結算的時間點**！

### 2.2 Action Interval (動作間隔閘門)
- **定義**：特定實體（PC 或 Monster）發起某一動作（移動、攻擊、施法）的瞬刻起算，到伺服器允許該實體再次通過動作閘門（Action Gate）發起下一次同類或異類合法動作的**最小時間跨度**。
- **證據來源**：`SprTable.java`, `CheckSpeed.java`, `Monster.modespeed`, `NpcInstance.isAi()`
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：PC 查閱 `sprite_frame.frame`；Monster 查閱 `modespeed[mode]`。
- **適用範圍**：伺服器端實體行為門檻。
- **What it does NOT mean**：**不是「動畫播完後才開始的後搖」**，而是**從動作觸發當下即開始計時的保護窗口**。

### 2.3 Attack Cooldown (攻擊冷卻窗口)
- **定義**：物理攻擊動作專屬之 Action Interval。
- **證據來源**：`SprTable.java:84` (`getAttackSpeed`), `MonsterInstance.java:300` (`getModespeed(GfxMode + 1)`)
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：PC 依武器與外形為 760 ~ 1840 ms；Monster 依 mode 1 時長。
- **適用範圍**：連續物理攻擊之間隔約束。
- **What it does NOT mean**：不包含法術專屬的 `skills.reuse_delay`。

### 2.4 Skill Reuse Delay (技能專屬重用冷卻)
- **定義**：個別法術在資料庫中定義的獨立冷卻時間，限制該特定法術不可被連續觸發。
- **證據來源**：`skills` 資料表之 `reuse_delay` 欄位, `PcSkill.java:123`
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：依法術 ID 獨立定義（毫秒或秒）。
- **適用範圍**：特定技能本身。
- **What it does NOT mean**：**獨立於全域動作間隔**；即使 Reuse Delay 為 0，仍受全域施法動作間隔約束。

### 2.5 Damage Timing (傷害結算時間點)
- **定義**：攻擊或法術命中判定、傷害數值計算以及目標實體 HP 扣除在邏輯時間軸上發生的時序點。
- **證據來源**：`PcInstance.java:623-631`, `NpcInstance.java:323-327`
- **分類**：`CONFIRMED_CANONICAL` (狹義普通物理攻擊)
- **規範數值**：$T = 0\text{ ms}$（**IMMEDIATE**，在發起動作的同一次函數調用中立即結算）。
- **適用範圍**：標準 PC 物理攻擊、標準 Monster 物理攻擊。
- **What it does NOT mean**：**不可推廣宣稱「L1J 1.82 所有傷害永遠 immediate」**；此規則目前僅適用於已驗證之常規物理攻擊與即時法術。

### 2.6 AI Tick (AI 輪詢間隔)
- **定義**：伺服器後台怪物 AI 排程執行緒每次休眠喚醒的基礎物理週期。
- **證據來源**：`MonAi.java:31` (`this.SleepTime = 30`), `MonAi.java:87` (`Thread.sleep(30)`)
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：$30\text{ ms}$。
- **適用範圍**：伺服器怪物管理執行緒 `MonAi`。
- **What it does NOT mean**：**絕對不是怪物攻擊速度**，也不是怪物移動週期！

### 2.7 AI Gate (AI 狀態閘門)
- **定義**：怪物實體判定是否可以執行下一次決策與行動的條件函式。
- **證據來源**：`NpcInstance.java:158-167` (`isAi(long time)`)
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：$\text{now} - \text{ai\_start\_time} \ge \text{speed}$。
- **適用範圍**：怪物移動、攻擊與技能決策。
- **What it does NOT mean**：不是時間推進器，而是布林檢測閥。

### 2.8 Anti-Cheat Threshold (防外掛檢測門檻)
- **定義**：伺服器用於判定客戶端上報封包時間戳記是否異常過快的容忍閥值與處罰記數器。
- **證據來源**：`CheckSpeed.java:61-84`
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：$\text{interval} \times \frac{\text{Config.CHECK\_STRICTNESS} - 5}{100} < \text{rightInterval}$，連續違規 10 次處罰。
- **適用範圍**：伺服器被動校驗客戶端封包合法性。
- **What it does NOT mean**：**不是伺服器主動發起行為的調度器**；伺服器不會主動替 PC 延遲發包。

### 2.9 Movement Interval (移動間隔)
- **定義**：實體由一格移動至相鄰格所需之 Action Interval。
- **證據來源**：`SprTable.java:69`, `MonsterInstance.java:303`
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：PC 基礎固定為 $640\text{ ms}$；Monster 依 `modespeed[0]`。
- **適用範圍**：標準單格行走。
- **What it does NOT mean**：不是路徑搜尋時間。

### 2.10 Attack Interval (攻擊間隔)
- **定義**：見 2.3 Attack Cooldown，實體由發起一次物理打擊至被允許發起下一次打擊的最小跨度。
- **證據來源**：`SprTable.java:84`, `MonsterInstance.java:300`
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：PC 依武器外觀；Monster 依 `modespeed[GfxMode + 1]`。
- **適用範圍**：近戰與遠程常規物理攻擊。
- **What it does NOT mean**：不包含弓箭之客戶端飛行視覺時間。

### 2.11 Cast / Skill Action Interval (施法動作間隔)
- **定義**：角色發動魔法時，全域阻斷下一次物理攻擊或施法動作的時間跨度。
- **證據來源**：`CheckSpeed.java:92-97`, `SprTable.java:101, 116`
- **分類**：`CONFIRMED_CANONICAL`
- **規範數值**：定向攻擊魔法 (Action 18) 基礎 $880\text{ ms}$；無方向輔助魔法 (Action 19) 基礎 $800\text{ ms}$。
- **適用範圍**：PC 施法全域動作冷卻。
- **What it does NOT mean**：不同於特定技能的 `reuse_delay`。

---

## 3. Action Interval 核心語義重構 (Action Interval Semantics)

在傳統遊戲模擬中，常有人誤將動作時間視為「攻擊動作播放結束後，才進入後搖冷卻」。
**L1J 1.82 原始碼否定了這個模型。**

### 3.1 伺服器端真實執行模型
伺服器端不存在「動畫播放完畢」的事件回調（No Animation Complete Callback）。真實呼叫鏈為：

```text
[T = 0] ACTION_TRIGGER (發起動作)
   │
   ├── 1. 傷害結算與 HP 扣減 (DAMAGE_TIMING = IMMEDIATE)
   ├── 2. 廣播動畫視覺封包給客戶端 (S_ObjectAttack / S_ChangeHeading 等)
   │
   └── 3. 設定動作時間閘門 (Action Gate Setup):
          - PC: 記錄 _actTimers[type] = now
          - Monster: this.ai_start_time = now; this.ai_time = modespeed
   │
[0 < T < ActionInterval] ACTION_GATE_LOCKED (動作閘門鎖定)
   │      - PC 若於此期間再次發包，CheckSpeed 累加違規次數 (_injusticeCount++)
   │      - Monster 於 MonAi 輪詢時，isAi() 返回 false，禁止任何思考與行動
   │
[T >= ActionInterval] ACTION_GATE_OPEN (動作閘門開啟)
          - 實體狀態恢復 IDLE，允許發起下一次行動 (Move, Attack, Cast)
```

### 3.2 嚴格語義規範
> **Canonical 定義**：
> **Action Interval 是從動作觸發瞬刻（Action Trigger）起算，到下一個動作閘門（Action Gate）可以再次通過之前的最小時間窗口。**
> 任何假設「傷害發生在動畫中間幀（Impact Frame）」或「後搖在動畫結束後才開始計時」的模型，皆屬**違背 1.82 實證之錯誤假設**。

---

## 4. PC Timing 規格 (PC Timing Specification)

### 4.1 基礎移動間隔 (Base Movement)
- **數值**：**`640 ms`** (`CONFIRMED_CANONICAL`)
- **實證來源**：`SprTable.java:69` (`getMoveSpeed`)、`sprite_frame.sql` (`action = 0` 且 `frame = 640`)。
- **適用範圍**：所有四種職業（王、騎、妖、法）男女角色之無狀態單格步行。

### 4.2 基礎物理攻擊間隔 (Base Attack)
- **數值分佈**：依持用武器類別與外觀 GFX 而定，範圍為 **`760 ~ 1840 ms`** (`CONFIRMED_CANONICAL`)。
- **代表性數據 (`sprite_frame.sql`)**：
  - 空手攻擊 (Action 1): $960\text{ ms}$ (男王) / $840\text{ ms}$ (男騎) / $800\text{ ms}$ (男女妖/法)
  - 單手劍 (Action 20): $920\text{ ms}$ (男王/男騎) / $840\text{ ms}$ (男妖) / $1160\text{ ms}$ (男法)
  - 雙手劍 (Action 24): $1080\text{ ms}$ (男王/男騎) / $1280\text{ ms}$ (男妖)
  - 匕首 (Action 40): $800\text{ ms}$ (男王/男騎/男妖) / $960\text{ ms}$ (男法)
  - 弓箭 (Action 28): $800\text{ ms}$ (男妖) / $880\text{ ms}$ (男女王/騎/法)
  - 矛 (Action 32): $1080\text{ ms}$ (男王/男騎)
  - 雙刀/爪 (Action 46, 50): $760\text{ ms}$
- **實證來源**：`SprTable.java:84` (`getAttackSpeed`)。

### 4.3 `CheckSpeed` 之真實機制與 Headless Runtime 限制
- **性質判定**：
  在原始 L1J 1.82 服務端中，`CheckSpeed.java` 是**被動防加速檢測器（Anti-Cheat Detector）**，而非主動排程器。
  - 當正常玩家以官方客戶端遊玩時，DirectDraw 的動畫播放節奏使客戶端自發以約 `rightInterval` 的頻率發送 `C_Attack` / `C_Move`。
  - 若封包間隔小於 `rightInterval`（經嚴格度折算後），伺服器僅做違規計數；達 10 次違規方予以懲處。
- **Headless Runtime 之契約轉換**：
  - 在缺乏官方客戶端畫面幀率自鎖的 Headless 環境中，**Agent Runtime 必須主動將 `rightInterval` 作為主動行動閘門（Action Gate）**。
  - 嚴禁以無間隔密集發送攻擊指令，否則即構成外掛行為。

---

## 5. PC Skill Timing 規格 (PC Skill Timing Specification)

PC 施法時序存在三重完全獨立的維度：

```text
1. Global Cast Action Interval (全域施法動作間隔)
   - 定向攻擊魔法 (Action 18): 880 ms (SprTable.java:101)
   - 無方向輔助魔法 (Action 19): 800 ms (SprTable.java:116)
   - 效果：此時段內無法再發起任何物理攻擊或施法。

2. Skill Reuse Delay (技能專屬重用冷卻)
   - 來源：skills 資料表之 reuse_delay 欄位
   - 檢測：PcSkill.java:123 (checkSkillDelay)
   - 效果：若 reuse_delay > 0，在冷卻結束前該特定法術不可再次使用。

3. Animation Duration (客戶端施法動畫播放)
   - 視覺效果，不影響伺服器在 T = 0 瞬刻結算魔法效果 (PcSkill.java:125)。
```

---

## 6. Monster Timing 規格 (Monster Timing Specification)

### 6.1 完整時序計算鏈
```text
client/list.spr (原始動作幀定義字串)
       ↓
ClientFileLoad.dataTest() (累加 frame units)
       ↓ (第 290-293 行字節碼)
total_units × 40 ms
       ↓
Monster.modespeed[mode]
       ↓ (MonsterInstance 執行動作時賦值)
this.ai_time = modespeed[mode]
       ↓ (MonAi 30ms 輪詢循環)
NpcInstance.isAi(time): time - ai_start_time >= speed
```

### 6.2 單位換算公式證明
- **實證依據**：`ClientFileLoad.class` 第 290-293 行字節碼確認包含 `iload; bipush 40; imul; istore;`。
- **公式**：
  $$\text{modespeed}(\text{mode}) = \left(\sum \text{frame\_units}\right) \times 40\text{ ms}$$
- **Fallback 規則**：若資料庫或 `list.spr` 未定義該 mode，或取值為 0，普適 Fallback 為 **`1000 ms`** (`Monster.java:316`, `ClientFileLoad.java:494`)。

---

## 7. Monster Action Mapping 與代表性時序矩陣

### 7.1 模式映射語義 (Mode Mapping Semantics)
- **`Mode 0`**：移動 (Walk / Move)，對應 `GfxMode` (`CONFIRMED_CANONICAL`)。
- **`Mode 1`**：攻擊 (Attack)，對應 `GfxMode + 1` (`CONFIRMED_CANONICAL`)。
- **`Mode 2`**：受擊硬直 (Damage)（客戶端動作，伺服器不主動排程）。
- **`Mode 8`**：死亡 (Death)（客戶端動作）。
- **`Mode 19`**：無方向魔法 / 特殊技能 (Spell No-Dir)（如漂浮之眼麻痺視線 `FloatingEye.java:46`）。

### 7.2 代表性怪物 Canonical Timing Matrix
經由 `client/list.spr` 與 `tools/query_monster_modespeed.py` 嚴格比對所得數據：

| 怪物名稱 (Monster) | GFX | Sprite ID | Mode 0 (Move) | Mode 1 (Attack) | Mode 2 (Damage) | Mode 8 (Death) | Mode 19 (Spell) | 實證分類 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **骷髏 (Skeleton)** | 30 | 300 | 16 units / **640 ms** | 5 units / **200 ms** | 3 units / 120 ms | 27 units / 1080 ms | 未定義 (Fallback 1000ms) | `CONFIRMED_CANONICAL` |
| **高侖石頭怪 (Golem)** | 49 | 48 | 32 units / **1280 ms** | 48 units / **1920 ms** | 18 units / 720 ms | 22 units / 880 ms | 48 units / **1920 ms** | `CONFIRMED_CANONICAL` |
| **漂浮之眼 (Floating Eye)**| 29 | 40 | 24 units / **960 ms** | 43 units / **1720 ms** | 16 units / 640 ms | 29 units / 1160 ms | 43 units / **1720 ms** | `CONFIRMED_CANONICAL` |
| **狼人 (Werewolf)** | 33 | 40 | 16 units / **640 ms** | 24 units / **960 ms** | 10 units / 400 ms | 31 units / 1240 ms | 36 units / **1440 ms** | `CONFIRMED_CANONICAL` |
| **人形僵屍 (Zombie)** | 52 | 40 | 41 units / **1640 ms** | 26 units / **1040 ms** | 12 units / 480 ms | 19 units / 760 ms | 31 units / **1240 ms** | `CONFIRMED_CANONICAL` |

---

## 8. Monster AI Tick 與排程量化分析 (AI Tick & Quantization)

### 8.1 輪詢機制
`MonAi.java:85-88`：
```java
while (true) {
    for (MonsterInstance mon : this.list) {
        if (mon.isAi(time)) { ... }
    }
    Thread.sleep(this.SleepTime); // SleepTime = 30 ms
    time = System.currentTimeMillis();
}
```

### 8.2 輪詢量化推導 (Derived Quantization Interval)
- **目標到期時間**：$T_{\text{target}} = \text{ai\_start\_time} + \text{speed}$。
- **實際執行時間**：由於執行緒每 30ms 喚醒一次，實際觸發點 $T_{\text{actual}}$ 滿足：
  $$T_{\text{actual}} \in \left[ T_{\text{target}},\, T_{\text{target}} + 30\text{ ms} \right)$$
- **實證分類**：**`DERIVED_CANONICAL`**
  - **重要說明**：這是排程器量化（Scheduler Quantization）的系統效應，**絕對不可**將其與 `modespeed` 混淆。怪物的本質間隔仍為 `modespeed`，30ms 僅為輪詢顆粒度。

---

## 9. Damage Timing 嚴格邊界 (Damage Timing Strict Boundaries)

### 9.1 已驗證區域 (Confirmed Immediate Damage)
在以下情況下，傷害判定與血量扣除**嚴格在調用當下同步完成**：
1. **PC 普通近戰物理攻擊**：[`PcInstance.java:623-631`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/PcInstance.java#L623-L631)
2. **PC 遠程物理攻擊 (弓箭)**：[`PcInstance.java:684`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/PcInstance.java#L684)（箭矢飛行時間僅為客戶端圖形表現，伺服器同步扣血）。
3. **Monster 普通近戰物理攻擊**：[`NpcInstance.java:323-327`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/NpcInstance.java#L323-L327)
4. **標準單體法術**：[`PcSkill.java:125`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/skill/PcSkill.java#L125) (`toMagic(id)` 立即生效)。

### 9.2 邊界與限制 (Narrow Scope Boundary)
- **禁止過度宣稱**：「L1J 1.82 所有傷害永遠 immediate」。
- **未驗證或已知例外**：
  - 毒性狀態持續傷害 (Poison DOT)：由專屬計時器定時扣減。
  - 地面陷阱 / 延遲法術 (Delayed Spell / Traps)：需依個別法術實作判定。
  - 召喚物特殊自爆攻擊：未經逐一源碼審查前，保留為 `INFERRED` 或 `UNKNOWN`。

---

## 10. Haste / Slow 狀態修改器機制 (Haste & Slow Modifiers)

### 10.1 PC 狀態修改公式 (`CheckSpeed.java:101-106`)
```java
if (this._pc.isSpeed())
    interval = (int)(interval * 0.75D); 
if (this._pc.isSlow())
    interval = (int)(interval / 0.75D); 
if (this._pc.isBrave())
    interval = (int)(interval * 0.75D);
```
1. **作用對象**：累進作用於前一步驟計算出的 `interval`。
2. **捨去規則**：Java `(int)` 強制轉型，直接捨去小數點（Truncation towards zero）。
3. **重要代碼異象 (Source Code Quirk / Bug)**：
   在 `CheckSpeed.java:99` 中：
   `default: return interval = SprTable.getInstance().getAttackSpeed(...);`
   - 因 `default` 分支存在直接 `return`，**導致 `CheckSpeed.java` 內部的 `isSpeed()`, `isSlow()`, `isBrave()` 乘率未作用於普通攻擊 (ATTACK)**！僅作用於 `MOVE`, `SPELL_DIR`, `SPELL_NODIR`。
   - **實證判定**：此為 Legacy Server 防加速模組之歷史代碼實作特徵。在客戶端真實視覺中，加速藥水由客戶端封包驅動加速動畫。

### 10.2 Monster 狀態修改公式 (`NpcInstance.java:160-163`)
```java
int speed = this.ai_time;
if (isSpeed())
    speed = (int)(speed - speed * 0.3D); // 即 speed * 0.70
if (isSlow())
    speed = (int)(speed + speed * 0.3D); // 即 speed * 1.30
```
1. **作用對象**：累進作用於 `speed` 變數。
2. **捨去規則**：Java `(int)` 強制轉型截斷。
3. **適用範圍**：**全面適用於所有動作**（移動、物理攻擊、特殊技能）。因為所有怪物行為皆需通過 `isAi(long time)` 之閘門檢測。

---

## 11. Anti-Cheat 與 Scheduler 的最終分離 (Anti-Cheat vs Scheduler Matrix)

| 機制維度 (Mechanism) | 玩家角色 (PC) | 怪物 (Monster) | 實證源碼 |
| :--- | :--- | :--- | :--- |
| **Action Timing Source** | `db/lineage/sprite_frame.sql` | `client/list.spr` $\rightarrow$ `Monster.modespeed` | `SprTable.java:23` / `ClientFileLoad.class:292` |
| **Server Scheduler** | **無主動排程器**（依賴客戶端自發發包） | `net.world.ai.MonAi` 獨立執行緒 | `MonAi.java:27` |
| **Timing Gate** | `CheckSpeed.checkInterval()` | `NpcInstance.isAi(time)` | `CheckSpeed.java:61` / `NpcInstance.java:158` |
| **Damage Timing** | **IMMEDIATE** ($T = 0$) | **IMMEDIATE** ($T = 0$) | `PcInstance.java:631` / `NpcInstance.java:327` |
| **Polling Interval** | 無 (事件驅動 Event-driven) | **30 ms** (`SleepTime = 30`) | `MonAi.java:31` |
| **Anti-Cheat Logic** | 連續 10 次違規處罰 (`injusticeCount`) | **無** (Server AI 自行控制，不需防外掛) | `CheckSpeed.java:70` |
| **Reuse Delay** | `skills.reuse_delay` 獨立冷卻 | 特殊技能手動設定 `ai_time` (如 1720ms) | `PcSkill.java:123` / `FloatingEye.java:46` |

---

## 12. Canonical Timing Evidence Matrix (權威時序證據矩陣)

| Claim (論斷) | Source (實證來源) | Classification | Confidence | Allowed for Native Runtime |
| :--- | :--- | :--- | :---: | :---: |
| **PC 基礎步行間隔 = 640ms** | `SprTable.java:69`, `sprite_frame.sql` | `CONFIRMED_CANONICAL` | High | **YES** |
| **PC 單手劍基礎攻擊間隔 = 920ms** | `SprTable.java:84`, `sprite_frame.sql` | `CONFIRMED_CANONICAL` | High | **YES** |
| **PC 雙手劍基礎攻擊間隔 = 1080ms** | `SprTable.java:84`, `sprite_frame.sql` | `CONFIRMED_CANONICAL` | High | **YES** |
| **PC 施法全域動作間隔 = 800~880ms** | `SprTable.java:101, 116`, `CheckSpeed.java` | `CONFIRMED_CANONICAL` | High | **YES** |
| **怪物動作間隔公式 = units $\times$ 40ms** | `ClientFileLoad.class:290-293`, `list.spr` | `CONFIRMED_CANONICAL` | High | **YES** |
| **怪物查無模式時之 Fallback = 1000ms** | `Monster.java:316`, `ClientFileLoad.java:494` | `CONFIRMED_CANONICAL` | High | **YES** |
| **怪物 AI 全域輪詢間隔 = 30ms** | `MonAi.java:31, 87` | `CONFIRMED_CANONICAL` | High | **YES** |
| **怪物有效觸發時間受 30ms 輪詢量化** | 數學排程推導 $\in [T, T+30)$ | `DERIVED_CANONICAL` | High | **YES** |
| **PC / Monster 普通物理攻擊傷害即時生效** | `PcInstance.java:631`, `NpcInstance.java:327`| `CONFIRMED_CANONICAL` | High | **YES** |
| **PC 弓箭遠程攻擊傷害在伺服器端即時結算**| `PcInstance.java:684` | `CONFIRMED_CANONICAL` | High | **YES** |
| **PC 加速狀態間隔 $\times$ 0.75** | `CheckSpeed.java:102` | `CONFIRMED_CANONICAL` | High | **YES** |
| **怪物加速狀態間隔 $\times$ 0.70** | `NpcInstance.java:161` | `CONFIRMED_CANONICAL` | High | **YES** |
| **客戶端動畫播放 FPS ＝ 伺服器動作間隔** | 無實證，且 1.82 伺服器端無視客戶端幀率 | `REJECTED` | — | **NO** |
| **Client 3.80 幀數 ＝ L1J 1.82 伺服器間隔** | 版本不同且用途不同 | `REJECTED` | — | **NO** |
| **OpenKore 定時規則 ＝ L1J 1.82 世界規則** | 外部不同遊戲專案 | `REJECTED` | — | **NO** |
| **所有魔法與特殊攻擊傷害皆為即時** | 缺乏對所有個別法術之全量實證 | `UNKNOWN` | — | **NO** (僅限窄化驗證) |
| **客戶端受擊硬直幀數鎖定鍵盤輸入** | 屬客戶端未解密封閉邏輯 | `UNKNOWN` | — | **NO** |

---

## 13. Contract for Phase C (Phase C Temporal Runtime 契約規範)

本節為 Phase C 實作的**絕對邊界契約**。後續任何 agent 或工程師在實作 Temporal Runtime 時，必須遵守以下準則：

### 13.1 Temporal Runtime MAY assume (允許依賴之契約公理):
1. **動作具備明確觸發時間戳記 (Trigger Timestamp)**：每個動作自 $T_0$ 被觸發。
2. **動作具備 Canonical 最小合法間隔 (Action Interval)**：
   - PC 查詢 `sprite_frame.sql`。
   - Monster 查詢 `modespeed`（或由 `list.spr` 匯出之數值），Fallback 為 1000ms。
3. **傷害可在動作觸發時立即結算 (Immediate Damage)**：
   - 已證明之常規物理攻擊與即時法術，傷害結算發生於 $T = 0$。
4. **怪物行動受 30ms 輪詢排程器量化 (Scheduler Quantization)**：
   - 怪物動作完成後的下一次決策時間點受 30ms 顆粒度影響。
5. **技能專屬冷卻獨立於全域動作間隔 (Skill Reuse Delay Independence)**：
   - `skills.reuse_delay` 僅約束該技能本身，全域施法動作間隔 (800/880ms) 約束所有行動。
6. **狀態修改器採整數截斷 (Integer Truncation)**：
   - 加速/緩速依源碼公式計算並轉型為 `(int)`。

### 13.2 Temporal Runtime MUST NOT assume (嚴格禁止之錯誤假設):
1. **MUST NOT assume: 動畫時長 ＝ 伺服器動作間隔**。
2. **MUST NOT assume: 客戶端 FPS ＝ 遊戲邏輯 Timing**。
3. **MUST NOT assume: 傷害必須在動畫打擊幀（Impact Frame）才結算**。
4. **MUST NOT assume: 怪物 30ms AI Tick ＝ 怪物攻擊速度**。
5. **MUST NOT assume: CheckSpeed 是伺服器主動排程調度器**。
6. **MUST NOT assume: L1J 1.82 所有傷害（含 DOT、陷阱、特殊技能）永遠無前搖且即時**。
7. **MUST NOT assume: OpenKore 的定時模式可直接套用為 L1J 1.82 世界規則**。
8. **MUST NOT assume: 可以藉由 `time.sleep()` 實現 Temporal Runtime**。
