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


def build_graph():
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
    g.add_edge("drug", "literature")

    # 两条支路在决策节点汇合（LangGraph 会等两个上游都完成）
    g.add_edge("pathology", "decision")
    g.add_edge("literature", "decision")
    g.add_edge("decision", END)

    return g.compile()


# 思考题：如果某个病例没有任何可用药变异，
# 怎么用 add_conditional_edges 让 genomics 直接跳到 decision？
