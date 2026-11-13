"""PubMed 文献检索工具（NCBI E-utilities，免费无需 key）。"""

import requests

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
TIMEOUT = 15


def search_pubmed(query: str, max_results: int = 3) -> list[dict]:
    """检索文献，返回 PMID、标题、期刊、发表日期。

    Args:
        query: 检索式，例如 "EGFR L858R osimertinib resistance"
        max_results: 返回条数，建议 1-5
    """
    try:
        r = requests.get(
            ESEARCH,
            params={
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max_results,
                "sort": "relevance",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return [{"status": "not_found", "message": f"未检索到与 {query} 相关的文献"}]

        s = requests.get(
            ESUMMARY,
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            timeout=TIMEOUT,
        )
        s.raise_for_status()
        result = s.json().get("result", {})

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
