"""药物 Agent：把可用药变异映射到知识库中的真实药物。"""

from src.llm import run_agent
from src.prompts import DRUG
from src.state import MDTState
from src.tools.knowledge_base import (
    LIST_DRUGS_SPEC,
    SEARCH_VARIANT_SPEC,
    list_targeted_drugs,
    search_variant_evidence,
)

TOOLS = [SEARCH_VARIANT_SPEC, LIST_DRUGS_SPEC]
TOOL_MAP = {
    "search_variant_evidence": search_variant_evidence,
    "list_targeted_drugs": list_targeted_drugs,
}


def drug_agent(state: MDTState) -> dict:
    case = state["case"]
    user = (
        f"癌种：{case.get('cancer_type')}\n"
        f"基因组报告：\n{state.get('genomics', '')}\n\n"
        "请确认候选药物，按证据等级排序，并标注靶点。"
    )
    report = run_agent(DRUG, user, TOOLS, TOOL_MAP)
    return {"drug": report, "trace": [{"agent": "药物 Agent", "content": report}]}
