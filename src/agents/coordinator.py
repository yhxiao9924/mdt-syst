"""协调 Agent：制定分工计划。不碰任何医学结论。"""

import json

from src.llm import chat
from src.prompts import COORDINATOR
from src.state import MDTState


def coordinator_agent(state: MDTState) -> dict:
    case = state["case"]
    brief = (
        f"癌种：{case.get('cancer_type', '未知')}\n"
        f"分期：{case.get('stage', '未知')}\n"
        f"突变：{json.dumps(case.get('mutations', []), ensure_ascii=False)}\n"
        f"病理摘要：{case.get('pathology_text', '')[:200]}\n"
        f"临床备注：{case.get('clinical_notes', '')}"
    )
    plan = chat(
        [
            {"role": "system", "content": COORDINATOR},
            {"role": "user", "content": f"请为以下病例制定会诊分工：\n{brief}"},
        ]
    )
    return {"plan": plan, "trace": [{"agent": "协调 Agent", "content": plan}]}
