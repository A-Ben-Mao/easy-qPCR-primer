> [中文版](README.md)

# Easy qPCR Primer

A pipeline for designing and verifying qPCR primers: NCBI Gene Symbol resolution → PrimerBank search → BLAST specificity verification → literature search.

## Features

- **Multi-gene, multi-species** — Search PrimerBank for multiple genes across human and mouse
- **NCBI Gene Symbol resolution** — Automatically resolves gene aliases to official NCBI symbols
- **Primer-BLAST verification** — Sequentially validates primer specificity via NCBI Primer-BLAST
- **Literature search integration** — Optionally searches Google Scholar for primer usage references
- **Comprehensive reports** — Generates detailed Markdown reports with all results

## Usage

This skill is invoked through Claude Code when you ask about qPCR primer design:

- "Design qPCR primers for mouse GAPDH and ACTB"
- "Search PrimerBank for human TP53"
- "Verify primer specificity with BLAST"
- "设计小鼠的qPCR引物"

### Manual CLI Commands

The underlying `primer_blast.py` script can also be used directly:

```bash
# Resolve gene symbol
python scripts/primer_blast.py resolve-gene -g GAPDH,ACTB -s mouse --json

# Search PrimerBank
python scripts/primer_blast.py primerbank -g Gapdh,Actb -s mouse --json

# BLAST verification
python scripts/primer_blast.py -f AGGTCGGTGTGAACGGATTTG -r TGTAGACCATGTAGTTGAGGTCA -g Gapdh -s "Mus musculus" --json
```

## Requirements

- Python 3.8+
- `requests>=2.25.0` (install via `pip install -r scripts/requirements.txt`)
- Internet connection (for NCBI E-utilities and Primer-BLAST API)

## Workflow

1. **Gene Symbol Resolution** — Converts user-provided gene names to NCBI official symbols
2. **PrimerBank Search** — Retrieves validated primer pairs from the PrimerBank database
3. **User Selection** — Asks user to select primer pairs for BLAST verification
4. **BLAST Verification** — Validates each selected pair against the NCBI RefSeq database
5. **Results Summary** — Displays specificity, Tm, GC%, and off-target analysis
6. **Literature Search** (optional) — Searches Google Scholar for primer usage
7. **Report Generation** — Saves a comprehensive Markdown report

## Supported Species

- Human (*Homo sapiens*)
- Mouse (*Mus musculus*)

## Output

All results are provided as structured JSON (for programmatic use) or Markdown reports. The BLAST verification includes:

- Product length and melting temperatures
- GC content for each primer
- Intended target hits (RefSeq transcripts)
- Off-target analysis (unintended hits)

## License

MIT
