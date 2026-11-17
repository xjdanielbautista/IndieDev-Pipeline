// Coloreado de código con highlight.js, repartido por líneas para numerarlas.
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import cpp from "highlight.js/lib/languages/cpp";
import csharp from "highlight.js/lib/languages/csharp";
import css from "highlight.js/lib/languages/css";
import dos from "highlight.js/lib/languages/dos";
import glsl from "highlight.js/lib/languages/glsl";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import kotlin from "highlight.js/lib/languages/kotlin";
import lua from "highlight.js/lib/languages/lua";
import markdown from "highlight.js/lib/languages/markdown";
import powershell from "highlight.js/lib/languages/powershell";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import swift from "highlight.js/lib/languages/swift";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

// Solo los lenguajes que suelen usarse en un juego: así el bundle no carga los ~190 de highlight.js.
const LANGUAGES = {
  bash, cpp, csharp, css, dos, glsl, go, ini, java, javascript, json, kotlin, lua,
  markdown, powershell, python, rust, sql, swift, typescript, xml, yaml,
};
for (const [name, definition] of Object.entries(LANGUAGES)) hljs.registerLanguage(name, definition);

// Colorear textos muy largos congela la pestaña; arriba de esto se muestra sin colores.
const MAX_HIGHLIGHT_CHARS = 200_000;

export function highlightLines(text, language) {
  if (!language || !hljs.getLanguage(language) || text.length > MAX_HIGHLIGHT_CHARS) return null;
  // highlight.js puede abrir un <span> en una línea y cerrarlo en otra; se reparte
  // por líneas cerrando y reabriendo las etiquetas abiertas para numerarlas.
  const html = hljs.highlight(text, { language, ignoreIllegals: true }).value;
  const lines = [];
  let open = [];
  for (const raw of html.split("\n")) {
    const prefix = open.join("");
    const tags = raw.match(/<span[^>]*>|<\/span>/g) || [];
    for (const tag of tags) {
      if (tag === "</span>") open.pop();
      else open.push(tag);
    }
    lines.push(prefix + raw + "</span>".repeat(open.length));
  }
  return lines;
}
