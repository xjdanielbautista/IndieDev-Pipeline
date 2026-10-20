import { Lock } from "lucide-react";
import { CATEGORIES, formatDateTime, statusLabel } from "../utils/labels";
import { Avatar } from "./ui";

// Vista de tabla con todas las tareas/archivos del proyecto.
export default function AssetVault({ assets, members, onOpen }) {
  const nameOf = (id) => members.find((m) => m.id === id)?.username ?? `#${id}`;

  if (assets.length === 0) {
    return <p className="text-sm text-gray-500 text-center mt-10">No hay archivos que coincidan con los filtros.</p>;
  }

  return (
    <div className="overflow-x-auto border border-[#272B3B] rounded-lg">
      <table className="w-full text-sm">
        <thead className="bg-[#151822] text-xs text-gray-400 font-mono text-left">
          <tr>
            <th className="px-4 py-3">#</th>
            <th className="px-4 py-3">Nombre</th>
            <th className="px-4 py-3">Tipo</th>
            <th className="px-4 py-3">Estado</th>
            <th className="px-4 py-3">Asignados</th>
            <th className="px-4 py-3">Bloqueo</th>
            <th className="px-4 py-3">Creada</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((a) => {
            const category = CATEGORIES[a.category];
            return (
              <tr
                key={a.id}
                onClick={() => onOpen(a)}
                className="border-t border-[#272B3B] hover:bg-[#151822] cursor-pointer"
              >
                <td className="px-4 py-3 font-mono text-gray-500">{a.id}</td>
                <td className="px-4 py-3 text-white">{a.original_name}</td>
                <td className="px-4 py-3">
                  <span style={{ color: category?.color }}>{category?.label}</span>
                </td>
                <td className="px-4 py-3 text-gray-300">{statusLabel(a.status)}</td>
                <td className="px-4 py-3">
                  <div className="flex -space-x-1.5">
                    {a.assigned_users.map((u) => (
                      <Avatar key={u.id} user={u} ring />
                    ))}
                    {a.assigned_users.length === 0 && <span className="text-gray-600">—</span>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  {a.locked_by_user_id !== null ? (
                    <span className="inline-flex items-center gap-1 text-[#FF3D00]">
                      <Lock className="w-3.5 h-3.5" /> {nameOf(a.locked_by_user_id)}
                    </span>
                  ) : (
                    <span className="text-gray-600">Libre</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500 font-mono text-xs">{formatDateTime(a.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
