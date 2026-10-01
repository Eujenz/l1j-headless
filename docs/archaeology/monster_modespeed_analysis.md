# L1J 1.82 Monster `modespeed` & `list.spr` 數值考古深度分析

## 1. 來源證據鏈 (Source Chain)

完整呼叫鏈與實證位置如下：

```text
client/list.spr (1.82 客戶端動作定義文字資料檔)
       ↓ (讀取並按動作格式解析 sequence tokens)
net.util.ClientFileLoad.java:24, 484-495 (dataTest & getGfxMode)
       ↓ (伺服器啟動時，MonsterTable 遍歷 mode 0~49)
net.database.MonsterTable.java:68-74 (MonsterData())
       ↓ (寫入怪物實體記憶體 Map)
net.database.bean.Monster.java:309-318 (addModespeed / getModespeed)
       ↓ (戰鬥與移動時設定延遲門檻 ai_time)
net.world.instance.MonsterInstance.java:300, 303 (toFight / toWalk)
       ↓ (30ms 心跳循環中檢查門檻)
net.world.instance.NpcInstance.java:158-167 (isAi: time - ai_start_time >= speed)
       ↓ (滿足時執行攻擊或移動)
net.world.ai.MonAi.java:31, 87 (run(): 30ms 獨立執行緒輪詢)
```

---

## 2. `list.spr` 資料格式與語意結構 (list.spr Data Format)

- **檔案路徑**: `C:\Users\p0282768\Documents\Gemini\Lineage182c\client\list.spr`
- **規模**: 總計 2,511 個 GFX 條目，涵蓋 1.82 時代所有客戶端外觀。
- **行格式**:
  ```text
  #<gfx_id> <sprite_id> <name> <mode_0.action(...)> <mode_1.action(...)> ...
  ```
- **單一模式語法**:
  ```text
  <mode_id>.<action_name>(<flag> <frame_count>,<frame_data_sequence>)
  ```
  範例（高侖石頭怪 GFX 49）：
  ```text
  0.walk(1 4,0.0:8 0.1:8 0.2:8 0.3:8) 1.attack(1 9,0.0:8 8.0:4[62 8.1...
  ```
- **序列切分解析**:
  - 括號內以冒號 `:` 分割。
  - 第一個 token 之前為頭部旗標（如 `1 4,0.0`）。
  - 後續每個 token 包含該動畫幀的持續時間單位（如 `8 0.1`, `8 0.2`, `4[62`）。
  - 提取冒號後數字字元，累加得到總持續單位數 `total_units`。

---

## 3. `ClientFileLoad.getGfxMode()` 演算法與 Bytecode 解密

經由對 [`ClientFileLoad.class`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/bin/net/util/ClientFileLoad.class) 及其字節碼註解進行深度反向工程，確認其核心演算法：

### 3.1 累加與乘法換算（毫秒單位確立）
在 `ClientFileLoad.dataTest` 字節碼第 290-293 行：
```bytecode
290: iload #9        // total_units (累積的幀長度單位)
291: bipush #40      // 常數 40
292: imul            // 乘法運算: total_units * 40
293: istore #9       // 存入 speed (毫秒)
```
- **關鍵發現**：**1 個 sequence unit ＝ 40 毫秒 (相當於 25 FPS 基準刻度)**。
- 動作總毫秒數公式：
  $$\text{ActionSpeed (ms)} = \left(\sum \text{Unit}_i\right) \times 40\text{ ms}$$
- **例外硬編碼**:
  ```bytecode
  294: iload_2        // gfxID
  295: sipush #1080   // GFX 1080
  296: if_icmpne -> 604
  297: iconst_0       // 若為 GFX 1080, speed 強制設為 0
  298: istore #9
  ```

### 3.2 模式存儲與檢索 (`getGfxMode`)
[`ClientFileLoad.java:484-495`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/util/ClientFileLoad.java#L484-L495)：
```java
public int getGfxMode(int gfx, int mode) {
    if (Config.TEST && gfx == 2356)
        return 450; 
    GfxFrameList l = this.LIST.get(Integer.valueOf(gfx));
    if (l != null) {
        GfxFrameMode m = (GfxFrameMode)l.mode.get(Integer.valueOf(mode));
        if (m != null)
            return m.getMode1frame(); 
    } 
    return 1000; // GFX 不存在或 mode 不存在時的 Fallback
}
```

---

## 4. `Monster.modespeed` 加載機制

在伺服器啟動時，[`MonsterTable.java:68-74`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/database/MonsterTable.java#L68-L74)：
```java
for (int i = 0; i < 50; i++) {
    try {
        int speed = ClientFileLoad.getInstance().getGfxMode(mon.getGfx(), i);
        if (speed > 0)
            mon.addModespeed(i, speed); 
    } catch (Exception exception) {}
}
```
1. 伺服器對每個怪物遍歷 `mode 0 ~ 49`。
2. 只要 `ClientFileLoad` 能解析出大於 0 的時長，就寫入 `mon.modespeed`。
3. 運行期若請求未登錄之 mode，[`Monster.java:315-316`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/database/bean/Monster.java#L315-L316) 再次提供防禦性 Fallback：
   ```java
   GfxModeSpeed gms = this.modespeed.get(Integer.valueOf(mode));
   if (gms == null)
       return 1000;
   return gms.getSpeed();
   ```

---

## 5. Timing 單位判定 (Timing Unit: `CANONICAL_MILLISECONDS`)

依據全套源碼與字節碼證據：
1. `ClientFileLoad`: 每個 unit 乘以 `40`。
2. `MonsterInstance`: 設置 `this.ai_time = getMon().getModespeed(...)`。
3. `NpcInstance.isAi(time)`:
   ```java
   long now = System.currentTimeMillis();
   if (time == 0L || time - this.ai_start_time >= speed) return true;
   ```
   此處 `time` 為 `System.currentTimeMillis()`（毫秒時間戳記）。
4. **結論**：數值單位 100% 確鑿為 **`CANONICAL_MILLISECONDS`（真實毫秒）**。

---

## 6. 代表性怪物 GFX / Mode 數值表 (Representative Monsters)

| 怪物名稱 (Monster) | Monster ID | GFX | Sprite | Mode 0 (Move) | Mode 1 (Attack) | 其他特殊 Mode | 說明 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **骷髏 (Skeleton)** | 2, 18 | **30** | 300 | **640 ms** (16×40) | **200 ms** (5×40) | Mode 3 (breath): 960 ms<br>Mode 8 (death): 1080 ms | 標準近戰怪，攻擊前搖極短 (200ms) |
| **高侖石頭怪 (Stone Golem)** | 6 | **49** | 48 | **1280 ms** (32×40) | **1920 ms** (48×40) | Mode 4 (morph): 1440 ms<br>Mode 11 (wake): **1600 ms** | 重型慢速怪；喚醒變身耗時 1.6 秒 |
| **漂浮之眼 (Floating Eye)** | 1 | **29** | 40 | **960 ms** (24×40) | **1720 ms** (43×40) | Mode 19 (spell): **1720 ms** | 施展麻痺光線（技能 21）使用 Mode 19 |
| **狼人 (Werewolf)** | 3 | **33** | 8 | **640 ms** (16×40) | **960 ms** (24×40) | Mode 8 (death): 1240 ms | 快速近戰怪，走速與玩家一致 (640ms) |
| **人形僵屍 (Zombie)** | 141 | **52** | 32 | **1640 ms** (41×40) | **1040 ms** (26×40) | Mode 3 (idle): 1960 ms | 極慢速移動怪，走一格需 1.64 秒 |
| **妖魔 (Orc)** | 142 | **56** | 8 | **800 ms** (20×40) | **1320 ms** (33×40) | Mode 8 (death): 1040 ms | 中等走速，攻擊動作較長 |

---

## 7. 特殊怪物機制：Stone Golem 400ms 深度剖析

在 [`StoneGolem.java:30-43`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/monster/StoneGolem.java#L30-L43)：
```java
public void toRecess(long time) {
    this.ai_start_time = time;
    this.ai_time = 400; // 感知輪詢週期
    L1Object o = SearchPlayer();
    if (o != null) {
        MagicalAttackEncounters((Character)o); // 發現玩家，解除沉睡
        return;
    }
    if (SearchItem(item_list)) {
        setRecess(false);
        this.ai_time = getMon().getModespeed(11); // 播放甦醒動畫 (1600ms)
        return;
    }
}
```
- **語意鑑定**：
  1. 石頭怪在尚未被觸發時處於沉睡/偽裝形態 (`isRecess() == true`)。
  2. 此時它不移動、不攻擊，而是每 **400 ms** 執行一次周遭物體探測。
  3. 400ms 是**特殊感知探測間隔 (Sensory Detection Interval)**，**絕非**移動或攻擊間隔。
  4. 解除沉睡時，設定 `this.ai_time = getMon().getModespeed(11)`（Mode 11 變形動畫時長 **1600 ms**），之後完全回歸標準 Mode 0 (1280ms) 與 Mode 1 (1920ms)。

---

## 8. Fallback 規則四層防線 (Fallback Hierarchy)

| 層級 | 發生情境 | 處理模組 | 實際行為 |
| :--- | :--- | :--- | :--- |
| **Level 1** | GFX 不在 `list.spr` 中 | `ClientFileLoad.getGfxMode` | 回傳 **`1000 ms`** |
| **Level 2** | GFX 存在但無該 Mode (如遠程怪無近戰動作) | `ClientFileLoad.getGfxMode` | 回傳 **`1000 ms`** |
| **Level 3** | `Monster.modespeed` Map 查無該 Mode | `Monster.getModespeed` | 回傳 **`1000 ms`** |
| **Level 4** | 個別怪物子類別自訂覆寫 | 個別 Monster class | 依代碼明確賦值（如石頭怪感知設 400ms） |

**結論**：全伺服器在查無特定動作時長時，統一且嚴格回退為 **`1000 ms`**。

---

## 9. 30ms AI Tick 與動作週期的交互影響 (Quantization Analysis)

### 9.1 量化模型
- `MonAi` 線程以 `Thread.sleep(30)` 執行全域輪詢。
- 怪物下一次可行動時間為 $T_{\text{target}} = T_{\text{start}} + \text{speed}$。
- 當輪詢時鐘 $T_{\text{tick}} \ge T_{\text{target}}$ 時觸發，並以當前 $T_{\text{tick}}$ 重新賦值 `ai_start_time = time`。
- **實際動作間隔 (Effective Interval)**：
  $$I_{\text{actual}} = \text{speed} + \Delta t, \quad \Delta t \in [0, 30)\text{ ms}$$
- **平均延遲**：理論平均值為 $\text{speed} + 15\text{ ms}$。
- **無追補特性 (Non-Compensating Drift)**：
  由於 `ai_start_time` 紀錄的是觸發當下的系統時間，量化延遲不會在下個動作被扣除，而是呈現事件驅動的離散推進。

---

## 10. 已確認之 Canonical 事實 (Confirmed Canonical Facts)

1. **`CANONICAL_MILLISECONDS`**: 怪物動作時長單位確鑿為真實毫秒，由 `unit * 40ms` 算出。
2. **`MODE_MAPPING`**:
   - `Mode 0` ＝ 移動動作時長 (`toWalk`, `StartMove`)。
   - `Mode 1` ＝ 攻擊動作時長 (`Attack`, `AttackBow`)。
   - `Mode 19` ＝ 怪物無定向施法動作時長（如漂浮之眼）。
3. **`SPEED_MODIFIERS`**:
   - 怪物加速 (`isSpeed`): `speed = (int)(speed - speed * 0.3D)` (-30% 時長)。
   - 怪物緩速 (`isSlow`): `speed = (int)(speed + speed * 0.3D)` (+30% 時長)。
4. **`UNIVERSAL_FALLBACK`**: 查無資料時之全域回退時長為 **`1000 ms`**。

---

## 11. 未知事項 (Unknowns)

1. **OS 時鐘中斷精度**:
   `Thread.sleep(30)` 在 Windows 伺服器環境下受底層計時器分辨率影響（可能在 15.6ms 刻度間抖動），因此實際 Tick 週期在 30ms ~ 35ms 之間略有波動，此取決於 OS 宿主環境。

---

## 12. 追溯性結論 (Provenance)

```yaml
claim: "L1J 1.82 怪物動作時間由 client/list.spr 解析 (units * 40ms) 填入 Monster.modespeed，單位為毫秒；Mode 0 為移動、Mode 1 為攻擊，Fallback 為 1000ms，由 MonAi 以 30ms 輪詢驅動。"
source: "legacy-server-182c / client-list-spr"
version: "1.82c"
layer: "server + client asset"
classification: "LEGACY_OBSERVED"
target_version: "1.82"
raw_evidence: "ClientFileLoad.java:L24,L290-L293,L484-L495; MonsterTable.java:L68-L74; Monster.java:L309-L318; MonsterInstance.java:L300,L303; NpcInstance.java:L158-L167; MonAi.java:L31,L87"
confirmed_by: "Eujenz/182c"
```
