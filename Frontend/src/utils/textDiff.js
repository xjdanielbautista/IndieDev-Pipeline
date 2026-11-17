import { diffLines } from "diff";

// Compara dos textos línea por línea. Devuelve filas listas para pintar:
// { type: "same" | "added" | "removed", text, oldLine, newLine } y un resumen.
export function lineDiff(oldText, newText) {
  const rows = [];
  let oldLine = 1;
  let newLine = 1;
  let added = 0;
  let removed = 0;
  for (const part of diffLines(oldText ?? "", newText ?? "")) {
    const lines = part.value.replace(/\n$/, "").split("\n");
    for (const text of lines) {
      if (part.added) {
        rows.push({ type: "added", text, oldLine: null, newLine: newLine++ });
        added++;
      } else if (part.removed) {
        rows.push({ type: "removed", text, oldLine: oldLine++, newLine: null });
        removed++;
      } else {
        rows.push({ type: "same", text, oldLine: oldLine++, newLine: newLine++ });
      }
    }
  }
  return { rows, added, removed };
}

// Recorta las partes sin cambios largas y deja `context` líneas alrededor de cada cambio.
export function collapseUnchanged(rows, context = 3) {
  const keep = rows.map((row) => row.type !== "same");
  const show = rows.map((_, i) => {
    for (let j = Math.max(0, i - context); j <= Math.min(rows.length - 1, i + context); j++) if (keep[j]) return true;
    return false;
  });
  const result = [];
  let hidden = 0;
  rows.forEach((row, i) => {
    if (show[i]) {
      if (hidden) result.push({ type: "gap", count: hidden });
      hidden = 0;
      result.push(row);
    } else {
      hidden++;
    }
  });
  if (hidden) result.push({ type: "gap", count: hidden });
  return result;
}
