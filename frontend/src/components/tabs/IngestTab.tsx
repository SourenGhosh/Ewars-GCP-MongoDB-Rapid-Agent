// src/components/tabs/IngestTab.tsx
"use client";

import { useState, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/ewars";

// Example inputs the user can load to understand the format
const EXAMPLES = {
  "Free text": `November 16, 2002 — Foshan City, Guangdong Province, China.
Eight patients were admitted to Foshan Hospital with severe atypical pneumonia.
Two of the affected individuals are healthcare workers. Chest X-rays show 
bilateral infiltrates. Standard antibiotic treatment is not responding.
Antipyretic sales in the Foshan district are approximately 340 units above 
the seasonal baseline this week.`,

  "News article": `WHO SITUATION REPORT — West Africa, February 2014.
As of 9 February 2014, a total of 29 cases of viral haemorrhagic fever 
(VHF), including 18 deaths (case fatality ratio 62%), have been reported 
in Guinea. The outbreak is centred in Guéckédou district with cases 
appearing in Macenta and Kissidougou. Two healthcare workers have died.
Cross-border surveillance has been enhanced in Sierra Leone and Liberia.`,

  "CSV (any columns)": `report_date,city,country,illness_type,patient_count,hospital,deaths
2024-01-15,Mumbai,India,Severe Pneumonia,23,KEM Hospital,2
2024-01-15,Mumbai,India,Flu-like illness,145,City Dispensary,0
2024-01-16,Mumbai,India,Gastroenteritis,67,Cooper Hospital,1`,

  "DHIS2-style JSON": JSON.stringify({
    organisationUnits: [{ name: "Lagos University Teaching Hospital" }],
    dataValues: [
      { dataElement: "Malaria Cases", period: "202401", value: "234", orgUnit: "LUTH" },
      { dataElement: "Severe Malaria", period: "202401", value: "45",  orgUnit: "LUTH" },
      { dataElement: "ORS Sales",      period: "202401", value: "890", orgUnit: "Lagos Pharmacies" },
    ]
  }, null, 2),
};

interface IngestResult {
  status: string;
  signals_extracted: number;
  input_summary: string;
  extraction_warnings: string[];
  next_step: string;
  filename?: string;
  url?: string;
}

export default function IngestTab() {
  const [mode, setMode]             = useState<"text" | "file" | "url">("text");
  const [text, setText]             = useState("");
  const [url, setUrl]               = useState("");
  const [sourceHint, setSourceHint] = useState("");
  const [file, setFile]             = useState<File | null>(null);
  const [loading, setLoading]       = useState(false);
  const [result, setResult]         = useState<IngestResult | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => { setResult(null); setError(null); };

  const ingestText = async () => {
    setLoading(true); reset();
    try {
      const res = await fetch(`${API}/ingest/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_hint: sourceHint || undefined }),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const ingestFile = async () => {
    if (!file) return;
    setLoading(true); reset();
    try {
      const form = new FormData();
      form.append("file", file);
      if (sourceHint) form.append("source_hint", sourceHint);
      const res = await fetch(`${API}/ingest/file`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const ingestUrl = async () => {
    setLoading(true); reset();
    try {
      const res = await fetch(
        `${API}/ingest/url?url=${encodeURIComponent(url)}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleSubmit = () => {
    if (mode === "text") ingestText();
    else if (mode === "file") ingestFile();
    else ingestUrl();
  };

  const canSubmit = (
    (mode === "text" && text.trim().length > 10) ||
    (mode === "file" && file !== null) ||
    (mode === "url" && url.trim().length > 5)
  ) && !loading;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 p-4 space-y-4">
      {/* Header */}
      <div>
        <h3 className="text-sm font-semibold text-gray-200">Ingest Signal Data</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Any format — the AI extracts and normalises automatically
        </p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
        {(["text", "file", "url"] as const).map((m) => (
          <button key={m} onClick={() => { setMode(m); reset(); }}
            className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
              mode === m ? "bg-gray-600 text-white" : "text-gray-500 hover:text-gray-300"
            }`}>
            {m === "text" ? "Paste text" : m === "file" ? "Upload file" : "From URL"}
          </button>
        ))}
      </div>

      {/* Source hint */}
      <div>
        <label className="text-xs text-gray-500 block mb-1">
          Source type hint (optional — helps extraction accuracy)
        </label>
        <input
          value={sourceHint}
          onChange={(e) => setSourceHint(e.target.value)}
          placeholder="e.g. WHO situation report, DHIS2 export, news article..."
          className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700
                     rounded-lg px-3 py-2 focus:outline-none focus:border-gray-500"
        />
      </div>

      {/* Mode-specific input */}
      {mode === "text" && (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <label className="text-xs text-gray-500">Paste any text below</label>
            <select
              onChange={(e) => e.target.value && setText(EXAMPLES[e.target.value as keyof typeof EXAMPLES])}
              defaultValue=""
              className="text-xs bg-gray-800 text-gray-400 border border-gray-700
                         rounded px-2 py-1 cursor-pointer">
              <option value="" disabled>Load example →</option>
              {Object.keys(EXAMPLES).map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <textarea
            value={text}
            onChange={(e) => { setText(e.target.value); reset(); }}
            placeholder="Paste a news article, WHO report, CSV data, JSON, or any health surveillance text..."
            rows={8}
            className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700
                       rounded-lg px-3 py-2 font-mono resize-none
                       focus:outline-none focus:border-gray-500"
          />
          <div className="text-xs text-gray-700 text-right">{text.length} chars</div>
        </div>
      )}

      {mode === "file" && (
        <div
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-gray-700 hover:border-gray-600
                     rounded-xl p-6 text-center cursor-pointer transition-colors">
          <input
            ref={fileRef} type="file" className="hidden"
            accept=".txt,.csv,.json,.md,.pdf,.tsv"
            onChange={(e) => { setFile(e.target.files?.[0] || null); reset(); }}
          />
          {file ? (
            <div>
              <div className="text-sm text-gray-300 font-medium">{file.name}</div>
              <div className="text-xs text-gray-600 mt-1">
                {(file.size / 1024).toFixed(1)} KB · {file.type || "unknown type"}
              </div>
              <button onClick={(e) => { e.stopPropagation(); setFile(null); reset(); }}
                className="text-xs text-gray-600 hover:text-gray-400 mt-2">
                Remove
              </button>
            </div>
          ) : (
            <div>
              <div className="text-2xl mb-2">📄</div>
              <div className="text-sm text-gray-400">Drop or click to upload</div>
              <div className="text-xs text-gray-600 mt-1">
                .txt · .csv · .json · .pdf · .md · any text format
              </div>
            </div>
          )}
        </div>
      )}

      {mode === "url" && (
        <div>
          <label className="text-xs text-gray-500 block mb-1">URL</label>
          <input
            value={url}
            onChange={(e) => { setUrl(e.target.value); reset(); }}
            placeholder="https://www.who.int/docs/situation-report..."
            className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700
                       rounded-lg px-3 py-2 focus:outline-none focus:border-gray-500"
          />
          <div className="text-xs text-gray-700 mt-1">
            WHO reports, DHIS2 exports, news articles, any public URL
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-xs text-red-400 bg-red-400/10 border border-red-400/20
                        rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-gray-800 rounded-xl p-3 space-y-2">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              result.signals_extracted > 0 ? "bg-green-400" : "bg-yellow-400"
            }`} />
            <span className="text-xs font-medium text-gray-200">
              {result.signals_extracted > 0
                ? `${result.signals_extracted} signal${result.signals_extracted !== 1 ? "s" : ""} extracted and stored`
                : "No signals found in input"}
            </span>
          </div>

          <p className="text-xs text-gray-400 leading-relaxed">
            {result.input_summary}
          </p>

          {result.extraction_warnings.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-yellow-500 font-medium">Extraction notes:</div>
              {result.extraction_warnings.map((w, i) => (
                <div key={i} className="text-xs text-yellow-400/70 flex gap-1.5">
                  <span className="flex-shrink-0">⚠</span>
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {result.signals_extracted > 0 && (
            <div className="text-xs text-blue-400 border-t border-gray-700 pt-2 mt-2">
              {result.next_step}
            </div>
          )}
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="w-full py-2.5 text-sm font-medium rounded-xl transition-all
                   bg-blue-600 hover:bg-blue-500 text-white
                   disabled:opacity-40 disabled:cursor-not-allowed
                   flex items-center justify-center gap-2">
        {loading ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <span>Extracting signals…</span>
          </>
        ) : (
          <>
            <span>Extract & Store Signals</span>
            <span className="text-blue-300 text-xs">→ AI normalised</span>
          </>
        )}
      </button>
    </div>
  );
}