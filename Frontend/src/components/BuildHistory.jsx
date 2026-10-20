import { ExternalLink, Package, Plus } from "lucide-react";
import { BUILD_STATUSES, formatDateTime, timeAgo } from "../utils/labels";

export default function BuildHistory({ builds, onNew }) {
  const sorted = [...builds].sort((a, b) => b.id - a.id);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Historial de builds</h2>
          <p className="text-xs text-gray-500">Versiones compiladas del juego, de la más reciente a la más antigua.</p>
        </div>
        {onNew && (
        <button
          onClick={onNew}
          className="flex items-center gap-2 bg-[#00F0FF] hover:bg-cyan-300 text-black font-semibold rounded-lg px-3 py-2 text-sm"
        >
          <Plus className="w-4 h-4" /> Registrar build
        </button>
        )}
      </div>

      {sorted.length === 0 ? (
        <div className="border-2 border-dashed border-[#272B3B] rounded-lg p-10 text-center text-sm text-gray-500">
          <Package className="w-8 h-8 mx-auto mb-2 text-gray-600" />
          Aún no hay builds registradas.
        </div>
      ) : (
        <ol className="space-y-3">
          {sorted.map((build, i) => {
            const status = BUILD_STATUSES[build.status] ?? BUILD_STATUSES.pending;
            return (
              <li key={build.id} className="bg-[#151822] border border-[#272B3B] rounded-lg p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="font-mono text-white font-semibold">{build.version}</span>
                    <span className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border ${status.classes}`}>
                      {status.label}
                    </span>
                    {i === 0 && <span className="text-[10px] text-[#00F0FF] font-mono uppercase">Última</span>}
                  </div>
                  <time className="text-xs text-gray-500 font-mono shrink-0" title={formatDateTime(build.created_at)}>
                    {timeAgo(build.created_at)}
                  </time>
                </div>
                {build.notes && <p className="text-sm text-gray-400 mt-2 whitespace-pre-line">{build.notes}</p>}
                {build.build_url && (
                  <a
                    href={build.build_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-[#00F0FF] hover:underline mt-2"
                  >
                    Descargar <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
