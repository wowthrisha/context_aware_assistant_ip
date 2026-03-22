import { useState, useEffect, useRef } from 'react';
import { formatDistanceToNow, parseISO } from 'date-fns';

const API = "http://127.0.0.1:8000";

// ─── Smart reply suggestions ──────────────────────────────────────────────────

function getSuggestions(replyText) {
  const t = (replyText || "").toLowerCase();
  if (t.includes("reminder set") || t.includes("recurring reminder"))
    return ["List my reminders", "Cancel my last reminder", "Remind me in 1 hour"];
  if (t.includes("cancelled"))
    return ["List my reminders", "Remind me tomorrow at 9am", "What are my habits?"];
  if (t.includes("no pending reminders") || t.includes("upcoming reminders"))
    return ["Remind me in 30 minutes", "Remind me tomorrow at 9am", "What do I like?"];
  if (t.includes("preference") || t.includes("remember") || t.includes("noted"))
    return ["What do I like?", "What are my habits?", "Remind me in 1 hour"];
  if (t.includes("habit") || t.includes("routine"))
    return ["What are my habits?", "Remind me every day at 7am", "What do I like?"];
  if (t.includes("reminder") && t.includes("pending"))
    return ["Cancel my last reminder", "List my reminders", "Remind me in 30 minutes"];
  if (t.includes("when should i remind"))
    return ["In 30 minutes", "At 8pm", "Tomorrow at 9am"];
  return ["Remind me in 30 minutes", "What do I like?", "List my reminders"];
}

// ─── Audio ────────────────────────────────────────────────────────────────────

const playBeep = () => {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext(), osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.5);
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + 0.5);
  } catch {}
};

// ─── Chat Bubble ──────────────────────────────────────────────────────────────

function Bubble({ role, text, selectedVoice }) {
  const isUser = role === "user";
  const [speaking, setSpeaking] = useState(false);

  const speak = () => {
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); return; }
    const cleaned = text.replace(/[\u{1F000}-\u{1FFFF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|[\u{FE00}-\u{FEFF}]|[\u{1F900}-\u{1F9FF}]|[\u{1FA00}-\u{1FA6F}]/gu, "").trim();
    const utterance = new SpeechSynthesisUtterance(cleaned);
    if (selectedVoice) utterance.voice = selectedVoice;
    utterance.onend = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  };

  return (
    <div style={{
      display: "flex", justifyContent: isUser ? "flex-end" : "flex-start",
      alignItems: "flex-start", gap: "8px", marginBottom: "16px",
      animation: "fadeSlide 0.3s ease-out", flexDirection: isUser ? "row-reverse" : "row",
    }}>
      <div style={{
        width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0,
        background: isUser ? "rgba(37,99,235,0.3)" : "rgba(99,102,241,0.3)",
        border: `1px solid ${isUser ? "rgba(37,99,235,0.5)" : "rgba(99,102,241,0.5)"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "13px", marginTop: "2px",
      }}>
        {isUser ? "👤" : "🤖"}
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start", maxWidth: "80%" }}>
        <div style={{
          background: isUser ? "rgba(37,99,235,0.4)" : "rgba(22,27,34,0.6)",
          backdropFilter: "blur(4px)", border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: isUser ? "12px 2px 12px 12px" : "2px 12px 12px 12px",
          padding: "12px 16px", fontSize: "0.85rem", color: "#f0f6fc",
          fontFamily: "'Inter', sans-serif", whiteSpace: "pre-wrap",
        }}>
          {text}
        </div>
        {!isUser && (
          <button onClick={speak} style={{
            marginTop: "4px", background: "none", border: "none", cursor: "pointer",
            fontSize: "13px", color: speaking ? "#3b82f6" : "#484f58",
            padding: "2px 6px", borderRadius: "4px", transition: "color 0.2s",
          }}>
            {speaking ? "⏹ stop" : "🔈 listen"}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Suggestion Chips ─────────────────────────────────────────────────────────

function SuggestionChips({ suggestions, onSelect }) {
  return (
    <div style={{
      display: "flex", gap: "8px", flexWrap: "wrap",
      paddingLeft: "36px", marginTop: "-8px", marginBottom: "12px",
      animation: "fadeSlide 0.3s ease-out",
    }}>
      {suggestions.map((s, i) => (
        <button key={i} onClick={() => onSelect(s)} style={{
          background: "transparent", border: "1px solid rgba(99,102,241,0.35)",
          color: "#818cf8", padding: "5px 12px", borderRadius: "99px",
          fontSize: "11px", cursor: "pointer", fontFamily: "'Inter', sans-serif",
          fontWeight: 500, transition: "all 0.15s", whiteSpace: "nowrap",
        }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(99,102,241,0.15)"; e.currentTarget.style.borderColor = "rgba(99,102,241,0.6)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "rgba(99,102,241,0.35)"; }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}

// ─── Reminder Card ────────────────────────────────────────────────────────────

function ReminderCard({ reminder, onCancel }) {
  const isFired     = reminder.status === "fired";
  const isCancelled = reminder.status === "cancelled";
  const isPending   = reminder.status === "pending";
  const triggerDate = parseISO(reminder.trigger_at);
  const isPast      = triggerDate < new Date();
  const timeLabel   = isFired ? "DONE" : isCancelled ? "CANCELLED" : isPast ? "OVERDUE" : "PENDING";
  const relativeTime = formatDistanceToNow(triggerDate, { addSuffix: true });
  const accentColor = isFired ? "#238636" : isCancelled ? "#da3633" : "#3b82f6";

  return (
    <div
      onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      style={{
        display: "flex", alignItems: "center", padding: "16px 20px",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
        borderLeft: `3px solid ${accentColor}`,
        gap: "16px", transition: "background 0.2s", background: "transparent",
      }}
    >
      <div style={{
        width: "32px", height: "32px", borderRadius: "50%", background: accentColor,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "14px", flexShrink: 0,
      }}>
        {isFired ? "✓" : isCancelled ? "✕" : "🔔"}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: "14px", fontWeight: 600, color: "#f0f6fc",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>
          {reminder.message}
        </div>
        <div style={{ fontSize: "11px", color: "#8b949e", marginTop: "4px", display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span>{relativeTime.replace("about ", "")}</span>
          <span style={{
            color: isPast && isPending ? "#f85149" : isFired ? "#3fb950" : "#8b949e",
            fontWeight: "bold", textTransform: "uppercase",
          }}>• {timeLabel}</span>
          {reminder.recurrence && (
            <span style={{
              fontSize: "9px", padding: "2px 7px", borderRadius: "99px",
              background: "rgba(139,92,246,0.15)", border: "1px solid rgba(139,92,246,0.3)",
              color: "#a78bfa", fontWeight: 700, letterSpacing: "0.05em",
            }}>
              🔁 {reminder.recurrence.replace(/_/g, " ")}
            </span>
          )}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
        <span style={{ fontSize: "10px", color: "#30363d", fontFamily: "monospace" }}>
          {reminder.id.slice(0, 8)}
        </span>
        {isPending && (
          <button onClick={() => onCancel(reminder.id)} style={{
            background: "#da3633", color: "#fff", border: "none", borderRadius: "4px",
            padding: "6px 14px", fontSize: "11px", fontWeight: 700, cursor: "pointer",
            textTransform: "uppercase",
          }}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [messages,      setMessages]      = useState([]);
  const [input,         setInput]         = useState("");
  const [loading,       setLoading]       = useState(false);
  const [reminders,     setReminders]     = useState([]);
  const [filter,        setFilter]        = useState("all");
  const [backendOnline, setBackendOnline] = useState(true);
  const [memoryPanel,   setMemoryPanel]   = useState(false);
  const [memoryData,    setMemoryData]    = useState({ preference: [], habit: [], general: [] });
  const [toast,         setToast]         = useState(null);
  const [userId]                          = useState("ridhu");
  const [listening,     setListening]     = useState(false);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [voices,        setVoices]        = useState([]);
  const [voiceStatus,   setVoiceStatus]   = useState("idle");

  const chatRef        = useRef(null);
  const sseRef         = useRef(null);
  const recognitionRef = useRef(null);
  const voiceStatusRef = useRef("idle");
  const sendVoiceRef   = useRef(null);

  useEffect(() => { voiceStatusRef.current = voiceStatus; }, [voiceStatus]);

  const headers = { "Content-Type": "application/json", "X-User-ID": userId };

  // ── Notification ─────────────────────────────────────────────────────────────
  const triggerNotification = (msg) => {
    setToast({ message: msg, id: Date.now() });
    playBeep();
    setTimeout(() => setToast(null), 10000);
    if (Notification.permission === "granted") {
      new Notification("Assistant ⏰", {
        body: msg,
        icon: "https://cdn-icons-png.flaticon.com/512/559/559360.png",
        silent: true,
      });
    }
  };

  // ── SSE ───────────────────────────────────────────────────────────────────────
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

          // Regular reminder fired
          if (payload.type === "reminder") {
            triggerNotification(payload.message);
            fetchReminders();
          }

          // Daily morning summary
          if (payload.type === "daily_summary") {
            triggerNotification(payload.message);
            setMessages(prev => [...prev, {
              role: "assistant",
              text: payload.message,
            }]);
          }

        } catch {}
      };

      es.onerror = () => { setBackendOnline(false); es.close(); setTimeout(connectSSE, 5000); };
      es.onopen  = () => setBackendOnline(true);
      sseRef.current = es;
    };
    connectSSE();
    return () => sseRef.current?.close();
  }, [userId]);

  // ── Fetch helpers ─────────────────────────────────────────────────────────────
  const fetchReminders = async () => {
    try {
      const r = await fetch(`${API}/reminders`, { headers });
      if (r.ok) { const data = await r.json(); setReminders(data.reminders || []); }
    } catch { setBackendOnline(false); }
  };

  const cancelReminder = async (id) => {
    await fetch(`${API}/reminders/${id}`, { method: "DELETE", headers });
    fetchReminders();
  };

  const fetchMemory = async () => {
    try {
      const results = await Promise.all(
        ["preference", "habit", "general"].map(t =>
          fetch(`${API}/memory/${t}`, { headers }).then(r => r.json())
        )
      );
      setMemoryData({
        preference: results[0].entries || [],
        habit:      results[1].entries || [],
        general:    results[2].entries || [],
      });
    } catch {}
  };

  // ── Poll + scroll ─────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchReminders();
    const interval = setInterval(fetchReminders, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // ── Chip send helper ──────────────────────────────────────────────────────────
  const sendMessage = async (msg) => {
    setMessages(prev => [...prev, { role: "user", text: msg }]);
    setLoading(true);
    try {
      const r    = await fetch(`${API}/chat`, { method: "POST", headers, body: JSON.stringify({ message: msg }) });
      const data = await r.json();
      setMessages(prev => [...prev, { role: "assistant", text: data.reply }]);

      // Habit suggestion from backend
      if (data.habit_suggestion) {
        setMessages(prev => [...prev, {
          role: "assistant",
          text: `🔁 ${data.habit_suggestion.message}`,
        }]);
      }

      if (data.system?.reminder_id || data.intent?.includes("reminder")) fetchReminders();
      if (data.memory_saved) fetchMemory();
    } catch { setBackendOnline(false); }
    setLoading(false);
  };

  // ── Send text ─────────────────────────────────────────────────────────────────
  const send = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setVoiceStatus("idle");
    await sendMessage(msg);
  };

  // ── Send voice ────────────────────────────────────────────────────────────────
  const sendVoice = async (voiceText) => {
    setLoading(true);
    setVoiceStatus("processing");
    setMessages(prev => [...prev, { role: "user", text: voiceText }]);

    try {
      const r    = await fetch(`${API}/chat`, { method: "POST", headers, body: JSON.stringify({ message: voiceText }) });
      const data = await r.json();
      setMessages(prev => [...prev, { role: "assistant", text: data.reply }]);

      // Habit suggestion
      if (data.habit_suggestion) {
        setMessages(prev => [...prev, {
          role: "assistant",
          text: `🔁 ${data.habit_suggestion.message}`,
        }]);
      }

      // Speak reply
      const cleaned = data.reply.replace(/[\u{1F000}-\u{1FFFF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|[\u{FE00}-\u{FEFF}]|[\u{1F900}-\u{1F9FF}]|[\u{1FA00}-\u{1FA6F}]/gu, "").trim();
      const speech = new SpeechSynthesisUtterance(cleaned);
      if (selectedVoice) speech.voice = selectedVoice;
      speech.onend = () => setVoiceStatus("idle");
      setVoiceStatus("speaking");
      window.speechSynthesis.speak(speech);

      if (data.system?.reminder_id || data.intent?.includes("reminder")) fetchReminders();
      if (data.memory_saved) fetchMemory();
    } catch { setBackendOnline(false); setVoiceStatus("idle"); }
    setLoading(false);
  };

  sendVoiceRef.current = sendVoice;

  // ── Speech recognition ────────────────────────────────────────────────────────
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.continuous = false; rec.interimResults = true; rec.lang = "en-US";
    rec.onstart = () => { setListening(true); setVoiceStatus("listening"); };
    rec.onend   = () => {
      setListening(false);
      if (voiceStatusRef.current !== "speaking" && voiceStatusRef.current !== "processing")
        setVoiceStatus("idle");
    };
    rec.onresult = (event) => {
      const last = event.results[event.results.length - 1];
      if (!last.isFinal) {
        let interim = "";
        for (let i = 0; i < event.results.length; i++) interim += event.results[i][0].transcript;
        setInput(interim);
        return;
      }
      const finalText = last[0].transcript.trim();
      sendVoiceRef.current(finalText);
      setInput("");
    };
    rec.onerror = (e) => { if (e.error !== "no-speech" && e.error !== "aborted") setVoiceStatus("idle"); };
    recognitionRef.current = rec;
  }, []);

  // ── Voices ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const load = () => { const v = window.speechSynthesis.getVoices(); if (v.length) setVoices(v); };
    load(); window.speechSynthesis.onvoiceschanged = load;
  }, []);

  const stats = {
    pending:   reminders.filter(r => r.status === "pending").length,
    fired:     reminders.filter(r => r.status === "fired").length,
    cancelled: reminders.filter(r => r.status === "cancelled").length,
  };
  const filtered = reminders.filter(r => filter === "all" || r.status === filter);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div style={{
      width: "100vw", height: "100vh",
      background: "linear-gradient(-45deg, #0d1117, #0f1923, #0d1117, #111827)",
      backgroundSize: "400% 400%", animation: "gradientShift 15s ease infinite",
      color: "#c9d1d9", fontFamily: "'Inter', sans-serif",
      display: "flex", flexDirection: "column",
      padding: "20px", boxSizing: "border-box", overflow: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Syne:wght@800&display=swap');
        @keyframes fadeSlide  { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
        @keyframes toastIn    { from{transform:translateX(100%);opacity:0} to{transform:translateX(0);opacity:1} }
        @keyframes pulseIcon  { 0%,100%{transform:scale(1)} 50%{transform:scale(1.1)} }
        @keyframes micPulse   { 0%{box-shadow:0 0 0 0 rgba(16,185,129,0.6)} 70%{box-shadow:0 0 0 12px rgba(16,185,129,0)} 100%{box-shadow:0 0 0 0 rgba(16,185,129,0)} }
        @keyframes gradientShift { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
        @keyframes wave1 { 0%,100%{height:4px}  50%{height:16px} }
        @keyframes wave2 { 0%,100%{height:8px}  50%{height:24px} }
        @keyframes wave3 { 0%,100%{height:6px}  50%{height:20px} }
        @keyframes wave4 { 0%,100%{height:10px} 50%{height:18px} }
        @keyframes dots  { 0%,20%{opacity:0} 50%{opacity:1} 100%{opacity:0} }
        ::-webkit-scrollbar{width:8px} ::-webkit-scrollbar-track{background:rgba(0,0,0,0.1)} ::-webkit-scrollbar-thumb{background:#30363d;border-radius:4px}
        input:focus{outline:none;border-color:#3b82f6 !important}
      `}</style>

      {/* ── Toast ── */}
      {toast && (
        <div style={{
          position:"fixed", top:"40px", right:"40px", zIndex:3000,
          background:"rgba(13,17,23,0.95)", backdropFilter:"blur(20px)",
          border:"1px solid rgba(59,130,246,0.5)", color:"#fff",
          padding:"24px", borderRadius:"20px", width:"360px",
          display:"flex", alignItems:"flex-start", gap:"20px",
          boxShadow:"0 20px 50px rgba(0,0,0,0.6)",
          animation:"toastIn 0.5s cubic-bezier(0.175,0.885,0.32,1.275)",
        }}>
          <div style={{
            fontSize:"32px", background:"linear-gradient(135deg,#3b82f6,#1d4ed8)",
            padding:"12px", borderRadius:"16px", animation:"pulseIcon 2s infinite",
          }}>⏰</div>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:"11px", fontWeight:800, color:"#3b82f6", letterSpacing:"1.5px", marginBottom:"6px", textTransform:"uppercase" }}>
              NOTIFICATION
            </div>
            <div style={{ fontSize:"15px", fontWeight:700, color:"#fff", lineHeight:"1.5", whiteSpace:"pre-wrap" }}>
              {toast.message}
            </div>
            <button onClick={() => setToast(null)} style={{
              marginTop:"12px", width:"100%", background:"rgba(255,255,255,0.05)", color:"#fff",
              border:"1px solid rgba(255,255,255,0.1)", borderRadius:"8px",
              padding:"8px", fontSize:"12px", fontWeight:600, cursor:"pointer",
            }}
              onMouseOver={e=>e.target.style.background="rgba(255,255,255,0.1)"}
              onMouseOut={e=>e.target.style.background="rgba(255,255,255,0.05)"}
            >
              DISMISS
            </button>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"16px", padding:"0 10px" }}>
        <div style={{ display:"flex", alignItems:"baseline", gap:"12px" }}>
          <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:"26px", fontWeight:800, margin:0, color:"#fff", letterSpacing:"-0.5px" }}>
            ASSISTANT
          </h1>
          <span style={{ fontSize:"11px", fontWeight:700, color:"#484f58", letterSpacing:"1px" }}>REMINDER SYSTEM V2</span>
        </div>
        <div style={{ display:"flex", gap:"10px", alignItems:"center" }}>
          <select
            onChange={e => setSelectedVoice(voices.find(v => v.name === e.target.value) || null)}
            style={{ background:"rgba(255,255,255,0.03)", border:"1px solid #30363d", color:"#8b949e", fontSize:"11px", fontWeight:700, padding:"8px 12px", borderRadius:"8px", cursor:"pointer", outline:"none" }}
          >
            <option value="">🔊 Default Voice</option>
            {voices.filter(v => v.lang.startsWith("en")).map(v => <option key={v.name} value={v.name}>{v.name}</option>)}
          </select>

          <button
            onClick={() => { if (!memoryPanel) fetchMemory(); setMemoryPanel(v => !v); }}
            style={{ background:"rgba(255,255,255,0.03)", border:"1px solid #30363d", color:"#8b949e", fontSize:"11px", fontWeight:700, cursor:"pointer", padding:"8px 16px", borderRadius:"8px" }}
          >
            🧠 MEMORY {memoryPanel ? "▼" : "▲"}
          </button>

          {/* ☀️ Daily summary test button */}
          <button
            onClick={async () => {
              await fetch(`${API}/summary/trigger`, { method:"POST", headers });
            }}
            style={{ background:"rgba(255,255,255,0.03)", border:"1px solid #30363d", color:"#8b949e", fontSize:"11px", fontWeight:700, cursor:"pointer", padding:"8px 16px", borderRadius:"8px" }}
          >
            ☀️ SUMMARY
          </button>
        </div>
      </div>

      {/* ── Status bar ── */}
      <div style={{ fontSize:"11px", color:"#8b949e", display:"flex", gap:"10px", alignItems:"center", marginBottom:"16px", padding:"0 10px" }}>
        <div style={{ width:"8px", height:"8px", borderRadius:"50%", background: backendOnline?"#238636":"#da3633" }} />
        <span>{backendOnline ? "backend online" : "connecting..."}</span>
        <span style={{ opacity:0.3 }}>•</span>
        <span>user: <span style={{ color:"#f0f6fc", fontWeight:600 }}>{userId}</span></span>
        <span style={{ opacity:0.3 }}>•</span>
        <span style={{ color:"#a78bfa" }}>🔁 recurring · 💾 memory · ☀️ daily summary</span>
      </div>

      {/* ── Memory Panel ── */}
      {memoryPanel && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:"15px", marginBottom:"16px", animation:"fadeSlide 0.3s ease-out" }}>
          {["preference","habit","general"].map(cat => (
            <div key={cat} style={{ background:"rgba(22,27,34,0.5)", border:"1px solid rgba(255,255,255,0.05)", borderRadius:"12px", padding:"12px" }}>
              <div style={{ fontSize:"9px", fontWeight:800, color:"#8b949e", marginBottom:"8px", textTransform:"uppercase" }}>{cat}</div>
              {memoryData[cat].length === 0
                ? <div style={{ fontSize:"11px", color:"#30363d" }}>nothing stored yet</div>
                : memoryData[cat].map(item => (
                  <div key={item.id} style={{ fontSize:"11px", padding:"6px", borderBottom:"1px solid rgba(255,255,255,0.02)", color:"#8b949e" }}>
                    {item.text}
                  </div>
                ))
              }
            </div>
          ))}
        </div>
      )}

      {/* ── Main layout ── */}
      <div style={{ display:"flex", gap:"20px", flex:1, minHeight:0 }}>

        {/* ── Left: Chat ── */}
        <div style={{ width:"340px", display:"flex", flexDirection:"column", gap:"16px" }}>
          <div style={{ flex:1, background:"rgba(13,17,23,0.3)", border:"1px solid rgba(48,54,61,0.5)", borderRadius:"12px", display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <div style={{ padding:"12px 16px", background:"rgba(255,255,255,0.02)", borderBottom:"1px solid rgba(48,54,61,0.5)", fontSize:"10px", fontWeight:700, color:"#484f58", letterSpacing:"1px" }}>
              CHAT INTERFACE
            </div>

            <div style={{ flex:1, overflowY:"auto", padding:"20px" }} ref={chatRef}>
              {messages.map((m, i) => (
                <div key={i}>
                  <Bubble role={m.role} text={m.text} selectedVoice={selectedVoice} />
                  {m.role === "assistant" && i === messages.length - 1 && !loading && (
                    <SuggestionChips
                      suggestions={getSuggestions(m.text)}
                      onSelect={(suggestion) => {
                        setInput(suggestion);
                        setTimeout(() => { setInput(""); sendMessage(suggestion); }, 100);
                      }}
                    />
                  )}
                </div>
              ))}

              {loading && (
                <div style={{ display:"flex", marginBottom:"16px" }}>
                  <div style={{ background:"rgba(22,27,34,0.6)", border:"1px solid rgba(255,255,255,0.1)", borderRadius:"12px", padding:"12px 16px", display:"flex", gap:"5px", alignItems:"center" }}>
                    {[0, 0.2, 0.4].map((delay, i) => (
                      <div key={i} style={{ width:"6px", height:"6px", borderRadius:"50%", background:"#8b949e", animation:"dots 1.2s ease-in-out infinite", animationDelay:`${delay}s` }} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div style={{ padding:"16px", borderTop:"1px solid rgba(48,54,61,0.5)", background:"rgba(0,0,0,0.2)" }}>
              <div style={{ display:"flex", gap:"8px", alignItems:"center" }}>
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && send()}
                  placeholder='"Remind me every day at 7am..."'
                  style={{ flex:1, background:"rgba(255,255,255,0.02)", border:"1px solid #30363d", borderRadius:"8px", padding:"10px 14px", color:"#fff", fontSize:"13px", transition:"border-color 0.2s" }}
                />

                {/* Mic */}
                <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:"3px" }}>
                  {voiceStatus === "speaking" && (
                    <div style={{ display:"flex", alignItems:"center", gap:"3px", height:"20px" }}>
                      {["wave1 0.6s ease-in-out infinite","wave2 0.6s ease-in-out infinite 0.1s","wave3 0.6s ease-in-out infinite 0.2s","wave4 0.6s ease-in-out infinite 0.3s","wave1 0.6s ease-in-out infinite 0.15s"].map((anim,i) => (
                        <div key={i} style={{ width:"3px", borderRadius:"2px", background:"#3b82f6", animation:anim }} />
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => { window.speechSynthesis.cancel(); setVoiceStatus("idle"); try { recognitionRef.current?.start(); } catch {} }}
                    style={{
                      background: listening?"#ef4444":voiceStatus==="processing"?"#f59e0b":"#10b981",
                      color:"#fff", border:"none", borderRadius:"50%",
                      width:"38px", height:"38px", fontSize:"15px", cursor:"pointer",
                      animation: listening?"micPulse 1.2s infinite":"none", transition:"background 0.3s",
                    }}
                  >
                    {voiceStatus === "processing" ? "⏳" : "🎤"}
                  </button>
                  <span style={{
                    fontSize:"7px", fontWeight:700, letterSpacing:"0.5px", textTransform:"uppercase",
                    color: voiceStatus==="listening"?"#10b981":voiceStatus==="processing"?"#f59e0b":voiceStatus==="speaking"?"#3b82f6":"#484f58",
                  }}>{voiceStatus}</span>
                </div>

                <button onClick={send} style={{ background:"#2563eb", color:"#fff", border:"none", borderRadius:"8px", padding:"0 16px", height:"38px", fontWeight:600, fontSize:"13px", cursor:"pointer", whiteSpace:"nowrap" }}>
                  Send →
                </button>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:"10px" }}>
            {[
              { label:"PENDING",   val:stats.pending,   color:"#3b82f6" },
              { label:"FIRED",     val:stats.fired,     color:"#238636" },
              { label:"CANCELLED", val:stats.cancelled, color:"#da3633" },
            ].map(s => (
              <div key={s.label} style={{ background:"rgba(13,17,23,0.5)", border:"1px solid rgba(48,54,61,0.5)", borderRadius:"8px", padding:"12px", textAlign:"center" }}>
                <div style={{ fontSize:"18px", fontWeight:800, color:s.color }}>{s.val}</div>
                <div style={{ fontSize:"9px", fontWeight:700, color:"#484f58", marginTop:"4px", letterSpacing:"0.5px" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right: Reminders ── */}
        <div style={{ flex:1, background:"rgba(13,17,23,0.3)", border:"1px solid rgba(48,54,61,0.5)", borderRadius:"12px", display:"flex", flexDirection:"column", overflow:"hidden" }}>
          <div style={{ padding:"12px 20px", background:"rgba(255,255,255,0.02)", borderBottom:"1px solid rgba(48,54,61,0.5)", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <div style={{ display:"flex", alignItems:"baseline", gap:"10px" }}>
              <span style={{ fontSize:"15px", fontWeight:700, color:"#f0f6fc" }}>Reminders</span>
              <span style={{ fontSize:"11px", color:"#484f58" }}>{stats.pending} active tasks</span>
            </div>
            <div style={{ display:"flex", gap:"4px", background:"#0d1117", padding:"3px", borderRadius:"6px" }}>
              {["all","pending","fired","cancelled"].map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{
                  background: filter===f?"#21262d":"transparent", border:"none",
                  color: filter===f?"#fff":"#8b949e",
                  fontSize:"10px", fontWeight:700, padding:"5px 12px", borderRadius:"4px",
                  cursor:"pointer", textTransform:"uppercase",
                }}>
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div style={{ flex:1, overflowY:"auto" }}>
            {filtered.length === 0
              ? <div style={{ padding:"80px", textAlign:"center", color:"#484f58", fontSize:"14px" }}>No reminders found.</div>
              : filtered.map(r => <ReminderCard key={r.id} reminder={r} onCancel={cancelReminder} />)
            }
          </div>
        </div>
      </div>
    </div>
  );
}