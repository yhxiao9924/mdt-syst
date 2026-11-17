"""PubMed 文献检索工具（NCBI E-utilities，免费无需 key）。"""

import time

import requests

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
TIMEOUT = 15
RETRIES = 2


def _get_json(url: str, params: dict) -> dict:
    """带重试的 GET：NCBI 偶发超时，一次失败就放弃会让文献 Agent 静默失效。"""
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < RETRIES - 1:
                time.sleep(1 + attempt)
    raise last_error  # type: ignore[misc]


def search_pubmed(query: str, max_results: int = 3) -> list[dict]:
    """检索文献，返回 PMID、标题、期刊、发表日期。

    Args:
        query: 检索式，例如 "EGFR L858R osimertinib resistance"
        max_results: 返回条数，建议 1-5
    """
    try:
        data = _get_json(
            ESEARCH,
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max_results,
                "sort": "relevance",
            },
        )
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return [{"status": "not_found", "message": f"未检索到与 {query} 相关的文献"}]

        result = _get_json(
            ESUMMARY, {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        ).get("result", {})

        papers = []
        for pmid in ids:
            item = result.get(pmid, {})
            papers.append(
                {
                    "pmid": pmid,
                    "title": item.get("title", ""),
                    "journal": item.get("fulljournalname", ""),
                    "pubdate": item.get("pubdate", ""),
                }
            )
        return papers
    except Exception as exc:
        return [{"status": "error", "message": f"PubMed 查询失败: {exc}"}]


SEARCH_PUBMED_SPEC = {
    "type": "function",
    "function": {
        "name": "search_pubmed",
        "description": "在 PubMed 检索生物医学文献，返回 PMID、标题、期刊和发表日期",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "英文检索式，例如 EGFR L858R osimertinib"},
                "max_results": {"type": "integer", "description": "返回条数，1-5"},
            },
            "required": ["query"],
        },
    },
}
