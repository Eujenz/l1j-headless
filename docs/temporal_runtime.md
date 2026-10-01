# L1J 1.82 Virtual Temporal Runtime Core 架構規格

> **重要定位聲明**：
> 本文件描述 Phase C Task 1 所建立的 **Deterministic Virtual Temporal Runtime Core**。
> 本核心為純粹的領域無關（Domain-Agnostic）底層設施，**尚未接入任何 gameplay 行為（無 Combat, Movement, Monster, Player, Session 接入）**。

---

## 1. Virtual Time (虛擬時間架構)

傳統遊戲機器人或模擬器常依賴作業系統的真實時間（如 `time.sleep()`, `threading.Timer()`, `asyncio.sleep()` 或真實輪詢迴圈）。這種方式存在根本缺陷：
- 測試速度受限於真實世界流速（1 小時模擬需等待真實 1 小時）。
- 多執行緒排程受作業系統時間片抖動（Jitter）影響，無法完全重現。
- 無法進行毫秒級確定性回放（Deterministic Replay）與時序差分比對。

**Virtual Temporal Runtime** 透過純虛擬時鐘推進時間：
- 時間推進完全由事件驅動（Event-driven discrete event simulation）。
- 當無事件時，時鐘瞬時躍遷至目標時間，耗時 0 秒真實時間。
- 100,000 個虛擬時間事件可在不到 1 秒內執行完畢。

---

## 2. Integer Millisecond Representation (整數毫秒表示法)

### 2.1 基準單位
時鐘與事件時間戳記內部統一採用 **整數毫秒 (`int`)**：
- 理由來自 L1J 1.82 Legacy Server 源碼（`System.currentTimeMillis()`）。
- 嚴格對應 Legacy 實證數值：$30\text{ ms}$ (AI Polling), $40\text{ ms}$ (Mode Unit), $640\text{ ms}$ (PC Walk), $760\sim 1840\text{ ms}$ (Attack), $800/880\text{ ms}$ (Spells), $1000\text{ ms}$ (Fallback)。
- 嚴禁使用浮點數秒（`float seconds`）避免 IEEE 754 精度累積誤差。
- 嚴禁使用 `datetime` 或 Wall-clock 時間物件。

### 2.2 VirtualClock 嚴格不變量 (Invariants)
- **單調非遞減 (Monotonic)**：時間只能向前流逝或停留原地，`advance(delta_ms)` 要求 `delta_ms >= 0`。
- **禁止時間倒流 (No Rewind)**：負向推進 `advance(-1)` 或向前倒退 `set(past)` 立即拋出 `ValueError`。
- **零推進合法且等冪 (Zero-Advance)**：`advance(0)` 合法返回目前時間，不觸發重複執行或無窮迴圈。

---

## 3. Event Ordering (確定性事件排序)

### 3.1 排序維度
佇列（Priority Queue / Min-Heap）中的事件嚴格依序比較：
$$\text{Order Key} = (\text{timestamp},\, \text{sequence})$$

1. **`timestamp` (絕對時間戳記)**：發生時間較早的事件優先執行。
2. **`sequence` (單調增量序號)**：當兩個或多個事件排定於同一虛擬時間戳記時，嚴格依排入佇列的先後順序（FIFO）執行。

### 3.2 比較安全性
`ScheduledEvent` 實作了專屬的比較運算子（`__lt__`, `__le__`, `__gt__`, `__ge__`），僅比較 `(timestamp, sequence)`，**絕對不比較 `callback` 物件**。這消除了 Python 在比較兩個不可比較的函式物件時拋出 `TypeError: '<' not supported between instances of 'function'` 的隱患。

---

## 4. Scheduler Behavior (排程器行為語義)

### 4.1 核心 API
- **`schedule_at(timestamp_ms, callback, name="") -> ScheduledEvent`**：
  在指定之絕對虛擬時間戳記排程事件（`timestamp_ms >= clock.now()`）。
- **`schedule_after(delay_ms, callback, name="") -> ScheduledEvent`**：
  在相對於目前時間延遲 `delay_ms` 後排程事件（`delay_ms >= 0`）。實際時間為 `clock.now() + delay_ms`。
- **`run_due() -> int`**：
  執行所有時間戳記 $\le \text{clock.now()}$ 的已屆期事件。**時鐘不主動向後推進**。
- **`run_until(target_time_ms) -> int`**：
  依序推進虛擬時鐘至 `target_time_ms`，並依確定性順序執行期間所有到期事件。

### 4.2 `run_until` 推進語義與 Callback 執行瞬刻
```text
current_time
    ↓
peek next due event in queue
    ↓
advance clock to event.timestamp
    ↓
execute event.callback()   <--- 關鍵保證：此時 clock.now() == event.timestamp
    ↓
repeat until no more due events <= target_time_ms
    ↓
advance clock to target_time_ms (若時鐘尚未達 target)
```
- **核心保證**：當任何事件的 `callback` 被調用時，`clock.now()` 保證精確等於該事件的 `timestamp`。

---

## 5. Cancellation (事件取消機制)

- 調用 `scheduler.cancel(event)` 或 `event.cancel()` 將事件標記為 `cancelled = True`。
- 採用 **Lazy Cancellation（惰性取消）** 策略：
  - 取消操作時間複雜度為 $O(1)$，不需重整或線性掃描整個最小堆積。
  - 當被取消的事件浮動至堆積頂部時，排程器自動將其彈出並捨棄，不調用 callback。
  - 內部維護 `_active_count`，使 `pending_count()` 與 `has_pending_events()` 始終能在 $O(1)$ 時間內精準反映未取消之有效事件數。

---

## 6. Dynamic Scheduling (動態排程與自排程)

排程器原生支援在事件 Callback 執行期間動態變更時序圖形：
1. **排定未來事件**：Callback A (@ 100) 可調用 `schedule_at(150, B)`，若 `run_until` 目標為 200，B 將在同一輪批次中正常到期執行。
2. **同時間動態排程**：Callback A (@ 100) 可調用 `schedule_after(0, B)`，B 將在 $T = 100$ 緊接著 A 執行（因 B 之 `sequence > A.sequence`）。
3. **零延遲鏈 (Zero-delay Chain)**：$A \rightarrow B \rightarrow C$ 皆在 $T = 100$，依註冊序號確定性執行，不會造成無窮迴圈或漏失。
4. **自排程 (Self-Rescheduling)**：如怪物 30ms 輪詢心跳或週期性狀態更新，Callback 內調用 `schedule_after(30, self)`。
   - 由於排程迴圈為平坦的迭代結構（Iterative Loop），**絕對不會造成呼叫堆疊增長（No Stack Growth / Recursion Overflow）**。

---

## 7. Exception Behavior (異常處置與結構完整性)

- 當 Callback 執行拋出例外（如 `RuntimeError`）：
  - **嚴禁私自吞沒例外（No Silent Swallowing）**：例外立即向上傳播。
  - **堆積完整性維持（Heap Invariant Preserved）**：由於發生例外的事件在調用前已藉由 `heapq.heappop` 移出佇列，堆積結構維持完全合法，其餘排定事件不受損壞。
  - 當外層程式碼捕獲例外並修復後，排程器仍可安全呼叫 `run_until` 繼續處理後續事件。

---

## 8. Determinism (確定性保證)

給定相同的初始時鐘與事件輸入序列：
- 兩次獨立執行的事件調用順序 100% 相同。
- 每個事件執行時取得的 `clock.now()` 100% 相同。
- 完全排除 Python 雜湊隨機化、字典迭代順序、作業系統執行緒搶佔與真實世界網路延遲之干擾。

---

## 9. Scope Limitation (本 Task 邊界限制)

本 Task 僅聚焦於最小底層核心：
- **未實作**：`AgentRuntime`, `Perception`, `Policy`, `TaskScheduler`, `ActionExecutor`。
- **未實作**：`RealTimeClock`。
- **未修改**：任何既有 gameplay 邏輯（`combat.py`, `movement.py`, `session.py`, `simulator.py`, `world.py`）。
- **未接入**：`hunt()`, `Monster`, `Player`, `S007` 獵場驗證。

---

## 10. 與 `canonical_timing_spec.md` 的關係

在 Phase B Task 5 建立的 [`docs/archaeology/canonical_timing_spec.md`](file:///c:/Users/p0282768/Documents/l1j-headless/docs/archaeology/canonical_timing_spec.md) 中，定義了 L1J 1.82 世界規則之時序常數：
- PC 基礎移動間隔：$640\text{ ms}$
- PC 武器攻擊間隔：$760 \sim 1840\text{ ms}$
- PC 施法動作間隔：$800 / 880\text{ ms}$
- 怪物 Mode 0/1 間隔：$\sum \text{units} \times 40\text{ ms}$
- 怪物 AI 輪詢間隔：$30\text{ ms}$

本 Temporal Runtime Core 提供了上述時序常數在虛擬時間環境下運作的**原子調度基礎**（如 `scheduler.schedule_after(640, move_action)` 或 `scheduler.schedule_after(30, ai_tick)`）。後續 Phase C Task 2+ 將在此基礎上逐步構建動作時間軸與世界實體排程。

---

> **聲明：此版本 Temporal Runtime 尚未接入 gameplay。**
