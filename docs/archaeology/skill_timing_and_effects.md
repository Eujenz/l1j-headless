# L1J 1.82 Skill Timing and Effects Archaeology

## 1. 考古來源資料 (Archaeology Provenance)

- **資料庫來源**: `db/lineage/skill_list.sql` (`skill_list` 資料表)
- **Java 伺服器核心**:
  - `src/net/world/instance/skill/Magic.java`
  - `src/net/world/instance/skill/function/EnergyBolt.java`
  - `src/net/world/instance/skill/function/Heal.java`
  - `src/net/world/instance/skill/function/Haste.java`
  - `src/net/check/CheckSpeed.java`
  - `src/net/database/SprTable.java`
- **證據等級**: `CONFIRMED_CANONICAL` (PRIMARY_DATA_AUTHORITY)

---

## 2. 施法時序三大獨立維度 (Three Decoupled Timing Dimensions)

原始伺服器將施法時序嚴格拆分為三個獨立維度，**禁止混淆**：

```text
1. 全域施法動作間隔 (Global Cast Action Interval)
   - 定向攻擊魔法 (Action 18): 880 ms (SprTable.java:101, CheckSpeed.java:82)
   - 無方向輔助魔法 (Action 19): 800 ms (SprTable.java:116, CheckSpeed.java:85)
   - 語義：施法瞬刻開啟的動作冷卻窗口，此窗口內禁止發起下一次物理攻擊或施法。

2. 技能獨立冷卻時間 (Skill Reuse Delay)
   - 來源：`skill_list.sql` 的 `reuse_delay` 欄位。
   - 語義：個別法術的冷卻時間（如木乃伊、極道落雷等）。若為 0，則僅受全域動作間隔約束。

3. 傷害與效果結算時間 (Damage & Effect Timing)
   - 語義：在 `toMagic()` 函數調用當下立即結算，傷害扣血與治癒加血為 IMMEDIATE (T = 0)。
```

---

## 3. MVP-04 核心代表性法術規範 (Certified Skills Specification)

### 3.1 攻擊法術：光箭 (Energy Bolt)
- **Skill ID**: 4 (內部位元旗標 ID: 8)
- **名稱**: `光箭` (`EnergyBolt.java`)
- **消耗**: MP 3, HP 0
- **動作類別**: 定向攻擊魔法 (`Action 18`, 動作間隔 **`880 ms`**)
- **獨立冷卻**: `reuse_delay = 0 ms`
- **傷害結算點**: **`IMMEDIATE` ($T = 0\text{ ms}$)**
- **公式** (`Magic.java:164-176`):
  $$\text{Damage} = \frac{\text{rand}(\text{mindmg}, \text{sp}) \times \text{maxdmg} + \text{IntDmg}}{2}$$
  對於初階角色（SP 約 1～2，mindmg=1，maxdmg=2），傷害基礎約為 2～8 點魔法傷害。

### 3.2 支援/治療法術：初級治癒術 (Lesser Heal)
- **Skill ID**: 1 (內部位元旗標 ID: 1)
- **名稱**: `初級治癒術` (`Heal.java`)
- **消耗**: MP 4, HP 0
- **動作類別**: 無方向魔法 (`Action 19`, 動作間隔 **`800 ms`**)
- **獨立冷卻**: `reuse_delay = 0 ms`
- **效果結算點**: **`IMMEDIATE` ($T = 0\text{ ms}$)**
- **治癒效果**:
  - 目標為生者：立即回復 HP (`min_dmg=4, max_dmg=14`，約回復 4~14 HP)。
  - 目標為不死系怪物（Undead）：反轉為神聖魔法傷害（立即扣除目標怪物 HP）。

### 3.3 狀態/增益法術：加速術 (Haste)
- **Skill ID**: 28 (內部位元旗標 ID: 4)
- **名稱**: `加速術` (`Haste.java`)
- **消耗**: MP 25, HP 20
- **動作類別**: 無方向魔法 (`Action 19`, 動作間隔 **`800 ms`**)
- **持續時間**: 法術版 1200 秒（藥水版 300 秒）
- **效果機制** (`CheckSpeed.java:101-106`, `NpcInstance.java:160-163`):
  - 玩家：移動與攻擊間隔 $\times 0.75$（行走 640ms $\to$ 480ms；女騎劍 920ms $\to$ 690ms；男騎劍 880ms $\to$ 660ms）。
  - 怪物：動作間隔 $- 30\%$（即 $\times 0.70$）。
  - 衝突消除：若目標處於緩速（Slow）狀態，加速術會直接消除緩速，並相互抵消（`HastePotion.java:31`）。
