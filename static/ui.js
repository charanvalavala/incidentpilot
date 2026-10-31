export const $ = (id) => document.getElementById(id);
export const savedOnly = document.body.dataset.saved === "true";
const requests = new Map();
export const safe = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export function highlight(text, question = "") {
  const words = [
    ...new Set(question.toLowerCase().match(/[a-z]{4,}/g) || []),
  ].slice(0, 12);
  const escaped = safe(text);
  return words.length
    ? escaped.replace(
        new RegExp(`\\b(${words.join("|")})\\b`, "gi"),
        "<mark>$1</mark>",
      )
    : escaped;
}
export function notify(message, error = false) {
  const node = $("feedback");
  node.textContent = message;
  node.classList.toggle("error", error);
  node.hidden = false;
}
export async function request(
  path,
  { key = "request", timeout = 60000, ...options } = {},
) {
  requests.get(key)?.abort();
  const controller = new AbortController();
  requests.set(key, controller);
  const timer = setTimeout(() => controller.abort("timeout"), timeout);
  try {
    const response = await fetch(path, {
      ...options,
      signal: controller.signal,
    });
    const payload = await response
      .json()
      .catch(() => ({ detail: "Unexpected server response" }));
    if (!response.ok)
      throw new Error(
        typeof payload.detail === "string"
          ? payload.detail
          : JSON.stringify(payload.detail),
      );
    return payload;
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error(
        controller.signal.reason === "timeout"
          ? "The request timed out. Retry, or open the saved example."
          : "Request cancelled.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
    if (requests.get(key) === controller) requests.delete(key);
  }
}
export function cancel() {
  for (const controller of requests.values()) controller.abort();
}
export async function sample() {
  const response = await fetch(new URL("./sample.json", import.meta.url));
  if (!response.ok) throw new Error("The saved example could not be loaded.");
  return response.json();
}
export async function busy(button, task) {
  const label = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '<span class="busy-indicator"></span> Working';
  try {
    await task();
  } catch (error) {
    notify(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = label;
  }
}
export function jsonPost(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
export function tabs() {
  for (const button of document.querySelectorAll("[data-panel]")) {
    button.addEventListener("click", () => {
      for (const item of document.querySelectorAll("[data-panel]")) {
        item.classList.toggle("active", item === button);
        item.setAttribute("aria-pressed", String(item === button));
      }
      for (const panel of document.querySelectorAll("[data-view]"))
        panel.hidden = panel.dataset.view !== button.dataset.panel;
    });
  }
}
$("cancel")?.addEventListener("click", () => {
  cancel();
  notify("Requests cancelled.");
});
$("feedback")?.addEventListener("click", () => {
  $("feedback").hidden = true;
});
