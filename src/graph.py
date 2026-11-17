"""LangGraph 图编排：把六个 Agent 串成会诊流程。

    START → 协调 → (基因组 → 药物 → 文献) ∥ (病理) → 决策 → END
"""

from langgraph.graph import END, START, StateGraph

from src.agents.coordinator import coordinator_agent
from src.agents.decision import decision_agent
from src.agents.drug import drug_agent
from src.agents.genomics import genomics_agent
from src.agents.literature import literature_agent
from src.agents.pathology import pathology_agent
from src.state import MDTState


def build_graph(enable_literature: bool = True):
    """构建会诊图。

    enable_literature=False 时跳过文献 Agent（drug 直接连 decision），
    用于评测里的消融实验，正常使用保持默认值即可。
    """
    g = StateGraph(MDTState)

    g.add_node("coordinator", coordinator_agent)
    g.add_node("genomics", genomics_agent)
    g.add_node("pathology", pathology_agent)
    g.add_node("drug", drug_agent)
    g.add_node("literature", literature_agent)
    g.add_node("decision", decision_agent)

    g.add_edge(START, "coordinator")
    # 两条并行支路：基因组线和病理线同时开跑
    g.add_edge("coordinator", "genomics")
    g.add_edge("coordinator", "pathology")

    g.add_edge("genomics", "drug")

    if enable_literature:
        g.add_edge("drug", "literature")
        # 两条支路在决策节点汇合。
        # 必须写成列表：分开写两条边时，decision 会分别被两个上游各触发一次，
        # 导致决策 Agent 跑两遍（第一遍只有病理报告，白花一次 token）。
        g.add_edge(["pathology", "literature"], "decision")
    else:
        # 消融实验：没有文献支路，基因组线完成后直接进决策
        g.add_edge(["pathology", "drug"], "decision")

    g.add_edge("decision", END)

    return g.compile()


# 思考题：如果某个病例没有任何可用药变异，
# 怎么用 add_conditional_edges 让 genomics 直接跳到 decision？
