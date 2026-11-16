import { useMemo } from "react";
import "highlight.js/styles/github-dark.css";
import { highlightLines } from "../utils/highlight";

export default function CodeView({ text, language, maxHeight = "max-h-96" }) {
  const lines = useMemo(() => text.replace(/\n$/, "").split("\n"), [text]);
  const highlighted = useMemo(() => highlightLines(text.replace(/\n$/, ""), language), [text, language]);
  return (
    <div className={`${maxHeight} overflow-auto rounded-lg border border-[#272B3B] bg-[#0d1117] text-xs font-mono`}>
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line, i) => (
            <tr key={i} className="align-top">
              <td className="select-none text-right pr-3 pl-2 text-gray-600 w-px whitespace-nowrap">{i + 1}</td>
              {highlighted ? (
                // El HTML lo genera highlight.js a partir del texto escapado: no ejecuta nada del archivo.
                <td className="pr-3 whitespace-pre text-gray-200" dangerouslySetInnerHTML={{ __html: highlighted[i] || " " }} />
              ) : (
                <td className="pr-3 whitespace-pre text-gray-200">{line || " "}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
