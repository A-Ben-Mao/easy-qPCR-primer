> [English Version](README.en.md)

# Easy qPCR Primer

> 🧬 **Claude Code Agent Skill** — 在 Claude Code 中直接使用，无需手动安装依赖

**全自动 qPCR 引物设计 + 特异性验证 + 真实文献引用检索**

一键完成：从基因名到 PrimerBank 引物获取 → BLAST 特异性验证 → 在已发表文献中检索该引物的真实使用情况。不再只依赖算法预测，而是看到你的引物**到底被哪些论文实际用过**。

## 文件结构

```
easy-qPCR-primer/
│
├── SKILL.md                ← 技能核心定义（触发词、工作流、边界处理）
├── _meta.json              ← 技能元信息（版本、协议）
│
├── README.md               ← 中文说明文档
├── README.en.md            ← 英文说明文档
├── LICENSE                 ← MIT 开源协议
│
└── scripts/
    ├── primer_blast.py     ← 主要脚本：Gene 解析、PrimerBank 搜索、BLAST 验证
    └── requirements.txt    ← Python 依赖（requests）
```

| 文件 | 作用 |
|------|------|
| `SKILL.md` | 定义技能的行为：触发条件、执行流程、各阶段操作指令、异常处理。Claude Code 加载此文件后按流程执行 |
| `_meta.json` | 记录技能的版本号、发布日期、协议等信息 |
| `primer_blast.py` | 封装 NCBI E-utilities 和 Primer-BLAST API，提供 Gene Symbol 解析、PrimerBank 搜索、BLAST 提交与轮询三大功能 |
| `requirements.txt` | 声明 Python 依赖：`requests>=2.25.0` |

## 功能特性

- **多基因多物种** — 同时搜索多个基因的 PrimerBank 引物，支持人、小鼠
- **NCBI Gene Symbol 自动解析** — 输入别名，自动转换为官方 Gene Symbol
- **Primer-BLAST 验证** — 逐对验证引物在 RefSeq 数据库中的特异性
- **真实文献检索** — 自动检索每对引物在已发表论文中的实际使用情况
  - 安装 [Chrome DevTools MCP](https://www.npmjs.com/package/chrome-devtools-mcp) 后，直接操作 **Google Scholar** 检索，包含引用次数
  - 未安装时自动调用 **WebSearch** 全网检索，同样能找到真实文献
  - 两种方式并行运行、去重合并，覆盖更全
  - 每条结果附带文章标题、期刊年份、**可点击的文章链接**
- **完整报告** — 生成结构化 Markdown 报告，便于保存和分享

> 💡 **推荐安装 Chrome DevTools MCP**：`claude mcp add chrome-devtools --scope user npx chrome-devtools-mcp@latest`
> 安装后可获得 Google Scholar 直接检索能力，包含被引次数等额外信息。

## 使用方式

在 Claude Code 中直接提出需求即可，例如：

- `设计小鼠 GAPDH 和 ACTB 的 qPCR 引物`
- `搜索人类的 TP53 PrimerBank 引物`
- `验证这对引物的特异性，做 BLAST`

### 手动 CLI 命令

> 都用上 agent 了，其实不太需要手搓命令 😅
> 不过需要直接调用脚本的话：

```bash
# 解析 Gene Symbol
python scripts/primer_blast.py resolve-gene -g GAPDH,ACTB -s mouse --json

# 搜索 PrimerBank
python scripts/primer_blast.py primerbank -g Gapdh,Actb -s mouse --json

# BLAST 验证
python scripts/primer_blast.py -f AGGTCGGTGTGAACGGATTTG -r TGTAGACCATGTAGTTGAGGTCA -g Gapdh -s "Mus musculus" --json
```

## 环境要求

- **稳定的网络连接** — agent 会帮你处理剩下的事情，大概率需要科学上网
- Python 3.8+（依赖 `requests`，agent 会自动安装）
- 再次推荐安装 Chrome DevTools MCP：`claude mcp add chrome-devtools --scope user npx chrome-devtools-mcp@latest`

## 工作流程

| 步骤 | 说明 |
|------|------|
| 1. Gene Symbol 解析 | 将基因别名转换为 NCBI 官方符号 |
| 2. PrimerBank 搜索 | 从 PrimerBank 数据库获取引物对 |
| 3. 用户选择 | 选取需要 BLAST 验证的引物 |
| 4. BLAST 验证 | 逐对验证引物特异性 |
| 5. 结果汇总 | 产物长度、Tm、GC%、脱靶分析 |
| 6. 文献检索（可选） | 自动检索引物在真实文献中的使用（Chrome MCP + WebSearch） |
| 7. 报告生成 | 保存完整 Markdown 报告 |

## 支持物种

| 物种 | 学名 |
|------|------|
| 人 | *Homo sapiens* |
| 小鼠 | *Mus musculus* |

> 大鼠：PrimerBank 暂不支持，后续考虑接入其他数据库。

## 输出格式

所有结果支持 **JSON**（程序化使用）和 **Markdown**（可读报告）。

BLAST 验证报告包含：

```
产物长度    →  123 bp
熔解温度    →  F: 60.9°C / R: 58.6°C
GC 含量     →  F: 52% / R: 43%
预期靶标    →  匹配的 RefSeq 转录本列表
脱靶分析    →  非特异性靶标检测
```
## 开源协议

MIT
