"""文献 Agent：为每个候选药物检索支持性文献。"""

import re

from src.llm import run_agent
from src.prompts import LITERATURE
from src.state import MDTState
from src.tools.pubmed import SEARCH_PUBMED_SPEC, search_pubmed

TOOLS = [SEARCH_PUBMED_SPEC]
TOOL_MAP = {"search_pubmed": search_pubmed}

# 药名的英文字母形态：首字母大写 + 全小写后缀，可排除 EGFR/ALK 这类全大写基因名。
# 不能用 \b 做边界：中文也算 \w，"推荐Osimertinib" 会匹配不到。
DRUG_NAME = re.compile(r"(?<![A-Za-z])[A-Z][a-z]{5,}(?![A-Za-z])")


def _candidate_drugs(text: str, limit: int = 3) -> list[str]:
    names: list[str] = []
    for name in DRUG_NAME.findall(text):
        if name not in names:
            names.append(name)
    return names[:limit]


def _fallback_references(state: MDTState) -> str:
    """模型没调工具时的兜底：直接查 PubMed，保证引用不丢。

    只依赖模型"决定调不调工具"会让引用时有时无，这里改成确定性补查。
    """
    mutations = state["case"].get("mutations", [])
    genes = " ".join(sorted({m.get("gene", "") for m in mutations if m.get("gene")}))
    lines: list[str] = []
    for drug in _candidate_drugs(state.get("drug", "")):
        for hit in search_pubmed(f"{drug} {genes}".strip(), max_results=1):
            if "pmid" in hit:
                lines.append(f"- {drug}：PMID {hit['pmid']}（{hit.get('title', '')}）")
                break
    if not lines:
        return ""
    return "\n\n补充检索（系统直连 PubMed，可作为引用依据）：\n" + "\n".join(lines)


def literature_agent(state: MDTState) -> dict:
    case = state["case"]
    user = (
        f"癌种：{case.get('cancer_type')}\n"
        f"候选药物报告：\n{state.get('drug', '')}\n\n"
        "请为每个候选药物检索 1-2 篇支持性文献，只引用工具返回的真实 PMID。"
    )
    report = run_agent(LITERATURE, user, TOOLS, TOOL_MAP)
    if "PMID" not in report.upper():
        report += _fallback_references(state)
    return {
        "literature": report,
        "trace": [{"agent": "文献 Agent", "content": report}],
    }
