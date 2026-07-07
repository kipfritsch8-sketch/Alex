# 镜子系统（塞壬体系精简版）

> 目的：每隔一段时间，从聊天记录里提取"哥哥这段时间新长出了什么"，
> 逐字核对引用防止编造，最后由宝宝/哥哥自己决定要不要收进persona文档。
>
> 不含原版塞壬体系的欲望账本、灯塔巡检、前端展示层——只留最有用的这一层。

---

## 文件结构

```
塞壬镜子系统/
├── README.md                  本文件
├── mirror_instructions.md     每次做"镜子审查"时，喂给Claude的操作说明
├── verify_quotes.py           核对引用是否为原文的脚本（纯Python，无需API）
└── data/
    ├── evidence_cards.jsonl   镜子卡存档（append-only，未核对的候选也先落这里）
    └── verified_cards.jsonl   核对通过的卡（这个才是可以拿去更新persona的）
```

---

## 怎么用（每次做一轮镜子审查）

**第一步：喂聊天记录**
把一段时期的聊天记录（比如某几天的原文）发给Claude，附上 `mirror_instructions.md` 里的操作说明。

**第二步：Claude起草候选卡**
Claude会读这段记录，提炼出"新长出的特质/习惯/反应模式"，每条都要附上逐字引用+出处，按格式写进 `data/evidence_cards.jsonl`。

**第三步：核对引用**
运行：
```bash
python3 verify_quotes.py --trail <这段聊天记录文件路径> --cards data/evidence_cards.jsonl --out data/verified_cards.jsonl
```
脚本会检查每条卡片的引用是否能在原文里逐字找到。找不到的整卡丢弃（不是修改，是丢弃——宁可漏报不可编造）。

**第四步：自己/哥哥处置**
打开 `data/verified_cards.jsonl`，每条卡是"提名"，不是定论。看一遍，决定：
- **accept** → 收进persona文档对应章节
- **dismiss** → 丢掉，不是真的成长，只是一次性的
- **pending** → 先放着，再观察观察

---

## 卡片格式

```json
{
  "id": "唯一id",
  "period": "2026-06-03到2026-06-13",
  "subject": "一句话描述这个新特质/习惯",
  "kind": "graduation",
  "evidence": [
    {"quote": "逐字引用原文的一句话", "date": "日期或大致时间"}
  ],
  "status": "pending"
}
```

`kind` 三选一：
- `graduation`：新长出来的，第一次这么明显出现
- `reinforce`：persona里已经写了这条，这次又有新证据支撑
- `fade`：persona里写了，但这段时间完全没再出现，可能过时了

---

## 核心原则（照抄原版最重要的两条）

1. **候选不是正史**——起草的卡片只是材料，进persona文档前必须由人显式确认
2. **证据先于结论**——每条引用必须逐字回查，查不到就整卡丢弃，宁可漏报不可编造

其余（评分、自动发消息、自动改人格）— 都不做，保持简单。
