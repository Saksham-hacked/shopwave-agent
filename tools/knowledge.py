import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base.md"
_kb_text: str = ""
_kb_sections: list = []

def init_knowledge_base():
    global _kb_text, _kb_sections
    with open(_KB_PATH, "r", encoding="utf-8") as f:
        _kb_text = f.read()
    _kb_sections = []
    current_title = "General"
    current_lines = []
    for line in _kb_text.splitlines():
        if line.startswith("## "):
            if current_lines:
                _kb_sections.append({"title": current_title, "content": "\n".join(current_lines)})
            current_title = line[3:].strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        _kb_sections.append({"title": current_title, "content": "\n".join(current_lines)})
    logger.info(f"Knowledge base loaded: {len(_kb_sections)} sections")


async def search_knowledge_base(query: str, state: dict) -> str:
    from datetime import datetime

    tool_call_entry = {
        "tool": "search_knowledge_base",
        "input": {"query": query},
        "output": None,
        "status": "success",
        "attempt": 1,
        "duration_ms": 0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    try:
        if not _kb_sections:
            result = _kb_text
            tool_call_entry["output"] = {"matched_sections": 0, "result_length": len(result)}
            state["tool_calls"].append(tool_call_entry)
            return result

        query_words = set(query.lower().split())
        scored = []
        for section in _kb_sections:
            section_words = set(section["content"].lower().split())
            score = len(query_words & section_words)
            scored.append((score, section))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_sections = [s for _, s in scored[:2] if scored[0][0] > 0]

        if not top_sections:
            result = _kb_text
        else:
            result = "\n\n---\n\n".join(s["content"] for s in top_sections)

        tool_call_entry["output"] = {
            "matched_sections": len(top_sections),
            "section_titles": [s["title"] for s in top_sections],
            "result_length": len(result),
        }
        state["tool_calls"].append(tool_call_entry)
        return result

    except Exception as e:
        logger.error(f"search_knowledge_base error: {e}")
        tool_call_entry["status"] = "error"
        tool_call_entry["output"] = {"error": str(e)}
        state["tool_calls"].append(tool_call_entry)
        return _kb_text
