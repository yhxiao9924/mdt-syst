"""Streamlit 演示页：输入病例 → 实时显示各 Agent 进度 → 渲染会诊报告。

运行：
    streamlit run app.py
"""

import json
import time

import streamlit as st

from config import CASE_DIR, DEEPSEEK_API_KEY, DISCLAIMER
from src.graph import build_graph
from src.schemas import Case

AGENT_LABELS = {
    "coordinator": "协调 Agent",
    "genomics": "基因组 Agent",
    "pathology": "病理 Agent",
    "drug": "药物 Agent",
    "literature": "文献 Agent",
    "decision": "决策 Agent",
}

AGENT_HINTS = {
    "coordinator": "拆解会诊任务，确定需要哪些科室参与",
    "genomics": "解读基因突变，查询本地知识库的用药证据",
    "pathology": "从病理文本中抽取组织学类型、分期与标志物",
    "drug": "根据可靶向变异匹配候选药物",
    "literature": "为候选药物检索 PubMed 支持性文献",
    "decision": "汇总四方意见，形成分级治疗建议",
}

st.set_page_config(page_title="MDT 多智能体会诊系统", page_icon="🩺", layout="wide")


@st.cache_resource
def get_graph():
    """图只构建一次，避免每次点击都重新编译。"""
    return build_graph()


def strip_answer(case: dict) -> dict:
    """去掉评测用的标准答案，避免把答案喂给模型。"""
    payload = dict(case)
    payload.pop("ground_truth_drugs", None)
    return payload


def total_pmids(recs: list[dict]) -> int:
    return sum(
        1
        for rec in recs
        for ref in (rec.get("references") or [])
        if "PMID" in str(ref).upper()
    )


st.title("MDT 多智能体会诊系统")
st.caption("多 Agent 协作整合基因组、病理与文献证据 · 教学演示项目")

# ---------------------------------------------------------------- 侧边栏
with st.sidebar:
    st.header("病例输入")
    case_files = sorted(p.name for p in CASE_DIR.glob("*.json"))
    if not case_files:
        st.error(f"未找到病例文件，请检查 {CASE_DIR}")
        st.stop()

    chosen = st.selectbox("选择内置病例", case_files)
    # key 带上文件名：切换病例时输入框才会刷新
    raw = st.text_area(
        "病例 JSON（可自由修改）",
        value=(CASE_DIR / chosen).read_text(encoding="utf-8"),
        height=380,
        key=f"raw_{chosen}",
    )
    start = st.button("开始会诊", type="primary", use_container_width=True)
    st.divider()
    st.caption("每个 Agent 的结论都要求可溯源：知识库查不到就写「证据不足」，不编造药物与文献。")

# ---------------------------------------------------------------- 主流程
if start:
    if not DEEPSEEK_API_KEY:
        st.error("未检测到 DEEPSEEK_API_KEY，请在项目根目录的 .env 中配置后重启。")
        st.stop()

    try:
        case = strip_answer(Case.model_validate_json(raw).model_dump())
    except Exception as exc:  # noqa: BLE001
        st.error(f"病例格式有误：{exc}")
        st.stop()

    started = time.time()
    report = None
    logs: list[tuple[str, str]] = []

    with st.status("MDT 会诊进行中…", expanded=True) as status:
        try:
            for chunk in get_graph().stream(
                {"case": case, "trace": []}, stream_mode="updates"
            ):
                for node, update in chunk.items():
                    label = AGENT_LABELS.get(node, node)
                    if node == "decision":
                        report = update.get("report")
                    st.markdown(f"**{label}** — {AGENT_HINTS.get(node, '')}")
                    for item in update.get("trace", []):
                        content = item.get("content", "")
                        logs.append((label, content))
                        st.caption(content[:220] + ("…" if len(content) > 220 else ""))
            elapsed = time.time() - started
            status.update(
                label=f"会诊完成 · 耗时 {elapsed:.0f}s", state="complete", expanded=False
            )
        except Exception as exc:  # noqa: BLE001
            status.update(label="会诊失败", state="error")
            st.error(f"运行出错：{type(exc).__name__}: {exc}")
            st.stop()

    if not report:
        st.error("流程结束但没有生成会诊报告，请查看上方日志。")
        st.stop()

    recs = report.get("recommendations") or []

    # ------------------------------------------------------------ 概览指标
    st.subheader("会诊结论")
    col1, col2, col3 = st.columns(3)
    col1.metric("候选药物", len(recs))
    col2.metric("引用文献", total_pmids(recs))
    col3.metric("总耗时", f"{elapsed:.0f}s")

    st.info(report.get("case_summary", "（未生成病例摘要）"))

    tab_drug, tab_finding, tab_log, tab_raw = st.tabs(
        ["用药建议", "关键发现与不确定性", "过程记录", "原始 JSON"]
    )

    # ------------------------------------------------------------ 用药建议
    with tab_drug:
        if not recs:
            st.warning(
                "本病例未检索到可用靶向药。系统选择如实返回「证据不足」，而不是勉强给出推荐。"
            )
        for rec in recs:
            title = (
                f"**{rec.get('drug', '未命名')}** · 靶点 {rec.get('target') or '未标注'}"
                f" · 证据等级 {rec.get('evidence_level') or '未标注'}"
            )
            st.markdown(title)
            st.markdown(f"**作用机制**：{rec.get('mechanism', '')}")
            st.markdown(f"**推荐依据**：{rec.get('rationale', '')}")
            refs = rec.get("references") or []
            st.caption("参考文献：" + ("、".join(refs) if refs else "无"))
            st.divider()

    # ------------------------------------------------------------ 发现与局限
    with tab_finding:
        st.markdown("**关键发现**")
        findings = report.get("key_findings") or []
        for item in findings or ["（无）"]:
            st.markdown(f"- {item}")

        st.markdown("**证据不足之处**")
        for item in report.get("uncertainties") or ["（无）"]:
            st.markdown(f"- {item}")

    # ------------------------------------------------------------ 过程记录
    with tab_log:
        st.caption("每个 Agent 的原始输出，可用于说明多 Agent 是如何分工协作的。")
        for label, content in logs:
            with st.expander(label):
                st.text(content)

    # ------------------------------------------------------------ 原始数据
    with tab_raw:
        st.json(report)
        st.download_button(
            "下载报告 JSON",
            data=json.dumps(report, ensure_ascii=False, indent=2),
            file_name=f"{case.get('case_id', 'case')}_report.json",
            mime="application/json",
        )

st.divider()
st.caption(DISCLAIMER)
