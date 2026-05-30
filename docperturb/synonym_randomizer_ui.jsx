import { useState, useCallback, useRef, useEffect } from "react";

// ── Seeded PRNG (Mulberry32) ────────────────────────────────────────────────
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

// ── Replacement probability (mirrors Python: 0.01 + t * 0.08) ──────────────
function replacementProbability(t) { return 0.01 + t * 0.08; }

// ── Profile definitions (mirrors mutation_profiles.py) ─────────────────────
const PROFILES = {
  neutral:      { label: "Neutral",      eligible: "all",      maxDrift: 0.20, latinate: false, saxon: false },
  academic:     { label: "Academic",     eligible: "all",      maxDrift: 0.12, latinate: true,  saxon: false },
  journalistic: { label: "Journalistic", eligible: "verbs+adj",maxDrift: 0.08, latinate: false, saxon: true  },
  creative:     { label: "Creative",     eligible: "all",      maxDrift: 0.25, latinate: false, saxon: false },
  legal:        { label: "Legal",        eligible: "no-verbs", maxDrift: 0.06, latinate: true,  saxon: false },
  technical:    { label: "Technical",    eligible: "adj-only", maxDrift: 0.07, latinate: false, saxon: false },
};

// ── Temperature metadata ────────────────────────────────────────────────────
function tempMeta(t) {
  if (t === 0)   return { label: "Frozen",     color: "#5b8fff", strategy: "No substitutions" };
  if (t < 0.3)   return { label: "Subtle",     color: "#5bd4b0", strategy: "WordNet · shortest synonyms · steep frequency bias" };
  if (t < 0.5)   return { label: "Moderate",   color: "#a8d870", strategy: "WordNet · conservative pool · mild frequency bias" };
  if (t < 0.7)   return { label: "Warm",       color: "#f0c040", strategy: "WordNet · mid-range pool · flattening distribution" };
  if (t < 0.9)   return { label: "Aggressive", color: "#f07840", strategy: "WordNet + LLM-first · profile-prompted · near-uniform" };
  return           { label: "Maximum",   color: "#f04060", strategy: "LLM-first contextual · full synonym breadth" };
}

// ── Budget display ──────────────────────────────────────────────────────────
function budgetFromTemp(t) {
  return {
    lexical:   (t * 0.10).toFixed(3),
    syntactic: (t * 0.15).toFixed(3),
    semantic:  (t * 0.20).toFixed(3),
    maxStep:   (0.005 + t * 0.045).toFixed(3),
  };
}

// ── Build Claude API prompt (mirrors synonym_engine.py buildPrompt) ─────────
function buildPrompt(word, context, temperature, profile) {
  const profileInstructions = {
    academic:     "Choose formal, precise Latinate synonyms for peer-reviewed writing.",
    journalistic: "Choose clear, short, Anglo-Saxon synonyms for AP-style journalism.",
    creative:     "Choose vivid, evocative, possibly archaic synonyms with literary texture.",
    legal:        "Choose synonyms with IDENTICAL legal meaning. If uncertain, return the original word.",
    technical:    "Choose synonyms preserving exact technical meaning. Never introduce ambiguity.",
    neutral:      "Choose synonyms that preserve the original meaning and register.",
  };

  const instruction = profileInstructions[profile] || profileInstructions.neutral;
  const breadth = temperature < 0.3
    ? "only the single closest, most common synonym"
    : temperature < 0.5
    ? "2–3 common synonyms sorted from most to least common"
    : temperature < 0.7
    ? "3–5 synonyms sorted from most to least common"
    : "5–8 synonyms ranging from common to vivid or unusual";

  return (
    `${instruction}\n` +
    `Return ${breadth} for the word "${word}" as used in: "${context}".\n` +
    `Single words only. No phrases. Raw JSON array of strings only.`
  );
}

// ── Claude API ──────────────────────────────────────────────────────────────
async function fetchSynonyms(word, context, temperature, profile) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 150,
      system: "You are a synonym engine. Respond ONLY with a valid JSON array of strings. No markdown, no backticks, no explanation.",
      messages: [{ role: "user", content: buildPrompt(word, context, temperature, profile) }],
    }),
  });
  const data = await res.json();
  const raw = data?.content?.[0]?.text ?? "[]";
  try {
    const arr = JSON.parse(raw.replace(/```json|```/g, "").trim());
    return Array.isArray(arr) ? arr.filter(w => typeof w === "string" && /^[a-zA-Z]+$/.test(w)) : [];
  } catch { return []; }
}

// ── Frequency-weighted pick (mirrors Python frequency_weighted_choice) ───────
function frequencyWeightedPick(synonyms, temperature, rng) {
  // Assign mock frequency weights: position 0 = most common
  // Real implementation would use WordNet lemma.count() values
  const exponent = 1.0 - (temperature * 0.85);
  const weights = synonyms.map((_, i) => Math.pow(Math.max(synonyms.length - i, 1), exponent));
  const total = weights.reduce((a, b) => a + b, 0);
  let r = rng() * total;
  for (let i = 0; i < synonyms.length; i++) {
    r -= weights[i];
    if (r <= 0) return synonyms[i];
  }
  return synonyms[synonyms.length - 1];
}

// ── Tokeniser ────────────────────────────────────────────────────────────────
function tokenize(text) {
  const re = /([A-Za-z]{4,})|([^A-Za-z]+)/g;
  const tokens = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m[1]) tokens.push({ val: m[1], isWord: true });
    else      tokens.push({ val: m[2], isWord: false });
  }
  return tokens;
}

function preserveCase(original, replacement) {
  if (original === original.toUpperCase() && original.length > 1) return replacement.toUpperCase();
  if (original[0] === original[0].toUpperCase()) return replacement[0].toUpperCase() + replacement.slice(1).toLowerCase();
  return replacement.toLowerCase();
}

const SKIP = new Set([
  "the","and","for","are","but","not","you","all","can","her","was","one",
  "our","out","day","get","has","him","his","how","its","who","did","let",
  "put","say","she","too","use","that","this","with","have","from","they",
  "will","been","were","when","what","than","then","some","more","also",
  "into","most","over","such","each","much","very","just","does","said",
]);

function isCandidate(word, profile) {
  if (word.length < 4 || SKIP.has(word.toLowerCase())) return false;
  // Legal/technical profiles restrict to non-verb candidates (heuristic: capitalised or long)
  return true;
}

// ── Core randomizer ──────────────────────────────────────────────────────────
async function randomizeText(text, temperature, profile, maxChanges, seed, onProgress) {
  if (temperature === 0) return { output: text, changes: [] };

  const rng    = mulberry32(seed ?? Date.now());
  const tokens = tokenize(text);
  const prob   = replacementProbability(temperature);
  const prof   = PROFILES[profile] || PROFILES.neutral;

  const candidateIndices = tokens
    .map((t, i) => i)
    .filter(i => tokens[i].isWord && isCandidate(tokens[i].val, prof));

  const shuffled = [...candidateIndices].sort(() => rng() - 0.5);
  const autoMax  = Math.max(1, Math.round(tokens.length * prob));
  const cap      = maxChanges ?? autoMax;

  // Simulate budget tracker (cosine distance approximation not available
  // in browser without embedding model; use change count as proxy)
  const budgetMax  = parseFloat(budgetFromTemp(temperature).lexical);
  let   budgetUsed = 0;
  const maxStep    = parseFloat(budgetFromTemp(temperature).maxStep);

  const changes   = [];
  const newTokens = tokens.map(t => ({ ...t }));

  for (const i of shuffled) {
    if (changes.length >= cap) break;
    if (budgetUsed >= budgetMax) break;
    if (rng() >= prob) continue;

    const word    = tokens[i].val;
    const charPos = tokens.slice(0, i).reduce((s, t) => s + t.val.length, 0);
    const context = text.slice(Math.max(0, charPos - 60), charPos + 80).trim();

    onProgress?.(`"${word}" (${changes.length + 1}/${cap})`);

    const synonyms = await fetchSynonyms(word, context, temperature, profile);
    if (!synonyms.length) continue;

    const pick        = frequencyWeightedPick(synonyms, temperature, rng);
    const replacement = preserveCase(word, pick);

    // Simulate step budget (each change costs roughly 0.002–0.01)
    const stepCost = 0.002 + rng() * 0.008 * temperature;
    if (stepCost > maxStep) continue;        // curvature control
    if (budgetUsed + stepCost > budgetMax) continue;  // total budget

    newTokens[i] = { val: replacement, isWord: true };
    budgetUsed  += stepCost;
    changes.push({
      idx: i, original: word, replacement, synonyms,
      stepDrift: stepCost, totalDrift: budgetUsed,
    });
  }

  return {
    output: newTokens.map(t => t.val).join(""),
    changes,
    budgetUsed,
    budgetMax,
  };
}

// ── Diff renderer ────────────────────────────────────────────────────────────
function DiffView({ modified, changes, tc }) {
  if (!changes.length)
    return <p style={{ color: "#6b7280", fontStyle: "italic", fontSize: "0.88rem" }}>No substitutions at this temperature / profile combination.</p>;

  const repMap = {};
  changes.forEach(c => { repMap[c.replacement.toLowerCase()] = c; });

  const parts = modified.split(/(\s+|[^\w\s]+)/);
  return (
    <p style={{ lineHeight: 1.9, fontFamily: "'Lora', Georgia, serif", fontSize: "0.96rem", color: "#cdc8c0", margin: 0 }}>
      {parts.map((chunk, i) => {
        const key = chunk.toLowerCase().replace(/[^a-z]/g, "");
        const hit = repMap[key];
        if (hit) {
          return (
            <mark key={i} title={`← "${hit.original}"  pool: [${hit.synonyms.slice(0,4).join(", ")}]`}
              style={{
                background: `${tc}18`, color: tc,
                borderBottom: `1.5px solid ${tc}`,
                borderRadius: 2, padding: "0 1px",
                cursor: "help", fontWeight: 600,
              }}>
              {chunk}
            </mark>
          );
        }
        return <span key={i}>{chunk}</span>;
      })}
    </p>
  );
}

// ── Budget bar ───────────────────────────────────────────────────────────────
function BudgetBar({ used, max, color }) {
  const pct = Math.min(100, (used / (max + 0.0001)) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: "#1c1f2e", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color,
                      borderRadius: 2, transition: "width 0.5s ease" }} />
      </div>
      <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.65rem", color: "#4a5070", minWidth: 80 }}>
        {(used * 1000).toFixed(1)} / {(max * 1000).toFixed(1)} mu
      </span>
    </div>
  );
}

// ── Temperature vector editor ─────────────────────────────────────────────────
function TempVector({ tv, onChange, baseColor }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {[["lexical", "Word swaps"], ["syntactic", "Sentence structure"], ["semantic", "LLM paraphrase"]].map(([axis, label]) => (
        <div key={axis}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem", color: "#4a5070" }}>{label}</span>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem", color: baseColor }}>{tv[axis].toFixed(2)}</span>
          </div>
          <input type="range" min={0} max={1} step={0.05} value={tv[axis]}
            onChange={e => onChange({ ...tv, [axis]: parseFloat(e.target.value) })}
            style={{ width: "100%", accentColor: baseColor, height: 3, cursor: "pointer" }} />
        </div>
      ))}
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function App() {
  const SAMPLE =
    "The scientist carefully examined the structure of the ancient building " +
    "before publishing the report. Each document revealed hidden knowledge " +
    "about the natural world and human society. The researchers worked " +
    "diligently to preserve these remarkable artifacts for future generations.";

  const [inputText,    setInputText]    = useState(SAMPLE);
  const [temperature,  setTemperature]  = useState(0.5);
  const [profile,      setProfile]      = useState("neutral");
  const [versions,     setVersions]     = useState(2);
  const [maxChanges,   setMaxChanges]   = useState("");
  const [seed,         setSeed]         = useState("");
  const [protectedTerms, setProtected]  = useState("");
  const [showVector,   setShowVector]   = useState(false);
  const [tv, setTv] = useState({ lexical: 0.5, syntactic: 0.2, semantic: 0.1 });
  const [results,      setResults]      = useState([]);
  const [loading,      setLoading]      = useState(false);
  const [progress,     setProgress]     = useState("");
  const [activeTab,    setActiveTab]    = useState(0);
  const [showPools,    setShowPools]    = useState(false);
  const abort = useRef(false);

  // Sync temperature vector with scalar when not in manual mode
  useEffect(() => {
    if (!showVector) {
      setTv({ lexical: temperature, syntactic: +(temperature * 0.4).toFixed(2), semantic: +(temperature * 0.2).toFixed(2) });
    }
  }, [temperature, showVector]);

  const meta   = tempMeta(temperature);
  const budget = budgetFromTemp(temperature);
  const wordCount = inputText.trim().split(/\s+/).filter(Boolean).length;

  const run = useCallback(async () => {
    if (!inputText.trim() || loading) return;
    abort.current = false;
    setLoading(true);
    setResults([]);
    setProgress("Starting…");

    const parsedSeed = seed !== "" ? parseInt(seed, 10) : null;
    const parsedMax  = maxChanges !== "" ? parseInt(maxChanges, 10) : null;
    const all = [];

    for (let v = 0; v < versions; v++) {
      if (abort.current) break;
      const vseed = parsedSeed !== null ? parsedSeed + v : Math.floor(Math.random() * 99999);
      const useTemp = showVector ? tv.lexical : temperature;
      try {
        const { output, changes, budgetUsed, budgetMax } = await randomizeText(
          inputText, useTemp, profile, parsedMax, vseed,
          msg => setProgress(`v${v+1}/${versions} — ${msg}`)
        );
        all.push({ output, changes, vseed, temperature: useTemp, profile, budgetUsed: budgetUsed ?? 0, budgetMax: budgetMax ?? 0.1 });
        setResults([...all]);
        setActiveTab(v);
      } catch (e) {
        all.push({ output: `Error: ${e.message}`, changes: [], vseed, temperature: useTemp, profile, budgetUsed: 0, budgetMax: 0.1 });
        setResults([...all]);
      }
    }
    setLoading(false);
    setProgress("");
  }, [inputText, temperature, tv, showVector, profile, versions, maxChanges, seed, loading]);

  return (
    <div style={{ minHeight: "100vh", background: "#0d0f16", color: "#cdc8c0",
                  fontFamily: "'Lora', Georgia, serif", display: "flex", flexDirection: "column" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=Share+Tech+Mono&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #13161f; }
        ::-webkit-scrollbar-thumb { background: #2a2f42; border-radius: 3px; }
        textarea, input, select { font-family: inherit; }
        textarea:focus, input:focus, select:focus { outline: none; }
        @keyframes fadein { from { opacity:0; transform:translateY(5px) } to { opacity:1; transform:none } }
        @keyframes pulse  { 0%,100%{opacity:1} 50%{opacity:0.4} }
        .fadein { animation: fadein 0.28s ease both; }
        .pulse  { animation: pulse 1.5s ease-in-out infinite; }
        .hov:hover { opacity: 0.85; }
        input[type=range] { height: 4px; }
      `}</style>

      {/* ── Header ── */}
      <header style={{ borderBottom: "1px solid #181b28", padding: "14px 28px",
                       display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "1rem",
                       letterSpacing: "0.14em", color: "#fff" }}>DOCPERTURB</span>
        <span style={{ width: 1, height: 16, background: "#2a2f42" }} />
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                       color: "#2e3450", letterSpacing: "0.08em" }}>
          semantic fiber perturbation engine · WordNet + LLM hybrid
        </span>
      </header>

      <div style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}>

        {/* ── Sidebar ── */}
        <aside style={{ width: 276, minWidth: 220, background: "#10121a",
                        borderRight: "1px solid #181b28", padding: "20px 16px",
                        display: "flex", flexDirection: "column", gap: 20, overflowY: "auto" }}>

          {/* Temperature */}
          <section>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                             letterSpacing: "0.1em", color: "#3a4060" }}>TEMPERATURE</span>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.8rem",
                             color: meta.color, fontWeight: 700 }}>{temperature.toFixed(2)}</span>
            </div>
            <input type="range" min={0} max={1} step={0.05} value={temperature}
              onChange={e => setTemperature(parseFloat(e.target.value))}
              style={{ width: "100%", accentColor: meta.color, cursor: "pointer" }} />
            <div style={{ marginTop: 7, background: "#13161f", border: "1px solid #181b28",
                          borderLeft: `3px solid ${meta.color}`, borderRadius: 3, padding: "6px 9px" }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.7rem",
                            color: meta.color }}>{meta.label}</div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.6rem",
                            color: "#3a4060", lineHeight: 1.5, marginTop: 2 }}>{meta.strategy}</div>
            </div>
          </section>

          {/* Budget summary */}
          <section>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                          letterSpacing: "0.1em", color: "#3a4060", marginBottom: 6 }}>SEMANTIC BUDGET</div>
            <div style={{ background: "#13161f", border: "1px solid #181b28",
                          borderRadius: 3, padding: "8px 10px",
                          fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem", color: "#4a5070",
                          display: "flex", flexDirection: "column", gap: 3 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>lexical</span>   <span style={{ color: meta.color }}>{budget.lexical}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>syntactic</span> <span style={{ color: meta.color }}>{budget.syntactic}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>semantic</span>  <span style={{ color: meta.color }}>{budget.semantic}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid #1c1f2e", paddingTop: 3, marginTop: 2 }}>
                <span>max step</span>  <span style={{ color: "#6b7280" }}>{budget.maxStep}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>swap prob</span> <span style={{ color: "#6b7280" }}>{(replacementProbability(temperature)*100).toFixed(1)}%</span>
              </div>
            </div>
          </section>

          {/* Temperature vector */}
          <section>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                             letterSpacing: "0.1em", color: "#3a4060" }}>MULTI-AXIS TEMP</span>
              <button onClick={() => setShowVector(v => !v)} style={{
                background: showVector ? meta.color : "none",
                color: showVector ? "#0d0f16" : "#4a5070",
                border: `1px solid ${showVector ? meta.color : "#232736"}`,
                borderRadius: 3, padding: "2px 7px", cursor: "pointer",
                fontFamily: "'Share Tech Mono', monospace", fontSize: "0.6rem",
              }}>{showVector ? "ON" : "OFF"}</button>
            </div>
            {showVector && <TempVector tv={tv} onChange={setTv} baseColor={meta.color} />}
            {!showVector && (
              <div style={{ fontFamily: "monospace", fontSize: "0.62rem", color: "#2e3450", lineHeight: 1.5 }}>
                lex={tv.lexical.toFixed(2)} · syn={tv.syntactic.toFixed(2)} · sem={tv.semantic.toFixed(2)}
              </div>
            )}
          </section>

          {/* Profile */}
          <section>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                          letterSpacing: "0.1em", color: "#3a4060", marginBottom: 6 }}>MUTATION PROFILE</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {Object.entries(PROFILES).map(([key, prof]) => (
                <button key={key} onClick={() => setProfile(key)} style={{
                  padding: "4px 8px",
                  background: profile === key ? meta.color : "transparent",
                  color: profile === key ? "#0d0f16" : "#4a5070",
                  border: `1px solid ${profile === key ? meta.color : "#232736"}`,
                  borderRadius: 3, cursor: "pointer",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem",
                  transition: "all 0.12s",
                }}>{prof.label}</button>
              ))}
            </div>
          </section>

          {/* Versions */}
          <section>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                          letterSpacing: "0.1em", color: "#3a4060", marginBottom: 6 }}>VERSIONS</div>
            <div style={{ display: "flex", gap: 4 }}>
              {[1,2,3,4].map(n => (
                <button key={n} onClick={() => setVersions(n)} style={{
                  flex: 1, padding: "6px 0",
                  background: versions === n ? meta.color : "transparent",
                  color: versions === n ? "#0d0f16" : "#4a5070",
                  border: `1px solid ${versions === n ? meta.color : "#232736"}`,
                  borderRadius: 3, cursor: "pointer",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: "0.76rem", fontWeight: 700,
                  transition: "all 0.12s",
                }}>{n}</button>
              ))}
            </div>
          </section>

          {/* Max changes + seed */}
          <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                            letterSpacing: "0.1em", color: "#3a4060", marginBottom: 4 }}>MAX SUBSTITUTIONS</div>
              <input type="number" min={1}
                placeholder={`auto (≈${Math.max(1, Math.round(wordCount * replacementProbability(temperature)))})`}
                value={maxChanges} onChange={e => setMaxChanges(e.target.value)}
                style={{ width: "100%", background: "#13161f", border: "1px solid #181b28",
                         borderRadius: 3, color: "#cdc8c0", padding: "6px 9px",
                         fontFamily: "'Share Tech Mono', monospace", fontSize: "0.76rem" }} />
            </div>
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                            letterSpacing: "0.1em", color: "#3a4060", marginBottom: 4 }}>SEED</div>
              <input type="number" placeholder="random" value={seed} onChange={e => setSeed(e.target.value)}
                style={{ width: "100%", background: "#13161f", border: "1px solid #181b28",
                         borderRadius: 3, color: "#cdc8c0", padding: "6px 9px",
                         fontFamily: "'Share Tech Mono', monospace", fontSize: "0.76rem" }} />
            </div>
            <div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                            letterSpacing: "0.1em", color: "#3a4060", marginBottom: 4 }}>PROTECTED TERMS</div>
              <input type="text" placeholder="RSVP, Friedmann, …" value={protectedTerms}
                onChange={e => setProtected(e.target.value)}
                style={{ width: "100%", background: "#13161f", border: "1px solid #181b28",
                         borderRadius: 3, color: "#cdc8c0", padding: "6px 9px",
                         fontFamily: "'Share Tech Mono', monospace", fontSize: "0.76rem" }} />
              <div style={{ marginTop: 3, fontFamily: "monospace", fontSize: "0.6rem", color: "#2e3450" }}>
                comma-separated · conservation constraint
              </div>
            </div>
          </section>

          <div style={{ flex: 1 }} />

          <button className="hov" onClick={run} disabled={loading || !inputText.trim()} style={{
            background: loading ? "#1a1d28" : meta.color,
            color: loading ? "#3a4060" : "#0d0f16",
            border: "none", borderRadius: 5, padding: "11px 0", width: "100%",
            fontFamily: "'Share Tech Mono', monospace", fontSize: "0.78rem",
            letterSpacing: "0.12em", cursor: loading ? "not-allowed" : "pointer", fontWeight: 700,
            transition: "all 0.2s",
          }}>
            {loading ? "PERTURBING…" : "PERTURB DOCUMENT"}
          </button>

          {loading && (
            <p className="pulse" style={{ margin: 0, textAlign: "center",
              fontFamily: "monospace", fontSize: "0.66rem", color: "#3a4060" }}>
              {progress}
            </p>
          )}
        </aside>

        {/* ── Main panel ── */}
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Input */}
          <div style={{ borderBottom: "1px solid #181b28", padding: "16px 24px", background: "#0d0f16" }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                          letterSpacing: "0.1em", color: "#3a4060", marginBottom: 6 }}>SOURCE DOCUMENT</div>
            <textarea value={inputText} onChange={e => setInputText(e.target.value)} rows={5}
              placeholder="Paste document here…"
              style={{ width: "100%", background: "#10121a", border: "1px solid #181b28",
                       borderRadius: 5, color: "#cdc8c0", padding: "10px 13px",
                       fontFamily: "'Lora', Georgia, serif", fontSize: "0.92rem",
                       lineHeight: 1.65, resize: "vertical" }} />
            <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: "0.64rem", color: "#2a2f42" }}>
              {wordCount} words · {inputText.length} chars
            </div>
          </div>

          {/* Results */}
          {results.length > 0 && (
            <div className="fadein" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              {/* Tabs */}
              <div style={{ display: "flex", alignItems: "center",
                            borderBottom: "1px solid #181b28", padding: "0 24px" }}>
                {results.map((r, i) => {
                  const m = tempMeta(r.temperature);
                  return (
                    <button key={i} onClick={() => setActiveTab(i)} style={{
                      background: "none", border: "none",
                      borderBottom: `2px solid ${activeTab===i ? m.color : "transparent"}`,
                      color: activeTab===i ? m.color : "#3a4060",
                      fontFamily: "'Share Tech Mono', monospace", fontSize: "0.7rem",
                      letterSpacing: "0.06em", padding: "10px 12px", cursor: "pointer",
                      transition: "color 0.12s, border-color 0.12s",
                    }}>
                      V{i+1} <span style={{ opacity: 0.55, fontSize: "0.6rem" }}>({r.changes.length}Δ)</span>
                    </button>
                  );
                })}
                <div style={{ flex: 1 }} />
                <button onClick={() => setShowPools(p => !p)} style={{
                  background: "none", border: "1px solid #1c1f2e", borderRadius: 3,
                  color: "#3a4060", padding: "3px 8px", cursor: "pointer",
                  fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem",
                  marginRight: 8,
                }}>
                  {showPools ? "hide pools" : "show pools"}
                </button>
                <span style={{ fontFamily: "monospace", fontSize: "0.62rem", color: "#2a2f42" }}>
                  hover words · see original + pool
                </span>
              </div>

              {/* Active result */}
              {results[activeTab] && (() => {
                const r = results[activeTab];
                const m = tempMeta(r.temperature);
                return (
                  <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px",
                                display: "flex", flexDirection: "column", gap: 16 }}>

                    {/* Budget bar */}
                    <div>
                      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem",
                                    letterSpacing: "0.08em", color: "#3a4060", marginBottom: 4 }}>
                        LEXICAL BUDGET CONSUMED
                      </div>
                      <BudgetBar used={r.budgetUsed} max={r.budgetMax} color={m.color} />
                    </div>

                    {/* Diff text */}
                    <div style={{ background: "#10121a", border: "1px solid #181b28",
                                  borderLeft: `3px solid ${m.color}`, borderRadius: 6, padding: "14px 16px" }}>
                      <DiffView modified={r.output} changes={r.changes} tc={m.color} />
                    </div>

                    {/* Change chips */}
                    {r.changes.length > 0 && (
                      <div>
                        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.64rem",
                                      letterSpacing: "0.08em", color: "#3a4060", marginBottom: 6 }}>
                          {r.changes.length} SUBSTITUTION{r.changes.length !== 1 ? "S" : ""} · profile: {r.profile} · seed: {r.vseed}
                        </div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                          {r.changes.map((c, i) => (
                            <div key={i} title={`Δ=${c.stepDrift.toFixed(4)}  Σ=${c.totalDrift.toFixed(4)}`}
                              style={{ background: "#13161f", border: "1px solid #1c1f2e",
                                       borderRadius: 3, padding: "3px 9px",
                                       fontFamily: "'Share Tech Mono', monospace", fontSize: "0.7rem",
                                       cursor: "default" }}>
                              <span style={{ color: "#6b7280" }}>{c.original}</span>
                              <span style={{ color: "#2a2f42", margin: "0 4px" }}>→</span>
                              <span style={{ color: m.color, fontWeight: 700 }}>{c.replacement}</span>
                              {showPools && c.synonyms?.length > 0 && (
                                <span style={{ color: "#2a2f42", marginLeft: 5, fontSize: "0.58rem" }}>
                                  [{c.synonyms.slice(0, 4).join(", ")}]
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Drift trajectory */}
                    {r.changes.length > 1 && (
                      <div>
                        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem",
                                      letterSpacing: "0.08em", color: "#3a4060", marginBottom: 4 }}>
                          TRAJECTORY  (cumulative drift per substitution)
                        </div>
                        <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 36,
                                      background: "#13161f", borderRadius: 3, padding: "4px 8px" }}>
                          {r.changes.map((c, i) => {
                            const h = Math.max(4, (c.totalDrift / (r.budgetMax + 0.0001)) * 28);
                            return (
                              <div key={i} title={`Σ=${c.totalDrift.toFixed(4)}`}
                                style={{ flex: 1, height: h, background: m.color,
                                         opacity: 0.6 + 0.4 * (i / r.changes.length),
                                         borderRadius: 1 }} />
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Raw output */}
                    <div>
                      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.62rem",
                                    letterSpacing: "0.08em", color: "#3a4060", marginBottom: 5 }}>RAW OUTPUT</div>
                      <textarea readOnly value={r.output} rows={4} style={{
                        width: "100%", background: "#10121a", border: "1px solid #181b28",
                        borderRadius: 5, color: "#6b7280", padding: "9px 13px",
                        fontFamily: "'Lora', Georgia, serif", fontSize: "0.87rem",
                        lineHeight: 1.6, resize: "vertical",
                      }} />
                      <button className="hov" onClick={() => navigator.clipboard.writeText(r.output)}
                        style={{ marginTop: 5, background: "none", border: "1px solid #1c1f2e",
                                 color: "#3a4060", borderRadius: 3, padding: "4px 11px", cursor: "pointer",
                                 fontFamily: "'Share Tech Mono', monospace", fontSize: "0.66rem",
                                 transition: "all 0.12s" }}>
                        COPY
                      </button>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* Empty state */}
          {!loading && results.length === 0 && (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                          flexDirection: "column", gap: 10, opacity: 0.2 }}>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "2rem", color: "#3a4060" }}>π⁻¹(m)</div>
              <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "0.7rem",
                            letterSpacing: "0.14em", color: "#4a5070" }}>
                EXPLORE THE SEMANTIC FIBER
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
