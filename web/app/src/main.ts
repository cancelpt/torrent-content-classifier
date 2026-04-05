import "./style.css";
import defaultRulesYaml from "../default-rules.yaml?raw";
import { classifyRecord, parseRuleSet } from "./classifier";
import { parseTorrentFile } from "./torrent";
import type { ClassificationResult, Rule, TorrentRecord } from "./types";

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("Missing #app root element.");
}

app.innerHTML = `
  <main class="layout">
    <section class="card hero">
      <h1>Torrent Content Classifier</h1>
      <p>Drop a <code>.torrent</code> file to classify its content type instantly in the browser.</p>
      <p class="hint">
        <a class="project-link" href="https://github.com/cancelpt/torrent-content-classifier" target="_blank" rel="noreferrer">
          <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.48 7.48 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z"></path>
          </svg>
          <span>View on GitHub</span>
        </a>
      </p>
    </section>

    <section class="card controls">
      <div class="field">
        <label for="rules-file">Custom Rules YAML (Optional)</label>
        <input id="rules-file" type="file" accept=".yaml,.yml,text/yaml" />
      </div>
      <p id="rules-state" class="hint">Using built-in default rules.</p>
    </section>

    <section class="card dropzone" id="dropzone" tabindex="0" role="button" aria-label="Upload torrent">
      <input id="torrent-file" type="file" accept=".torrent" hidden />
      <p class="title">Drop .torrent Here</p>
      <p class="hint">or click to select file</p>
    </section>

    <section class="card result">
      <h2>Classification Result</h2>
      <div id="result-empty" class="result-empty">No file processed yet.</div>
      <div id="result-content" class="result-content hidden">
        <div class="grid">
          <div><span>Info Hash</span><strong id="result-hash">-</strong></div>
          <div><span>Files</span><strong id="result-files">-</strong></div>
          <div><span>Kind</span><strong id="result-kind">-</strong></div>
          <div><span>Subtype</span><strong id="result-subtype">-</strong></div>
          <div><span>Confidence</span><strong id="result-confidence">-</strong></div>
          <div><span>Matched Rules</span><strong id="result-rules">-</strong></div>
        </div>
        <details>
          <summary>Classification JSON</summary>
          <pre id="result-json"></pre>
        </details>
        <details open>
          <summary>Parsed File List Preview</summary>
          <pre id="parsed-file-list"></pre>
        </details>
        <details>
          <summary>Parsed Torrent Record JSON</summary>
          <pre id="parsed-record-json"></pre>
        </details>
      </div>
    </section>
  </main>
`;

const dropzone = must<HTMLDivElement>("#dropzone");
const torrentInput = must<HTMLInputElement>("#torrent-file");
const rulesInput = must<HTMLInputElement>("#rules-file");
const rulesState = must<HTMLParagraphElement>("#rules-state");
const resultEmpty = must<HTMLDivElement>("#result-empty");
const resultContent = must<HTMLDivElement>("#result-content");
const resultHash = must<HTMLElement>("#result-hash");
const resultFiles = must<HTMLElement>("#result-files");
const resultKind = must<HTMLElement>("#result-kind");
const resultSubtype = must<HTMLElement>("#result-subtype");
const resultConfidence = must<HTMLElement>("#result-confidence");
const resultRules = must<HTMLElement>("#result-rules");
const resultJson = must<HTMLElement>("#result-json");
const parsedFileList = must<HTMLElement>("#parsed-file-list");
const parsedRecordJson = must<HTMLElement>("#parsed-record-json");

let activeRules: Rule[] = parseRuleSet(defaultRulesYaml);

rulesInput.addEventListener("change", async () => {
  const rulesFile = rulesInput.files?.[0];
  if (!rulesFile) {
    activeRules = parseRuleSet(defaultRulesYaml);
    rulesState.textContent = "Using built-in default rules.";
    return;
  }

  try {
    const content = await rulesFile.text();
    activeRules = parseRuleSet(content);
    rulesState.textContent = `Loaded custom rules: ${rulesFile.name}`;
  } catch (error) {
    activeRules = parseRuleSet(defaultRulesYaml);
    rulesState.textContent = `Custom rule file invalid: ${toError(error)}. Reverted to default rules.`;
  }
});

dropzone.addEventListener("click", () => torrentInput.click());
dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    torrentInput.click();
  }
});

torrentInput.addEventListener("change", () => {
  const torrentFile = torrentInput.files?.[0];
  if (torrentFile) {
    void processTorrentFile(torrentFile);
  }
});

for (const eventName of ["dragenter", "dragover"]) {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("active");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("active");
  });
}

dropzone.addEventListener("drop", (event) => {
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) {
    return;
  }
  const torrentFile = files[0];
  void processTorrentFile(torrentFile);
});

async function processTorrentFile(file: File): Promise<void> {
  if (!file.name.toLowerCase().endsWith(".torrent")) {
    rulesState.textContent = "Only .torrent files are supported.";
    return;
  }

  setBusyState(true, `Parsing ${file.name} ...`);
  try {
    const record = await parseTorrentFile(file);
    const result = classifyRecord(record, activeRules);
    renderResult(record, result);
    rulesState.textContent = `Processed ${file.name} with ${activeRules.length} active rules.`;
  } catch (error) {
    setBusyState(false);
    resultEmpty.classList.remove("hidden");
    resultContent.classList.add("hidden");
    resultEmpty.textContent = `Failed to parse or classify torrent: ${toError(error)}`;
  }
}

function renderResult(record: TorrentRecord, result: ClassificationResult): void {
  const previewLimit = 200;
  const listPreviewLines = record.fileList
    .slice(0, previewLimit)
    .map((file, index) => `${index + 1}. ${file.path} (${formatBytes(file.size)})`);
  if (record.fileList.length > previewLimit) {
    listPreviewLines.push(`... (${record.fileList.length - previewLimit} more files hidden)`);
  }

  setBusyState(false);
  resultEmpty.classList.add("hidden");
  resultContent.classList.remove("hidden");
  resultHash.textContent = result.infoHash.slice(0, 12);
  resultHash.title = result.infoHash;
  resultFiles.textContent = `${record.fileList.length}`;
  resultKind.textContent = result.kind;
  resultSubtype.textContent = result.subtype;
  resultConfidence.textContent = result.confidence.toFixed(2);
  resultRules.textContent = result.matchedRuleIds.length > 0 ? result.matchedRuleIds.join(", ") : "none";

  resultJson.textContent = JSON.stringify(
    {
      file_name: record.torrentName,
      file_count: record.fileList.length,
      ...result
    },
    null,
    2
  );

  parsedFileList.textContent = listPreviewLines.join("\n");
  parsedRecordJson.textContent = JSON.stringify(
    {
      info_hash: record.infoHash,
      torrent_name: record.torrentName,
      file_list: record.fileList
    },
    null,
    2
  );
}

function setBusyState(isBusy: boolean, message?: string): void {
  dropzone.classList.toggle("busy", isBusy);
  if (message) {
    resultEmpty.textContent = message;
  }
  if (isBusy) {
    resultEmpty.classList.remove("hidden");
    resultContent.classList.add("hidden");
  }
}

function must<T extends Element>(selector: string): T {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element as T;
}

function toError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 ** 2) {
    return `${(value / 1024).toFixed(2)} KiB`;
  }
  if (value < 1024 ** 3) {
    return `${(value / 1024 ** 2).toFixed(2)} MiB`;
  }
  return `${(value / 1024 ** 3).toFixed(2)} GiB`;
}
