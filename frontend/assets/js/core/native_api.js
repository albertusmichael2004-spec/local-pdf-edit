const BASE_URL = "/api/desktop-native";
const HASH_POLL_INTERVAL_MS = 200;

function injectedNativeApi() {
  for (const candidate of [window, window.parent, window.top]) {
    try {
      if (candidate?.pywebview?.api) return candidate.pywebview.api;
    } catch {
      // Keep the lookup defensive if the UI embedding changes later.
    }
  }
  return null;
}

async function responseJson(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // The HTTP bridge always returns JSON, but keep the user-facing error useful
    // if a local proxy or antivirus replaces the response.
  }
  if (!response.ok) {
    throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
  }
  return payload;
}

async function postJson(path, payload = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return responseJson(response);
}

function delay(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function publishHashProgress(payload) {
  if (!payload) return;
  window.postMessage({
    type: "pdf-workbench-native-hash-progress",
    payload,
  }, window.location.origin);
}

async function hashSecurityPath(path) {
  const started = await postJson("/hash/start", { path });
  const jobId = started?.job_id;
  if (!jobId) throw new Error("The local hash engine did not return a job ID.");
  publishHashProgress(started.progress);

  while (true) {
    await delay(HASH_POLL_INTERVAL_MS);
    const response = await fetch(
      `${BASE_URL}/hash/jobs/${encodeURIComponent(jobId)}`,
      { credentials: "same-origin", cache: "no-store" },
    );
    const job = await responseJson(response);
    publishHashProgress(job.progress);
    if (job.status === "complete") return job.result;
    if (job.status === "error") {
      throw new Error(job.error || "Could not calculate SHA-256 for the selected path.");
    }
  }
}

const httpNativeApi = Object.freeze({
  choose_archive: () => postJson("/choose/archive"),
  choose_security_file: () => postJson("/choose/security-file"),
  choose_security_folder: () => postJson("/choose/security-folder"),
  choose_hash_file: () => postJson("/choose/hash-file"),
  choose_hash_folder: () => postJson("/choose/hash-folder"),
  extract_archive: (path, sameFolder, password = "") => postJson("/extract-archive", {
    path,
    same_folder: Boolean(sameFolder),
    password: password || "",
  }),
  secure_all_in_one: (path, password, deleteOriginal, reduceSize = false) => postJson("/secure-all-in-one", {
    path,
    password,
    delete_original: Boolean(deleteOriginal),
    reduce_size: Boolean(reduceSize),
  }),
  hash_security_path: hashSecurityPath,
});

export function getNativeApi() {
  return injectedNativeApi() || httpNativeApi;
}
