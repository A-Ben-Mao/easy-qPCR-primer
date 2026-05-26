"""
primer_blast.py - qPCR primer tool (PrimerBank search + Primer-BLAST verify)

Enhanced version with:
  - Multi-gene PrimerBank search
  - Full field extraction (Length, Tm, Location, Validation status)
  - JSON output for programmatic use
  - Markdown output for BLAST results (--append-md)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import textwrap
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

# ─── Constants ──────────────────────────────────────────────────────────────

PRIMER_BLAST_URL = "https://www.ncbi.nlm.nih.gov/tools/primer-blast/primertool.cgi"
USER_AGENT = "Mozilla/5.0 (compatible; Primer-Pipeline/1.0)"

PB_SPECIES = {"human": "Human", "mouse": "Mouse"}
SCIENTIFIC_NAMES = {"human": "Homo sapiens", "mouse": "Mus musculus"}
NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ═══════════════════════════════════════════════════════════════════════════════
#  Data models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BlastPrimerHit:
    """一条 BLAST 比对准信息"""
    title: str = ""
    accession: str = ""
    evalue: str = ""
    identities: str = ""
    alignment_length: str = ""


@dataclass
class BlastPrimerPair:
    """引物对 + BLAST 验证结果"""
    forward_seq: str = ""
    reverse_seq: str = ""
    forward_tm: str = ""
    reverse_tm: str = ""
    forward_gc: str = ""
    reverse_gc: str = ""
    product_length: str = ""
    has_offtarget: bool = False
    intended_hits: list[BlastPrimerHit] = field(default_factory=list)
    unintended_hits: list[BlastPrimerHit] = field(default_factory=list)

    @property
    def is_specific(self) -> bool:
        return not self.has_offtarget


@dataclass
class BlastResult:
    total_pairs: int = 0
    primers: list[BlastPrimerPair] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    gene: str = ""
    forward_seq: str = ""
    reverse_seq: str = ""

    @property
    def has_specific_primers(self) -> bool:
        return any(p.is_specific for p in self.primers)


# ═══════════════════════════════════════════════════════════════════════════════
#  PrimerBank
# ═══════════════════════════════════════════════════════════════════════════════

PRIMERBANK_URL = "https://pga.mgh.harvard.edu/cgi-bin/primerbank/new_search2.cgi"
PRIMERBANK_DETAIL_URL = "https://pga.mgh.harvard.edu/cgi-bin/primerbank/new_displayDetail2.cgi"


def search_primerbank(genes: str, species: str = "mouse") -> list[dict]:
    """从 PrimerBank 搜索引物，支持逗号分隔的多基因。"""
    gene_list = [g.strip() for g in genes.split(",") if g.strip()]
    all_primers: list[dict] = []

    for gene in gene_list:
        results = _search_single_gene(gene, species)
        for r in results:
            r["gene"] = gene
            r["species"] = species
        all_primers.extend(results)

    return all_primers


def _search_single_gene(gene: str, species: str) -> list[dict]:
    """搜索单个基因的 PrimerBank 引物。"""
    sp = PB_SPECIES.get(species.lower(), "Mouse")
    data = {
        "searchBox": gene,
        "selectBox": "NCBI Gene Symbol",
        "species": sp,
        "Submit": "Submit",
    }

    log(f"搜索 PrimerBank: {gene} ({species}) ...")
    try:
        resp = requests.post(
            PRIMERBANK_URL, data=data,
            headers={"User-Agent": USER_AGENT}, timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        die(f"PrimerBank 访问失败: {e}")

    return _parse_primerbank(resp.text)


def _parse_primerbank(html: str) -> list[dict]:
    """
    解析 PrimerBank 结果 HTML，按 <table> 块逐一提取。
    捕获: ID, Amplicon Size, Forward/Reverse 的 Sequence/Length/Tm/Location, Validation 状态。
    """
    primers: list[dict] = []

    # 每个引物对是一个独立的 <table border="0" cellpadding="2" cellspacing="10">
    # 用 "Primer Pair" 分割各块
    blocks = re.split(r'<table border="0" cellpadding="2" cellspacing="10">', html)[1:]

    for block in blocks:
        primer: dict[str, str | bool] = {"validated": False}

        # PrimerBank ID
        m = re.search(r'<tr>\s*<td><b>PrimerBank ID</b></td>\s*<td[^>]*>([^<]+)</td>', block, re.I)
        if m:
            primer["primerbank_id"] = m.group(1).strip()

        # Amplicon Size
        m = re.search(r'<tr>\s*<td[^>]*><b>Amplicon Size</b></td>\s*<td[^>]*>([^<]+)</td>', block, re.I)
        if m:
            primer["product_length"] = m.group(1).strip()

        # Forward Primer row
        fwd = re.search(
            r'<td[^>]*>Forward Primer</td>\s*'
            r'<td[^>]*><font[^>]*>([^<]+)</font></td>\s*'
            r'<td[^>]*>([^<]*)</td>\s*'
            r'<td[^>]*>([^<]*)</td>\s*'
            r'<td[^>]*>([^<]*)</td>',
            block, re.I
        )
        if fwd:
            primer["forward"] = fwd.group(1).strip()
            primer["forward_length"] = fwd.group(2).strip()
            primer["forward_tm"] = fwd.group(3).strip()
            primer["forward_location"] = fwd.group(4).strip()

        # Reverse Primer row
        rev = re.search(
            r'<td[^>]*>Reverse Primer</td>\s*'
            r'<td[^>]*><font[^>]*>([^<]+)</font></td>\s*'
            r'<td[^>]*>([^<]*)</td>\s*'
            r'<td[^>]*>([^<]*)</td>\s*'
            r'<td[^>]*>([^<]*)</td>',
            block, re.I
        )
        if rev:
            primer["reverse"] = rev.group(1).strip()
            primer["reverse_length"] = rev.group(2).strip()
            primer["reverse_tm"] = rev.group(3).strip()
            primer["reverse_location"] = rev.group(4).strip()

        # Validation Results: 检查是否有绿色背景行包含 "Validation Results"
        if re.search(r'bgcolor="#00FF00"[^>]*>\s*<b>Validation Results', block, re.I):
            primer["validated"] = True

        # 至少要有 forward 序列才算有效
        if primer.get("forward"):
            primers.append(primer)

    return primers


# ═══════════════════════════════════════════════════════════════════════════════
#  Core: 提交 + 解析 Primer-BLAST
# ═══════════════════════════════════════════════════════════════════════════════

def submit_and_parse(
    forward: str,
    reverse: str,
    organism: str = "Mus musculus",
    min_len: int = 70,
    max_len: int = 200,
) -> BlastResult:
    """一站式提交引物并解析结果。"""
    payload = {
        "CMD": "Put",
        "PRIMER_LEFT_INPUT": forward.upper().strip(),
        "PRIMER_RIGHT_INPUT": reverse.upper().strip(),
        "ORGANISM": organism,
        "PRIMER_PRODUCT_MIN": str(min_len),
        "PRIMER_PRODUCT_MAX": str(max_len),
        "PRIMER_NUM_RETURN": "10",
        "SEARCH_SPECIFIC_PRIMER": "on",
        "PRIMER_SPECIFICITY_DATABASE": "refseq_mrna",
        "PRIMER_MIN_TM": "57",
        "PRIMER_MAX_TM": "63",
        "PRIMER_MIN_GC": "20",
        "PRIMER_MAX_GC": "80",
    }

    log("提交至 NCBI Primer-BLAST ...")
    log(f"  Forward:  {forward}")
    log(f"  Reverse:  {reverse}")
    log(f"  Organism: {organism}")

    try:
        resp = requests.post(
            PRIMER_BLAST_URL,
            data=payload,
            headers={"User-Agent": USER_AGENT},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        die(f"Primer-BLAST 提交失败: {e}")

    html = resp.text

    rid = _extract_rid(html)
    if rid:
        log(f"提交成功 RID={rid}，轮询中 ...")
        result_text = _poll_rid(rid)
        # 检测返回的是 XML 还是 HTML
        if "FW_PRIMER_SEQ_0" in result_text or "<h2>Primer pair" in result_text:
            return _parse_html(result_text)
        else:
            return _parse_xml(result_text)
    else:
        log("✓ 结果已返回")
        return _parse_html(html)


# ── 同步 HTML 解析 ──────────────────────────────────────────────────────

def _parse_html(html: str) -> BlastResult:
    """直接从 Primer-BLAST HTML 结果页解析引物对和特异性。"""
    result = BlastResult()

    def _find_hidden(pattern_base: str) -> list[tuple[str, str]]:
        pat = rf'(?:name="{pattern_base}_(\d+)"[^>]*value="([^"]+)"' \
              rf'|value="([^"]+)"[^>]*name="{pattern_base}_(\d+)")'
        results = []
        for m in re.finditer(pat, html):
            idx = m.group(1) or m.group(4)
            val = m.group(2) or m.group(3)
            results.append((idx, val))
        return results

    pair_seqs_fwd = _find_hidden("FW_PRIMER_SEQ")
    pair_seqs_rev = _find_hidden("RV_PRIMER_SEQ")
    fwd_map = dict(pair_seqs_fwd)
    rev_map = dict(pair_seqs_rev)

    fwd_tm = dict(_find_hidden("FW_PRIMER_TM"))
    rev_tm = dict(_find_hidden("RV_PRIMER_TM"))
    fwd_gc = dict(_find_hidden("FW_PRIMER_GC"))
    rev_gc = dict(_find_hidden("RV_PRIMER_GC"))

    pair_indices = sorted(set(fwd_map) | set(rev_map), key=int)
    result.total_pairs = len(pair_indices)

    for idx in pair_indices:
        pp = BlastPrimerPair()
        pp.forward_seq = fwd_map.get(idx, "")
        pp.reverse_seq = rev_map.get(idx, "")
        pp.forward_tm = fwd_tm.get(idx, "")
        pp.reverse_tm = rev_tm.get(idx, "")
        pp.forward_gc = fwd_gc.get(idx, "")
        pp.reverse_gc = rev_gc.get(idx, "")

        pair_section = _find_pair_section(html, idx)
        m = re.search(r'Product\s*length\s*[=:\s]*(\d+)', pair_section, re.I)
        if m:
            pp.product_length = m.group(1)

        pp.has_offtarget = _has_offtarget(pair_section)
        pp.intended_hits = _extract_hits(pair_section, "intended")
        pp.unintended_hits = _extract_hits(pair_section, "unintended")

        result.primers.append(pp)

    return result


def _find_pair_section(html: str, idx: str | int) -> str:
    """从 HTML 中找到第 idx 对引物的区块。"""
    marker = f'name="FW_PRIMER_SEQ_{idx}"'
    start = html.find(marker)
    if start < 0:
        return ""
    end_markers = [
        html.find(f'<h2>Primer pair {int(idx)+1}', start),
        html.find("</form>", start),
    ]
    ends = [e for e in end_markers if e > 0]
    end = min(ends) if ends else start + 5000
    return html[start:end]


def _has_offtarget(section: str) -> bool:
    """判断区块是否有 unintended targets 产物。"""
    m = re.search(
        r'Products on potentially unintended templates\s*</div>\s*<hr/>\s*<div[^>]*>\s*(.*?)</div>',
        section, re.DOTALL | re.I,
    )
    if m:
        content = m.group(1).strip()
        if content and content != "&nbsp;":
            return True
    return False


def _extract_hits(section: str, hit_type: str) -> list[BlastPrimerHit]:
    """
    从 BLAST 区块中提取命中信息。
    支持新旧两种 HTML 格式：
    - 旧格式: 表格 (<table>) 包含 Accession, Title, E-value, Identities, Alignment
    - 新格式: <a> 链接 + <pre> 文本块
    """
    hits: list[BlastPrimerHit] = []

    if hit_type == "intended":
        # 新格式: "Products on target templates" → <a>链接 + <pre>块
        # 注意: 旧格式 "Products on intended targets" 在新版中可能是空的
        pattern = r'Products on target templates.*?<div class="prPairDtl">(.*?)</div>'
        m = re.search(pattern, section, re.DOTALL | re.I)
        if m:
            dtl = m.group(1)
            # 提取 <a> 链接中的 accession 和标题
            for a_m in re.finditer(
                r'<a[^>]*>([^<]+)</a>\s*([^<]+)',
                dtl, re.I
            ):
                hit = BlastPrimerHit(
                    accession=a_m.group(1).strip(),
                    title=a_m.group(2).strip(),
                )
                # 从 <pre> 块中提取 product length
                pre_m = re.search(r'product length\s*=\s*(\d+)', dtl, re.I)
                if pre_m:
                    hit.alignment_length = pre_m.group(1)
                hits.append(hit)
            if hits:
                return hits

        # 旧格式: 表格中的 intended targets
        pattern = r'intended[^"]*"[^>]*>.*?<table[^>]*>(.*?)</table>'

    else:
        # unintended: 检查是否有非空内容
        pattern = r'unintended[^"]*"[^>]*>.*?<table[^>]*>(.*?)</table>'

    table_match = re.search(pattern, section, re.DOTALL | re.I)
    if not table_match:
        return hits

    table_html = table_match.group(1)

    # 解析表格行 - 跳过表头行
    for row_match in re.finditer(
        r'<tr[^>]*>(?:<td[^>]*>([^<]*)</td>\s*){3,}</tr>',
        table_html, re.I
    ):
        cells = [c.strip() for c in row_match.groups() if c is not None]
        if not cells or re.match(r'^(Accession|Description|Total|Products)', cells[0], re.I):
            continue
        hit = BlastPrimerHit()
        if len(cells) >= 1:
            hit.accession = cells[0]
        if len(cells) >= 2:
            hit.title = cells[1]
        if len(cells) >= 3:
            hit.evalue = cells[2]
        if len(cells) >= 4:
            hit.identities = cells[3]
        if len(cells) >= 5:
            hit.alignment_length = cells[4]
        hits.append(hit)

    return hits


# ── 异步 RID 轮询 ──────────────────────────────────────────────────────

def _extract_rid(html: str) -> str | None:
    """Extract RID or job_key from Primer-BLAST response."""
    # New interface: job_key in hidden input or meta refresh URL
    m = re.search(r'name="job_key"\s+value="([^"]+)"', html)
    if m:
        return m.group(1).strip()
    # Also check meta refresh URL
    m = re.search(r'job_key=([a-zA-Z0-9_-]+)', html)
    if m:
        return m.group(1).strip()
    # Old interface: RID hidden input
    m = re.search(r'name=["\']RID["\'][^>]*value=["\']([^"\']+)["\']', html)
    if m:
        rid = m.group(1).strip()
        if rid and rid not in ("group", "GET", "POST") and len(rid) > 5:
            return rid
    return None


def _check_status(rid: str) -> dict:
    """查询异步 RID / job_key 状态。"""
    is_job_key = rid.startswith("-") or len(rid) > 25
    try:
        params: dict[str, str] = {"CMD": "Get"}
        params["FORMAT"] = "XML"
        if is_job_key:
            params["job_key"] = rid
            params["CheckStatus"] = "Check"
        else:
            params["RID"] = rid
        resp = requests.get(
            PRIMER_BLAST_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"status": "ERROR", "error": str(e)}

    text = resp.text

    # Detect waiting page (new interface: HTML table with "Submitted" status)
    if is_job_key and re.search(r'Status.*Submitted', text, re.I):
        return {"status": "WAITING"}
    # Detect waiting page (old interface: Status=WAITING)
    if re.search(r'Status\s*=\s*WAITING', text, re.I):
        return {"status": "WAITING"}
    # Detect failure
    if re.search(r'Status\s*=\s*FAILED', text, re.I):
        m = re.search(r'Message\s*=\s*(.+?)[\r\n]', text)
        return {"status": "FAILED", "error": m.group(1) if m else "未知错误"}
    # Detect XML results (old interface: Status=READY)
    if re.search(r'Status\s*=\s*READY', text, re.I):
        return {"status": "READY", "xml": text}
    # Detect HTML results (primer pairs present)
    if "FW_PRIMER_SEQ_0" in text or "<h2>Primer pair" in text:
        return {"status": "READY", "xml": text}
    # XML content (not HTML)
    if text.strip().startswith("<?xml"):
        return {"status": "READY", "xml": text}
    return {"status": "UNKNOWN", "raw": text[:500]}


def _poll_rid(rid: str, interval: int = 5, timeout: int = 300) -> str:
    elapsed, wait = 0, interval
    while elapsed < timeout:
        result = _check_status(rid)
        if result["status"] == "READY":
            log(f"✓ BLAST 完成（{elapsed}s）")
            return result.get("xml", "")
        if result["status"] == "FAILED":
            die(f"BLAST 失败: {result.get('error')}")
        if result["status"] == "ERROR":
            die(f"查询出错: {result.get('error')}")
        print(".", end="", flush=True)
        time.sleep(wait)
        elapsed += wait
        wait = min(wait + 5, 20)
    die(f"超时（{timeout}s）。RID={rid} 可到 NCBI 手动查看。")


def _parse_xml(xml_str: str) -> BlastResult:
    import xml.etree.ElementTree as ET
    result = BlastResult()
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        result.errors.append(f"XML 解析失败: {e}")
        return result

    pairs = root.findall(".//PrimerPair") or root.findall(".//*[ForwardSequence]")
    result.total_pairs = len(pairs)

    for pair in pairs:
        pp = BlastPrimerPair()
        for tag, attr in [
            ("ForwardSequence", "forward_seq"),
            ("ReverseSequence", "reverse_seq"),
            ("ForwardTm", "forward_tm"),
            ("ReverseTm", "reverse_tm"),
            ("ForwardGCPercent", "forward_gc"),
            ("ReverseGCPercent", "reverse_gc"),
            ("ProductLength", "product_length"),
        ]:
            el = pair.find(f".//{tag}")
            if el is not None and el.text:
                setattr(pp, attr, el.text.strip())
        result.primers.append(pp)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Markdown 格式化
# ═══════════════════════════════════════════════════════════════════════════════

def format_blast_markdown(
    result: BlastResult,
    forward: str, reverse: str,
    gene: str = "", organism: str = "",
    primerbank_id: str = "",
    pair_index: int = 1,
) -> str:
    """Format BLAST verification results as a markdown block."""
    lines: list[str] = []

    if result.primers:
        p = result.primers[0]
        pp = p

        lines.append(f"\n---\n")
        gene_tag = f" — {gene}" if gene else ""
        org_tag = f" ({organism})" if organism else ""
        id_tag = f" ({primerbank_id})" if primerbank_id else ""
        lines.append(f"### #{pair_index}{gene_tag}{org_tag} — Pair {pair_index}{id_tag}")
        lines.append(f"**Forward**: `{forward}`")
        lines.append(f"**Reverse**: `{reverse}`")

        parts = []
        if pp.product_length:
            parts.append(f"**产物**: {pp.product_length} bp")
        if pp.forward_tm and pp.reverse_tm:
            parts.append(f"**Tm**: {pp.forward_tm}°C / {pp.reverse_tm}°C")
        if parts:
            lines.append(" | ".join(parts))

        lines.append("")
        lines.append("#### 特异性评估")
        if pp.is_specific:
            lines.append(f"- **状态**: ✅ 特异性良好 — 无非特异性靶标")
        else:
            lines.append(f"- **状态**: ⚠ 检测到 off-target 产物")

        if pp.intended_hits:
            lines.append(f"\n##### Intended Targets")
            lines.append(f"| Accession | Description | E-value | Identities | Alignment |")
            lines.append(f"|-----------|-------------|---------|------------|-----------|")
            for h in pp.intended_hits:
                lines.append(f"| {h.accession} | {h.title[:60]} | {h.evalue} | {h.identities} | {h.alignment_length} |")

        if pp.unintended_hits:
            lines.append(f"\n##### Unintended Targets ({len(pp.unintended_hits)})")
            lines.append(f"| Accession | Description | E-value | Identities | Alignment |")
            lines.append(f"|-----------|-------------|---------|------------|-----------|")
            for h in pp.unintended_hits:
                lines.append(f"| {h.accession} | {h.title[:60]} | {h.evalue} | {h.identities} | {h.alignment_length} |")
        else:
            lines.append("\n*无 unintended targets*")

    if result.errors:
        lines.append(f"\n**错误**:")
        for e in result.errors:
            lines.append(f"- {e}")

    lines.append("")
    return "\n".join(lines)


def format_primerbank_markdown(primers: list[dict], gene_arg: str, species: str, group_by_gene: bool = True) -> str:
    """Generate a complete markdown report from PrimerBank search results, optionally grouped by gene."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 引物设计报告",
        "",
        "## 查询信息",
        f"- **物种**: {species}",
        f"- **基因**: {gene_arg}",
        f"- **搜索时间**: {now}",
        f"- **总引物对数**: {len(primers)}",
        "",
        "---",
        "",
        "## PrimerBank 搜索结果",
        "",
    ]

    if group_by_gene:
        # Group primers by gene for easier multi-gene reading
        gene_groups: dict[str, list[dict]] = {}
        gene_order: list[str] = []
        for p in primers:
            g = p.get("gene", "Unknown")
            if g not in gene_groups:
                gene_groups[g] = []
                gene_order.append(g)
            gene_groups[g].append(p)

        for gene_name in gene_order:
            gene_primers = gene_groups[gene_name]
            lines.append(f"### {gene_name}")
            lines.append(f"**物种**: {species} | **共 {len(gene_primers)} 对引物**")
            lines.append("")

            for i, p in enumerate(gene_primers, 1):
                lines.append(f"#### 引物对 #{i}")
                pid = p.get("primerbank_id", "N/A")
                plen = p.get("product_length", "?")
                validated = p.get("validated", False)
                badge = " ✅ **已验证**" if validated else ""
                lines.append(f"**PrimerBank ID**: {pid} | **Amplicon**: {plen} bp{badge}")
                lines.append("")

                f_seq = p.get("forward", "")
                f_len = p.get("forward_length", "")
                f_tm = p.get("forward_tm", "")
                f_loc = p.get("forward_location", "")
                r_seq = p.get("reverse", "")
                r_len = p.get("reverse_length", "")
                r_tm = p.get("reverse_tm", "")
                r_loc = p.get("reverse_location", "")

                lines.append("| | Sequence (5'→3') | Length | Tm | Location |")
                lines.append("|---|-------------------|--------|----|----------|")
                lines.append(f"| **Forward** | `{f_seq}` | {f_len} | {f_tm}°C | {f_loc} |")
                lines.append(f"| **Reverse** | `{r_seq}` | {r_len} | {r_tm}°C | {r_loc} |")
                lines.append("")
    else:
        # Original sequential format (for backward compatibility)
        for i, p in enumerate(primers, 1):
            lines.append(f"### 引物对 #{i}")
            pid = p.get("primerbank_id", "N/A")
            plen = p.get("product_length", "?")
            gene = p.get("gene", "")
            validated = p.get("validated", False)
            badge = " ✅ **已验证**" if validated else ""
            lines.append(f"**基因**: {gene} | **PrimerBank ID**: {pid} | **Amplicon**: {plen} bp{badge}")
            lines.append("")

            # Primer info table
            f_seq = p.get("forward", "")
            f_len = p.get("forward_length", "")
            f_tm = p.get("forward_tm", "")
            f_loc = p.get("forward_location", "")
            r_seq = p.get("reverse", "")
            r_len = p.get("reverse_length", "")
            r_tm = p.get("reverse_tm", "")
            r_loc = p.get("reverse_location", "")

            lines.append("| | Sequence (5'→3') | Length | Tm | Location |")
            lines.append("|---|-------------------|--------|----|----------|")
            lines.append(f"| **Forward** | `{f_seq}` | {f_len} | {f_tm}°C | {f_loc} |")
            lines.append(f"| **Reverse** | `{r_seq}` | {r_len} | {r_tm}°C | {r_loc} |")
            lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def log(msg: str, end: str = "\n"):
    print(msg, end=end, file=sys.stderr, flush=True)

def die(msg: str):
    print(f"\n[!] {msg}", file=sys.stderr)
    sys.exit(1)

def validate_seq(seq: str, name: str):
    if not re.fullmatch(r'[ATCGatcg]+', seq.strip()):
        die(f"{name} 序列含非法碱基（只允许 A/T/C/G）: {seq}")


# ═══════════════════════════════════════════════════════════════════════════════
#  NCBI Gene Symbol Resolution
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_gene_symbol(gene_name: str, species: str) -> list[dict]:
    """Resolve a gene name/alias to official NCBI Gene Symbol(s) using NCBI E-utilities.

    Returns list of dicts with: input_name, symbol, gene_id, description, summary.
    """
    species_map = {
        "human": "Homo sapiens",
        "mouse": "Mus musculus",
    }
    scientific_name = species_map.get(species.lower(), species)

    # Step 1: Search for the gene
    search_url = f"{NCBI_EUTILS}/esearch.fcgi"
    params = {
        "db": "gene",
        "term": f"{gene_name}[Gene Name] AND {scientific_name}[Organism]",
        "retmode": "json",
    }
    try:
        resp = requests.get(search_url, params=params,
                            headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"input_name": gene_name, "error": str(e)}]

    ids = data.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return [{"input_name": gene_name,
                 "error": f"未找到 '{gene_name}' 在 {scientific_name} 中的基因记录"}]

    # Step 2: Get details for the top result
    summary_url = f"{NCBI_EUTILS}/esummary.fcgi"
    params = {"db": "gene", "id": ids[0], "retmode": "json"}
    try:
        resp = requests.get(summary_url, params=params,
                            headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"input_name": gene_name, "gene_id": ids[0], "error": str(e)}]

    result = data.get("result", {})
    gene_info = result.get(ids[0], {})
    return [{
        "input_name": gene_name,
        "symbol": gene_info.get("name", ""),
        "gene_id": ids[0],
        "description": gene_info.get("description", ""),
        "summary": gene_info.get("summary", ""),
    }]


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="primer_blast.py",
        description="qPCR 引物工具 — PrimerBank 搜索 + Primer-BLAST 验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              # 搜索 PrimerBank
              python primer_blast.py primerbank -g GAD1 -s mouse

              # 搜索 + JSON 输出
              python primer_blast.py primerbank -g GAD1 -s mouse --json

              # 多基因搜索
              python primer_blast.py primerbank -g GAD1,GAPDH -s mouse --json

              # 验证引物特异性 + 追加到 markdown
              python primer_blast.py -f AACGTATGATACTTGGTGTGGC -r CCAGGCTATTGGTCCTTTGTAAG -g GAD1 --append-md report.md
        """),
    )

    p.add_argument("-f", "--forward", help="Forward primer 序列 (5'→3')")
    p.add_argument("-r", "--reverse", help="Reverse primer 序列 (5'→3')")
    p.add_argument("-g", "--gene", default="", help="基因名称")
    p.add_argument("-s", "--species", default="Mus musculus",
                   help="物种 (默认: Mus musculus)")
    p.add_argument("--min", type=int, default=70, help="最小产物长度 (默认: 70)")
    p.add_argument("--max", type=int, default=200, help="最大产物长度 (默认: 200)")
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    p.add_argument("-o", "--output", help="将结果写入文件")
    p.add_argument("--rid", help="使用已有 RID 查询结果")
    p.add_argument("--append-md", help="将 BLAST 验证结果追加到指定 Markdown 文件")
    p.add_argument("--primerbank-id", help="PrimerBank ID（用于 markdown 标注）")

    sub = p.add_subparsers(dest="command")
    pb = sub.add_parser("primerbank", help="从 PrimerBank 搜索引物")
    pb.add_argument("-g", "--gene", required=True, help="基因名称（多个用逗号分隔）")
    pb.add_argument("-s", "--species", default="mouse",
                    choices=["human", "mouse"], help="物种 (默认: mouse)")
    pb.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    pb.add_argument("--markdown", action="store_true", help="以 Markdown 格式输出")
    pb.add_argument("-o", "--output", help="将结果写入文件")

    # resolve-gene subcommand
    rg = sub.add_parser("resolve-gene", help="将基因名称转换为 NCBI 官方 Gene Symbol")
    rg.add_argument("-g", "--gene", required=True, help="基因名称（多个用逗号分隔）")
    rg.add_argument("-s", "--species", default="mouse",
                    choices=["human", "mouse"], help="物种 (默认: mouse)")
    rg.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    return p


def run_verify(args):
    if not args.forward or not args.reverse:
        die("请提供 -f (forward) 和 -r (reverse) 引物序列")

    forward = args.forward.upper().strip()
    reverse = args.reverse.upper().strip()
    validate_seq(forward, "Forward")
    validate_seq(reverse, "Reverse")

    organism = args.species
    # If species is a short name, map to scientific name
    if organism.lower() in SCIENTIFIC_NAMES:
        organism = SCIENTIFIC_NAMES[organism.lower()]

    result = submit_and_parse(
        forward, reverse, organism, args.min, args.max
    )

    result.gene = args.gene or ""
    result.forward_seq = forward
    result.reverse_seq = reverse

    if args.json:
        output = json.dumps(asdict(result), ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            log(f"JSON 结果已保存至 {args.output}")
        else:
            print(output)
        return

    if args.append_md:
        md_block = format_blast_markdown(
            result, forward, reverse,
            gene=args.gene or "",
            organism=organism,
            primerbank_id=args.primerbank_id or "",
        )
        with open(args.append_md, "a", encoding="utf-8") as f:
            f.write(md_block)
        log(f"BLAST 结果已追加至 {args.append_md}")
        # Also print to console
        print_report(result, forward, reverse, args.gene or "", organism)
        return

    print_report(result, forward, reverse, args.gene or "", organism)


def _format_primerbank_console(primers: list[dict], species: str) -> str:
    """Format PrimerBank results as console text."""
    lines: list[str] = []
    lines.append(f"\n{'='*58}")
    genes_shown: set[str] = set()
    for i, p in enumerate(primers, 1):
        pid = p.get("primerbank_id", "N/A")
        plen = p.get("product_length", "?")
        gene = p.get("gene", "")
        validated = p.get("validated", False)
        badge = " ✅已验证" if validated else ""
        f_tm = p.get("forward_tm", "")
        f_loc = p.get("forward_location", "")
        r_tm = p.get("reverse_tm", "")
        r_loc = p.get("reverse_location", "")
        if i == 1 or gene not in genes_shown:
            if i > 1:
                lines.append(f"{'─'*58}")
            lines.append(f"\n  [{i}] {gene} ({species}) — ID={pid}{badge}")
            genes_shown.add(gene)
        else:
            lines.append(f"\n  [{i}] ID={pid}{badge}")
        lines.append(f"      F: {p['forward']}  ({p.get('forward_length','?')}nt, Tm={f_tm}°C, {f_loc})")
        lines.append(f"      R: {p['reverse']}  ({p.get('reverse_length','?')}nt, Tm={r_tm}°C, {r_loc})")
        lines.append(f"      产物: {plen} bp")
    lines.append(f"\n{'='*58}")
    lines.append(f"  共 {len(primers)} 对引物")
    lines.append(f"{'='*58}\n")
    return "\n".join(lines)


def run_primerbank(args):
    primers = search_primerbank(args.gene, args.species)
    if not primers:
        die(f"未找到 {args.gene} ({args.species}) 的引物")

    # Generate output string based on format
    if args.json:
        output_str = json.dumps(primers, ensure_ascii=False, indent=2)
    elif args.markdown:
        output_str = format_primerbank_markdown(primers, args.gene, args.species)
    else:
        output_str = _format_primerbank_console(primers, args.species)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        log(f"结果已保存至 {args.output}")
    else:
        print(output_str)


def run_resolve_gene(args):
    """Resolve gene names to NCBI official Gene Symbols."""
    gene_list = [g.strip() for g in args.gene.split(",") if g.strip()]
    results = []
    for gene in gene_list:
        resolved = resolve_gene_symbol(gene, args.species)
        results.extend(resolved)

    if args.json:
        output = json.dumps(results, ensure_ascii=False, indent=2)
        print(output)
    else:
        print(f"\n{'=' * 58}")
        print(f"  NCBI Gene Symbol 解析结果 ({args.species})")
        print(f"{'=' * 58}")
        for r in results:
            if r.get("symbol"):
                print(f"  {r['input_name']} → {r['symbol']} (ID: {r['gene_id']})")
                print(f"     {r.get('description', '')}")
            else:
                print(f"  {r['input_name']} → ❌ {r.get('error', '未知错误')}")
        print(f"{'=' * 58}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  Report
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(
    result: BlastResult,
    forward: str, reverse: str,
    gene: str = "", organism: str = "", rid: str = "",
):
    """打印格式化的验证报告。"""
    S = "═" * 58

    print(f"\n{S}")
    print(f"  Primer-BLAST 引物特异性验证报告")
    print(f"{S}")
    if gene:     print(f"  基因:     {gene}")
    if organism: print(f"  物种:     {organism}")
    if rid:      print(f"  RID:      {rid}")
    print(f"{S}")
    print(f"  Forward:  {forward}")
    print(f"  Reverse:  {reverse}")
    print(f"{S}")

    if not result.primers:
        print("\n  ⚠ 未找到引物对结果。")
        if result.errors:
            for e in result.errors:
                print(f"    {e}")
        print(f"{S}\n")
        return

    p = result.primers[0]

    print(f"\n  ■ 引物对 #1 信息")
    print(f"  ─────────────────────────────────────")
    if p.forward_seq:     print(f"  Forward:   {p.forward_seq}")
    if p.reverse_seq:     print(f"  Reverse:   {p.reverse_seq}")
    if p.product_length:  print(f"  产物:      {p.product_length} bp")
    if p.forward_tm and p.reverse_tm:
        print(f"  Tm:        {p.forward_tm}°C / {p.reverse_tm}°C (F/R)")
    if p.forward_gc and p.reverse_gc:
        print(f"  GC%%:      {p.forward_gc}%% / {p.reverse_gc}%% (F/R)")

    print(f"\n  ■ 特异性分析")
    print(f"  ─────────────────────────────────────")
    if p.is_specific:
        print(f"  ✅ 特异性良好 — 无非特异性靶标")
    else:
        print(f"  ⚠ 检测到 off-target 产物")

    if p.unintended_hits:
        print(f"\n     Off-target 命中 ({len(p.unintended_hits)}):")
        for h in p.unintended_hits[:5]:
            print(f"       {h.accession}  {h.title[:50]}")

    if len(result.primers) > 1:
        print(f"\n  ─ 其他候选引物 ({len(result.primers)-1})")
        for i, o in enumerate(result.primers[1:4], 2):
            pl = o.product_length or "?"
            tag = " ✅" if o.is_specific else " ⚠"
            print(f"     #{i}: {o.forward_seq[:18]}/{o.reverse_seq[:18]}  ({pl} bp){tag}")
        if len(result.primers) > 4:
            print(f"     ... 还有 {len(result.primers)-4} 对")

    print(f"{S}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args = build_parser().parse_args()
    if args.command == "primerbank":
        run_primerbank(args)
    elif args.command == "resolve-gene":
        run_resolve_gene(args)
    else:
        run_verify(args)


if __name__ == "__main__":
    main()
