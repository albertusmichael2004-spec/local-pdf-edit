import { $, setStatus } from "./dom.js";
import { onFilesChanged } from "./file_store.js";
import { PageWorkspace, parsePageOrderExpression } from "./page_workspace.js";

function formatPageRanges(pages) {
  if (!pages.length) return "";
  const ranges = [];
  let start = pages[0];
  let end = start;
  for (const page of pages.slice(1)) {
    if (page === end + 1) {
      end = page;
      continue;
    }
    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    start = end = page;
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`);
  return ranges.join(",");
}

export function bindPageSelection({ inputId, workspaceId, wrapperId, countId, pagesInputId, statusId }) {
  const wrapper = $(`#${wrapperId}`);
  const count = $(`#${countId}`);
  const pagesInput = $(`#${pagesInputId}`);
  const status = $(`#${statusId}`);
  const workspace = new PageWorkspace({
    inputId,
    container: `#${workspaceId}`,
    selectable: true,
    checkboxSelection: true,
    onSelectionChange: (pages) => {
      pagesInput.value = formatPageRanges(pages);
      count.textContent = `${pages.length} selected`;
    },
  });
  onFilesChanged(inputId, async (files) => {
    workspace.clear();
    wrapper.classList.toggle("hidden", !files.length);
    if (!files.length) {
      pagesInput.value = "";
      return;
    }
    try {
      setStatus(status, "Rendering page thumbnails locally…");
      const info = await workspace.load(files[0]);
      count.textContent = `0 selected · ${info.pages} pages`;
      status.classList.add("hidden");
    } catch (error) {
      wrapper.classList.add("hidden");
      setStatus(status, error.message || String(error), "error");
    }
  });
  pagesInput.addEventListener("change", () => {
    if (!workspace.info || !pagesInput.value.trim()) return;
    try {
      const selected = new Set(parsePageOrderExpression(pagesInput.value, workspace.info.pages));
      workspace.items.forEach((item) => workspace.setSelected(item.id, selected.has(item.sourcePage)));
      count.textContent = `${selected.size} selected`;
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
  return workspace;
}
