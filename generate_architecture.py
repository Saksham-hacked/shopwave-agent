"""
generate_architecture.py
Run this script to produce architecture.png — a diagram of the ShopWave
autonomous support agent pipeline.

Usage:
    python generate_architecture.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Colour palette (dark theme) ───────────────────────────────────────────────
BG       = "#1a1a2e"
LAYER_BG = "#16213e"
NODE_CLR = "#0f3460"
NODE_EDGE = "#e94560"
ARROW    = "#e94560"
TEXT_CLR = "#eaeaea"
TOOL_CLR = "#533483"
FAULT_CLR = "#c84b31"
ACCENT   = "#e94560"

FIG_W, FIG_H = 18, 13

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")


def box(ax, x, y, w, h, label, sublabel="", color=NODE_CLR, edge=NODE_EDGE,
        fontsize=10, sublabel_fontsize=8, radius=0.3, bold=False):
    """Draw a rounded rectangle with a label (and optional sublabel)."""
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.05,rounding_size={radius}",
        linewidth=1.5,
        edgecolor=edge,
        facecolor=color,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    cy = y + h / 2 + (0.12 if sublabel else 0)
    ax.text(x + w / 2, cy, label, ha="center", va="center",
            color=TEXT_CLR, fontsize=fontsize, fontweight=weight)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.18, sublabel, ha="center", va="center",
                color="#aaaaaa", fontsize=sublabel_fontsize, style="italic")


def arrow(ax, x1, y1, x2, y2, label="", color=ARROW):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8),
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.05, my, label, color="#aaaaaa", fontsize=7, va="center")


def section_bg(ax, x, y, w, h, label, color=LAYER_BG, edge="#333355"):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.1,rounding_size=0.4",
        linewidth=1,
        edgecolor=edge,
        facecolor=color,
        zorder=0,
    )
    ax.add_patch(patch)
    ax.text(x + 0.15, y + h - 0.22, label, color="#888899",
            fontsize=8, va="top", style="italic")


# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(FIG_W / 2, 12.6, "ShopWave Autonomous Support Agent — Architecture",
        ha="center", va="center", color=TEXT_CLR, fontsize=14, fontweight="bold")

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Ticket Ingestion
# ══════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 11.4, 17.4, 1.0, "Ticket Ingestion Layer", edge="#445566")
box(ax, 1.0, 11.55, 3.5, 0.65, "tickets.json (20 tickets)",
    sublabel="data/tickets.json", color="#0d2137", edge="#4488aa", fontsize=9)
box(ax, 5.2, 11.55, 3.5, 0.65, "asyncio.gather()",
    sublabel="parallel dispatch", color="#0d2137", edge="#4488aa", fontsize=9)
box(ax, 9.4, 11.55, 3.5, 0.65, "asyncio.Semaphore(5)",
    sublabel="max 5 concurrent workers", color="#0d2137", edge="#4488aa", fontsize=9)
box(ax, 13.6, 11.55, 3.5, 0.65, "process_ticket(ticket)",
    sublabel="per-ticket coroutine", color="#0d2137", edge="#4488aa", fontsize=9)

arrow(ax, 4.5, 11.88, 5.2, 11.88)
arrow(ax, 8.7, 11.88, 9.4, 11.88)
arrow(ax, 12.9, 11.88, 13.6, 11.88)

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — LangGraph StateGraph
# ══════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 1.6, 10.8, 9.6, "LangGraph StateGraph", edge="#335533")

NODE_W = 4.8
NODE_H = 0.72
NX = 0.7  # left x of nodes
NX2 = NX + NODE_W + 0.3  # second column (conditional labels)

nodes = [
    ("Node 1", "classify_and_triage", "Gemini: classify → category/urgency/confidence", 9.9),
    ("Node 2", "fetch_context", "asyncio.gather: get_customer ‖ get_order → get_product", 8.85),
    ("Node 3", "tool_execution  (ReAct loop)", "Gemini plans tools → sequential execution", 7.8),
    ("Node 4", "decide_resolution  ◆", "Hard rules override + Gemini decision", 6.75),
    ("Node 5", "execute_resolution", "issue_refund / escalate / send_reply", 5.7),
    ("Node 6", "audit_logger", "Assemble audit_entry → audit_log.json", 4.65),
]

for title, name, sub, ny in nodes:
    box(ax, NX, ny, NODE_W, NODE_H, name, sublabel=sub,
        color=NODE_CLR, edge=NODE_EDGE, fontsize=9, sublabel_fontsize=7.5, bold=True)
    ax.text(NX - 0.05, ny + NODE_H / 2, title, color="#888888",
            fontsize=7, ha="right", va="center")

# Vertical arrows between nodes
for i in range(len(nodes) - 1):
    ny_bottom = nodes[i][3]
    ny_top_next = nodes[i + 1][3] + NODE_H
    arrow(ax, NX + NODE_W / 2, ny_bottom, NX + NODE_W / 2, ny_top_next)

# Conditional edge labels from Node 1 (social_engineering → skip to Node 4)
ax.annotate(
    "", xy=(NX + NODE_W / 2, 6.75 + NODE_H),
    xytext=(NX + NODE_W, 9.9 + NODE_H / 2),
    arrowprops=dict(arrowstyle="-|>", color="#ffaa00", lw=1.4,
                    connectionstyle="arc3,rad=0.35"),
)
ax.text(6.5, 8.7, "social_engineering\n→ skip to decide", color="#ffaa00",
        fontsize=7, ha="left", va="center")

# Conditional edge labels from Node 4 → Node 5
ax.text(NX + NODE_W / 2 + 0.15, 6.1, "resolved / escalated / clarify",
        color="#aaffaa", fontsize=7, ha="left", va="center")

# END node
box(ax, NX, 3.6, NODE_W, 0.65, "END", color="#0d1f0d", edge="#33aa33",
    fontsize=10, bold=True)
arrow(ax, NX + NODE_W / 2, 4.65, NX + NODE_W / 2, 4.25)
ax.text(NX - 0.05, 3.925, "→", color="#888888", fontsize=7, ha="right", va="center")

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — Tools panel (right side)
# ══════════════════════════════════════════════════════════════════════════════
section_bg(ax, 11.5, 1.6, 6.2, 7.5, "Tools (8)", color="#1e1a2e", edge="#553355")

tools = [
    ("get_customer(email)", "lookup.py"),
    ("get_order(order_id)", "lookup.py"),
    ("get_product(product_id)", "lookup.py"),
    ("search_knowledge_base(query)", "knowledge.py"),
    ("check_refund_eligibility(order_id)", "actions.py"),
    ("issue_refund(order_id, amount)", "actions.py"),
    ("send_reply(ticket_id, message)", "actions.py"),
    ("escalate(ticket_id, summary, priority)", "actions.py"),
    ("cancel_order(order_id)", "actions.py"),
]

tool_y_start = 8.6
tool_spacing = 0.73

for i, (tname, tfile) in enumerate(tools):
    ty = tool_y_start - i * tool_spacing
    box(ax, 11.8, ty, 5.6, 0.55, tname,
        sublabel=tfile, color=TOOL_CLR, edge="#aa44aa",
        fontsize=7.5, sublabel_fontsize=6.5)

# Fault injection wrapper label
box(ax, 11.8, 2.0, 5.6, 0.55,
    "⚡ fault_injection.py — call_with_retry()",
    sublabel="timeout / malformed / partial • 3 retries • exp backoff",
    color=FAULT_CLR, edge="#ff6633",
    fontsize=7.5, sublabel_fontsize=6.5)

# Arrow from tool_execution node to tools panel
arrow(ax, NX + NODE_W, 7.8 + NODE_H / 2, 11.8, 7.8 + NODE_H / 2,
      label="tool calls", color="#aa66ff")

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — State box
# ══════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 1.6, 0.0, 0.0, "")  # invisible placeholder

# TicketState label inside graph area (bottom left)
ax.text(0.5, 2.05,
        "TicketState (TypedDict)\n"
        "ticket · customer · order · product\n"
        "kb_results · tool_calls · reasoning_steps\n"
        "classification · confidence · confidence_trace\n"
        "resolution · reply_message · escalation_summary\n"
        "errors · refund_issued · audit_entry · policy_flags",
        color="#777799", fontsize=6.5, va="bottom", ha="left",
        fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#12122a", edgecolor="#334"))

# ── Footer ────────────────────────────────────────────────────────────────────
ax.text(FIG_W / 2, 0.3,
        "LangGraph + Google Gemini 2.5 Flash + FastAPI  |  asyncio.Semaphore(5)  |  audit_log.json",
        ha="center", va="center", color="#555577", fontsize=8)

plt.tight_layout(pad=0.2)
plt.savefig("architecture.png", dpi=150, bbox_inches="tight", facecolor=BG)
print("architecture.png saved.")
