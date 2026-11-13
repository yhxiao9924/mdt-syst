"""文献 Agent：为每个候选药物检索支持性文献。"""

from src.llm import run_agent
from src.prompts import LITERATURE
from src.state import MDTState
from src.tools.pubmed import SEARCH_PUBMED_SPEC, search_pubmed

TOOLS = [SEARCH_PUBMED_SPEC]
TOOL_MAP = {"search_pubmed": search_pubmed}


def literature_agent(state: MDTState) -> dict:
    case = state["case"]
    user = (
        f"癌种：{case.get('cancer_type')}\n"
        f"候选药物报告：\n{state.get('drug', '')}\n\n"
        "请为每个候选药物检索 1-2 篇支持性文献，只引用工具返回的真实 PMID。"
    )
    report = run_agent(LITERATURE, user, TOOLS, TOOL_MAP)
    return {
        "literature": report,
        "trace": [{"agent": "文献 Agent", "content": report}],
    }
