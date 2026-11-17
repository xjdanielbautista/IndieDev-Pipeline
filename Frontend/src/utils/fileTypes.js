// Decide cómo mostrar un archivo en la vista previa según su nombre y tipo MIME.

const IMAGE_EXT = ["png", "jpg", "jpeg", "gif", "webp", "bmp", "avif", "ico"];
const AUDIO_EXT = ["mp3", "wav", "ogg", "oga", "flac", "m4a", "aac", "opus"];
const VIDEO_EXT = ["mp4", "webm", "mov", "m4v", "ogv"];

// extensión -> lenguaje de highlight.js
const CODE_LANGUAGES = {
  cs: "csharp",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  ts: "typescript",
  tsx: "typescript",
  py: "python",
  gd: "python", // GDScript se parece lo suficiente a Python para colorearlo
  lua: "lua",
  c: "cpp",
  h: "cpp",
  cpp: "cpp",
  hpp: "cpp",
  cc: "cpp",
  java: "java",
  kt: "kotlin",
  rs: "rust",
  go: "go",
  swift: "swift",
  shader: "glsl",
  glsl: "glsl",
  hlsl: "cpp",
  vert: "glsl",
  frag: "glsl",
  json: "json",
  xml: "xml",
  html: "xml",
  svg: "xml",
  tscn: "ini",
  tres: "ini",
  yaml: "yaml",
  yml: "yaml",
  toml: "ini",
  ini: "ini",
  cfg: "ini",
  css: "css",
  md: "markdown",
  sh: "bash",
  bat: "dos",
  ps1: "powershell",
  sql: "sql",
};
const PLAIN_TEXT_EXT = ["txt", "csv", "log", "gitignore", "env", "properties"];

export function extensionOf(name = "") {
  const clean = name.toLowerCase().split(/[?#]/)[0];
  const dot = clean.lastIndexOf(".");
  return dot >= 0 ? clean.slice(dot + 1) : "";
}

// Devuelve { kind, language }. kind: "image" | "audio" | "video" | "code" | "text" | "pdf" | "other".
// El SVG se trata como código: mostrarlo como imagen permitiría ejecutar lo que traiga dentro.
export function previewKind(name, contentType = "") {
  const ext = extensionOf(name);
  const type = (contentType || "").toLowerCase();
  if (ext === "svg" || type === "image/svg+xml") return { kind: "code", language: "xml" };
  if (IMAGE_EXT.includes(ext) || (type.startsWith("image/") && !ext)) return { kind: "image" };
  if (AUDIO_EXT.includes(ext) || type.startsWith("audio/")) return { kind: "audio" };
  if (VIDEO_EXT.includes(ext) || type.startsWith("video/")) return { kind: "video" };
  if (ext === "pdf" || type === "application/pdf") return { kind: "pdf" };
  if (CODE_LANGUAGES[ext]) return { kind: "code", language: CODE_LANGUAGES[ext] };
  if (PLAIN_TEXT_EXT.includes(ext) || type.startsWith("text/") || type === "application/json") {
    return { kind: "text" };
  }
  return { kind: "other" };
}

export const isTextKind = (kind) => kind === "code" || kind === "text";

// Tipo MIME seguro para crear el blob de la vista previa: nunca HTML ni SVG
// ejecutables, aunque el archivo diga serlo.
export function safeBlobType(kind, contentType = "") {
  if (kind === "image" || kind === "audio" || kind === "video") return contentType || "application/octet-stream";
  if (kind === "pdf") return "application/pdf";
  return "text/plain";
}

// Revisa si unos bytes parecen texto (sin bytes nulos en el primer bloque).
export function looksLikeText(bytes) {
  const sample = bytes.subarray(0, 4096);
  for (const byte of sample) if (byte === 0) return false;
  return true;
}
