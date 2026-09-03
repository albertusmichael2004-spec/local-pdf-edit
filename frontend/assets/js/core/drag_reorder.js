const controllers = new WeakMap();
const blocked = "button,input,select,textarea,a";
function directItems(container, selector) {
  return [...container.children].filter((node) => node.matches(selector));
}
function animateLayout(container, selector, mutate) {
  const items = directItems(container, selector);
  const before = new Map(items.map((item) => [item, item.getBoundingClientRect()]));
  mutate();
  for (const item of items) {
    const first = before.get(item);
    const last = item.getBoundingClientRect();
    const x = first.left - last.left;
    const y = first.top - last.top;
    if ((x || y) && item.animate) {
      item.animate([{ transform: `translate(${x}px, ${y}px)` }, { transform: "translate(0, 0)" }], {
        duration: 190, easing: "cubic-bezier(.2,.75,.25,1)",
      });
    }
  }
}

function beforeTarget(event, target) {
  const rect = target.getBoundingClientRect();
  const sameRow = Math.abs(event.clientY - (rect.top + rect.height / 2)) < rect.height * 0.42;
  return sameRow ? event.clientX < rect.left + rect.width / 2 : event.clientY < rect.top + rect.height / 2;
}

function dragGhost(item, event) {
  const ghost = item.cloneNode(true);
  const rect = item.getBoundingClientRect();
  ghost.classList.add("reorder-ghost");
  ghost.style.width = `${rect.width}px`;
  ghost.style.left = `${event.clientX - rect.width / 2}px`;
  ghost.style.top = `${event.clientY - 30}px`;
  ghost.querySelectorAll("img").forEach((image) => { image.draggable = false; });
  document.body.appendChild(ghost);
  return ghost;
}

export function bindAnimatedReorder({ container, itemSelector, key = (item) => item.dataset.reorderKey, onCommit }) {
  controllers.get(container)?.();
  container.classList.add("reorder-enabled");
  let dragged = null;
  let ghost = null;
  let pointer = null;
  let active = false;
  let suppressClick = false;

  const clearTargets = () => directItems(container, itemSelector).forEach((item) => item.classList.remove("reorder-before", "reorder-after"));
  const finish = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", up);
    document.removeEventListener("pointercancel", up);
    if (!pointer) return;
    const order = directItems(container, itemSelector).map(key);
    const shouldCommit = active;
    dragged?.classList.remove("dragging", "reorder-lifted");
    ghost?.remove();
    clearTargets();
    dragged = null;
    ghost = null;
    pointer = null;
    active = false;
    if (shouldCommit) {
      suppressClick = true;
      window.setTimeout(() => { suppressClick = false; }, 0);
      onCommit(order);
    }
  };
  const move = (event) => {
    if (!pointer || event.pointerId !== pointer.id) return;
    if (!active && Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) < 5) return;
    if (!active) {
      active = true;
      ghost = dragGhost(dragged, event);
      dragged.classList.add("dragging", "reorder-lifted");
    }
    event.preventDefault();
    ghost.style.left = `${event.clientX - ghost.offsetWidth / 2}px`;
    ghost.style.top = `${event.clientY - 30}px`;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(itemSelector);
    if (!target || target === dragged || target.parentElement !== container) return;
    const before = beforeTarget(event, target);
    clearTargets();
    target.classList.add(before ? "reorder-before" : "reorder-after");
    const anchor = before ? target : target.nextSibling;
    if (anchor === dragged || anchor === dragged.nextSibling) return;
    animateLayout(container, itemSelector, () => container.insertBefore(dragged, anchor));
  };
  const down = (event) => {
    if (event.button !== 0 || event.target.closest(blocked)) return;
    const item = event.target.closest(itemSelector);
    if (!item || item.parentElement !== container) return;
    dragged = item;
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY };
    document.addEventListener("pointermove", move, { passive: false });
    document.addEventListener("pointerup", up);
    document.addEventListener("pointercancel", up);
  };
  const up = (event) => {
    if (!pointer || event.pointerId !== pointer.id) return;
    finish();
  };
  const click = (event) => {
    if (!suppressClick) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  container.addEventListener("pointerdown", down);
  container.addEventListener("click", click, true);
  const destroy = () => {
    finish();
    container.removeEventListener("pointerdown", down);
    container.removeEventListener("click", click, true);
    container.classList.remove("reorder-enabled");
  };
  controllers.set(container, destroy);
  return destroy;
}
