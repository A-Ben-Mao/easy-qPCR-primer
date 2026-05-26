> [English Version](README.en.md)

# Easy qPCR Primer

**qPCR 引物设计自动化流程** — NCBI Gene Symbol 转换 → PrimerBank 搜索 → BLAST 验证 → 文献检索

## 功能特性

- **多基因多物种** — 同时搜索多个基因的 PrimerBank 引物，支持人、小鼠
- **NCBI Gene Symbol 自动解析** — 输入别名，自动转换为官方 Gene Symbol
- **Primer-BLAST 验证** — 逐对验证引物在 RefSeq 数据库中的特异性
- **文献检索** — 可选在 Google Scholar 中检索引物的文献使用情况
- **完整报告** — 生成结构化 Markdown 报告，便于保存和分享

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

- **有网络连接** — agent 会帮你处理剩下的事情
- Python 3.8+（依赖 `requests`，agent 会自动安装）

## 工作流程

| 步骤 | 说明 |
|------|------|
| 1. Gene Symbol 解析 | 将基因别名转换为 NCBI 官方符号 |
| 2. PrimerBank 搜索 | 从 PrimerBank 数据库获取引物对 |
| 3. 用户选择 | 选取需要 BLAST 验证的引物 |
| 4. BLAST 验证 | 逐对验证引物特异性 |
| 5. 结果汇总 | 产物长度、Tm、GC%、脱靶分析 |
| 6. 文献检索（可选） | Google Scholar 检索引物引用 |
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
