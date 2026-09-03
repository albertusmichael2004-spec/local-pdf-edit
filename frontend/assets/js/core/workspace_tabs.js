const workspaceParams = () => new URLSearchParams(window.location.search);

export const isWorkspacePage = () => workspaceParams().get("workspace") === "1";

function workspaceUrl(number) {
  const parentParams = workspaceParams();
  const url = new URL(window.location.href);
  url.search = "";
  for (const key of ["startup_cache", "asset_version"]) {
    const value = parentParams.get(key);
    if (value !== null) url.searchParams.set(key, value);
  }
  url.searchParams.set("workspace", "1");
  url.searchParams.set("page", String(number));
  return url.href;
}

export function initializeWorkspaceIdentity() {
  const number = Math.max(1, Number.parseInt(workspaceParams().get("page") || "1", 10));
  const label = `Page ${number}`;
  document.title = `${label} — Local PDF Workbench`;
  const pill = document.querySelector(".header-pill");
  if (pill) pill.textContent = label;
}

export function initializeWorkspaceTabs() {
  const shell = document.querySelector("#windowTabs");
  const list = document.querySelector("#windowTabsList");
  const host = document.querySelector("#windowWorkspaceHost");
  const app = document.querySelector(".app-frame");
  const addButton = document.querySelector("#addWindowPage");
  const pages = new Map();
  let nextNumber = 1;
  let activeNumber = 0;

  const selectPage = (number) => {
    activeNumber = number;
    pages.forEach(({ tab, frame }, pageNumber) => {
      const active = pageNumber === number;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
      frame.hidden = !active;
    });
  };

  const closePage = (number) => {
    if (pages.size === 1) return;
    const numbers = [...pages.keys()];
    const index = numbers.indexOf(number);
    const page = pages.get(number);
    page.tab.remove();
    page.frame.remove();
    pages.delete(number);
    if (activeNumber === number) selectPage(numbers[index + 1] || numbers[index - 1]);
  };

  const addPage = () => {
    const number = nextNumber++;
    const tab = document.createElement("button");
    tab.type = "button";
    tab.role = "tab";
    tab.className = "window-page-tab";
    tab.innerHTML = `<span class="window-page-icon">P</span><span>Page ${number}</span><span class="window-page-close" aria-label="Close Page ${number}">×</span>`;
    tab.addEventListener("click", (event) => {
      if (event.target.closest(".window-page-close")) closePage(number);
      else selectPage(number);
    });

    const frame = document.createElement("iframe");
    frame.className = "window-workspace-frame";
    frame.src = workspaceUrl(number);
    frame.title = `Page ${number}`;
    frame.hidden = true;
    pages.set(number, { tab, frame });
    list.append(tab);
    host.append(frame);
    selectPage(number);
  };

  app.hidden = true;
  shell.hidden = false;
  host.hidden = false;
  document.body.classList.add("tab-shell");
  document.body.classList.remove("shell-loading");
  addButton.addEventListener("click", addPage);
  addPage();
}
