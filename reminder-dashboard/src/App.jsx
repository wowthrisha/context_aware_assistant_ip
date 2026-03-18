import { useState, useEffect, useRef } from 'react';
import { formatDistanceToNow, parseISO } from 'date-fns';

const API = "http://127.0.0.1:8000";

// --- Helpers ---
const getIcon = (msg, status) => {
  if (status === "fired") return "✅";
  if (status === "cancelled") return "❌";
  return "⏰"; // Default clock icon from screenshot
};

const playBeep = () => {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.5);
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) {}
};

// --- Components ---
function Bubble({ role, text }) {
  const isUser = role === "user";
  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "16px",
      animation: "fadeSlide 0.3s ease-out"
    }}>
      <div style={{
        background: isUser ? "rgba(37, 99, 235, 0.4)" : "rgba(22, 27, 34, 0.6)",
        backdropFilter: "blur(4px)",
        border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: "12px",
        padding: "12px 16px",
        maxWidth: "85%",
        fontSize: "0.85rem",
        color: "#f0f6fc",
        fontFamily: "'Inter', sans-serif"
      }}>
        {text}
      </div>
    </div>
  );
}

function ReminderCard({ reminder, onCancel }) {
  const isFired = reminder.status === "fired";
  const isCancelled = reminder.status === "cancelled";
  const isPending = reminder.status === "pending";
  const triggerDate = parseISO(reminder.trigger_at);
  const isPast = triggerDate < new Date();

  const timeLabel = isFired ? "DONE" : isCancelled ? "CANCELLED" : isPast ? "OVERDUE" : "PENDING";
  const relativeTime = formatDistanceToNow(triggerDate, { addSuffix: true });

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      padding: "16px 20px",
      borderBottom: "1px solid rgba(255,255,255,0.05)",
      gap: "20px",
      transition: "background 0.2s"
    }}>
      <div style={{
        width: "32px",
        height: "32px",
        borderRadius: "50%",
        background: isFired ? "#238636" : isCancelled ? "#da3633" : "#3b82f6",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "14px"
      }}>
        {isFired ? "✓" : isCancelled ? "✕" : "🔔"}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "14px", fontWeight: 600, color: "#f0f6fc" }}>{reminder.message}</div>
        <div style={{ fontSize: "11px", color: "#8b949e", marginTop: "4px" }}>
          <span style={{ marginRight: "10px" }}>{relativeTime.replace("about ", "")}</span>
          <span style={{ color: isPast && isPending ? "#f85149" : isFired ? "#3fb950" : "#8b949e", fontWeight: "bold", textTransform: "uppercase" }}>• {timeLabel}</span>
        </div>
      </div>
      <div>
        {isPending && (
          <button 
            onClick={() => onCancel(reminder.id)}
            style={{ 
              background: "#da3633", color: "#fff", border: "none", borderRadius: "4px", 
              padding: "6px 16px", fontSize: "11px", fontWeight: 700, cursor: "pointer",
              textTransform: "uppercase"
            }}
          >
            Cancel
          </button>
        )}
        <span style={{ fontSize: "10px", color: "#30363d", marginLeft: "12px", fontFamily: "monospace" }}>{reminder.id.slice(0, 8)}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [reminders, setReminders] = useState([]);
  const [filter, setFilter] = useState("all");
  const [backendOnline, setBackendOnline] = useState(true);
  const [memoryPanel, setMemoryPanel] = useState(false);
  const [memoryData, setMemoryData] = useState({ preference: [], habit: [], general: [] });
  const [toast, setToast] = useState(null);
  const [userId, setUserId] = useState("ridhu");
  const chatRef = useRef(null);
  const sseRef = useRef(null);

  // --- Notification System ---
  const triggerNotification = (msg) => {
    // 1. In-App Premium Toast
    setToast({ message: msg, id: Date.now() });
    playBeep();
    setTimeout(() => setToast(null), 10000);

    // 2. Real OS Desktop Notification
    if (Notification.permission === "granted") {
      new Notification("Assistant Reminder ⏰", {
        body: msg,
        icon: "https://cdn-icons-png.flaticon.com/512/559/559360.png", // Added a professional icon
        silent: true // We play our own high-fi sound via playBeep()
      });
    }
  };

  useEffect(() => {
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
      Notification.requestPermission();
    }

    const connectSSE = () => {
      if (sseRef.current) sseRef.current.close();
      const es = new EventSource(`${API}/reminders/stream?user_id=${userId}`);
      es.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.type === 'reminder') {
            triggerNotification(payload.message);
            fetchReminders();
          }
        } catch (err) {}
      };
      es.onerror = () => { setBackendOnline(false); es.close(); setTimeout(connectSSE, 5000); };
      es.onopen = () => setBackendOnline(true);
      sseRef.current = es;
    };
    connectSSE();
    return () => sseRef.current?.close();
  }, [userId]);

  const fetchReminders = async () => {
    try {
      const r = await fetch(`${API}/reminders`);
      if (r.ok) {
        const data = await r.json();
        setReminders(data.reminders || []);
      }
    } catch { setBackendOnline(false); }
  };

  const cancelReminder = async (id) => {
    await fetch(`${API}/reminders/${id}`, { method: "DELETE" });
    fetchReminders();
  };

  const fetchMemory = async () => {
    try {
      const results = await Promise.all(["preference", "habit", "general"].map(t => fetch(`${API}/memory/${t}`).then(res => res.json())));
      setMemoryData({ preference: results[0].entries || [], habit: results[1].entries || [], general: results[2].entries || [] });
    } catch {}
  };

  const send = async () => {
    if (!input.trim() || loading) return;
    setMessages(prev => [...prev, { role: "user", text: input }]);
    setLoading(true);
    setInput("");
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input })
      });
      const data = await r.json();
      setMessages(prev => [...prev, { role: "assistant", text: data.reply }]);
      if (data.system?.reminder_id) fetchReminders();
      if (data.memory_saved) fetchMemory();
    } catch { setBackendOnline(false); }
    setLoading(false);
  };

  useEffect(() => {
    fetchReminders();
    const interval = setInterval(fetchReminders, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" }); }, [messages]);

  const stats = {
    pending: reminders.filter(r => r.status === "pending").length,
    fired: reminders.filter(r => r.status === "fired").length,
    cancelled: reminders.filter(r => r.status === "cancelled").length
  };

  return (
    <div style={{
      width: "100vw", height: "100vh", background: "#0d1117", color: "#c9d1d9",
      fontFamily: "'Inter', sans-serif", display: "flex", flexDirection: "column",
      padding: "20px", boxSizing: "border-box", overflow: "hidden"
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Syne:wght@800&display=swap');
        @keyframes fadeSlide { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes toastIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes pulseIcon { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
        ::-webkit-scrollbar-thumb { background: #30363d; borderRadius: 4px; }
      `}</style>
      
      {/* Premium Legible Toast */}
      {toast && (
        <div style={{
          position: "fixed", top: "40px", right: "40px", zIndex: 3000,
          background: "rgba(13, 17, 23, 0.9)", backdropFilter: "blur(20px)",
          border: "1px solid rgba(59, 130, 246, 0.5)", color: "#fff", 
          padding: "24px", borderRadius: "20px", width: "360px",
          display: "flex", alignItems: "flex-start", gap: "20px", 
          boxShadow: "0 20px 50px rgba(0,0,0,0.6), 0 0 20px rgba(59, 130, 246, 0.2)",
          animation: "toastIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275)"
        }}>
          <div style={{ 
            fontSize: "32px", background: "linear-gradient(135deg, #3b82f6, #1d4ed8)", 
            padding: "12px", borderRadius: "16px", boxShadow: "0 8px 16px rgba(59, 130, 246, 0.4)",
            animation: "pulseIcon 2s infinite"
          }}>⏰</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "11px", fontWeight: 800, color: "#3b82f6", letterSpacing: "1.5px", marginBottom: "6px", textTransform: "uppercase" }}>REMINDER FIRED</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#ffffff", lineHeight: "1.4", textShadow: "0 2px 4px rgba(0,0,0,0.3)" }}>{toast.message}</div>
            <div style={{ marginTop: "16px", display: "flex", gap: "10px" }}>
              <button 
                onClick={() => setToast(null)} 
                style={{ 
                  flex: 1, background: "rgba(255,255,255,0.05)", color: "#fff", 
                  border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", 
                  padding: "8px", fontSize: "12px", fontWeight: 600, cursor: "pointer",
                  transition: "background 0.2s"
                }}
                onMouseOver={e => e.target.style.background = "rgba(255,255,255,0.1)"}
                onMouseOut={e => e.target.style.background = "rgba(255,255,255,0.05)"}
              >
                DISMISS
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header exactly like screenshot */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", padding: "0 10px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "12px" }}>
          <h1 style={{ fontFamily: "'Syne', sans-serif", fontSize: "26px", fontWeight: 800, margin: 0, color: "#fff", letterSpacing: "-0.5px" }}>ASSISTANT</h1>
          <span style={{ fontSize: "11px", fontWeight: 700, color: "#484f58", letterSpacing: "1px" }}>REMINDER SYSTEM V2</span>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
           <button onClick={() => { if(!memoryPanel) fetchMemory(); setMemoryPanel(!memoryPanel); }} style={{ background: "transparent", border: "none", color: "#8b949e", fontSize: "11px", fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", background: "rgba(255,255,255,0.03)", padding: "8px 16px", borderRadius: "8px" }}>🧠 MEMORY {memoryPanel ? "▼" : "▲"}</button>
        </div>
      </div>

      <div style={{ fontSize: "11px", color: "#8b949e", display: "flex", gap: "10px", alignItems: "center", marginBottom: "20px", padding: "0 10px" }}>
        <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: backendOnline ? "#238636" : "#da3633" }}></div>
        <span>{backendOnline ? "backend online" : "connecting..."}</span>
        <span style={{ opacity: 0.3 }}>•</span>
        <span>user: <span style={{color: "#f0f6fc", fontWeight: 600}}>{userId}</span></span>
      </div>

      {/* Memory Panel */}
      {memoryPanel && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "15px", marginBottom: "20px", animation: "fadeSlide 0.3s ease-out" }}>
          {["preference", "habit", "general"].map(cat => (
            <div key={cat} style={{ background: "rgba(22, 27, 34, 0.5)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "12px", padding: "12px" }}>
              <div style={{ fontSize: "9px", fontWeight: 800, color: "#8b949e", marginBottom: "8px", textTransform: "uppercase" }}>{cat}</div>
              {memoryData[cat].map(item => <div key={item.id} style={{ fontSize: "11px", padding: "6px", borderBottom: "1px solid rgba(255,255,255,0.02)" }}>{item.text}</div>)}
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: "20px", flex: 1, minHeight: 0 }}>
        {/* Left: Chat interface */}
        <div style={{ width: "340px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <div style={{ flex: 1, background: "rgba(13, 17, 23, 0.3)", border: "1px solid rgba(48, 54, 61, 0.5)", borderRadius: "12px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
             <div style={{ padding: "12px 16px", background: "rgba(255,255,255,0.02)", borderBottom: "1px solid rgba(48, 54, 61, 0.5)", fontSize: "10px", fontWeight: 700, color: "#484f58", letterSpacing: "1px" }}>CHAT INTERFACE</div>
             <div style={{ flex: 1, overflowY: "auto", padding: "20px" }} ref={chatRef}>
               {messages.map((m, i) => <Bubble key={i} role={m.role} text={m.text} />)}
               {loading && <div style={{ fontSize: "11px", color: "#8b949e", fontStyle: "italic" }}>Assistant is analyzing...</div>}
             </div>
             <div style={{ padding: "16px", borderTop: "1px solid rgba(48, 54, 61, 0.5)", background: "rgba(0,0,0,0.2)" }}>
               <div style={{ display: "flex", gap: "10px" }}>
                 <input 
                  value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()}
                  placeholder='"I love coffee" or "Remind me..."'
                  style={{ flex: 1, background: "rgba(255,255,255,0.02)", border: "1px solid #30363d", borderRadius: "8px", padding: "10px 14px", color: "#fff", fontSize: "13px", outline: "none" }}
                 />
                 <button onClick={send} style={{ background: "#2563eb", color: "#fff", border: "none", borderRadius: "8px", padding: "0 16px", fontWeight: 600, fontSize: "13px", cursor: "pointer" }}>Send →</button>
               </div>
             </div>
          </div>

          {/* Stats Boxes from screenshot */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
            {[
              { label: "PENDING", val: stats.pending, color: "#3b82f6" },
              { label: "FIRED", val: stats.fired, color: "#238636" },
              { label: "CANCELLED", val: stats.cancelled, color: "#da3633" }
            ].map(s => (
              <div key={s.label} style={{ background: "rgba(13, 17, 23, 0.5)", border: "1px solid rgba(48, 54, 61, 0.5)", borderRadius: "8px", padding: "12px", textAlign: "center" }}>
                <div style={{ fontSize: "18px", fontWeight: 800, color: s.color }}>{s.val}</div>
                <div style={{ fontSize: "9px", fontWeight: 700, color: "#484f58", marginTop: "4px", letterSpacing: "0.5px" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Reminders list */}
        <div style={{ flex: 1, background: "rgba(13, 17, 23, 0.3)", border: "1px solid rgba(48, 54, 61, 0.5)", borderRadius: "12px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "12px 20px", background: "rgba(255,255,255,0.02)", borderBottom: "1px solid rgba(48, 54, 61, 0.5)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
              <span style={{ fontSize: "15px", fontWeight: 700, color: "#f0f6fc" }}>Reminders</span>
              <span style={{ fontSize: "11px", color: "#484f58" }}>{stats.pending} active tasks</span>
            </div>
            <div style={{ display: "flex", gap: "6px", background: "#0d1117", padding: "3px", borderRadius: "6px" }}>
              {["all", "pending", "fired", "cancelled"].map(f => (
                <button 
                  key={f} onClick={() => setFilter(f)}
                  style={{ background: filter === f ? "#21262d" : "transparent", border: "none", color: filter === f ? "#fff" : "#8b949e", fontSize: "10px", fontWeight: 700, padding: "5px 12px", borderRadius: "4px", cursor: "pointer", textTransform: "uppercase" }}
                >
                  {f === "fired" ? "FIRED" : f}
                </button>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {reminders.filter(r => filter === "all" || r.status === filter).map(r => (
              <ReminderCard key={r.id} reminder={r} onCancel={cancelReminder} />
            ))}
            {reminders.length === 0 && <div style={{ padding: "80px", textAlign: "center", color: "#484f58", fontSize: "14px" }}>No active reminders found.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
