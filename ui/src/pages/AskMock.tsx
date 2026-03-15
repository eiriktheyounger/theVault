// ui/src/pages/AskMock.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Link } from "react-router-dom";

type Status = "ok" | "fail" | "unknown";
type Mode = "fast" | "chat";
type Msg = { id: number; role: "user" | "assistant"; text: string; ts: string };

function Dot({ status, label }: { status: Status; label: string }) {
  const color = useMemo(() => {
    if (status === "ok") return "bg-emerald-500";
    if (status === "fail") return "bg-rose-500";
    return "bg-zinc-500";
  }, [status]);
  return (
    <div className="flex items-center gap-1" title={`${label}: ${status}`}>
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="text-xs text-zinc-300">{label}</span>
    </div>
  );
}

function PinDot() {
  return (
    <span className="inline-block h-2.5 w-2.5 rounded-full bg-indigo-400 shrink-0 mt-1" title="Pinned" />
  );
}

export default function AskMock() {
  // Hide app chrome at top
  useEffect(() => {
    const style = document.createElement("style");
    style.id = "hide-chrome-on-mock";
    style.textContent = `
      header, [role="banner"], .sticky.top-0, .fixed.top-0, .bg-red-100, .bg-amber-100 { display:none!important; }
      body { padding-top:0!important; }
    `;
    document.head.appendChild(style);
    return () => document.getElementById("hide-chrome-on-mock")?.remove();
  }, []);

  // Demo statuses
  const [llmStatus] = useState<Status>("ok");
  const [ragStatus] = useState<Status>("unknown");
  const [contractStatus] = useState<Status>("ok");

  // ---- Mode + UI state ----
  const [mode, setMode] = useState<Mode>("fast");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showHistory, setShowHistory] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // ---- Fast data ----
  const pinnedFast = [
    { id: 1, text: "How do I rebuild the index?" },
    { id: 2, text: "Summarize latest ingest report" },
    { id: 3, text: "Where are my Plaud transcripts?" },
  ];
  const recentFast = [
    { id: 4, text: "What changed in last update?" },
    { id: 5, text: "Show logs for deep model" },
    { id: 6, text: "Explain contract mismatch banner" },
    { id: 7, text: "List last 10 ingested files" },
    { id: 8, text: "Why did deep fallback yesterday?" },
  ];

  // ---- Chat data ----
  const [chat, setChat] = useState<Msg[]>([
    {
      id: 1,
      role: "assistant",
      text: "Chat Mode ready. This is a mock thread—messages will append here.",
      ts: new Date().toLocaleTimeString(),
    },
  ]);
  const [draft, setDraft] = useState("");
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const pinnedChat = [
    { id: 101, text: "Daily status: summarize yesterday" },
    { id: 102, text: "List open action items" },
    { id: 103, text: "Prep talking points for 1:1" },
    { id: 104, text: "Explain latest ingest errors" },
    { id: 105, text: "Generate Type A note outline" },
  ];
  const recentChat = Array.from({ length: 10 }).map((_, i) => ({
    id: 200 + i,
    text: `Recent chat #${i + 1}`,
  }));

  // ⛑️ Only scroll on NEW MESSAGES, not when switching modes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  function sendMessage() {
    const text = draft.trim();
    if (!text) return;
    const ts = new Date().toLocaleTimeString();
    const next: Msg[] = [
      ...chat,
      { id: Date.now(), role: "user", text, ts },
      {
        id: Date.now() + 1,
        role: "assistant",
        text:
          "Mock reply (no backend yet). In the real app, this will stream a grounded answer with sources.",
        ts,
      },
    ];
    setChat(next);
    setDraft("");
  }

  return (
    // Full-screen overlay (ensures top chrome never affects layout)
    <div className="fixed inset-0 bg-zinc-950 text-zinc-100 flex flex-col" style={{ color: "#e5e7eb" }}>
      {/* Tiny home pill */}
      <Link
        to="/"
        className="absolute top-3 left-3 z-20 rounded-md px-2 py-1 text-sm font-semibold bg-zinc-800/70 hover:bg-zinc-700/70"
        title="Home"
      >
        TheVault
      </Link>

      {/* CONTENT (pad bottom for fixed bottom bar) */}
      <div className="flex-1 overflow-auto pb-16">
        <div className="mx-auto w-full max-w-[1400px] px-4">
          {/* Mode toggle */}
          <div className="pt-6 pb-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-2 py-1">
              <button
                aria-pressed={mode === "fast"}
                onClick={() => setMode("fast")}
                className={`px-3 py-1 rounded-full text-sm transition ${
                  mode === "fast" ? "bg-emerald-600 text-white" : "text-zinc-300 hover:text-white"
                }`}
              >
                Fast Mode
              </button>
              <button
                aria-pressed={mode === "chat"}
                onClick={() => setMode("chat")}
                className={`px-3 py-1 rounded-full text-sm transition ${
                  mode === "chat" ? "bg-blue-600 text-white" : "text-zinc-300 hover:text-white"
                }`}
              >
                Chat Mode
              </button>
            </div>
          </div>

          {/* Main + History row */}
          <div className="flex items-start gap-6">
            {/* MAIN */}
            <div className="flex-1 min-w-0">
              {mode === "fast" ? (
                <>
                  {/* FAST INPUTS */}
                  <label className="block text-sm font-semibold mb-1 text-zinc-200">Question</label>
                  <input
                    type="text"
                    placeholder="Type your question…"
                    className="w-full rounded-md border border-zinc-700 bg-white text-zinc-900 placeholder-zinc-500 px-3 py-2"
                  />
                  <div className="mt-2">
                    <button
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="text-xs text-indigo-300 hover:text-indigo-200 underline"
                    >
                      {showAdvanced ? "Hide advanced prompt" : "Show advanced prompt"}
                    </button>
                    {showAdvanced && (
                      <div className="mt-2">
                        <textarea
                          placeholder="System prompt / options (non-risky changes only)"
                          className="w-full rounded-md border border-zinc-700 bg-white text-zinc-900 placeholder-zinc-500 px-3 py-2 text-sm"
                          rows={3}
                        />
                      </div>
                    )}
                  </div>

                  {/* FAST RESPONSE */}
                  <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">Response</h3>
                      <span className="text-xs text-zinc-400">
                        Mode: <strong className="text-zinc-200">Fast</strong>
                      </span>
                    </div>
                    <div className="mt-3 space-y-3 text-sm">
                      <p>
                        <span className="font-semibold text-zinc-200">Short Summary:</span>{" "}
                        Example 1–3 line summary here.
                      </p>
                      <p className="text-zinc-200 font-semibold">Long Summary:</p>
                      <div className="text-zinc-300">Example longer explanation goes here, up to two paragraphs.</div>
                      <div>
                        <span className="font-semibold text-zinc-200">Citations:</span>{" "}
                        <span className="text-zinc-300">Doc1.md, Doc2.pdf</span>
                      </div>
                      <div>
                        <span className="font-semibold text-zinc-200">Fast Answer:</span>{" "}
                        <span className="text-zinc-300">Direct, minimal answer optimized for Fast Mode.</span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* CHAT THREAD */}
                  <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                    <div className="text-xs text-zinc-400 px-1 pb-2">
                      Mode: <strong className="text-zinc-200">Chat</strong>
                    </div>
                    <div className="h-[56vh] overflow-auto px-1 space-y-3">
                      {chat.map((m) => (
                        <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                          <div
                            className={`max-w-[80%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                              m.role === "user" ? "bg-emerald-700 text-white" : "bg-zinc-800 text-zinc-100"
                            }`}
                          >
                            <div className="text-[10px] uppercase tracking-wide opacity-70 mb-1">
                              {m.role === "user" ? "You" : "Assistant"} · {m.ts}
                            </div>
                            <div className="whitespace-pre-wrap">{m.text}</div>
                          </div>
                        </div>
                      ))}
                      <div ref={chatEndRef} />
                    </div>

                    {/* CHAT INPUT */}
                    <div className="mt-3 flex items-end gap-2">
                      <textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={2}
                        placeholder="Message…"
                        className="flex-1 rounded-md border border-zinc-700 bg-white text-zinc-900 placeholder-zinc-500 px-3 py-2 text-sm"
                      />
                      <button
                        onClick={sendMessage}
                        className="rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold px-3 py-2"
                      >
                        Send
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* HISTORY (auto-height) */}
            {showHistory && (
              <aside className="w-[340px] self-start">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-sm font-semibold">History</h2>
                  <button
                    onClick={() => setShowHistory(false)}
                    className="text-xs text-zinc-300 hover:text-white underline"
                  >
                    Hide
                  </button>
                </div>

                {/* Pinned */}
                <div className="text-xs text-zinc-400 mb-1">Pinned</div>
                <ul className="space-y-2 mb-4">
                  {(mode === "fast" ? pinnedFast : pinnedChat)
                    .slice(0, mode === "fast" ? 3 : 5)
                    .map((p) => (
                      <li
                        key={p.id}
                        className="rounded-md border border-zinc-800 bg-zinc-950 p-2 flex items-start gap-2 text-sm"
                      >
                        <PinDot />
                        <span className="text-zinc-200">{p.text}</span>
                      </li>
                    ))}
                </ul>

                {/* Last N */}
                <div className="text-xs text-zinc-400 mb-1">{mode === "fast" ? "Last 5" : "Last 10"}</div>
                <ul className="space-y-2">
                  {(mode === "fast" ? recentFast : recentChat)
                    .slice(0, mode === "fast" ? 5 : 10)
                    .map((r) => (
                      <li key={r.id} className="rounded-md border border-zinc-800 bg-zinc-950 p-2 text-sm">
                        {r.text}
                      </li>
                    ))}
                </ul>
              </aside>
            )}
          </div>
        </div>
      </div>

      {/* Error banner just ABOVE bottom bar */}
      {errorMsg && (
        <div className="fixed left-0 right-0 bottom-10 px-4">
          <div className="mx-auto w-full max-w-[1400px] rounded-md border border-amber-700 bg-amber-900/40 text-amber-200 p-2 flex items-start justify-between">
            <div className="text-sm">{errorMsg}</div>
            <button onClick={() => setErrorMsg(null)} className="text-xs underline hover:text-amber-100 ml-4">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Bottom bar */}
      <div className="fixed left-0 right-0 bottom-0 border-t border-zinc-800 bg-zinc-900/95 px-3 py-2">
        <div className="mx-auto w-full max-w-[1400px] flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Dot status={llmStatus} label="LLM" />
            <Dot status={ragStatus} label="RAG" />
            <Dot status={contractStatus} label="Contract" />
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <NavLink to="/ask" className="text-zinc-300 hover:text-white">
              Ask
            </NavLink>
            <NavLink to="/index" className="text-zinc-300 hover:text-white">
              Index
            </NavLink>
            <NavLink to="/logs" className="text-zinc-300 hover:text-white">
              Logs
            </NavLink>
            <NavLink to="/settings" className="text-zinc-300 hover:text-white">
              Settings
            </NavLink>
            <NavLink to="/mock" className="font-semibold text-indigo-300 hover:text-indigo-200">
              Mock
            </NavLink>
          </nav>
        </div>
      </div>

      {/* Reopen history */}
      {!showHistory && (
        <button
          onClick={() => setShowHistory(true)}
          className="fixed right-3 bottom-14 z-20 rounded-md bg-zinc-800/80 hover:bg-zinc-700/80 px-2 py-1 text-xs text-zinc-200 border border-zinc-700"
          title="Show history"
        >
          Show History
        </button>
      )}
    </div>
  );
}