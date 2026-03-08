import { useState, useEffect, useRef } from "react";

// ─── Time parsing (mirrors Python backend logic) ─────────────────────────────

function parseTimeFromMsg(msg) {
  const text = msg.toLowerCase();

  // "in X minutes/hours/seconds"
  const relMatch = text.match(/\bin\s+(\d+)\s*(second|minute|hour|day|min|hr|sec)s?\b/);
  if (relMatch) {
    const val = parseInt(relMatch[1]);
    const unit = relMatch[2];
    const ms = unit.startsWith("s") ? val * 1000
              : unit.startsWith("m") || unit === "min" ? val * 60000
              : unit.startsWith("h") || unit === "hr"  ? val * 3600000
              : unit.startsWith("d") ? val * 86400000
              : val * 60000;
    return new Date(Date.now() + ms);
  }

  // "at H:MM am/pm" or "at Hpm"
  const atMatch = text.match(/\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b/);
  if (atMatch) {
    let hours   = parseInt(atMatch[1]);
    const mins  = parseInt(atMatch[2] ?? "0");
    const mer   = atMatch[3];

    if (mer === "pm" && hours !== 12) hours += 12;
    if (mer === "am" && hours === 12) hours = 0;

    const hasTomorrow = /\btomorrow\b/.test(text);
    const hasToday    = /\btoday\b|\btonight\b/.test(text);

    const t = new Date();
    t.setHours(hours, mins, 0, 0);
    if (hasTomorrow) t.setDate(t.getDate() + 1);
    else if (t <= Date.now() && !hasToday) t.setDate(t.getDate() + 1);

    return t;
  }

  // "tomorrow" with no explicit time → tomorrow 9am
  if (/\btomorrow\b/.test(text)) {
    const t = new Date();
    t.setDate(t.getDate() + 1);
    t.setHours(9, 0, 0, 0);
    return t;
  }

  return null;
}

function extractTask(msg) {
  let t = msg;
  t = t.replace(/\b(remind me to|remind me|set a reminder to|set a reminder for|set reminder|please remind me to|can you remind me to)\b/gi, "");
  t = t.replace(/\bin \d+ (second|minute|hour|day|week)s?\b/gi, "");
  t = t.replace(/\bat \d{1,2}(:\d{2})?\s*(am|pm)?\b/gi, "");
  t = t.replace(/\b(tomorrow|today|tonight|this evening|this morning|next week)\b/gi, "");
  t = t.replace(/\s{2,}/g, " ").trim().replace(/^[,.\s-]+|[,.\s-]+$/g, "");
  return t || msg;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

// ─── Components ──────────────────────────────────────────────────────────────

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
        <button onClick={() => onCancel(reminder.id)} style={{
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

// ─── Seed data ────────────────────────────────────────────────────────────────

const SEED = [
  { id:"a1b2c3d4", task:"Call John about the project",  time:new Date(Date.now()+3600000).toISOString(),  status:"pending",   created_at:new Date().toISOString() },
  { id:"e5f6g7h8", task:"Take medication",              time:new Date(Date.now()+7200000).toISOString(),  status:"pending",   created_at:new Date().toISOString() },
  { id:"i9j0k1l2", task:"Team standup meeting",         time:new Date(Date.now()-3600000).toISOString(),  status:"fired",     created_at:new Date().toISOString() },
  { id:"m3n4o5p6", task:"Submit weekly report",         time:new Date(Date.now()+86400000).toISOString(), status:"pending",   created_at:new Date().toISOString() },
];

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [reminders, setReminders] = useState(SEED);
  const [messages,  setMessages]  = useState([
    { role:"assistant", text:'Hey! I\'m your context-aware assistant.\nTry: "Remind me to call John at 6pm tomorrow" or "Remind me in 20 minutes to stretch".' }
  ]);
  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [filter,  setFilter]  = useState("all");
  const chatRef = useRef(null);

  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 15000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, loading]);

  const send = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role:"user", text:msg }]);
    setLoading(true);
    await new Promise(r => setTimeout(r, 600));

    const lower = msg.toLowerCase();
    const isCancel   = /\b(cancel|delete|remove)\b.*\b(reminder|alarm)\b/i.test(lower);
    const isList     = /\b(list|show|what are my|view)\b.*\b(reminder|alarm)s?\b/i.test(lower);
    const isReminder = /\b(remind|alarm|schedule)\b/i.test(lower) || /\breminder\b/i.test(lower);

    if (isCancel) {
      const pending = reminders.filter(r => r.status === "pending");
      if (pending.length > 0) {
        const latest = [...pending].sort((a,b) => b.created_at.localeCompare(a.created_at))[0];
        setReminders(prev => prev.map(r => r.id === latest.id ? {...r, status:"cancelled"} : r));
        setMessages(prev => [...prev, { role:"assistant", text:`🚫 Cancelled: "${latest.task}"` }]);
      } else {
        setMessages(prev => [...prev, { role:"assistant", text:"You have no pending reminders to cancel." }]);
      }

    } else if (isList) {
      const pending = reminders.filter(r => r.status === "pending");
      if (!pending.length) {
        setMessages(prev => [...prev, { role:"assistant", text:"You have no upcoming reminders." }]);
      } else {
        const lines = [...pending]
          .sort((a,b) => a.time.localeCompare(b.time))
          .map(r => `• ${r.task} — ${formatDate(r.time)}`).join("\n");
        setMessages(prev => [...prev, { role:"assistant", text:`Your upcoming reminders:\n${lines}` }]);
      }

    } else if (isReminder) {
      const time = parseTimeFromMsg(msg);
      if (!time || time <= Date.now()) {
        setMessages(prev => [...prev, { role:"assistant", text:'I couldn\'t understand the time. Try:\n• "Remind me to call John at 3pm"\n• "Remind me in 30 minutes"\n• "Remind me tomorrow at 6pm"' }]);
      } else {
        const task = extractTask(msg);
        const id   = Math.random().toString(36).slice(2, 10);
        const newR = { id, task, raw_message:msg, time:time.toISOString(), created_at:new Date().toISOString(), status:"pending" };
        setReminders(prev => [newR, ...prev]);
        const friendly = time.toLocaleString("en-US", { weekday:"short", month:"short", day:"numeric", hour:"numeric", minute:"2-digit", hour12:true });
        setMessages(prev => [...prev, { role:"assistant", text:`✅ Reminder set for ${friendly} — "${task}"` }]);
      }

    } else {
      setMessages(prev => [...prev, { role:"assistant", text:'Got it! You can also try:\n• "Remind me to take a break in 45 minutes"\n• "Remind me to check emails tomorrow at 9am"\n• "Cancel my last reminder"\n• "List my reminders"' }]);
    }

    setLoading(false);
  };

  const cancelReminder = (id) =>
    setReminders(prev => prev.map(r => r.id === id ? {...r, status:"cancelled"} : r));

  const filtered = reminders.filter(r => filter === "all" || r.status === filter);
  const stats = {
    pending:   reminders.filter(r => r.status === "pending").length,
    fired:     reminders.filter(r => r.status === "fired").length,
    cancelled: reminders.filter(r => r.status === "cancelled").length,
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

        {/* Header */}
        <div style={{ marginBottom:"32px" }}>
          <div style={{ display:"flex", alignItems:"baseline", gap:"14px", marginBottom:"6px" }}>
            <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:"26px", fontWeight:800, color:"#e2e8f0", margin:0, letterSpacing:".02em" }}>
              ASSISTANT
            </h1>
            <span style={{ fontSize:"10px", color:"#3b82f6", letterSpacing:".18em", fontWeight:500 }}>
              REMINDER SYSTEM v2
            </span>
          </div>
          <p style={{ color:"#334155", fontSize:"12px", margin:0, letterSpacing:".05em" }}>
            Context-aware · Persistent · Scheduled
          </p>
        </div>

        <div style={{ display:"grid", gridTemplateColumns:"1fr 1.25fr", gap:"20px", alignItems:"start" }}>

          {/* LEFT */}
          <div style={{ display:"flex", flexDirection:"column", gap:"16px" }}>
            <div style={{ background:"#0a0e1a", border:"1px solid #1e2a3a", borderRadius:"14px", padding:"22px" }}>
              <div style={{ fontSize:"10px", color:"#334155", letterSpacing:".12em", marginBottom:"14px" }}>CHAT INTERFACE</div>

              <div ref={chatRef} style={{ height:"300px", overflowY:"auto", display:"flex", flexDirection:"column", gap:"10px", marginBottom:"14px" }}>
                {messages.map((m,i) => <Bubble key={i} role={m.role} text={m.text} />)}
                {loading && (
                  <div>
                    <div style={{ display:"inline-block", background:"#0d1117", border:"1px solid #1e2a3a", borderRadius:"10px", padding:"10px 14px", fontSize:"13px", color:"#334155", fontFamily:"'DM Mono',monospace" }}>
                      thinking…
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display:"flex", gap:"10px" }}>
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && send()}
                  placeholder='"Remind me at 6pm tomorrow"'
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

          {/* RIGHT */}
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
                <div style={{ textAlign:"center", padding:"48px 0", color:"#1e2a3a", fontSize:"13px" }}>No reminders</div>
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