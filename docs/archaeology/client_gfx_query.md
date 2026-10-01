# Client GFX 考古查詢工具使用手冊

## 1. 架構原則

為避免大語言模型或考古工具每次重複讀取 7.4 MB、15.5 萬行的文字檔案，專案實作了高效能的 SQLite 索引結構：

```text
TW13081901.txt (7.07 MB)
       ↓
tools/index_client_gfx.py
       ↓
legacy/client/3.80/TW13081901.sqlite (16.66 MB)
       ↓
legacy/archaeology/evidence.py (ClientGfxEvidenceStore)
       ↓
tools/query_client_gfx.py (CLI 工具)
```

---

## 2. CLI 命令操作範例

### 2.1 查詢特定 GFX 定義（單一 Timing Segment）
```bash
python tools/query_client_gfx.py --gfx 18315
```
輸出範例：
```text
Source:
  legacy-client-tw13081901

Version:
  3.80

Classification:
  LEGACY_CLIENT_OBSERVED

SHA256:
  ddcbd759d4124877768990db505a8b1f7b7cbba23e7e78fe7e3fafd4bda356fe

GFX:
  18315

Sprite:
  56

Name:
  tw xiaolongbao monster

FrameRate:
  36

Timing Segments (1):
  - Segment 1: framerate=36, actions=19, lines=L127808-L127830

Actions (19 total):
  walk (Action 0, 8 frames)
  attack (Action 1, 6 frames)
  damage (Action 2, 3 frames)
  breath (Action 3, 10 frames)
  attack[sword] (Action 5, 6 frames)
  death (Action 8, 18 frames)
  attack[axe] (Action 12, 6 frames)
  ...

References:
  shadow -> 18316
  type -> 10
  clothes -> 18317
  clothes -> 18318

Raw evidence:
  TW13081901.txt:L127807-L127830
```

### 2.2 查詢多段 Framerate 之 GFX（如 GFX 18310）
```bash
python tools/query_client_gfx.py --gfx 18310
```
輸出範例：
```text
GFX:
  18310
Name:
  Legend_Silvia
FrameRate:
  36 (multi-segment: 2 segments)

Timing Segments (2):
  - Segment 1: framerate=36, actions=12, lines=L127658-L127670
  - Segment 2: framerate=59, actions=53, lines=L127671-L127727
```

### 2.3 查詢特定動作與武器分支
```bash
python tools/query_client_gfx.py --action attack --weapon dagger
```
輸出範例：
```text
Targeted Action Evidence: 2 results for action='attack', weapon=dagger

GFX 18315 (tw xiaolongbao monster):
  Action:        attack[dagger] (Action 47, 6 frames)
  FrameRate:     36
  Segment ID:    12999
  Raw evidence:  TW13081901.txt:L127817-L127817
  Sequence:      1 6,8.0:4 16.0:4 16.1:4 16.2:4 16.3:4! 16.4:4...
----------------------------------------
GFX 22180 (Myth_God_Thunder):
  Action:        attack[dagger] (Action 47, 6 frames)
  FrameRate:     59
  Segment ID:    14742
  Raw evidence:  TW13081901.txt:L146839-L146839
  Sequence:      1 6,96.0:3 96.1:3<24076<24077 96.2:2 96.3:3! 96.4:4 96.5:3...
```

### 2.4 模糊搜尋名稱
```bash
python tools/query_client_gfx.py --name "xiaolongbao"
```

### 2.5 查詢特定 GFX 的幀率資訊
```bash
python tools/query_client_gfx.py --framerate --gfx 18315
```

---

## 3. Python API 調用

```python
from legacy.archaeology.evidence import ClientGfxEvidenceStore

store = ClientGfxEvidenceStore()

# 取得特定 GFX 記錄
rec = store.query_gfx(18310)
print(rec.name, rec.framerate, len(rec.timing_segments))
for seg in rec.timing_segments:
    print(f"Segment {seg.segment_index}: framerate={seg.framerate}, actions={seg.action_count}")

# 查詢特定動作
anims = store.query_actions(action_name="attack", weapon="dagger")
for a in anims:
    print(a.gfx_id, a.action_name, a.weapon, a.frame_count, a.segment_id, a.start_line)

store.close()
```
