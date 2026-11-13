"""Pydantic 数据结构：约束 LLM 输出格式，也用作 Agent 之间的接口契约。"""

from typing import Literal

from pydantic import BaseModel, Field


class Mutation(BaseModel):
    """病例中的一个基因变异。"""

    gene: str = Field(description="基因名，例如 EGFR")
    variant: str = Field(description="变异写法，例如 L858R")
    vaf: float | None = Field(default=None, description="变异等位基因频率，0-1")


class Case(BaseModel):
    """一份虚拟病例，系统唯一的输入。"""

    case_id: str
    cancer_type: str = Field(description="癌种，例如 肺腺癌")
    stage: str = Field(default="", description="分期，例如 IIIB")
    mutations: list[Mutation] = Field(default_factory=list)
    pathology_text: str = Field(default="", description="病理报告的原始文本")
    clinical_notes: str = Field(default="", description="临床补充信息")
    # 评测用标准答案：该病例应对应的药物列表
    ground_truth_drugs: list[str] = Field(default_factory=list)


class PathologyFinding(BaseModel):
    """病理 Agent 的结构化抽取结果。"""

    histological_type: str = Field(default="", description="组织学类型")
    grade: str = Field(default="", description="分级")
    stage: str = Field(default="", description="分期")
    markers: dict[str, str] = Field(default_factory=dict, description="免疫组化/分子标志物")
    summary: str = Field(default="", description="一句话病理结论")


class DrugRecommendation(BaseModel):
    """决策 Agent 给出的单条用药建议。"""

    drug: str
    target: str = Field(default="", description="药物靶点")
    evidence_level: Literal["A", "B", "C", "D", "未知"] = "未知"
    mechanism: str = Field(default="", description="机制解释链：突变 → 通路 → 药物作用")
    rationale: str = Field(default="", description="推荐理由，需引用上游 Agent 的结论")
    references: list[str] = Field(default_factory=list, description="PMID 或数据库编号")


class FinalReport(BaseModel):
    """最终结构化会诊报告。"""

    case_summary: str = Field(default="", description="病例要点复述")
    key_findings: list[str] = Field(default_factory=list, description="各学科关键发现")
    recommendations: list[DrugRecommendation] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list, description="证据不足之处")
    disclaimer: str = ""
