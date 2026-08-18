# Natural Language → TransposeRequest V1 实现报告

**日期**: 2026-08-16  
**范围**: 仅自然语言转调意图层（NL → `TransposeRequest`）。不涉及 MusicXML/ScoreIR 修改、不配器、不分谱、不改节奏力度、不自动修谱。  
**测试结果**: 全仓库 168 个单元测试全部通过（含 42 个新增意图层测试）。

---

## 1. 新增 / 修改文件

### 新增文件

| 文件 | 职责 | 行数（约） |
|------|------|-----------|
| `src/ai/intent_schema.py` | `TransposeIntent`、`TransposeIntentResult`、`IntentContext`、`ValidationResult` 数据契约 | 78 |
| `src/ai/intent_parser.py` | `AIIntentProvider` 抽象、`LLMIntentProvider`（包装任意 `AIClient`）、`MockIntentProvider` | 166 |
| `src/ai/intent_validator.py` | 确定性校验：状态、方向、operation、basis、part IDs、measure 范围、interval 合法性 | 134 |
| `src/ai/intent_resolver.py` | `TransposeIntentResolver` + `PartResolver` / `MeasureResolver` / `IntervalResolver` / `BasisResolver` | 466 |
| `tests/test_transpose_intent.py` | 42 个单元/端到端测试，全部使用 `MockIntentProvider`，无需真实 API | 540 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `src/ai/__init__.py` | 导出 NL 转调层的全部公共 API：`AIIntentProvider`、`LLMIntentProvider`、`MockIntentProvider`、`TransposeIntent`、`TransposeIntentResult`、`IntentContext`、`ValidationResult`、`IntentValidator`、`TransposeIntentResolver`、`build_intent_context` |

**未修改**: `TranspositionEngine`、`SafeTranspositionService`、`MusicXMLImporter`、`MusicXMLExporter`、ScoreIR 核心类。本轮严格遵循"不要重新设计或重写 TranspositionEngine"的约束。

---

## 2. Natural Language → TransposeRequest 数据流

```
用户自然语言请求
        |
        v
LLMIntentProvider.parse_transpose(text, IntentContext)
        |
        v
   TransposeIntent  (候选意图)
        |
        v
TransposeIntentResolver.resolve(intent, score)
  ├─ BasisResolver   → TranspositionOperation
  ├─ IntervalResolver → Interval
  ├─ PartResolver     → part_ids
  └─ MeasureResolver  → 1-based measure indices
        |
        v
IntentValidator.validate_request(TransposeRequest, score)
        |
        v
   TransposeIntentResult
   status ∈ {ready, needs_clarification, unsupported, invalid}
        |
        v
if status == "ready":
    SafeTranspositionService.transpose(score, result.request)
```

关键约束：
- 只有 `status == "ready"` 且通过确定性校验后才会生成 `TransposeRequest`。
- `TransposeIntentResolver` 不直接执行转调，只生产请求对象。
- 所有真实修改仍由现有的 `SafeTranspositionService` / `TranspositionEngine` 完成。

---

## 3. AI 提供方解耦

沿用已有的 `AIClient`/`AIRequest`/`AIResponse` 抽象，新增一层意图解析抽象：

```python
class AIIntentProvider(ABC):
    @abstractmethod
    def parse_transpose(self, user_text: str, context: IntentContext) -> TransposeIntent: ...
```

实现：
- `LLMIntentProvider`: 包装任意 `AIClient`（OpenAI、Kimi、本地模型等），通过 JSON schema 提示词让模型输出结构化意图。
- `MockIntentProvider`: 按请求文本返回预置的 `TransposeIntent`，用于测试和离线开发。
- `NullAIClient`（已存在）：无配置时返回空内容，下游自动进入 `invalid`/`needs_clarification`。

切换模型只需替换 `AIClient` 实现，业务逻辑（resolver/validator）不变。

---

## 4. Prompt / 上下文设计（Token 成本控制）

`LLMIntentProvider._build_prompt` 只发送：
- 用户请求原文。
- 紧凑的声部表（`id`、`name`、`instrument`），例如 `[{"id": "P1", "name": "Trumpet 1", "instrument": "Trumpet"}]`。
- 最小/最大小节号。
- 支持的 interval 词汇表（11 个）。
- 方向关键词、Basis 关键词、JSON schema。

**不发送**：
- 完整 MusicXML。
- 完整 ScoreIR。
- 项目代码。
- 大量乐谱数据（音符、和弦、谱号等）。

典型提示词长度约 500–1500 tokens，取决于声部数量。

---

## 5. 状态模型

`TransposeIntent` 与 `TransposeIntentResult` 共享四态模型：

| 状态 | 含义 | 下游行为 |
|------|------|---------|
| `ready` | 意图清晰且结构合法 | 继续解析、校验、可能生成 `TransposeRequest` |
| `needs_clarification` | 信息不足或存在歧义 | 返回 `clarification_question`，不执行 |
| `unsupported` | 请求不是转调，或 interval/operation 不在 V1 支持范围 | 返回说明，不执行 |
| `invalid` | 结构错误、LLM 输出异常、校验失败 | 返回失败原因，不执行 |

示例：
- "低一点" → `needs_clarification`。
- "降一个调" → `needs_clarification`（未给出具体 interval）。
- "把钢琴改成小提琴" → `unsupported`（非转调意图）。
- LLM 返回非法 JSON → `invalid`。

---

## 6. Part 解析

`PartResolver` 按以下优先级匹配用户描述的声部：

1. **精确 `part_id` 匹配**（如 `"P1"`、`"P2"`）。
2. **声部名/乐器名子串匹配**（`part.name`、`part.instrument.name`）。
3. **中英文乐器别名匹配**（`src/ai/intent_resolver.py:27` 的 `_INSTRUMENT_ALIASES`）：
   - 小号 → Trumpet
   - 长号 → Trombone
   - 圆号 → Horn
   - 单簧管 → Clarinet
   - 长笛 → Flute
   - 小提琴 → Violin
   - 钢琴 → Piano
   - 等。

处理规则：
- 0 个匹配 → `needs_clarification`（`not_found`）。
- 1 个匹配 → 直接解析。
- 2+ 个匹配 → `needs_clarification`（列出歧义项，如 "小号 matches P1 Trumpet 1, P2 Trumpet 2"）。
- `is_all_parts=True` → 全部声部。

测试覆盖：精确 ID、中文别名、英文乐器名、歧义、未找到、全选声部。

---

## 7. Measure 解析

`MeasureResolver.resolve` 将用户描述转换为 **1-based measure index**，而非直接使用显示数字，以支持非标准小节编号。

支持格式：
- 阿拉伯数字：`"32"`、`"32-48"`、`"第32到48小节"`、`"M32-M48"`、`"measure 32 to 48"`。
- 单一数字 → 单小节。
- 无数字 → 全曲范围。
- 非标准编号（如 `"X1"`）→ 按字符串精确匹配，已修复并测试通过。

校验：
- `start <= end`（仅当两者均为纯数字时）。
- 起始/结束小节在每个目标声部中都存在。
- 跨声部小节索引一致（V1 要求）。

修复记录：
- 原 `test_nonstandard_measure_number` 失败，原因是 `_extract_number` 从 `"X1"` 中提取出 `1`，导致 `start=end=1`。
- 改为 token-based 查找（`src/ai/intent_resolver.py:227-248`），保留纯数字的排序检查，同时支持非标准编号字符串匹配。

---

## 8. Interval 解析

`IntervalResolver` 将自然语言映射到现有的 `Interval` 类，**不复建 interval 模型**。

支持列表：

| 中文 | 英文 | Interval |
|------|------|----------|
| 半音 / 小二度 | minor second / half step / semitone | m2 |
| 全音 / 大二度 | major second / whole step / tone | M2 |
| 小三度 | minor third | m3 |
| 大三度 | major third | M3 |
| 纯四度 | perfect fourth / fourth | P4 |
| 纯五度 | perfect fifth / fifth | P5 |
| 小六度 | minor sixth | m6 |
| 大六度 | major sixth | M6 |
| 小七度 | minor seventh | m7 |
| 大七度 | major seventh | M7 |
| 八度 / 一个八度 | octave / perfect octave | P8 |

方向：
- 升 / 上移 / 提高 / up / raise → `direction=+1`
- 降 / 下移 / 降低 / down / lower → `direction=-1`

不支持：增减音程、三全音、中文数字（"三十二"）、"降一个调" 等模糊表达 → 返回 `needs_clarification` 或 `unsupported`。

---

## 9. 确定性校验（防止 LLM 幻觉）

`IntentValidator` 在代码层面对 LLM 输出做最终审查：

- `status` 必须是四态之一。
- `operation` 必须是 `transpose | written_to_sounding | sounding_to_written`。
- `direction` 必须是 `up | down`。
- `basis` 必须是 `written | sounding | concert`。
- `INTERVAL` 操作必须有合法 `Interval`（通过 `Interval.semitones` 触发构造校验，拒绝增减音程等）。
- `part_ids` 非空且全部存在于 `score.parts`。
- `measure_start >= 1`。
- `measure_end >= measure_start`。
- 每个声部的小节索引不越界。

LLM 只能提出候选；validator 拥有最终否决权。例如测试中 `test_hallucinated_part_id` 验证 LLM 编造 `"P99"` 会被拒绝。

---

## 10. 测试覆盖

新增 `tests/test_transpose_intent.py`，共 **42 个测试**，分类如下：

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestIntervalResolver` | 5 | 大二度上行、小三度下行、八度、大三度英文、不支持音程 |
| `TestPartResolver` | 6 | 精确 ID、中文别名、英文名、歧义、未找到、全选 |
| `TestMeasureResolver` | 6 | 范围、单小节、全曲默认、小节未找到、start>end、非标准编号 |
| `TestLLMIntentProvider` | 3 | JSON 解析、markdown fence 剥离、非法 JSON 处理 |
| `TestIntentValidator` | 5 | 合法请求、缺 interval、越界小节、非法状态、编造 part_id |
| `TestBuildIntentContext` | 1 | 上下文最小化构造 |
| `TestTransposeIntentEndToEnd` | 16 | 整首升/降、按声部、按小节范围、英文请求、concert/written basis、歧义、模糊表达、Mock + Engine 集成 |

全仓库测试汇总：

```
Ran 168 tests in 2.338s
OK
```

其中：
- 转调引擎（`tests/test_transposition.py`）: 63 个测试全部通过。
- 意图层（`tests/test_transpose_intent.py`）: 42 个测试全部通过。
- 其他既有测试无回归。

---

## 11. 失败案例分析

本轮开发中出现并修复的主要问题：

| 问题 | 原因 | 修复 |
|------|------|------|
| `test_nonstandard_measure_number` 返回 `end=1` | `_extract_number` 从 `"X1"` 中提取出 `1` | 改为 token-based 查找，保留纯数字排序检查 |
| 正则内联 flag 报错 | `re.sub(r"^(?i)(m|measure|第)", ...)` 不被接受 | 使用 `flags=re.IGNORECASE` |
| 早期 `test_missing_interval_for_interval_operation` 触发 `ValueError` | 测试期望 resolver 返回错误，但 `TransposeRequest.__post_init__` 直接抛异常 | 调整测试断言为 `ValueError`（schema 级保护），并增加 resolver 层的 `needs_clarification` 分支 |
| 历史问题 `resolve_part_transposition` 忽略 `part.instrument.transposition` | 只检查 `transposition_events` | V1 引擎阶段已修复：优先检查 `part.instrument.transposition` |

---

## 12. 与 V1 Engine 的集成方式

调用方代码示例：

```python
from ai import LLMIntentProvider, build_intent_context, TransposeIntentResolver
from ai import AIClient  # 具体实现由项目注入
from score_engine.musicxml import MusicXMLImporter
from score_engine.transposition import SafeTranspositionService

score = MusicXMLImporter().import_file(path)
context = build_intent_context(score)

provider = LLMIntentProvider(client=ai_client, model="kimi-k2.7")
intent = provider.parse_transpose("把小号第32-48小节升大二度", context)

resolver = TransposeIntentResolver()
result = resolver.resolve(intent, score)

if result.is_ready:
    new_score = SafeTranspositionService.transpose(score, result.request)
else:
    print(result.clarification_question)
```

关键点：
- `SafeTranspositionService` 复用 V1 引擎的编辑安全门（clean/permissive/strict gate）。
- `TransposeRequest` 与引擎接口完全兼容，无需任何适配。
- 自然语言层只负责"理解"，不负责"修改"。

---

## 13. 已排除范围（明确本轮不做）

根据用户约束，以下功能**未加入**本轮：

- 配器（orchestration）
- 分谱 / 声部提取（part extraction）
- 删除乐器
- 修改节奏（rhythm）
- 修改力度（dynamics）
- 和声修改
- AI 自动修谱
- 中文数字小节号（"第三十二小节"）
- 增减音程、三全音等不常用 interval
- 模糊表达如 "低一点"、"降一个调"（返回 clarification）

这些功能被有意隔离在意图层之外；若用户请求命中，统一返回 `unsupported` 或 `needs_clarification`。

---

## 14. 是否已经可以把真实用户自然语言请求接入现有 TranspositionEngine？

**可以，但需满足以下条件：**

1. **接入真实 `AIClient`**：当前 `LLMIntentProvider` 已与具体模型解耦，只需注入一个实现 `AIClient.call(AIRequest) -> AIResponse` 的真实客户端（如 OpenAI/Kimi 适配器）。
2. **Prompt 已就绪**：提示词包含 schema、声部表、measure 范围、interval 词汇，模型输出可直接解析。
3. **确定性校验兜底**：即使 LLM 幻觉，也会在 `IntentValidator` 层被拒绝，不会破坏 ScoreIR。
4. **修改仍由 V1 引擎执行**：`SafeTranspositionService.transpose` 保证 deep-copy、不变性、key signature 恢复、range QA 等既有行为。
5. **建议增加一层 UI/确认流程**：对于 `needs_clarification` 状态，应把 `clarification_question` 展示给用户；对于 `ready` 状态，建议让用户确认 `TransposeRequest` 摘要后再执行。

**已验证的端到端路径**：
- 自然语言 → `MockIntentProvider` → `TransposeIntentResolver` → `IntentValidator` → `TransposeRequest` → `SafeTranspositionService.transpose` → 转调后的 `Score`。

因此，NL → TransposeRequest V1 层已完成，真实用户请求可在接入 `AIClient` 后直接驱动现有 `TranspositionEngine`。

---

**结论**：本轮按约束实现了最小可用的自然语言转调意图层，未触碰 ScoreIR/MusicXML/Engine，新增 42 个测试，全仓库 168 个测试通过。可停止本轮，进入下一阶段的模型客户端接入或 UI 确认层设计。
