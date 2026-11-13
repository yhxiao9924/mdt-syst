"""Streamlit 演示页：输入病例 → 实时显示各 Agent 进度 → 渲染会诊报告。

运行：
    streamlit run app.py
"""

import json

import streamlit as st

from config import CASE_DIR, DISCLAIMER
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

st.set_page_config(page_title="MDT 多智能体会诊系统", page_icon="🩺", layout="wide")
st.title("MDT 多智能体会诊系统")
st.caption("多 Agent 协作整合基因组、病理与文献证据 · 教学演示项目")

# ---------- 侧边栏：病例输入 ----------
with st.sidebar:
    st.header("病例输入")
    case_files = sorted(p.name for p in CASE_DIR.glob("*.json"))
    chosen = st.selectbox("选择内置病例", case_files, index=0)
    raw = st.text_area(
        "病例 JSON（可自由修改）",
        value=(CASE_DIR / chosen).read_text(encoding="utf-8"),
        height=420,
    )
    start = st.button("开始会诊", type="primary", use_container_width=True)

if start:
    try:
        case = Case.model_validate_json(raw).model_dump()
    except Exception as exc:
        st.error(f"病例格式有误：{exc}")
        st.stop()

    app = build_graph()
    report = None

    with st.status("MDT 会诊进行中…", expanded=True) as status:
        for chunk in app.stream({"case": case, "trace": []}, stream_mode="updates"):
            for node, update in chunk.items():
                label = AGENT_LABELS.get(node, node)
                for item in update.get("trace", []):
                    st.markdown(f"**{label}**")
                    st.text(item["content"])
                if node == "decision":
                    report = update.get("report")
        status.update(label="会诊完成", state="complete", expanded=False)

    if report:
        st.subheader("会诊结论")
        st.info(report.get("case_summary", ""))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**关键发现**")
            for finding in report.get("key_findings", []):
                st.markdown(f"- {finding}")
        with col2:
            st.markdown("**证据不足之处**")
            for item in report.get("uncertainties", []) or ["无"]:
                st.markdown(f"- {item}")

        st.markdown("**用药建议**")
        for rec in report.get("recommendations", []):
            with st.expander(f"{rec['drug']} · 靶点 {rec.get('target') or '未标注'} · 证据等级 {rec['evidence_level']}"):
                st.markdown(f"**机制**：{rec.get('mechanism', '')}")
                st.markdown(f"**依据**：{rec.get('rationale', '')}")
                if rec.get("references"):
                    st.markdown(f"**参考文献**：{', '.join(rec['references'])}")

        with st.expander("查看原始 JSON"):
            st.json(report)

        st.download_button(
            "下载报告 JSON",
            data=json.dumps(report, ensure_ascii=False, indent=2),
            file_name=f"{case['case_id']}_report.json",
            mime="application/json",
        )

st.divider()
st.caption(DISCLAIMER)
