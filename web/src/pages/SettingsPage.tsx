import { useCallback, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Download, FileUp, Sparkles } from "lucide-react";
import { useReport } from "../lib/report-context";
import { parseProfile } from "../lib/profile-parse";
import PageHeader from "../components/PageHeader";
import ErrorBanner from "../components/ErrorBanner";

export default function SettingsPage() {
  const { loading, error: analysisError, analyse, profileJson, setProfileJson } = useReport();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [parseError, setParseError] = useState<string | null>(null);
  const [format, setFormat] = useState<"json" | "yaml" | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);

  const handleText = useCallback(
    (text: string) => {
      setProfileJson(text);
      if (!text.trim()) {
        setParseError(null);
        setFormat(null);
        return;
      }
      const result = parseProfile(text);
      setParseError(result.error);
      setFormat(result.format);
    },
    [setProfileJson],
  );

  async function handleAnalyse() {
    const result = parseProfile(profileJson);
    if (result.error || !result.data) {
      setParseError(result.error || "Profile is empty");
      setFormat(result.format);
      return;
    }
    setParseError(null);
    await analyse(result.data);
    navigate("/");
  }

  async function handleLoadSample() {
    setLoadingSample(true);
    setParseError(null);
    try {
      const res = await fetch("/sample_input.yaml");
      if (!res.ok) throw new Error(`Sample fetch failed (${res.status})`);
      const text = await res.text();
      handleText(text);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Failed to load sample");
    } finally {
      setLoadingSample(false);
    }
  }

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) readFile(file);
    e.target.value = ""; // allow re-selecting the same file
  }

  function readFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => handleText(String(reader.result ?? ""));
    reader.onerror = () => setParseError(`Failed to read ${file.name}`);
    reader.readAsText(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) readFile(file);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave() {
    setDragOver(false);
  }

  function handleExportJson() {
    const result = parseProfile(profileJson);
    const text = result.data ? JSON.stringify(result.data, null, 2) : profileJson;
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `profile-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const hasContent = profileJson.trim().length > 0;
  const canAnalyse = hasContent && !parseError && !loading;

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Paste a profile (JSON or YAML), drop a file, or load the sample to begin."
      />

      {analysisError && (
        <div className="mb-4">
          <ErrorBanner title="Analysis failed" message={analysisError} />
        </div>
      )}

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`rounded-xl border bg-white p-6 shadow-sm transition-colors dark:bg-gray-900 ${
          dragOver
            ? "border-gray-900 ring-2 ring-gray-900/10 dark:border-gray-100 dark:ring-gray-100/10"
            : "border-gray-200 dark:border-gray-800"
        }`}
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <label htmlFor="profile-text" className="text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
            Profile {format ? `(${format.toUpperCase()} detected)` : ""}
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleLoadSample}
              disabled={loadingSample}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              <Sparkles size={14} />
              {loadingSample ? "Loading..." : "Load sample"}
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              <FileUp size={14} />
              Upload file
            </button>
            <button
              type="button"
              onClick={handleExportJson}
              disabled={!hasContent}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              <Download size={14} />
              Export JSON
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.yaml,.yml,application/json,application/x-yaml,text/yaml,text/plain"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
        </div>

        <textarea
          id="profile-text"
          value={profileJson}
          onChange={(e) => handleText(e.target.value)}
          placeholder="Paste JSON or YAML profile here, drop a file, or click Load sample..."
          spellCheck={false}
          className="h-96 w-full resize-y rounded-lg border border-gray-300 bg-white p-3 font-mono text-xs text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-gray-900 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:focus:ring-gray-100"
          aria-describedby="profile-help"
        />

        <p id="profile-help" className="mt-2 text-xs text-gray-600 dark:text-gray-400">
          Accepts both JSON and YAML. Drag-and-drop a <code className="rounded bg-gray-100 px-1 py-0.5 dark:bg-gray-800">.yaml</code> or <code className="rounded bg-gray-100 px-1 py-0.5 dark:bg-gray-800">.json</code> file anywhere on this card.
        </p>

        {parseError && (
          <div className="mt-3">
            <ErrorBanner title="Profile cannot be parsed" message={parseError} />
          </div>
        )}

        <button
          type="button"
          onClick={handleAnalyse}
          disabled={!canAnalyse}
          aria-busy={loading}
          className="mt-4 rounded-lg bg-gray-900 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300 dark:focus:ring-gray-100"
        >
          {loading ? "Analysing..." : "Run Analysis"}
        </button>
      </div>
    </div>
  );
}
