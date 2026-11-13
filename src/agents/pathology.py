"""病理 Agent：把非结构化病理文本抽成结构化字段。"""

import json

from src.llm import chat_json
from src.prompts import PATHOLOGY
from src.schemas import PathologyFinding
from src.state import MDTState


def pathology_agent(state: MDTState) -> dict:
    case = state["case"]
    finding = chat_json(
        [
            {"role": "system", "content": PATHOLOGY},
            {"role": "user", "content": f"病理报告原文：\n{case.get('pathology_text', '')}"},
        ],
        PathologyFinding,
    )
    data = finding.model_dump()
    return {
        "pathology": data,
        "trace": [
            {"agent": "病理 Agent", "content": json.dumps(data, ensure_ascii=False, indent=2)}
        ],
    }
