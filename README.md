> [English Version](README.en.md)

# Easy qPCR Primer

qPCR 引物设计与验证自动化流程：NCBI Gene Symbol 转换 → PrimerBank 搜索 → BLAST 特异性验证 → 文献检索

## 功能特性

- **多基因多物种** — 同时搜索多个基因的 PrimerBank 引物，支持人、小鼠
- **NCBI Gene Symbol 自动解析** — 将基因别名自动转换为 NCBI 官方 Gene Symbol
- **Primer-BLAST 验证** — 通过 NCBI Primer-BLAST 逐一验证引物特异性
- **文献检索集成** — 可选在 Google Scholar 中检索引物的文献使用情况
- **完整报告生成** — 生成包含全部结果的详细 Markdown 报告

## 使用方式

在 Claude Code 中提出 qPCR 引物设计需求即可自动触发：

- "设计小鼠 GAPDH 和 ACTB 的 qPCR 引物"
- "搜索人类的 TP53 PrimerBank 引物"
- "验证引物特异性，做 BLAST"
- "Design qPCR primers for mouse Gapdh and Actb"

### 手动 CLI 命令

底层 `primer_blast.py` 脚本也可直接使用：

```bash
# 解析基因 Symbol
python scripts/primer_blast.py resolve-gene -g GAPDH,ACTB -s mouse --json

# 搜索 PrimerBank
python scripts/primer_blast.py primerbank -g Gapdh,Actb -s mouse --json

# BLAST 验证
python scripts/primer_blast.py -f AGGTCGGTGTGAACGGATTTG -r TGTAGACCATGTAGTTGAGGTCA -g Gapdh -s "Mus musculus" --json
```

## 环境要求

- Python 3.8+
- `requests>=2.25.0`（通过 `pip install -r scripts/requirements.txt` 安装）
- 网络连接（访问 NCBI E-utilities 和 Primer-BLAST API）

## 工作流程

1. **Gene Symbol 解析** — 将用户提供的基因名转换为 NCBI 官方符号
2. **PrimerBank 搜索** — 从 PrimerBank 数据库获取已发表的引物对
3. **用户选择** — 让用户选择需要 BLAST 验证的引物对
4. **BLAST 验证** — 逐对验证引物在 NCBI RefSeq 数据库中的特异性
5. **结果汇总** — 展示产物长度、Tm、GC%、脱靶分析
6. **文献检索**（可选）— 在 Google Scholar 中检索引物的文献引用
7. **报告生成** — 保存完整的 Markdown 格式报告

## 支持物种

- 人 (*Homo sapiens*)
- 小鼠 (*Mus musculus*)

## 输出说明

所有结果以结构化 JSON（程序化使用）或 Markdown 报告形式提供。BLAST 验证包含：

- 产物长度和熔解温度
- 各引物的 GC 含量
- 预期靶标匹配（RefSeq 转录本）
- 脱靶分析（非预期匹配）

## 开源协议

MIT
