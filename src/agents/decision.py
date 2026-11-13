"""决策 Agent：汇总四位专家的报告，产出结构化最终结论。"""

import json

from config import DISCLAIMER
from src.llm import chat_json
from src.prompts import DECISION
from src.schemas import FinalReport
from src.state import MDTState


def decision_agent(state: MDTState) -> dict:
    case = state["case"]
    context = (
        f"癌种：{case.get('cancer_type')}，分期：{case.get('stage', '未提供')}\n\n"
        f"【会诊分工】\n{state.get('plan', '')}\n\n"
        f"【基因组报告】\n{state.get('genomics', '')}\n\n"
        f"【病理报告】\n{json.dumps(state.get('pathology', {}), ensure_ascii=False)}\n\n"
        f"【药物报告】\n{state.get('drug', '')}\n\n"
        f"【文献报告】\n{state.get('literature', '')}\n\n"
        "请整合以上信息，输出结构化会诊结论。"
    )
    report = chat_json(
        [
            {"role": "system", "content": DECISION},
            {"role": "user", "content": context},
        ],
        FinalReport,
    )
    data = report.model_dump()
    data["disclaimer"] = DISCLAIMER
    return {
        "report": data,
        "trace": [{"agent": "决策 Agent", "content": "已生成最终会诊报告"}],
    }
