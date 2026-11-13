"""本地知识库查询工具。

kb/variant_drug_evidence.csv 是 CIViC 导出数据的简化版（字段对齐 CIViC 的
gene / variant / drug / evidence_level）。正式做课题时，把 CIViC 官网下载的完整
TSV 转成同样的 7 列即可，不需要改动任何代码。
"""

import csv
from functools import lru_cache

from config import KB_DIR

KB_FILE = KB_DIR / "variant_drug_evidence.csv"


@lru_cache(maxsize=1)
def _load_rows() -> tuple[dict, ...]:
    """一次性读入内存并缓存，避免每个 Agent 反复读盘。"""
    with KB_FILE.open(encoding="utf-8-sig") as f:
        return tuple(csv.DictReader(f))


def search_variant_evidence(gene: str, variant: str = "", cancer_type: str = "") -> list[dict]:
    """按基因 + 变异查证据，返回最多 5 条匹配记录。

    Args:
        gene: 基因名，例如 EGFR
        variant: 变异，例如 L858R；留空表示该基因的所有变异
        cancer_type: 癌种，例如 肺腺癌；留空表示不限制
    """
    gene_key = gene.strip().upper()
    variant_key = variant.strip().lower()
    hits = []
    for row in _load_rows():
        if row["gene"].upper() != gene_key:
            continue
        if variant_key and variant_key not in row["variant"].lower():
            continue
        if cancer_type and cancer_type not in row["cancer_type"]:
            continue
        hits.append(row)
        if len(hits) >= 5:
            break
    if not hits:
        # 明确告诉模型"查不到"，避免它自行编造
        return [{"status": "not_found", "message": f"知识库中无 {gene} {variant} 的记录"}]
    return hits


def list_targeted_drugs(cancer_type: str) -> list[dict]:
    """按癌种列出知识库中所有可用靶向药，供药物 Agent 兜底查询。

    Args:
        cancer_type: 癌种，例如 肺腺癌
    """
    seen, out = set(), []
    for row in _load_rows():
        if cancer_type and cancer_type not in row["cancer_type"]:
            continue
        if not row["drug"] or row["drug"] in seen:
            continue
        seen.add(row["drug"])
        out.append(row)
    return out or [{"status": "not_found", "message": f"无 {cancer_type} 的靶向药记录"}]


# --- OpenAI function calling 的 schema 定义 ---

SEARCH_VARIANT_SPEC = {
    "type": "function",
    "function": {
        "name": "search_variant_evidence",
        "description": "查询本地肿瘤变异-药物证据库，返回该基因变异的药物、靶点与证据等级",
        "parameters": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "基因名，例如 EGFR"},
                "variant": {"type": "string", "description": "变异写法，例如 L858R"},
                "cancer_type": {"type": "string", "description": "癌种，例如 肺腺癌"},
            },
            "required": ["gene"],
        },
    },
}

LIST_DRUGS_SPEC = {
    "type": "function",
    "function": {
        "name": "list_targeted_drugs",
        "description": "按癌种列出知识库中所有可用靶向药",
        "parameters": {
            "type": "object",
            "properties": {
                "cancer_type": {"type": "string", "description": "癌种，例如 肺腺癌"},
            },
            "required": ["cancer_type"],
        },
    },
}
