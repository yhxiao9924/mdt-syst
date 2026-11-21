"""LangGraph 的全局状态定义"""

import operator
from typing import Annotated, TypedDict


class MDTState(TypedDict, total=False):
    case: dict                     # 输入病例（Case.model_dump() 后的结果）
    plan: str                      # 协调 Agent 的分工计划
    genomics: str                  # 基因组 Agent 报告
    pathology: dict                # 病理 Agent 的结构化结果
    drug: str                      # 药物 Agent 报告
    literature: str                # 文献 Agent 报告
    report: dict                   # 决策 Agent 的最终报告（FinalReport）
    trace: Annotated[list, operator.add]  # 各节点的执行日志，用于前端展示
