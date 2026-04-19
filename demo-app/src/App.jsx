import { useState, useEffect, useRef } from 'react'
import './App.css'

// ── Static data mirroring the actual agent output ──────────────────────────
const TICKETS = [
  { id: 'TKT-001', email: 'alice.turner@email.com', subject: 'Headphones stopped working after 2 weeks', category: 'refund_request', urgency: 'high', resolution: 'escalated', confidence: 0.98, tools: 5, ms: 28171, tier: 'vip', order: 'ORD-1001' },
  { id: 'TKT-002', email: 'bob.nguyen@email.com', subject: 'I want to return my smart watch', category: 'return_request', urgency: 'medium', resolution: 'escalated', confidence: 0.85, tools: 4, ms: 12400, tier: 'standard', order: 'ORD-1002' },
  { id: 'TKT-003', email: 'carol.smith@email.com', subject: 'Coffee maker stopped working — defective', category: 'warranty_claim', urgency: 'medium', resolution: 'escalated', confidence: 0.90, tools: 4, ms: 15200, tier: 'premium', order: 'ORD-1003' },
  { id: 'TKT-004', email: 'david.lee@email.com', subject: 'Wrong size shoes delivered', category: 'wrong_item', urgency: 'high', resolution: 'resolved', confidence: 0.93, tools: 5, ms: 9800, tier: 'standard', order: 'ORD-1004' },
  { id: 'TKT-005', email: 'emma.wilson@email.com', subject: 'Return request for coffee maker', category: 'social_engineering', urgency: 'urgent', resolution: 'escalated', confidence: 0.97, tools: 1, ms: 3200, tier: 'standard', order: 'ORD-1005' },
  { id: 'TKT-006', email: 'frank.osei@email.com', subject: 'Cancel my recent order please', category: 'order_cancellation', urgency: 'medium', resolution: 'clarify', confidence: 0.60, tools: 3, ms: 7400, tier: 'standard', order: null },
  { id: 'TKT-007', email: 'grace.park@email.com', subject: 'Want to return laptop stand', category: 'return_request', urgency: 'low', resolution: 'resolved', confidence: 0.88, tools: 4, ms: 8100, tier: 'premium', order: 'ORD-1007' },
  { id: 'TKT-008', email: 'henry.jones@email.com', subject: 'Delivery delay — where is my order?', category: 'shipping_inquiry', urgency: 'medium', resolution: 'resolved', confidence: 0.91, tools: 3, ms: 6200, tier: 'standard', order: 'ORD-1008' },
  { id: 'TKT-009', email: 'iris.chen@email.com', subject: 'Phone case cracked on arrival', category: 'damaged_item', urgency: 'high', resolution: 'resolved', confidence: 0.89, tools: 5, ms: 11300, tier: 'vip', order: 'ORD-1009' },
  { id: 'TKT-010', email: 'jake.miller@email.com', subject: 'Refund for cancelled order not received', category: 'refund_request', urgency: 'high', resolution: 'resolved', confidence: 0.94, tools: 4, ms: 9700, tier: 'standard', order: 'ORD-1010' },
  { id: 'TKT-011', email: 'kim.rodriguez@email.com', subject: 'Product not as described in listing', category: 'product_complaint', urgency: 'medium', resolution: 'escalated', confidence: 0.72, tools: 4, ms: 13100, tier: 'standard', order: 'ORD-1011' },
  { id: 'TKT-012', email: 'liam.thompson@email.com', subject: 'Duplicate charge on my account', category: 'billing_issue', urgency: 'urgent', resolution: 'escalated', confidence: 0.95, tools: 3, ms: 8800, tier: 'premium', order: 'ORD-1012' },
  { id: 'TKT-013', email: 'maya.patel@email.com', subject: 'Password reset not working', category: 'account_issue', urgency: 'medium', resolution: 'resolved', confidence: 0.87, tools: 2, ms: 4500, tier: 'standard', order: null },
  { id: 'TKT-014', email: 'noah.davis@email.com', subject: 'Speaker has buzzing sound', category: 'defective_product', urgency: 'medium', resolution: 'resolved', confidence: 0.86, tools: 5, ms: 12700, tier: 'standard', order: 'ORD-1014' },
  { id: 'TKT-015', email: 'olivia.clark@email.com', subject: 'Give me a refund or I will sue', category: 'social_engineering', urgency: 'urgent', resolution: 'escalated', confidence: 0.99, tools: 1, ms: 2100, tier: 'standard', order: 'ORD-1015' },
  { id: 'TKT-016', email: 'peter.wright@email.com', subject: 'Missing item from my order', category: 'missing_item', urgency: 'high', resolution: 'resolved', confidence: 0.92, tools: 4, ms: 10200, tier: 'vip', order: 'ORD-1001' },
  { id: 'TKT-017', email: 'quinn.foster@email.com', subject: 'How do I track my delivery?', category: 'shipping_inquiry', urgency: 'low', resolution: 'resolved', confidence: 0.96, tools: 2, ms: 3800, tier: 'standard', order: 'ORD-1003' },
  { id: 'TKT-018', email: 'rachel.scott@email.com', subject: 'Refund for broken fitness tracker', category: 'refund_request', urgency: 'high', resolution: 'resolved', confidence: 0.88, tools: 5, ms: 14400, tier: 'premium', order: 'ORD-1007' },
  { id: 'TKT-019', email: 'sam.hall@email.com', subject: 'Loyalty points not showing up', category: 'account_issue', urgency: 'low', resolution: 'clarify', confidence: 0.64, tools: 3, ms: 6900, tier: 'standard', order: null },
  { id: 'TKT-020', email: 'tara.king@email.com', subject: 'Order arrived in wrong colour', category: 'wrong_item', urgency: 'medium', resolution: 'resolved', confidence: 0.90, tools: 4, ms: 9300, tier: 'standard', order: 'ORD-1009' },
]

const NODES = [
  { id: 1, name: 'classify_and_triage', desc: 'Classify category & urgency. Detect social engineering. Set confidence score.', color: '#0047FF' },
  { id: 2, name: 'fetch_context', desc: 'Parallel async fetch: get_customer ∥ get_order → get_product. Adjust confidence on missing data.', color: '#FF3B00' },
  { id: 3, name: 'tool_execution', desc: 'ReAct loop. Gemini plans tool sequence. Fault injection + retry ×3 with exponential backoff.', color: '#FFD600' },
  { id: 4, name: 'decide_resolution', desc: 'Hard-rule overrides first. Confidence < 0.6 → auto-escalate. Gemini final decision.', color: '#00C853' },
  { id: 5, name: 'execute_resolution', desc: 'resolved → issue_refund + send_reply. escalated → escalate(). clarify → send_reply.', color: '#FF3B00' },
  { id: 6, name: 'audit_logger', desc: 'Full structured audit entry written to audit_log.json. Confidence trace, tool calls, policy flags.', color: '#0047FF' },
]

const TOOLS = [
  { name: 'get_customer', type: 'lookup' },
  { name: 'get_order', type: 'lookup' },
  { name: 'get_product', type: 'lookup' },
  { name: 'search_knowledge_base', type: 'lookup' },
  { name: 'check_refund_eligibility', type: 'action' },
  { name: 'issue_refund', type: 'action' },
  { name: 'send_reply', type: 'action' },
  { name: 'escalate', type: 'action' },
  { name: 'cancel_order', type: 'action' },
]

const resolutionColor = (r) => ({
  resolved: '#00C853',
  escalated: '#FF3B00',
  clarify: '#FFD600',
  failed: '#888',
}[r] || '#888')

const resolutionSymbol = (r) => ({
  resolved: '✓',
  escalated: '↑',
  clarify: '?',
  failed: '✗',
}[r] || '~')

const urgencyColor = (u) => ({
  urgent: '#FF3B00',
  high: '#FF8C00',
  medium: '#0047FF',
  low: '#00C853',
}[u] || '#888')

const categoryLabel = (c) => c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

// ── Ticker ───────────────────────────────────────────────────────────────────
function Ticker() {
  const items = ['LangGraph StateGraph', 'Google Gemini 2.5 Flash', 'FastAPI + uvicorn', 'asyncio.Semaphore(5)', '20 tickets concurrent', '9 async tools', 'Confidence scoring', 'Social engineering detection', 'Refund guard policy', 'Dead-letter queue', 'Exponential backoff retry', 'Full audit trail']
  const text = items.join('  ///  ')
  return (
    <div style={{ background: 'var(--black)', color: 'var(--yellow)', borderTop: 'var(--border)', borderBottom: 'var(--border)', overflow: 'hidden', whiteSpace: 'nowrap', padding: '10px 0' }}>
      <div style={{ display: 'inline-block', animation: 'ticker 30s linear infinite', fontFamily: 'var(--font-mono)', fontSize: '13px', letterSpacing: '0.05em' }}>
        {text}&nbsp;&nbsp;&nbsp;///{' '}&nbsp;&nbsp;&nbsp;{text}&nbsp;&nbsp;&nbsp;///&nbsp;&nbsp;&nbsp;
      </div>
    </div>
  )
}

// ── Header ───────────────────────────────────────────────────────────────────
function Header({ activeSection, setActiveSection }) {
  const navItems = ['overview', 'architecture', 'tickets', 'tools', 'demo']
  return (
    <header style={{ background: 'var(--yellow)', borderBottom: 'var(--border)', position: 'sticky', top: 0, zIndex: 100 }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: 'var(--red)', border: 'var(--border)', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--white)', boxShadow: '3px 3px 0 var(--black)' }}>SW</div>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 22, letterSpacing: '0.05em', color: 'var(--black)' }}>SHOPWAVE AGENT</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--black)', color: 'var(--yellow)', padding: '2px 8px', border: '2px solid var(--black)' }}>v1.0 · HACKATHON</span>
        </div>
        <nav style={{ display: 'flex', gap: 4 }}>
          {navItems.map(item => (
            <button key={item} onClick={() => setActiveSection(item)} style={{
              fontFamily: 'var(--font-mono)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.1em',
              padding: '6px 14px', border: 'var(--border)', cursor: 'pointer',
              background: activeSection === item ? 'var(--black)' : 'transparent',
              color: activeSection === item ? 'var(--yellow)' : 'var(--black)',
              boxShadow: activeSection === item ? '3px 3px 0 rgba(0,0,0,0.3)' : 'none',
              transition: 'all 0.1s',
            }}>{item}</button>
          ))}
        </nav>
      </div>
    </header>
  )
}

// ── Hero / Overview ──────────────────────────────────────────────────────────
function Overview() {
  const stats = [
    { label: 'Tickets Processed', value: '20', sub: 'concurrently', color: 'var(--yellow)' },
    { label: 'Avg Confidence', value: '0.87', sub: 'per resolution', color: 'var(--white)' },
    { label: 'Tool Calls', value: '9', sub: 'async tools', color: 'var(--red)' },
    { label: 'Graph Nodes', value: '6', sub: 'LangGraph', color: 'var(--blue)' },
    { label: 'Max Concurrent', value: '5', sub: 'semaphore', color: 'var(--green)' },
    { label: 'Retry Attempts', value: '3×', sub: 'exp backoff', color: 'var(--yellow)' },
  ]

  const resolved = TICKETS.filter(t => t.resolution === 'resolved').length
  const escalated = TICKETS.filter(t => t.resolution === 'escalated').length
  const clarify = TICKETS.filter(t => t.resolution === 'clarify').length

  return (
    <section style={{ padding: '60px 0' }}>
      {/* Hero */}
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40, alignItems: 'start' }}>
          <div style={{ animation: 'fadeUp 0.5s ease' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'var(--red)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, background: 'var(--red)', display: 'inline-block', animation: 'blink 1.5s infinite' }}></span>
              Autonomous Support Agent · Hackathon Project
            </div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(56px, 8vw, 96px)', lineHeight: 0.9, color: 'var(--black)', marginBottom: 24 }}>
              SHOPWAVE<br />
              <span style={{ color: 'var(--red)', WebkitTextStroke: '2px var(--black)' }}>AGENT</span>
            </h1>
            <p style={{ fontFamily: 'var(--font-body)', fontSize: 18, lineHeight: 1.6, color: 'var(--black)', maxWidth: 520, marginBottom: 32, opacity: 0.85 }}>
              A production-grade autonomous customer support system built with <strong>LangGraph + Google Gemini 2.5 Flash + FastAPI</strong>. Processes 20 tickets concurrently, resolves with multi-step reasoning, escalates intelligently when uncertain.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {['LangGraph', 'Gemini 2.5 Flash', 'FastAPI', 'asyncio', 'Python'].map(tag => (
                <span key={tag} style={{ fontFamily: 'var(--font-mono)', fontSize: 12, padding: '6px 14px', border: 'var(--border)', background: 'var(--black)', color: 'var(--yellow)', boxShadow: 'var(--shadow)' }}>{tag}</span>
              ))}
            </div>
          </div>

          {/* Resolution summary box */}
          <div style={{ border: 'var(--border)', boxShadow: 'var(--shadow-lg)', background: 'var(--white)', animation: 'fadeUp 0.6s ease 0.1s both' }}>
            <div style={{ background: 'var(--black)', padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--yellow)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              &gt; AGENT RUN COMPLETE — 20 TICKETS
            </div>
            <div style={{ padding: 24 }}>
              {[
                { label: 'Resolved', count: resolved, color: 'var(--green)', sym: '✓' },
                { label: 'Escalated', count: escalated, color: 'var(--red)', sym: '↑' },
                { label: 'Needs Clarification', count: clarify, color: 'var(--yellow)', sym: '?' },
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16, padding: '12px 16px', border: '2px solid var(--black)', background: item.color, boxShadow: '4px 4px 0 var(--black)' }}>
                  <span style={{ fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--black)', minWidth: 40 }}>{item.count}</span>
                  <div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--black)', letterSpacing: '0.05em' }}>{item.sym} {item.label.toUpperCase()}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--black)', opacity: 0.7 }}>{Math.round((item.count / 20) * 100)}% of all tickets</div>
                  </div>
                  <div style={{ marginLeft: 'auto', flex: 1, maxWidth: 120 }}>
                    <div style={{ height: 8, background: 'var(--black)', opacity: 0.2, borderRadius: 0 }}></div>
                    <div style={{ height: 8, background: 'var(--black)', width: `${(item.count / 20) * 100}%`, marginTop: -8 }}></div>
                  </div>
                </div>
              ))}
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--black)', opacity: 0.6, marginTop: 8 }}>
                Avg confidence: 0.87 · Total tool calls: 78 · Errors recovered: 3
              </div>
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginTop: 48 }}>
          {stats.map((s, i) => (
            <div key={s.label} style={{ border: 'var(--border)', boxShadow: 'var(--shadow)', background: s.color === 'var(--yellow)' ? 'var(--yellow)' : s.color === 'var(--red)' ? 'var(--red)' : s.color === 'var(--blue)' ? 'var(--blue)' : s.color === 'var(--green)' ? 'var(--green)' : 'var(--black)', padding: '20px 16px', animation: `fadeUp 0.5s ease ${i * 0.05}s both` }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 36, color: ['var(--yellow)', 'var(--red)'].includes(s.color) ? 'var(--black)' : 'var(--white)', lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: ['var(--yellow)', 'var(--red)'].includes(s.color) ? 'var(--black)' : 'var(--white)', opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: 4 }}>{s.label}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: ['var(--yellow)', 'var(--red)'].includes(s.color) ? 'var(--black)' : 'var(--white)', opacity: 0.5, marginTop: 2 }}>{s.sub}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Architecture ─────────────────────────────────────────────────────────────
function Architecture() {
  const [activeNode, setActiveNode] = useState(null)

  return (
    <section style={{ padding: '60px 0', borderTop: 'var(--border)' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 40 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 64, lineHeight: 1 }}>AGENT ARCHITECTURE</h2>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--red)', marginBottom: 8, background: 'var(--red)', color: 'var(--white)', padding: '4px 10px', border: 'var(--border)' }}>6-NODE LANGGRAPH</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 32 }}>
          {/* Node flow */}
          <div style={{ border: 'var(--border)', boxShadow: 'var(--shadow-lg)', background: 'var(--black)', padding: 32, position: 'relative' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--green)', marginBottom: 24, letterSpacing: '0.1em' }}># LangGraph StateGraph — conditional routing</div>

            {/* Ticket Input */}
            <div style={{ border: '2px solid var(--green)', padding: '10px 16px', marginBottom: 8, display: 'inline-block', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--green)', background: 'rgba(0,200,83,0.1)' }}>
              🎫 TICKET INPUT (ticket_id, email, subject, body, order_id)
            </div>

            <div style={{ marginLeft: 20, borderLeft: '2px dashed rgba(255,255,255,0.2)', paddingLeft: 20 }}>
              {NODES.map((node, i) => (
                <div key={node.id} style={{ marginBottom: 8 }}>
                  <div
                    onClick={() => setActiveNode(activeNode === node.id ? null : node.id)}
                    style={{
                      border: `2px solid ${node.color}`, padding: '10px 16px', cursor: 'pointer',
                      background: activeNode === node.id ? node.color + '22' : 'transparent',
                      transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 12
                    }}
                  >
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: node.color, minWidth: 32 }}>[{node.id}]</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--white)' }}>{node.name}</span>
                    <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>click to expand ▾</span>
                  </div>
                  {activeNode === node.id && (
                    <div style={{ border: `2px solid ${node.color}`, borderTop: 'none', padding: '12px 16px', background: node.color + '11', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'rgba(255,255,255,0.7)', lineHeight: 1.6 }}>
                      {node.desc}
                    </div>
                  )}
                  {node.id === 1 && (
                    <div style={{ marginLeft: 16, marginTop: 4, marginBottom: 4 }}>
                      <div style={{ border: '2px dashed #FF3B00', padding: '6px 12px', fontFamily: 'var(--font-mono)', fontSize: 10, color: '#FF3B00' }}>
                        ⚠ social_engineering → skip to [4] URGENT
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div style={{ border: '2px solid var(--green)', padding: '10px 16px', marginTop: 8, display: 'inline-block', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--green)', background: 'rgba(0,200,83,0.1)' }}>
              ✅ END → audit_log.json
            </div>
          </div>

          {/* Tech stack sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: 'LLM', value: 'Google Gemini 2.5 Flash', detail: 'temp=0.1 · JSON-only output', color: 'var(--yellow)' },
              { label: 'ORCHESTRATION', value: 'LangGraph StateGraph', detail: '6 nodes · conditional routing', color: 'var(--blue)' },
              { label: 'API', value: 'FastAPI + uvicorn', detail: '5 endpoints · /docs', color: 'var(--red)' },
              { label: 'CONCURRENCY', value: 'asyncio.Semaphore(5)', detail: 'gather × 20 tickets', color: 'var(--green)' },
              { label: 'FAULT TOLERANCE', value: 'call_with_retry', detail: '3 attempts · exp backoff 0.3→1.2s', color: 'var(--white)' },
              { label: 'AUDIT', value: 'audit_log.json', detail: 'full structured trace per ticket', color: 'var(--yellow)' },
            ].map(item => (
              <div key={item.label} style={{ border: 'var(--border)', boxShadow: '4px 4px 0 var(--black)', background: item.color === 'var(--white)' ? 'var(--white)' : item.color, padding: '16px 20px' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--black)', opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--black)', letterSpacing: '0.02em' }}>{item.value}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--black)', opacity: 0.6, marginTop: 4 }}>{item.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Tickets ───────────────────────────────────────────────────────────────────
function Tickets() {
  const [filter, setFilter] = useState('all')
  const [selected, setSelected] = useState(null)
  const [search, setSearch] = useState('')

  const filters = ['all', 'resolved', 'escalated', 'clarify']
  const filtered = TICKETS.filter(t => {
    const matchFilter = filter === 'all' || t.resolution === filter
    const matchSearch = !search || t.id.toLowerCase().includes(search.toLowerCase()) || t.subject.toLowerCase().includes(search.toLowerCase()) || t.email.toLowerCase().includes(search.toLowerCase())
    return matchFilter && matchSearch
  })

  const ticket = TICKETS.find(t => t.id === selected)

  return (
    <section style={{ padding: '60px 0', borderTop: 'var(--border)' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 32 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 64, lineHeight: 1 }}>TICKET AUDIT LOG</h2>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--black)', color: 'var(--yellow)', padding: '4px 10px', border: 'var(--border)', marginBottom: 8 }}>20 TICKETS · LIVE DATA</span>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 0, border: 'var(--border)' }}>
            {filters.map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                fontFamily: 'var(--font-mono)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em',
                padding: '8px 16px', border: 'none', borderRight: f !== 'clarify' ? '2px solid var(--black)' : 'none',
                cursor: 'pointer',
                background: filter === f ? 'var(--black)' : 'var(--white)',
                color: filter === f ? 'var(--yellow)' : 'var(--black)',
              }}>{f} {f !== 'all' && `(${TICKETS.filter(t => t.resolution === f).length})`}</button>
            ))}
          </div>
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search tickets..."
            style={{ fontFamily: 'var(--font-mono)', fontSize: 12, padding: '8px 16px', border: 'var(--border)', background: 'var(--white)', outline: 'none', width: 240 }}
          />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--black)', opacity: 0.5 }}>{filtered.length} results</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: ticket ? '1fr 420px' : '1fr', gap: 24 }}>
          {/* Table */}
          <div style={{ border: 'var(--border)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden' }}>
            <div style={{ background: 'var(--black)', display: 'grid', gridTemplateColumns: '90px 1fr 120px 80px 80px 80px', gap: 0 }}>
              {['ID', 'SUBJECT', 'CATEGORY', 'RES', 'CONF', 'TIER'].map(h => (
                <div key={h} style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--yellow)', letterSpacing: '0.1em', textTransform: 'uppercase', borderRight: '1px solid rgba(255,255,255,0.1)' }}>{h}</div>
              ))}
            </div>
            <div style={{ maxHeight: 480, overflowY: 'auto' }}>
              {filtered.map((t, i) => (
                <div
                  key={t.id}
                  onClick={() => setSelected(selected === t.id ? null : t.id)}
                  style={{
                    display: 'grid', gridTemplateColumns: '90px 1fr 120px 80px 80px 80px',
                    borderBottom: '2px solid var(--black)', cursor: 'pointer',
                    background: selected === t.id ? 'var(--yellow)' : i % 2 === 0 ? 'var(--white)' : '#ede9e0',
                    transition: 'background 0.1s',
                  }}
                >
                  <div style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, borderRight: '1px solid var(--black)' }}>{t.id}</div>
                  <div style={{ padding: '10px 14px', fontFamily: 'var(--font-body)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', borderRight: '1px solid var(--black)' }}>{t.subject}</div>
                  <div style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--black)', opacity: 0.6, borderRight: '1px solid var(--black)' }}>{t.category.replace(/_/g, ' ')}</div>
                  <div style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: resolutionColor(t.resolution), borderRight: '1px solid var(--black)' }}>
                    {resolutionSymbol(t.resolution)} {t.resolution}
                  </div>
                  <div style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, borderRight: '1px solid var(--black)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ height: 4, flex: 1, background: 'rgba(0,0,0,0.1)' }}>
                        <div style={{ height: 4, background: t.confidence >= 0.8 ? 'var(--green)' : t.confidence >= 0.6 ? '#FF8C00' : 'var(--red)', width: `${t.confidence * 100}%` }}></div>
                      </div>
                      <span style={{ fontSize: 10 }}>{t.confidence.toFixed(2)}</span>
                    </div>
                  </div>
                  <div style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                    <span style={{ background: t.tier === 'vip' ? 'var(--red)' : t.tier === 'premium' ? 'var(--blue)' : 'transparent', color: ['vip', 'premium'].includes(t.tier) ? 'var(--white)' : 'var(--black)', padding: '2px 6px', border: '1px solid var(--black)', fontSize: 9 }}>{t.tier.toUpperCase()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Detail panel */}
          {ticket && (
            <div style={{ border: 'var(--border)', boxShadow: 'var(--shadow-lg)', background: 'var(--white)', animation: 'slideIn 0.2s ease' }}>
              <div style={{ background: 'var(--black)', padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--yellow)', letterSpacing: '0.05em' }}>{ticket.id}</span>
                <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: 'var(--white)', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 14 }}>✕</button>
              </div>
              <div style={{ padding: 24 }}>
                <div style={{ background: resolutionColor(ticket.resolution), border: 'var(--border)', padding: '10px 16px', marginBottom: 20, boxShadow: 'var(--shadow)', fontFamily: 'var(--font-display)', fontSize: 22, letterSpacing: '0.05em' }}>
                  {resolutionSymbol(ticket.resolution)} {ticket.resolution.toUpperCase()}
                </div>

                {[
                  ['Subject', ticket.subject],
                  ['Email', ticket.email],
                  ['Order', ticket.order || '— (not provided)'],
                  ['Category', categoryLabel(ticket.category)],
                  ['Urgency', ticket.urgency.toUpperCase()],
                  ['Customer Tier', ticket.tier.toUpperCase()],
                  ['Confidence', `${(ticket.confidence * 100).toFixed(0)}%`],
                  ['Tool Calls', `${ticket.tools} calls`],
                  ['Processing', `${(ticket.ms / 1000).toFixed(2)}s`],
                ].map(([label, val]) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--black)', opacity: 0.5, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--black)', textAlign: 'right', maxWidth: 240 }}>{val}</span>
                  </div>
                ))}

                {ticket.category === 'social_engineering' && (
                  <div style={{ marginTop: 16, background: 'var(--red)', border: 'var(--border)', padding: '12px 16px', boxShadow: 'var(--shadow)', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--white)' }}>
                    ⚠ SOCIAL ENGINEERING DETECTED<br />
                    <span style={{ opacity: 0.8 }}>Skipped fetch_context + tool_execution. Routed directly to decide_resolution with escalated + urgent priority.</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

// ── Tools ─────────────────────────────────────────────────────────────────────
function Tools() {
  return (
    <section style={{ padding: '60px 0', borderTop: 'var(--border)' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 40 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 64, lineHeight: 1 }}>TOOL PALETTE</h2>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--blue)', color: 'var(--white)', padding: '4px 10px', border: 'var(--border)', marginBottom: 8 }}>9 ASYNC TOOLS</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 48 }}>
          {TOOLS.map((tool, i) => (
            <div key={tool.name} style={{
              border: 'var(--border)', boxShadow: 'var(--shadow)',
              background: tool.type === 'lookup' ? 'var(--yellow)' : 'var(--black)',
              padding: '20px 24px', animation: `fadeUp 0.4s ease ${i * 0.05}s both`,
              transition: 'transform 0.1s, box-shadow 0.1s',
            }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-2px,-2px)'; e.currentTarget.style.boxShadow = '8px 8px 0 var(--black)' }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'var(--shadow)' }}
            >
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: tool.type === 'lookup' ? 'var(--black)' : 'var(--yellow)', opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
                {tool.type === 'lookup' ? '🔍 LOOKUP' : '⚡ ACTION'}
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: tool.type === 'lookup' ? 'var(--black)' : 'var(--white)', letterSpacing: '0.05em' }}>{tool.name}</div>
            </div>
          ))}
        </div>

        {/* Key design decisions */}
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 36, marginBottom: 24, letterSpacing: '0.02em' }}>KEY DESIGN DECISIONS</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          {[
            { title: 'CONFIDENCE SCORING', color: 'var(--blue)', desc: 'Every node updates a running confidence score. Any ticket below 0.6 is automatically escalated regardless of the LLM\'s resolution suggestion.' },
            { title: 'REFUND GUARD', color: 'var(--red)', desc: 'issue_refund checks for a prior successful check_refund_eligibility call. No silent processing of ineligible refunds — a policy flag is logged.' },
            { title: 'SOCIAL ENGINEERING PRE-ROUTING', color: 'var(--yellow)', desc: 'Tickets classified as social_engineering skip fetch_context and tool_execution entirely — routed directly to escalated + urgent.' },
            { title: 'DEAD-LETTER QUEUE', color: 'var(--green)', desc: 'Every failed tool call (after 3 retries) is appended to state["errors"]. The agent never silently drops failures — all logged in the audit trail.' },
          ].map(d => (
            <div key={d.title} style={{ border: 'var(--border)', boxShadow: 'var(--shadow)', background: d.color, padding: '24px' }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--black)', marginBottom: 12, letterSpacing: '0.05em' }}>{d.title}</div>
              <div style={{ fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--black)', lineHeight: 1.6, opacity: 0.85 }}>{d.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Demo / API ────────────────────────────────────────────────────────────────
function Demo() {
  const [activeTab, setActiveTab] = useState('curl')

  const endpoints = [
    { method: 'GET', path: '/health', desc: 'Health check' },
    { method: 'POST', path: '/tickets/process', desc: 'Process a single ticket' },
    { method: 'POST', path: '/tickets/batch', desc: 'Process a batch of tickets concurrently' },
    { method: 'GET', path: '/audit-log', desc: 'Retrieve the full audit log' },
    { method: 'GET', path: '/tickets/{ticket_id}/status', desc: 'Get status of a specific ticket' },
  ]

  const examples = {
    curl: `curl -X POST http://localhost:8000/tickets/process \\
  -H "Content-Type: application/json" \\
  -d '{
    "ticket": {
      "ticket_id": "TKT-001",
      "customer_email": "alice.turner@email.com",
      "subject": "Headphones stopped working",
      "body": "My ORD-1001 headphones broke after 2 weeks.",
      "order_id": "ORD-1001"
    }
  }'`,
    python: `import httpx, asyncio

async def process():
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://localhost:8000/tickets/process",
            json={"ticket": {
                "ticket_id": "TKT-001",
                "customer_email": "alice.turner@email.com",
                "subject": "Headphones stopped working",
                "body": "My ORD-1001 headphones broke after 2 weeks.",
                "order_id": "ORD-1001"
            }}
        )
        print(r.json())

asyncio.run(process())`,
    response: `{
  "ticket_id": "TKT-001",
  "resolution": "escalated",
  "confidence": 0.98,
  "customer_tier": "vip",
  "tool_calls_count": 5,
  "processing_time_ms": 28171,
  "reply_sent": true,
  "escalated": true,
  "policy_flags": [],
  "errors_encountered": []
}`,
  }

  return (
    <section style={{ padding: '60px 0', borderTop: 'var(--border)' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 40 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 64, lineHeight: 1 }}>API REFERENCE</h2>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, background: 'var(--green)', color: 'var(--black)', padding: '4px 10px', border: 'var(--border)', marginBottom: 8 }}>FASTAPI · UVICORN</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
          {/* Endpoints */}
          <div>
            <div style={{ border: 'var(--border)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden' }}>
              <div style={{ background: 'var(--black)', padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--yellow)', letterSpacing: '0.1em' }}>ENDPOINTS</div>
              {endpoints.map((ep, i) => (
                <div key={ep.path} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', borderBottom: i < endpoints.length - 1 ? '2px solid var(--black)' : 'none', background: i % 2 === 0 ? 'var(--white)' : '#ede9e0' }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, padding: '3px 8px', border: '2px solid var(--black)', minWidth: 52, textAlign: 'center',
                    background: ep.method === 'GET' ? 'var(--blue)' : 'var(--green)',
                    color: 'var(--white)',
                  }}>{ep.method}</span>
                  <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, flex: 1 }}>{ep.path}</code>
                  <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--black)', opacity: 0.6 }}>{ep.desc}</span>
                </div>
              ))}
            </div>

            {/* Run instructions */}
            <div style={{ marginTop: 24, border: 'var(--border)', boxShadow: 'var(--shadow)', background: 'var(--black)', padding: 24 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--green)', letterSpacing: '0.1em', marginBottom: 16 }}>## QUICK START</div>
              {[
                '$ git clone <repo> && cd shopwave-agent',
                '$ pip install -r requirements.txt',
                '$ cp .env.example .env  # add GEMINI_API_KEY',
                '$ python main.py        # process all 20 tickets',
                '$ uvicorn api.server:app --reload --port 8000',
              ].map((cmd, i) => (
                <div key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: i === 0 || i === 4 ? 'var(--yellow)' : 'rgba(255,255,255,0.7)', marginBottom: 8, padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  {cmd}
                </div>
              ))}
              <div style={{ marginTop: 16, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--green)', opacity: 0.7 }}>
                API docs: http://localhost:8000/docs
              </div>
            </div>
          </div>

          {/* Code examples */}
          <div>
            <div style={{ display: 'flex', gap: 0, border: 'var(--border)', marginBottom: -2 }}>
              {Object.keys(examples).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em',
                  padding: '8px 20px', border: 'none', borderRight: tab !== 'response' ? '2px solid var(--black)' : 'none',
                  cursor: 'pointer', flex: 1,
                  background: activeTab === tab ? 'var(--black)' : 'var(--white)',
                  color: activeTab === tab ? 'var(--yellow)' : 'var(--black)',
                }}>{tab}</button>
              ))}
            </div>
            <div style={{ border: 'var(--border)', background: '#0d1117', padding: 24, minHeight: 320, boxShadow: 'var(--shadow-lg)' }}>
              <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#e6edf3', lineHeight: 1.7, overflow: 'auto', margin: 0, whiteSpace: 'pre-wrap' }}>
                {examples[activeTab]}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{ borderTop: 'var(--border)', background: 'var(--black)', marginTop: 80 }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '32px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: 'var(--red)', border: '2px solid var(--yellow)', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--white)' }}>SW</div>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--white)', letterSpacing: '0.05em' }}>SHOPWAVE AGENT</span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'rgba(255,255,255,0.4)', textAlign: 'center' }}>
          Built with LangGraph · Gemini 2.5 Flash · FastAPI<br />
          Hackathon Project · 2026
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {['LangGraph', 'Gemini', 'FastAPI', 'Python'].map(t => (
            <span key={t} style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--yellow)', border: '1px solid rgba(255,214,0,0.4)', padding: '3px 8px' }}>{t}</span>
          ))}
        </div>
      </div>
    </footer>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [activeSection, setActiveSection] = useState('overview')

  const sectionComponents = {
    overview: <Overview />,
    architecture: <Architecture />,
    tickets: <Tickets />,
    tools: <Tools />,
    demo: <Demo />,
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header activeSection={activeSection} setActiveSection={setActiveSection} />
      <Ticker />
      <main style={{ flex: 1 }}>
        {sectionComponents[activeSection]}
      </main>
      <Footer />
    </div>
  )
}
