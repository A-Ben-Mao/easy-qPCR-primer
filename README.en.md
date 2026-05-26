> [中文版](README.md)

# Easy qPCR Primer

**Automated qPCR primer design pipeline** — NCBI Gene Symbol resolution → PrimerBank search → BLAST verification → literature search

## Features

- **Multi-gene, multi-species** — Search PrimerBank for multiple genes across human and mouse
- **Auto Symbol Resolution** — Input an alias, get the official NCBI Gene Symbol
- **Primer-BLAST Verification** — Validates each primer pair against RefSeq
- **Literature Search** — Optionally check Google Scholar for primer usage references
- **Full Report** — Structured Markdown output for saving and sharing

## Usage

Invoke through Claude Code:

- `Design qPCR primers for mouse GAPDH and ACTB`
- `Search PrimerBank for human TP53`
- `Verify these primers with BLAST`

### CLI Commands

> With an agent at your service, you probably won't need these 😅
> But here they are if you do:

```bash
# Resolve gene symbol
python scripts/primer_blast.py resolve-gene -g GAPDH,ACTB -s mouse --json

# Search PrimerBank
python scripts/primer_blast.py primerbank -g Gapdh,Actb -s mouse --json

# BLAST verification
python scripts/primer_blast.py -f AGGTCGGTGTGAACGGATTTG -r TGTAGACCATGTAGTTGAGGTCA -g Gapdh -s "Mus musculus" --json
```

## Requirements

- **Internet connection** — the agent handles the rest
- Python 3.8+ (depends on `requests`, auto-installed by the agent)

## Workflow

| Step | Description |
|------|-------------|
| 1. Gene Symbol Resolution | Convert aliases to official NCBI symbols |
| 2. PrimerBank Search | Retrieve primer pairs from PrimerBank |
| 3. User Selection | Pick primers for BLAST verification |
| 4. BLAST Verification | Validate specificity of each pair |
| 5. Results Summary | Product length, Tm, GC%, off-targets |
| 6. Literature Search (opt.) | Google Scholar primer lookup |
| 7. Report Generation | Save complete Markdown report |

## Supported Species

| Species | Scientific Name |
|---------|----------------|
| Human | *Homo sapiens* |
| Mouse | *Mus musculus* |

> Rat: not yet supported by PrimerBank. Other databases may be integrated in the future.

## Output Format

Results in **JSON** (machine-readable) or **Markdown** (human-readable).

BLAST verification report:

```
Product length  →  123 bp
Melting temp    →  F: 60.9°C / R: 58.6°C
GC content      →  F: 52% / R: 43%
Intended hits   →  Matching RefSeq transcripts
Off-targets     →  Non-specific hits detected
```

## File Structure

```
easy-qPCR-primer/
│
├── SKILL.md               ← Skill definition (triggers, workflow, edge cases)
├── _meta.json              ← Metadata (version, license)
│
├── README.md               ← Chinese documentation
├── README.en.md            ← English documentation
├── LICENSE                 ← MIT License
│
├── scripts/
│   ├── primer_blast.py     ← Core script: gene resolution, PrimerBank, BLAST
│   └── requirements.txt    ← Python dependencies (requests)
│
└── evals/                  ← Evaluation test cases
```

| File | Purpose |
|------|---------|
| `SKILL.md` | Defines skill behavior: triggers, workflow phases, error handling. Claude Code loads this and executes the pipeline |
| `_meta.json` | Version, publish date, license info |
| `primer_blast.py` | Wraps NCBI E-utilities and Primer-BLAST API: gene symbol resolution, PrimerBank search, BLAST submission & polling |
| `requirements.txt` | Python dependency: `requests>=2.25.0` |
| `evals/` | Evaluation test cases for skill verification |

## License

MIT
