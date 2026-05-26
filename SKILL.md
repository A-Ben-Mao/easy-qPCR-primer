---
name: easy-qPCR-primer
description: >-
  Easy qPCR primer design and verification pipeline.
  PrimerBank search + NCBI BLAST verification + literature search.
  Supports multi-gene, multi-species primer searches.
  Use when user asks about: primer design, qPCR primers, PrimerBank search,
  BLAST verification, primer specificity checking, primer literature search.
  Triggers on: 引物设计, qPCR引物, 引物搜索, 引物验证, PrimerBank,
  BLAST验证, 多基因引物, 引物特异性验证, 文献检索引物.
allowed-tools: Bash(python:*), mcp__chrome-devtools__*
---

# Easy qPCR Primer

引物设计全流程工具：NCBI Gene Symbol 转换 → PrimerBank 搜索 → BLAST 验证 → 文献检索（可选）

---

## Requirements

- Python 3.8+
- `pip install requests` (or `pip install -r scripts/requirements.txt`)
- 脚本路径: `scripts/primer_blast.py`（相对于本 SKILL.md）

---

## 工作流

### Phase 1A: NCBI Gene Symbol 转换

用户提供的基因名可能是别名或俗称（如 "GAD67" 是 "GAD1" 的别名），而 PrimerBank 使用 NCBI 官方 Gene Symbol 检索。因此先将每个基因名称转换为 NCBI 官方 Gene Symbol，再用转换后的符号进行后续搜索。

```bash
python scripts/primer_blast.py resolve-gene -g <GENE> -s <SPECIES> --json
```

- 多基因用逗号分隔: `-g GAD1,ACTB`
- 解析 JSON 输出，获取每个基因的 `symbol`（官方符号）、`gene_id`、`description`
- 若某基因未找到对应 Symbol，告知用户并建议核实拼写或提供已知别名
- **用解析到的官方 Symbol 替换用户原始输入，用于后续步骤**

### Phase 1B: 搜索 PrimerBank

使用 Phase 1A 解析到的官方 NCBI Gene Symbol 搜索 PrimerBank。

```bash
python scripts/primer_blast.py primerbank -g <GENE_SYMBOL> -s <SPECIES> --json
```

- 多基因用逗号分隔: `-g GAD1,ACTB`
- 跨物种查询: 按 (物种, 基因) 分组，每组调用一次
- 输出 JSON 包含每个引物对的: primerbank_id, forward/reverse 序列, Length, Tm, Location, validated 状态（是否经过实验验证）

### Phase 2: 用户选择引物

1. 将 PrimerBank 返回的 JSON 保存在内存中（**不要写入文件**）
2. 向用户展示摘要（每个基因找到 N 对引物，区分已验证/未验证）
3. **用 AskUserQuestion (multiSelect) 让用户选择要验证的引物对**
   - 选项格式: `[Gene] Pair #N (X bp, ID=xxx) 已验证/未验证 — F: AACGT...`

**对于只提供引物序列不搜索的场景**：如果用户直接给出了 forward/reverse 序列，跳过 Phase 1A-2，直接进入 Phase 3。

### Phase 3: BLAST 验证

对用户选中的每对引物依次执行，使用 JSON 输出收集结果（不写入文件）：

```bash
python scripts/primer_blast.py -f <F> -r <R> -g <GENE> -s "<SCIENTIFIC_NAME>" --json
```

- 物种映射: human → Homo sapiens, mouse → Mus musculus
- 每对耗时约 15-60 秒（含轮询等待），**按顺序执行**
- 解析 JSON 输出，将 BLAST 验证结果保存在内存中
- 如果某对失败，记录错误信息，继续下一对
- 进度向用户报告（"第 2/5 对验证完成..."）

### Phase 4: 展示结果摘要

综合所有 BLAST 结果，向用户展示汇总表格：

| Gene | Pair | Product | 特异性 | Off-target | Tm (F/R) |
|------|------|---------|--------|------------|----------|
| GAD1 | #1 | 176 bp | ✅ | 0 | 58.5/59.7°C |

推荐最佳引物：优先选 特异性好 + 已验证 + Tm 差异 < 2°C 的

### Phase 5 (可选): 文献检索

**主动询问用户**："是否需要在 Google Scholar 中检索这些引物在文献中的使用情况？"

**检测 Chrome DevTools MCP 是否可用**：检查是否有 `mcp__chrome-devtools__navigate_page` 等工具可用。如果可用，**两种检索方式并行运行**，互相补充，取并集结果。

#### 方式 A: Chrome DevTools MCP（如已安装则启用）

如果 `chrome-devtools` MCP 可用，对每对引物使用浏览器自动化检索 Scholar：

1. 使用 `mcp__chrome-devtools__navigate_page` 跳转到:
   ```
   https://scholar.google.com/scholar?q="FORWARD_SEQ"+"REVERSE_SEQ"+GENE+species
   ```
2. 使用 `mcp__chrome-devtools__take_snapshot` 获取页面结构
3. 解析页面快照提取：
   - 文章标题（`link` 元素）
   - 作者/期刊/年份（`StaticText` 紧跟标题）
   - 被引用次数（`link` 包含"被引用次数：N"）
   - 文章 URL（`link` 的 `url` 属性）
4. 如果无结果，尝试缩短查询：仅搜索 Forward 序列 + 基因名
5. 提取前 3 条结果保存到内存

#### 方式 B: WebSearch（始终执行）

无论 Chrome MCP 是否可用，均执行 WebSearch 检索作为补充：
- 对每对选中引物，用 WebSearch 搜索 forward 序列 + 基因名
- 查询格式: `"AGGTCGGTGTGAACGGATTTG" GAPDH`
- 提取前 3 条结果保存到内存

#### 结果合并

- 将方式 A（如有）和方式 B 的结果**去重合并**（按文章 URL 去重）
- 保留方式 A 的 Google Scholar 引用次数信息
- 展示合并后的结果（前 3-5 条）
- 在文献检索结果中标注每条结果的来源（"Google Scholar" 或 "WebSearch"）

#### 通用要求

- 展示前 3 条结果，按以下优先级呈现：
  1. **学术文献优先** — 期刊论文、学位论文、预印本（含标题、期刊/年份、**带超链接的具体文章 URL**）
  2. **商品化信息居后** — OriGene、Bio-Rad 等商品引物页放在最后，并标注为"商品化引物"而非文献
- **关键要求：必须包含具体的文章 URL（用 Markdown 链接格式 `[标题](URL)`），禁止只罗列期刊名称而不附链接**
- 将文献检索结果保存在内存中，待最终报告一并输出
- 说明：搜索结果仅供参考，用户需自行浏览全文确认引物使用细节

### Phase 6: 保存最终报告

所有步骤完成后：

1. 在内存中构建完整的 Markdown 报告（按下方模板格式，含：查询信息 → 按基因分组的 PrimerBank 结果 → BLAST 验证结果 → 文献检索结果）
2. **询问用户**："是否需要将详细结果保存为 Markdown 文件？建议保存，方便后续查阅。"
3. 如果用户同意：
   - 让用户提供**文件保存目录**
   - 使用该目录，生成文件名: `primer_report_<GENES>_<YYYYMMDD_HHMM>.md`
   - 用 Write 工具写入文件，并告知用户已保存
4. 如果用户拒绝，告知用户结果在对话记录中可随时查阅

---

## Markdown 报告模板

```markdown
# 引物设计报告

## 查询信息
- **物种**: {species}
- **基因**: {genes}
- **搜索时间**: {datetime}
- **总引物对数**: {count}

---

## PrimerBank 搜索结果

### {GENE_1}
**物种**: {species} | **共 N 对引物**

#### 引物对 #1
**PrimerBank ID**: 126012538c1 | **Amplicon**: 95 bp | **已验证**: ✅

| | Sequence (5'→3') | Length | Tm | Location |
|---|-------------------|--------|----|----------|
| **Forward** | `AGGTCGGTGTGAACGGATTTG` | 21 | 62.6°C | 8-28 |
| **Reverse** | `GGGGTCGTTGATGGCAACA` | 19 | 62.6°C | 102-84 |

#### 引物对 #2
...

### {GENE_2}
**物种**: {species} | **共 M 对引物**

#### 引物对 #1
...

---

## BLAST 验证结果

### {GENE_1} — Pair 1 (126012538c1)
**Forward**: `AGGTCGGTGTGAACGGATTTG` | **Reverse**: `GGGGTCGTTGATGGCAACA`
**产物**: 95 bp | **Tm**: 60.9°C / 60.6°C

#### 特异性评估
- **状态**: ✅ 特异性良好 — 无非特异性靶标

##### Intended Targets
| Accession | Description |
|-----------|-------------|
| NM_008084.4 | Mus musculus GAPDH, transcript variant 2, mRNA |

---

## 文献检索结果

### {GENE_1} — F: `CACAGGTCACCCTCGATTTTT`
| # | 标题 / 来源 | 期刊/年份 |
|---|------------|----------|
| 1 | [Article Title](https://example.com/article) | Journal, 2024 |
| 2 | [Another Study](https://example.com/study) | Journal, 2023 |
| 3 | [Product Page](https://origene.com/xxx) (商品化引物) | OriGene |

> **注意**：搜索结果仅供参考。建议点击链接浏览全文，确认引物使用细节。部分来源可能为商品化引物对。
```

---

## 命令参考

| 命令 | 用途 |
|------|------|
| `resolve-gene -g GENES -s SP --json` | 将基因名称转换为 NCBI 官方 Gene Symbol |
| `primerbank -g GENES -s SP --json` | 搜索 PrimerBank，JSON 输出 |
| `primerbank -g GENES -s SP -o FILE` | 搜索并保存到文件 |
| `-f F -r R -g GENE --json` | BLAST 验证，JSON 输出 |
| `-f F -r R -g GENE --append-md FILE` | BLAST 验证 + 追加到 markdown |

---

## 边界处理

| 场景 | 处理方式 |
|------|---------|
| 基因名未解析到 NCBI Symbol | 建议用户核实拼写，或提供已知别名 |
| 无搜索结果 | 建议检查基因名拼写，或换同义基因名 |
| 部分基因无结果 | 展示已有的，标注哪些没找到 |
| 用户选择 0 对引物 | 询问是否调整搜索条件 |
| BLAST 失败/超时 | 记录错误信息，继续下一对 |
| BLAST 超时严重 | 建议用户用 RID 在 NCBI 官网查看 |
| PrimerBank 不可达 | 提示网络问题，建议稍后重试 |
| Python 不可用 | 提示 `pip install requests` |
| 自定义引物验证 | 用户直接提供序列时跳过 Phase 1-2 |
| 大量选择（>10 对） | 提示预计耗时 N 分钟，让用户确认 |
| 文献搜索无结果 | 建议缩短序列或不加引号重新搜索 |
| WebSearch 返回了摘要但无直接 URL | 使用搜索结果中的来源链接（如 PMC/DOI），标注为"搜索结果摘要" |
| 文献检索只罗列了期刊名未附链接 | **违反规则** — 必须重新搜索并补全具体文章 URL |
| 用户拒绝保存报告 | 告知结果在对话历史中可查阅 |
| Chrome MCP 不可用 | WebSearch 单独执行，仍有结果 |
| Google Scholar 触发 CAPTCHA | 跳过方式 A，仅用方式 B WebSearch 继续 |

---

## Tools 路径说明

本 skill 的脚本在 `scripts/primer_blast.py`（相对于本 SKILL.md 所在目录）。
Claude 在执行 Bash 命令时，需要 cd 到 skill 目录或使用相对路径。

Windows 示例：
```powershell
cd C:\Users\ABenMao\.claude\skills\easy-qPCR-primer
python scripts/primer_blast.py resolve-gene -g GAD1 -s mouse --json
python scripts/primer_blast.py primerbank -g GAD1 -s mouse --json
```
