"""基因组 Agent：查知识库，判断每个变异的可靶向性。"""

import json

from src.llm import run_agent
from src.prompts import GENOMICS
from src.state import MDTState
from src.tools.knowledge_base import (
    SEARCH_VARIANT_SPEC,
    search_variant_evidence,
)

TOOLS = [SEARCH_VARIANT_SPEC]
TOOL_MAP = {"search_variant_evidence": search_variant_evidence}


def genomics_agent(state: MDTState) -> dict:
    case = state["case"]
    user = (
        f"癌种：{case.get('cancer_type')}\n"
        f"变异列表：{json.dumps(case.get('mutations', []), ensure_ascii=False)}\n"
        "请逐个变异调用工具查询证据，并给出可用药变异清单。"
    )
    report = run_agent(GENOMICS, user, TOOLS, TOOL_MAP)
    return {"genomics": report, "trace": [{"agent": "基因组 Agent", "content": report}]}
