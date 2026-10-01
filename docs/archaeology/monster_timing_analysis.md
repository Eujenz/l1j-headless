# L1J 1.82 Legacy Server — Monster Timing & AI Scheduler 深度考古分析

## 1. 核心結論摘要 (Executive Summary)

本研究自 L1J 1.82c Legacy Server Java 源碼（`Eujenz/182c`）完整追查怪物 AI 執行鏈、移動 Timing、攻擊 Timing 與排程機制，得出決定性歷史結論：

> [!IMPORTANT]
> **重大判定：`SPRITE_FRAME_PC_ONLY` (Case B)**
> 1. **怪物完全不使用 `sprite_frame.sql` 或 `SprTable.java`**。
> 2. `sprite_frame.sql` 與 `SprTable` 僅為玩家角色 (`PcInstance`) 之防加速檢測 (`CheckSpeed.java`) 服務。
> 3. 怪物 AI 由獨立線程 `MonAi.java` 以 **`30 ms` 全域 Tick** 進行輪詢驅動。
> 4. 怪物的動作時間來自 `Monster.modespeed`（由 `client/list.spr` 初始化），未命中時之普適 Fallback 為 **`1000 ms`**。
> 5. 怪物移動判定動作為 `GfxMode`，攻擊判定動作為 `GfxMode + 1`。

---

## 2. 呼叫鏈完整追蹤 (Complete Call Chain)

### 2.1 怪物 AI 排程調度鏈
```text
net.Server.java:128
       ↓
net.world.ai.MonAi.getInstance().start()  (啟動獨立背景執行緒 Thread)
       ↓
net.world.ai.MonAi.run()  (Thread.sleep(30)，以 30ms 為基準 Tick 輪詢)
       ↓ (遍歷 list 中所有 MonsterInstance)
net.world.instance.NpcInstance.isAi(time)  (門檻判定: time - ai_start_time >= speed)
       ↓ (若門檻達成且處於戰鬥)
net.world.instance.MonsterInstance.toFight(time)
       ├── 距離內 → Attack / AttackBow → ai_time = getMon().getModespeed(GfxMode + 1)
       └── 距離外 → StartMove → ai_time = getMon().getModespeed(GfxMode)
```

### 2.2 怪物動作時長加載鏈
```text
client/list.spr (1.82 客戶端動作定義檔)
       ↓
net.util.ClientFileLoad.java:24 (讀取 list.spr 並快取各 GFX 模式時長)
       ↓
net.database.MonsterTable.java:70 (加載資料庫 monster 表時, 遍歷 mode 0~49)
       ↓
net.database.bean.Monster.java:310 (addModespeed(mode, speed))
       ↓
MonsterInstance 運行期調用: getMon().getModespeed(mode)
       ↓ (查無模式或 list.spr 未命中時)
Fallback: 1000 ms (Monster.java:316 / ClientFileLoad.java:494)
```

---

## 3. 怪物移動 Timing (Monster Move Timing)

### 3.1 觸發位置與實證行號
- **戰鬥中追擊移動**:
  [`MonsterInstance.java:302-303`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/MonsterInstance.java#L302-L303)
  ```java
  StartMove(cha.getX(), cha.getY());
  this.ai_time = getMon().getModespeed(getGfxMode());
  ```
- **非戰鬥隨機遊蕩**:
  [`NpcInstance.java:234-236`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/NpcInstance.java#L234-L236)
  ```java
  this.ai_start_time = time;
  if (this instanceof MonsterInstance) {
      this.ai_time = ((MonsterInstance)this).getMon().getModespeed(getGfxMode());
  }
  ```
- **逃跑移動**:
  [`NpcInstance.java:211-212`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/NpcInstance.java#L211-L212)
  ```java
  this.ai_start_time = time;
  this.ai_time = getNpc().getModespeed(getGfxMode());
  ```

### 3.2 動作模式與時間計算
- 移動動作模式恆為 `getGfxMode()`（一般為模式 0）。
- 基礎間隔自 `Monster.modespeed` 讀取，查無資料時預設為 **`1000 ms`**。
- 加速與緩速狀態修正（見第 5 節）。

---

## 4. 怪物攻擊 Timing (Monster Attack Timing)

### 4.1 觸發位置與實證行號
[`MonsterInstance.java:294-300`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/MonsterInstance.java#L294-L300)
```java
if (getDistance(cha.getX(), cha.getY(), cha.getMap(), this.Areaatk) && LongAttackCK(cha, this.Areaatk)) {
    if (this.Areaatk > 2) {
        AttackBow(cha, cha.getX(), cha.getY(), getGfxMode() + 1, 66, true);
    } else {
        Attack(cha, cha.getX(), cha.getY(), getGfxMode() + 1, 0);
    } 
    this.ai_time = getMon().getModespeed(getGfxMode() + 1);
}
```

### 4.2 核心規律
1. **攻擊 Action ID ＝ `getGfxMode() + 1`**：無論近戰或是遠程，攻擊動作模式皆為移動模式 + 1（一般為模式 1）。
2. **攻擊間隔 ＝ `getMon().getModespeed(getGfxMode() + 1)`**：若未定義則 Fallback 為 **`1000 ms`**。
3. 怪物攻擊**沒有獨立的攻擊計時器線程**，而是透過將下一次 AI 觸發時間 `ai_time` 設為攻擊動作時長，達成「攻擊後等待後搖結束才能進行下一次行動」的效果。

---

## 5. 怪物 AI Scheduler 架構分析

### 5.1 驅動心跳：30 ms 全域 Tick
[`MonAi.java:31, 87`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/ai/MonAi.java#L31-L87)
- 單一全域背景線程 `MonAi`：
  ```java
  this.SleepTime = 30; // 30ms 心跳
  ...
  while (true) {
      for (MonsterInstance mon : this.list) {
          if (mon.isAi(time)) { ... }
      }
      Thread.sleep(this.SleepTime);
      time = System.currentTimeMillis();
  }
  ```

### 5.2 門檻檢測器：`isAi(long time)`
[`NpcInstance.java:158-167`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/NpcInstance.java#L158-L167)
```java
public boolean isAi(long time) {
    int speed = this.ai_time;
    if (isSpeed())
        speed = (int)(speed - speed * 0.3D); // 加速狀態: 縮短 30% (70% 時長)
    if (isSlow())
        speed = (int)(speed + speed * 0.3D); // 緩速狀態: 增加 30% (130% 時長)
    if (time == 0L || time - this.ai_start_time >= speed)
        return true; 
    return false;
}
```

### 5.3 架構結論
怪物 AI 不是純粹的「每個 Tick 固定前進」，也不是純粹的「個別定時器 TimerTask」，而是：
> **「以 30ms 全域輪詢為心跳，各實體依前次 Action 決定的延遲門檻 (`ai_time`) 進行自主推進」的混成架構（Tick-Polled Action-Threshold Architecture）。**

---

## 6. Player vs Monster Timing Evidence Matrix

本表嚴格依據 1.82 Server Java 源碼及資料庫實證比對：

| 行為維度 | 玩家 (PC) | 怪物 (Monster) | 關鍵差異與本質原因 | 實證源碼位置 |
| :--- | :--- | :--- | :--- | :--- |
| **Move Cadence** | **640 ms** (基準步行) | **`modespeed(GfxMode)`**<br>(Fallback: **1000 ms**) | 玩家步速固定由伺服器校驗；怪物步速由外觀模式時長決定，預設為 1000ms。 | PC: `SprTable.java:69`<br>Mon: `MonsterInstance.java:303` |
| **Attack Cadence** | **760 ~ 1840 ms**<br>(依職業與武器高度異質) | **`modespeed(GfxMode + 1)`**<br>(Fallback: **1000 ms**) | 玩家依據武器特化動作時長；怪物依據 GfxMode+1 時長或預設 1 秒。 | PC: `SprTable.java:84`<br>Mon: `MonsterInstance.java:300` |
| **Skill (NoDir)** | **800 ms** (action 19) | **`modespeed(19)`** (例如浮眼) | 玩家與怪物施法動作均有獨立的 Action 19 定義。 | PC: `SprTable.java:73`<br>Mon: `FloatingEye.java:42` |
| **加速狀態 (Haste)** | **`interval * 0.75`**<br>(-25% 時長 / 1.33x 速) | **`speed - speed * 0.30`**<br>(-30% 時長 / 1.43x 速) | **怪物加速比玩家略快！** 怪物實作減 30% 時長，玩家實作乘 0.75。 | PC: `CheckSpeed.java:102`<br>Mon: `NpcInstance.java:161` |
| **緩速狀態 (Slow)** | **`interval / 0.75`**<br>(+33.3% 時長) | **`speed + speed * 0.30`**<br>(+30% 時長) | 玩家與怪物緩速公式存在些微浮點差異。 | PC: `CheckSpeed.java:104`<br>Mon: `NpcInstance.java:163` |
| **時間驅動核心** | **客戶端封包事件驅動**<br>(由 `CheckSpeed` 檢驗) | **`MonAi` 30ms 輪詢循環**<br>+ `isAi` 門檻檢查 | 玩家動作由客戶端送出封包；怪物由伺服器單一背景線程自主推進。 | PC: `PcInstance.java:460`<br>Mon: `MonAi.java:87` |
| **資料來源** | **`sprite_frame.sql`**<br>(via `SprTable`) | **`client/list.spr`**<br>(via `ClientFileLoad`) | **完全隔離的兩套體系！** | PC: `SprTable.java:48`<br>Mon: `ClientFileLoad.java:24` |

---

## 7. 證據分類明確判定 (Evidence Classification Decision)

### 判定：`SPRITE_FRAME_PC_ONLY` (Case B)
- 實證確認：`sprite_frame.sql` 僅在 `SprTable` 中讀取，且 `SprTable` 僅被 `CheckSpeed` (PC) 引用。
- 怪物實體 (`MonsterInstance` / `NpcInstance`) 內部完全未引用 `SprTable`。
- 怪物 Timing 具有原生獨立的架構：`MonAi` (30ms loop) + `NpcInstance.isAi()` + `Monster.modespeed` (來自 `list.spr`，fallback 1000ms)。

---

## 8. 未知事項與後續研究邊界 (Unknowns)

1. **`list.spr` 的完整二進位/文字結構**:
   `ClientFileLoad.java` 中的 `dataTest` 方法在 Java 源碼中為 byte-code 註解，雖然已知其讀取 `client/list.spr` 並返回 `mode1frame`，但該檔案的二進位欄位與各怪物的精確毫秒映射表可做進一步結構化導出。
2. **特殊怪物的覆寫行為**:
   部分怪物子類別（如 `StoneGolem.java:32` 的 `this.ai_time = 400`）具有 hard-coded 的自訂暫停時間（例如石頭怪偽裝沉睡時每 400ms 搜尋一次周遭玩家）。此類特殊行為屬於個別 Monster 覆寫，非通用公式。
