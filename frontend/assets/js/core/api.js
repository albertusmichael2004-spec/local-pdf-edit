import { startProgressTracking } from "./progress.js?v=4.5";

function trackedResponse(response, tracker) {
  if (!tracker) return response;
  const bodyMethods = new Set(["arrayBuffer", "blob", "formData", "json", "text"]);
  return new Proxy(response, {
    get(target, property) {
      if (bodyMethods.has(property)) {
        return async (...args) => {
          try {
            return await target[property](...args);
          } finally {
            tracker.stop();
          }
        };
      }
      const value = Reflect.get(target, property, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}

export async function apiFetch(endpoint, options = {}) {
  const {
    progressElement = null,
    progressLabel = "Processing locally…",
    ...fetchOptions
  } = options;
  const trackable = fetchOptions.body instanceof FormData && (fetchOptions.method || "GET") !== "GET";
  const tracker = trackable && progressElement
    ? startProgressTracking(endpoint, progressElement, progressLabel)
    : null;
  try {
    const headers = { ...(fetchOptions.headers || {}), ...(tracker?.headers || {}) };
    const response = await fetch(endpoint, { credentials: "same-origin", ...fetchOptions, headers });
    return trackedResponse(response, tracker);
  } catch (error) {
    tracker?.stop();
    throw new Error(
      `Could not reach the local PDF engine. Keep the desktop app open and retry. (${error.message || error})`,
    );
  }
}

export async function parseError(response) {
  try {
    const body = await response.json();
    return body.detail || JSON.stringify(body);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

function filenameFromDisposition(response, fallback) {
  const disposition = response.headers.get("content-disposition") || "";
  const utf = disposition.match(/filename\*=utf-8''([^;]+)/i);
  if (utf) return decodeURIComponent(utf[1]);
  const basic = disposition.match(/filename="?([^";]+)"?/i);
  return basic ? basic[1] : fallback;
}

export async function downloadResponse(response, fallbackName) {
  if (!response.ok) throw new Error(await parseError(response));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filenameFromDisposition(response, fallbackName);
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  return response;
}
