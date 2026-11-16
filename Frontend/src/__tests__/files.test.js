import { describe, expect, it } from "vitest";
import { extensionOf, looksLikeText, previewKind, safeBlobType } from "../utils/fileTypes";
import { highlightLines } from "../utils/highlight";
import { collapseUnchanged, lineDiff } from "../utils/textDiff";

describe("previewKind", () => {
  it("reconoce imágenes, audio, video y PDF", () => {
    expect(previewKind("hero.PNG").kind).toBe("image");
    expect(previewKind("theme.ogg").kind).toBe("audio");
    expect(previewKind("intro.webm").kind).toBe("video");
    expect(previewKind("gdd.pdf").kind).toBe("pdf");
  });

  it("elige el lenguaje del código", () => {
    expect(previewKind("PlayerController.cs")).toEqual({ kind: "code", language: "csharp" });
    expect(previewKind("enemy.gd")).toEqual({ kind: "code", language: "python" });
    expect(previewKind("water.shader")).toEqual({ kind: "code", language: "glsl" });
  });

  it("usa el tipo MIME cuando la extensión no dice nada", () => {
    expect(previewKind("LEEME", "text/plain").kind).toBe("text");
    expect(previewKind("sin-extension", "image/png").kind).toBe("image");
    expect(previewKind("modelo.fbx", "application/octet-stream").kind).toBe("other");
  });

  it("nunca muestra un SVG como imagen (podría traer scripts)", () => {
    expect(previewKind("icono.svg")).toEqual({ kind: "code", language: "xml" });
    expect(previewKind("x", "image/svg+xml").kind).toBe("code");
  });

  it("safeBlobType nunca devuelve HTML ni SVG para textos", () => {
    expect(safeBlobType("code", "text/html")).toBe("text/plain");
    expect(safeBlobType("image", "image/png")).toBe("image/png");
  });

  it("extensionOf y looksLikeText", () => {
    expect(extensionOf("a/b/c.tar.GZ")).toBe("gz");
    expect(extensionOf("Makefile")).toBe("");
    expect(looksLikeText(new TextEncoder().encode("hola\nmundo"))).toBe(true);
    expect(looksLikeText(new Uint8Array([0x89, 0x50, 0x00, 0x47]))).toBe(false);
  });
});

describe("lineDiff", () => {
  it("cuenta líneas agregadas y quitadas con sus números", () => {
    const { rows, added, removed } = lineDiff("a\nb\nc\n", "a\nB\nc\nd\n");
    expect(added).toBe(2);
    expect(removed).toBe(1);
    expect(rows.find((r) => r.type === "removed")).toMatchObject({ text: "b", oldLine: 2, newLine: null });
    expect(rows.at(-1)).toMatchObject({ type: "added", text: "d", newLine: 4 });
  });

  it("textos iguales no tienen cambios", () => {
    const { added, removed } = lineDiff("x\ny", "x\ny");
    expect(added + removed).toBe(0);
  });

  it("collapseUnchanged deja contexto alrededor de los cambios", () => {
    const old = Array.from({ length: 20 }, (_, i) => `l${i}`).join("\n");
    const changed = old.replace("l10", "cambio");
    const rows = collapseUnchanged(lineDiff(old, changed).rows, 2);
    expect(rows[0]).toEqual({ type: "gap", count: 8 });
    expect(rows.filter((r) => r.type !== "gap")).toHaveLength(6);
    expect(rows.at(-1)).toEqual({ type: "gap", count: 7 });
  });
});

describe("highlightLines", () => {
  it("colorea por línea y cierra las etiquetas abiertas", () => {
    const lines = highlightLines('/* uno\ndos */\nint x = 1;', "csharp");
    expect(lines).toHaveLength(3);
    for (const line of lines) {
      expect((line.match(/<span/g) || []).length).toBe((line.match(/<\/span>/g) || []).length);
    }
    expect(lines[1]).toContain("hljs-comment");
  });

  it("escapa el HTML del archivo", () => {
    const [line] = highlightLines('var s = "<img src=x onerror=alert(1)>";', "javascript");
    expect(line).not.toContain("<img");
    expect(line).toContain("&lt;img");
  });

  it("devuelve null si no conoce el lenguaje", () => {
    expect(highlightLines("hola", "cobol")).toBeNull();
    expect(highlightLines("hola", undefined)).toBeNull();
  });
});
