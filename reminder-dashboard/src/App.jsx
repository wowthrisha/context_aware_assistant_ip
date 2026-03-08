import { useState, useEffect, useRef } from "react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTimeLeft(iso) {
  const diff = new Date(iso) - Date.now();
  if (diff <= 0) return "now";
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  return `${Math.floor(h / 24)}d`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", hour12: true,
  });
}

// ─── Components ───────────────────────────────────────────────────────────────

function ReminderCard({ reminder, onCancel }) {
  const isPast      = new Date(reminder.time) < Date.now();
  const isFired     = reminder.status === "fired";
  const isCancelled = reminder.status === "cancelled";

  const accent = isCancelled ? "#333"
               : isFired     ? "#22c55e"
               : isPast      ? "#ef4444"
               :               "#3b82f6";

  return (
    <div style={{
      background:"#0d1117", border:"1px solid #1e2a3a", borderRadius:"12px",
      padding:"18px 22px", display:"flex", alignItems:"center", gap:"16px",
      opacity: isCancelled ? 0.35 : 1, transition:"opacity 0.3s",
      position:"relative", overflow:"hidden",
    }}>
      <div style={{ position:"absolute", left:0, top:0, bottom:0, width:"3px", background:accent }} />

      <div style={{
        width:"38px", height:"38px", borderRadius:"9px", flexShrink:0,
        background: isCancelled?"#1a1a1a":isFired?"rgba(34,197,94,.1)":"rgba(59,130,246,.1)",
        display:"flex", alignItems:"center", justifyContent:"center", fontSize:"16px",
      }}>
        {isCancelled?"🚫":isFired?"✅":"🔔"}
      </div>

      <div style={{ flex:1, minWidth:0 }}>
        <div style={{
          fontFamily:"'DM Mono',monospace", fontSize:"14px", fontWeight:500,
          color: isCancelled?"#555":"#e2e8f0", marginBottom:"5px",
          whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
        }}>
          {reminder.task}
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:"10px", flexWrap:"wrap" }}>
          <span style={{ fontFamily:"'DM Mono',monospace", fontSize:"11px", color:"#64748b" }}>
            {formatDate(reminder.time)}
          </span>
          <span style={{
            fontFamily:"'DM Mono',monospace", fontSize:"10px", fontWeight:700,
            padding:"2px 8px", borderRadius:"20px", letterSpacing:"0.06em",
            background: isCancelled?"#1a1a1a":isFired?"rgba(34,197,94,.15)":isPast?"rgba(239,68,68,.15)":"rgba(59,130,246,.15)",
            color: isCancelled?"#555":isFired?"#22c55e":isPast?"#ef4444":"#60a5fa",
          }}>
            {isCancelled?"CANCELLED":isFired?"DONE":isPast?"OVERDUE":formatTimeLeft(reminder.time)}
          </span>
        </div>
      </div>

      <span style={{ fontFamily:"'DM Mono',monospace", fontSize:"10px", color:"#2d3748", flexShrink:0 }}>
        #{reminder.id.slice(0,6)}
      </span>

      {reminder.status === "pending" && (
        <button
          onClick={() => onCancel(reminder.id)}
          style={{
            background:"transparent", border:"1px solid #1e2a3a", color:"#64748b",
            padding:"5px 11px", borderRadius:"7px", fontSize:"11px", cursor:"pointer",
            fontFamily:"'DM Mono',monospace", flexShrink:0, transition:"all .2s",
          }}
          onMouseEnter={e=>{e.target.style.borderColor="#ef4444";e.target.style.color="#ef4444";}}
          onMouseLeave={e=>{e.target.style.borderColor="#1e2a3a";e.target.style.color="#64748b";}}
        >
          Cancel
        </button>
      )}
    </div>
  );
}

function Bubble({ role, text }) {
  const isUser = role === "user";
  return (
    <div style={{ textAlign: isUser ? "right" : "left" }}>
      <div style={{
        display:"inline-block", maxWidth:"82%",
        background: isUser ? "rgba(59,130,246,.15)" : "#0d1117",
        border:`1px solid ${isUser?"rgba(59,130,246,.3)":"#1e2a3a"}`,
        borderRadius:"10px", padding:"10px 14px",
        fontSize:"13px", lineHeight:"1.65",
        color: isUser?"#93c5fd":"#94a3b8",
        fontFamily:"'DM Mono',monospace", whiteSpace:"pre-wrap",
      }}>
        {text}
      </div>
    </div>
  );
}

function MemoryTag({ text, type }) {
  const colors = {
    preference: { bg:"rgba(99,102,241,.1)", border:"rgba(99,102,241,.3)", color:"#818cf8" },
    habit:      { bg:"rgba(16,185,129,.1)", border:"rgba(16,185,129,.3)", color:"#10b981" },
    general:    { bg:"rgba(59,130,246,.1)", border:"rgba(59,130,246,.3)", color:"#60a5fa" },
  };
  const c = colors[type] || colors.general;
  return (
    <span style={{
      display:"inline-block", fontSize:"10px", padding:"2px 8px", borderRadius:"99px",
      background:c.bg, border:`1px solid ${c.border}`, color:c.color,
      fontFamily:"'DM Mono',monospace", letterSpacing:"0.05em",
    }}>
      💾 {type}
    </span>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

const API = "http://localhost:8000";

export default function App() {
  const [reminders, setReminders] = useState([]);
  const [messages,  setMessages]  = useState([
    { role:"assistant", text:"Hey! I'm your context-aware assistant ✦\n\nI remember your preferences and habits across sessions.\n\nTry:\n• \"I love coffee in the morning\"\n• \"I always work out at 7am\"\n• \"Remind me to call John at 6pm tomorrow\"\n• \"What do I like?\"" }
  ]);
  const [input,          setInput]          = useState("");
  const [loading,        setLoading]        = useState(false);
  const [filter,         setFilter]         = useState("all");
  const [backendOnline,  setBackendOnline]  = useState(null);
  const [memoryPanel,    setMemoryPanel]    = useState(false);
  const [memoryData,     setMemoryData]     = useState({ preference:[], habit:[], general:[] });
  const chatRef = useRef(null);

  // ── Check backend on load ────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API}/`)
      .then(r => r.json())
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  // ── Load reminders from backend on start ─────────────────────────────────
  useEffect(() => {
    if (!backendOnline) return;
    fetch(`${API}/reminders`)
      .then(r => r.json())
      .then(d => setReminders(d.reminders || []))
      .catch(() => {});
  }, [backendOnline]);

  // ── Live countdown tick ───────────────────────────────────────────────────
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 15000);
    return () => clearInterval(t);
  }, []);

  // ── Auto scroll chat ──────────────────────────────────────────────────────
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, loading]);

  // ── Load memory panel data ────────────────────────────────────────────────
  const loadMemory = async () => {
    try {
      const [p, h, g] = await Promise.all([
        fetch(`${API}/memory/preference`).then(r=>r.json()),
        fetch(`${API}/memory/habit`).then(r=>r.json()),
        fetch(`${API}/memory/general`).then(r=>r.json()),
      ]);
      setMemoryData({
        preference: p.entries || [],
        habit:      h.entries || [],
        general:    g.entries || [],
      });
    } catch(e) {}
  };

  const toggleMemory = () => {
    if (!memoryPanel) loadMemory();
    setMemoryPanel(v => !v);
  };

  // ── Cancel reminder via API ───────────────────────────────────────────────
  const cancelReminder = async (id) => {
    try {
      await fetch(`${API}/reminders/${id}`, { method:"DELETE" });
      setReminders(prev => prev.map(r => r.id===id ? {...r, status:"cancelled"} : r));
    } catch {
      setReminders(prev => prev.map(r => r.id===id ? {...r, status:"cancelled"} : r));
    }
  };

  // ── Send message ──────────────────────────────────────────────────────────
  const send = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role:"user", text:msg }]);
    setLoading(true);

    // If backend offline — show error immediately
    if (!backendOnline) {
      setMessages(prev => [...prev, {
        role:"assistant",
        text:"⚠️ Backend is offline.\n\nRun this in your terminal:\n\nuvicorn app.api:app --reload",
      }]);
      setLoading(false);
      return;
    }

    try {
      const res  = await fetch(`${API}/chat`, {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ message: msg }),
      });
      const data = await res.json();

      // Add new reminder to UI list
      if (data.system?.reminder) {
        setReminders(prev => [data.system.reminder, ...prev]);
      }

      // Cancel updated in UI
      if (data.intent === "cancel_reminder") {
        setReminders(prev => prev.map(r =>
          r.status === "pending" ? { ...r, status:"cancelled" } : r
        ));
        // Re-fetch to get accurate list
        fetch(`${API}/reminders`)
          .then(r=>r.json())
          .then(d=>setReminders(d.reminders||[]));
      }

      // Build reply text
      let replyText = data.reply || "Done.";

      // Append proactive suggestion
      if (data.proactive_suggestion) {
        replyText += `\n\n💡 ${data.proactive_suggestion.message}`;
      }

      // Show memory badge inline
      const memSaved = data.memory_saved || null;

      setMessages(prev => [...prev, {
        role:"assistant",
        text: replyText,
        memorySaved: memSaved,
      }]);

      // Refresh memory panel if open
      if (memoryPanel) loadMemory();

    } catch (err) {
      setBackendOnline(false);
      setMessages(prev => [...prev, {
        role:"assistant",
        text:"⚠️ Lost connection to backend.\n\nMake sure this is running:\n\nuvicorn app.api:app --reload",
      }]);
    }

    setLoading(false);
  };

  const filtered = reminders.filter(r => filter==="all" || r.status===filter);
  const stats = {
    pending:   reminders.filter(r=>r.status==="pending").length,
    fired:     reminders.filter(r=>r.status==="fired").length,
    cancelled: reminders.filter(r=>r.status==="cancelled").length,
  };

  return (
    <div style={{
      minHeight:"100vh", background:"#060810", fontFamily:"'DM Mono',monospace",
      padding:"28px 24px",
      backgroundImage:"radial-gradient(ellipse at 15% 15%,rgba(59,130,246,.05) 0%,transparent 55%),radial-gradient(ellipse at 85% 85%,rgba(99,102,241,.04) 0%,transparent 55%)",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@700;800&display=swap');
        *{box-sizing:border-box;}
        ::-webkit-scrollbar{width:4px;}
        ::-webkit-scrollbar-track{background:transparent;}
        ::-webkit-scrollbar-thumb{background:#1e2a3a;border-radius:4px;}
        input::placeholder{color:#2d3a4a;}
        input:focus{border-color:#3b82f6 !important;outline:none;}
      `}</style>

      <div style={{ maxWidth:"1120px", margin:"0 auto" }}>

        {/* ── Header ── */}
        <div style={{ marginBottom:"28px", display:"flex", alignItems:"flex-start", justifyContent:"space-between", flexWrap:"wrap", gap:"12px" }}>
          <div>
            <div style={{ display:"flex", alignItems:"baseline", gap:"14px", marginBottom:"6px" }}>
              <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:"26px", fontWeight:800, color:"#e2e8f0", margin:0, letterSpacing:".02em" }}>
                ASSISTANT
              </h1>
              <span style={{ fontSize:"10px", color:"#3b82f6", letterSpacing:".18em", fontWeight:500 }}>
                REMINDER SYSTEM v2
              </span>
            </div>
            <div style={{ display:"flex", alignItems:"center", gap:"8px" }}>
              <div style={{
                width:"6px", height:"6px", borderRadius:"50%",
                background: backendOnline===null?"#64748b":backendOnline?"#22c55e":"#ef4444",
                boxShadow: backendOnline?"0 0 6px rgba(34,197,94,.6)":"none",
              }} />
              <p style={{ color:"#334155", fontSize:"11px", margin:0, letterSpacing:".05em" }}>
                {backendOnline===null?"checking backend…":backendOnline?"backend online · memory active":"backend offline — run uvicorn app.api:app --reload"}
              </p>
            </div>
          </div>

          {/* Memory button */}
          <button onClick={toggleMemory} style={{
            background: memoryPanel?"rgba(99,102,241,.2)":"transparent",
            border:`1px solid ${memoryPanel?"rgba(99,102,241,.4)":"#1e2a3a"}`,
            color: memoryPanel?"#818cf8":"#475569",
            padding:"8px 16px", borderRadius:"8px", fontSize:"11px",
            cursor:"pointer", fontFamily:"'DM Mono',monospace",
            letterSpacing:".08em", transition:"all .2s",
          }}>
            🧠 MEMORY {memoryPanel?"▲":"▼"}
          </button>
        </div>

        {/* ── Memory Panel ── */}
        {memoryPanel && (
          <div style={{
            background:"#0a0e1a", border:"1px solid #1e2a3a", borderRadius:"14px",
            padding:"20px", marginBottom:"20px",
            display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"16px",
          }}>
            {[
              { key:"preference", label:"PREFERENCES", color:"#818cf8", icon:"❤️" },
              { key:"habit",      label:"HABITS",      color:"#10b981", icon:"🔁" },
              { key:"general",    label:"GENERAL",     color:"#60a5fa", icon:"💬" },
            ].map(({ key, label, color, icon }) => (
              <div key={key}>
                <div style={{ fontSize:"9px", color:"#334155", letterSpacing:".12em", marginBottom:"10px", display:"flex", alignItems:"center", gap:"6px" }}>
                  {icon} {label} ({memoryData[key].length})
                </div>
                {memoryData[key].length === 0 ? (
                  <div style={{ fontSize:"11px", color:"#1e2a3a", fontStyle:"italic" }}>nothing stored yet</div>
                ) : (
                  <div style={{ display:"flex", flexDirection:"column", gap:"6px" }}>
                    {memoryData[key].map(e => (
                      <div key={e.id} style={{
                        fontSize:"11px", color:"#64748b", padding:"6px 10px",
                        background:"#0d1117", borderRadius:"6px",
                        border:"1px solid #1e293b", lineHeight:"1.5",
                      }}>
                        {e.text}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div style={{ display:"grid", gridTemplateColumns:"1fr 1.25fr", gap:"20px", alignItems:"start" }}>

          {/* ── LEFT ── */}
          <div style={{ display:"flex", flexDirection:"column", gap:"16px" }}>
            <div style={{ background:"#0a0e1a", border:"1px solid #1e2a3a", borderRadius:"14px", padding:"22px" }}>
              <div style={{ fontSize:"10px", color:"#334155", letterSpacing:".12em", marginBottom:"14px" }}>CHAT INTERFACE</div>

              <div ref={chatRef} style={{ height:"340px", overflowY:"auto", display:"flex", flexDirection:"column", gap:"10px", marginBottom:"14px" }}>
                {messages.map((m,i) => (
                  <div key={i}>
                    <Bubble role={m.role} text={m.text} />
                    {m.memorySaved && (
                      <div style={{ marginTop:"4px", textAlign:"left", paddingLeft:"4px" }}>
                        <MemoryTag text={m.memorySaved.text} type={m.memorySaved.type} />
                      </div>
                    )}
                  </div>
                ))}
                {loading && (
                  <div>
                    <div style={{
                      display:"inline-block", background:"#0d1117", border:"1px solid #1e2a3a",
                      borderRadius:"10px", padding:"10px 14px", fontSize:"13px",
                      color:"#334155", fontFamily:"'DM Mono',monospace",
                    }}>
                      thinking…
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display:"flex", gap:"10px" }}>
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key==="Enter" && send()}
                  placeholder='"I love coffee" or "Remind me at 6pm"'
                  style={{
                    flex:1, background:"#0d1117", border:"1px solid #1e2a3a", borderRadius:"9px",
                    padding:"12px 16px", color:"#e2e8f0", fontSize:"13px",
                    fontFamily:"'DM Mono',monospace", transition:"border-color .2s",
                  }}
                />
                <button onClick={send} disabled={loading} style={{
                  background: loading?"#1e2a3a":"linear-gradient(135deg,#3b82f6,#1d4ed8)",
                  border:"none", borderRadius:"9px", padding:"12px 20px",
                  color:"#fff", fontSize:"13px", cursor:loading?"not-allowed":"pointer",
                  fontFamily:"'DM Mono',monospace", fontWeight:600, whiteSpace:"nowrap",
                }}>
                  {loading?"…":"Send →"}
                </button>
              </div>
            </div>

            {/* Stats */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"10px" }}>
              {[
                { label:"PENDING",   value:stats.pending,   color:"#3b82f6" },
                { label:"FIRED",     value:stats.fired,     color:"#22c55e" },
                { label:"CANCELLED", value:stats.cancelled, color:"#6366f1" },
              ].map(s => (
                <div key={s.label} style={{ background:"#0a0e1a", border:"1px solid #1e2a3a", borderRadius:"12px", padding:"16px 12px", textAlign:"center" }}>
                  <div style={{ fontFamily:"'Syne',sans-serif", fontSize:"26px", fontWeight:800, color:s.color }}>{s.value}</div>
                  <div style={{ fontSize:"9px", color:"#334155", letterSpacing:".12em", marginTop:"4px" }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* ── RIGHT ── */}
          <div style={{ background:"#0a0e1a", border:"1px solid #1e2a3a", borderRadius:"14px", padding:"22px" }}>
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"18px", flexWrap:"wrap", gap:"8px" }}>
              <span style={{ fontSize:"10px", color:"#334155", letterSpacing:".12em" }}>REMINDERS</span>
              <div style={{ display:"flex", gap:"6px", flexWrap:"wrap" }}>
                {["all","pending","fired","cancelled"].map(f => (
                  <button key={f} onClick={() => setFilter(f)} style={{
                    background: filter===f?"rgba(59,130,246,.2)":"transparent",
                    border:`1px solid ${filter===f?"rgba(59,130,246,.4)":"#1e2a3a"}`,
                    color: filter===f?"#60a5fa":"#475569",
                    padding:"3px 9px", borderRadius:"6px", fontSize:"9px",
                    cursor:"pointer", fontFamily:"'DM Mono',monospace",
                    letterSpacing:".08em", textTransform:"uppercase", transition:"all .15s",
                  }}>
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display:"flex", flexDirection:"column", gap:"8px", maxHeight:"490px", overflowY:"auto" }}>
              {filtered.length === 0 ? (
                <div style={{ textAlign:"center", padding:"48px 0", color:"#1e2a3a", fontSize:"13px" }}>
                  {backendOnline ? "No reminders" : "Start backend to load reminders"}
                </div>
              ) : (
                filtered.map(r => <ReminderCard key={r.id} reminder={r} onCancel={cancelReminder} />)
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}