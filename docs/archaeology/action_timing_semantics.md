# L1J 1.82 Action Timing Semantics 深度考古分析

## 1. 研究範圍與核心問題 (Research Scope)

承接 Phase B Task 1～3 確立的資料結構，本研究深入 L1J 1.82 Legacy Server（`Eujenz/182c`）之戰鬥、移動與施法執行鏈，解決最關鍵的語義問題：

> **L1J 1.82 所謂的 Action Timing，到底代表「動畫時長」、「傷害延遲時間」，還是「下一次可以行動的冷卻間隔」？**

---

## 2. 核心歷史結論 (Executive Summary)

> [!IMPORTANT]
> **重大實證結論**：
> 1. **物理攻擊傷害結算為瞬間完成 (`DAMAGE_TIMING = IMMEDIATE`)**：
>    已驗證之 PC 與 Monster 標準物理攻擊（含近戰與弓箭），傷害計算與目標血量扣減均在 `Attack()` 呼叫的當下**同步且立即完成**，不存在任何攻擊前搖延遲（No Pre-Damage Delay）。（注意：此結論限於常規物理打擊，特殊延遲法術或 DOT 需個別依源碼驗證）。
> 2. **Action Timing 實質為「動作間隔閘門」(`ACTION_INTERVAL`)**：
>    `sprite_frame.frame` (PC) 與 `Monster.modespeed` (Monster) 所定義的毫秒數，在伺服器端本質代表的是**「從動作發起瞬刻起算，到允許發起下一次動作之間的強制時間窗口 (Action Interval Gate)」**，伺服器端並不存在『攻擊動畫播放完成』才開始計算冷卻的事件機制。
> 3. **PC 端為事後檢驗，Monster 端為主動門檻**：
>    - PC：伺服器假設正常客戶端會受 DirectDraw 動畫播放限制發包，伺服器透過 `CheckSpeed.java` 進行被動校驗。
>    - Monster：伺服器透過 `MonAi.java`（30ms 輪詢）在 `ai_start_time + speed` 前主動阻擋下一次行動。

---

## 3. PC Attack Timing 與傷害時間點 (PC Attack Timing)

### 3.1 執行鏈追蹤
```text
Client C_Attack 封包
  ↓
net.world.instance.PcInstance.Attack() (PcInstance.java:600-641)
  ├── 1. getCheckSped().checkInterval(ATTACK) [防加速校驗] (line 603)
  ├── 2. dmg = DmgSystem(target, false, 1) [命中與傷害計算] (line 623)
  ├── 3. target.setCurrentHp(target.getCurrentHp() - dmg) [立即扣血!] (line 631)
  └── 4. SendPacket(new S_ObjectAttack(...)) [廣播動畫封包給客戶端] (line 641)
```

### 3.2 遠程攻擊 (AttackBow)
在 [`PcInstance.java:684-685`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/PcInstance.java#L684-L685)：
```java
target.setCurrentHp(target.getCurrentHp() - dmg);
SendPacket((S_BasePacket)new S_ObjectAttack(this, target, action, dmg, effectId, true, arrow), true);
```
- **實證事實**：雖然箭矢在客戶端畫面上需要飛行時間，但在 1.82 伺服器端，**扣血與命中是完全同步即時生效的**。

---

## 4. Monster Attack Timing 與傷害時間點 (Monster Attack Timing)

### 4.1 執行鏈追蹤
```text
net.world.ai.MonAi 30ms 輪詢檢測 isAi(time) == true
  ↓
net.world.instance.MonsterInstance.toFight(time) (MonsterInstance.java:293-305)
  ├── 1. this.ai_start_time = time [記錄動作起點] (line 293)
  ├── 2. Attack(...) / AttackBow(...) (line 296, 298)
  │        ↓
  │      NpcInstance.Attack() (NpcInstance.java:319-331)
  │        ├── dmg = DmgSystem(target, false, 1) (line 323)
  │        ├── target.setCurrentHp(target.getCurrentHp() - dmg) [立即扣血!] (line 327)
  │        └── SendPacket(new S_ObjectAttack(...)) (line 330)
  └── 3. this.ai_time = getMon().getModespeed(getGfxMode() + 1) [設定後搖冷卻] (line 300)
```

### 4.2 實證事實
- 怪物發起攻擊時，目標 HP 在同一呼叫訊框內即被扣除。
- 隨後設定 `this.ai_time = modespeed`。在接下來的毫秒跨度內，`isAi()` 持續返回 `false`，怪物處於動作僵直與冷卻狀態。

---

## 5. 動作時間軸模型：Action Interval vs Damage Timing

```text
時間軸 (Timeline)
T = 0 ms (Action Start)
  ├── [Damage Event]: 傷害結算、HP 扣除、死亡判定 (IMMEDIATE)
  ├── [Packet Broadcast]: S_ObjectAttack 送出
  │
  ├── [Action Cooldown Window]:
  │     - PC: CheckSpeed 累加計時，若再次發包過快則記錄違規
  │     - Monster: isAi() == false, 禁止任何移動、攻擊或施法
  │
T = ActionInterval (Action Complete / Next Action Allowed)
  └── 實體冷卻解除，允許發起下一次 Action (MOVE, ATTACK, SPELL)
```

### 概念矩陣 (PC vs Monster)
| 概念階段 | 玩家角色 (PC) | 怪物 (Monster) | 實證源碼 |
| :--- | :--- | :--- | :--- |
| **Action Start** | 接收客戶端攻擊封包瞬刻 | `MonAi` 輪詢觸發 `toFight` 瞬刻 | `PcInstance.java:600` / `MonAi.java:85` |
| **Damage Event** | **T = 0 ms (IMMEDIATE)** | **T = 0 ms (IMMEDIATE)** | `PcInstance.java:631` / `NpcInstance.java:327` |
| **Animation Duration** | 客戶端 DirectDraw 自行播放幀數 | 客戶端 DirectDraw 自行播放幀數 | `TW13081901.txt` / `list.spr` |
| **Action Cooldown** | 期間內發包視為異常 | 期間內 `isAi()` 返回 `false` | `CheckSpeed.java:67` / `NpcInstance.java:164` |
| **Next Action Allowed**| $T \ge \text{ActionInterval}$ | $T \ge \text{ai\_start\_time} + \text{ai\_time}$ | `CheckSpeed.java:75` / `NpcInstance.java:164` |

---

## 6. Skill Timing 語義分析

### 6.1 玩家技能 (PC Skill)
[`PcSkill.java:120-146`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/instance/skill/PcSkill.java#L120-L146)
1. **技能獨立冷卻 (`Skill Reuse Delay`)**:
   `if (m.skill.getReuseDelay() > 0 && this.pc.checkSkillDelay(m.getSkill().getSkill_id())) return;`
   個別魔法在 `skills` 表中有專屬的 `reuse_delay`（如特定大魔法冷卻數秒）。
2. **施法效果結算 (`Damage Timing`)**:
   `m.toMagic(id)` 立即結算傷害與狀態（**IMMEDIATE**）。
3. **全域施法動作冷卻 (`Global Cast Cooldown`)**:
   攻擊魔法檢查 `CheckSpeed.ACT_TYPE.SPELL_DIR` (Action 18: 880ms)；輔助魔法檢查 `SPELL_NODIR` (Action 19: 800ms)。

### 6.2 怪物技能 (Monster Skill)
[`FloatingEye.java:40-46`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/world/monster/FloatingEye.java#L40-L46)
1. `getSkill().get(21).toMagic(o.getObjectId());`：立即產生麻痺效果。
2. `this.ai_time = getMon().getModespeed(Magic.MagicAction2);`：將下一次行動間隔設為 Mode 19 之時長（1720ms）。

---

## 7. `CheckSpeed` 語義剖析：Gameplay Cooldown vs Anti-Cheat Threshold

[`CheckSpeed.java:61-84`](file:///C:/Users/p0282768/Documents/Gemini/Lineage182c/src/net/check/CheckSpeed.java#L61-L84)
- **被動檢測特徵**：
  若玩家在未滿 `rightInterval` 時再度發送攻擊，`checkInterval()` 僅累積 `_injusticeCount++`，**並未攔截阻擋當次攻擊**；只有連續違規達 10 次才執行處罰。
- **對 Headless Runtime 的啟示**：
  由於被動服務端仰賴客戶端自我約束，**在 Headless 環境下，代理必須將 `rightInterval` 作為主動的動作間隔排程依據**，否則將導致嚴重的非法違規。

---

## 8. 動作間隔影響因素完整體系 (Action Interval Modifiers)

```text
Base Action Interval (來自 sprite_frame.sql 或 list.spr)
       ↓
[Weapon / GfxMode 決定基礎動作代碼]
       ↓
[Speed Modifier]
  - PC 加速: interval = (int)(interval * 0.75D)
  - PC 緩速: interval = (int)(interval / 0.75D)
  - PC 勇水: interval = (int)(interval * 0.75D)
  - Monster 加速: speed = (int)(speed - speed * 0.3D)
  - Monster 緩速: speed = (int)(speed + speed * 0.3D)
       ↓
Final Action Interval (即為下一次 Action 前需等待的毫秒數)
```

---

## 9. Canonical Timing Vocabulary (標準時序詞彙表)

為防止未來架構混淆，確立以下嚴格專有名詞規範：

| 詞彙 (Vocabulary) | 嚴格定義 (Definition) | 1.82 實證來源 | 誤用警語 |
| :--- | :--- | :--- | :--- |
| **Animation Duration** | 客戶端動畫序列從第 0 幀播放至最後一幀的視覺呈現時間。 | `list.spr`, `TW13081901.txt` | 嚴禁誤用為傷害生效時間！ |
| **Action Interval** | 實體發起動作到允許發起下一次同類或異類動作的最小合法時間跨度（Action Interval Gate）。 | `sprite_frame.sql`, `Monster.modespeed` | 本專案 Temporal Runtime 之核心基準。 |
| **Damage Timing** | 攻擊判定、命中計算與目標 HP 扣減在時間軸上實際發生的時間點（**已驗證之標準物理攻擊為 IMMEDIATE**）。 | `PcInstance.java:631`<br>`NpcInstance.java:327` | 嚴禁自行假設攻擊前搖延遲！特殊法術需獨立驗證。 |
| **Attack Cooldown** | 攻擊動作發起後，禁止再次發起攻擊的等待時間窗口（數值等於 Attack Action Interval）。 | `CheckSpeed.java:99`<br>`MonsterInstance.java:300` | 與 Skill Reuse Delay 分離。 |
| **Skill Reuse Delay** | 個別特定魔法在資料庫定義的專屬重用冷卻時間。 | `skills.reuse_delay`, `PcSkill.java:123` | 獨立於全域動作間隔。 |
| **AI Tick** | 伺服器怪物 AI 執行緒的基礎輪詢掃描頻率（**固定為 30 ms**）。 | `MonAi.java:31` (`SleepTime = 30`) | 嚴禁誤用為怪物攻速！ |
| **Anti-Cheat Threshold** | 伺服器端校驗客戶端封包是否異常過快的容忍閥值。 | `CheckSpeed.java:65-67` | 這是安全門檻，非客戶端調度器。 |

---

## 10. 已確認之 Canonical 事實 (Confirmed Canonical Facts)

1. **`DAMAGE_TIMING_IMMEDIATE`**: L1J 1.82 伺服器在收到常規物理攻擊請求或怪物決定常規物理攻擊時，**立即進行命中與傷害結算，無前搖時間差**。
2. **`ACTION_INTERVAL_GATE`**: `sprite_frame.frame` 與 `modespeed` 代表的是**從動作觸發起算至允許下一次行動的保護窗口**。
3. **`SYNCHRONOUS_REMOTE_DAMAGE`**: 遠程物理攻擊（弓箭）在伺服器端同樣立即扣血，箭矢飛行時間僅為客戶端動畫效果。
4. **`DUAL_TIMING_FOR_SKILLS`**: 施法同時受「全域施法動作間隔 (800~880ms)」與「技能專屬 ReuseDelay」雙重約束。

---

## 11. 未知事項 (Unknowns)

1. **客戶端動畫阻斷機制 (Client Input Blocking)**:
   官方客戶端在播放受擊 (`damage`) 動畫或攻擊動畫時，具體的硬直幀數是否由客戶端 DirectDraw 鎖定輸入，抑或完全由伺服器封包狀態同步控制？此屬於 Client 內部機制，保留為 **`UNKNOWN`**。

---

## 12. 對未來 Temporal Runtime 設計之關鍵指引 (Runtime Implications)

在後續設計 Headless Temporal Runtime 時，應遵循此歷史實證架構：
1. **攻擊事件處理**：當狀態機切換至 `ATTACK` 時，於 **T = 0 立即結算傷害**。
2. **狀態鎖定期間**：將實體狀態置於 `COOLDOWN`，持續時長設定為 `ActionInterval`。
3. **推進下一次決策**：在 `ActionInterval` 屆滿前，禁止實體發起新的移動、攻擊或施法。
4. **絕不額外增加虛構的前搖計時器**，完全貼合 L1J 1.82 的真實行為。
