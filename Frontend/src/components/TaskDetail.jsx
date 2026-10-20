import { useCallback, useEffect, useState } from "react";
import { History, Lock, RotateCcw, Unlock, Users, X } from "lucide-react";
import { getAssetHistory, lockAsset, unlockAsset, updateAsset } from "../api/studio";
import { CATEGORIES, STATUSES, describeChange, formatDateTime, timeAgo } from "../utils/labels";
import { Avatar, inputClass, Label, useToast } from "./ui";

const UNDO_LIMIT = 3;
const REVERTIBLE = ["status_changed", "category_changed", "assignment_mode_changed", "assignments_changed"];

const splitNames = (value) => (value ? value.split(",").map((n) => n.trim()).filter(Boolean) : []);

// Calcula qué cambio hay que mandar al backend para volver al valor anterior
// de una entrada del historial. Devuelve null si no se puede revertir.
function buildRevert(entry, asset, members) {
  switch (entry.action) {
    case "status_changed":
      return entry.previous_value ? { status: entry.previous_value } : null;
    case "category_changed":
      return entry.previous_value ? { category: entry.previous_value } : null;
    case "assignment_mode_changed":
      return entry.previous_value ? { assignment_mode: entry.previous_value } : null;
    case "assignments_changed": {
      // El historial guarda nombres: new_value = agregados, previous_value = quitados.
      const byName = new Map(members.map((m) => [m.username, m.id]));
      const added = splitNames(entry.new_value).map((n) => byName.get(n));
      const removed = splitNames(entry.previous_value).map((n) => byName.get(n));
      if ([...added, ...removed].some((id) => id === undefined)) return null;
      const ids = asset.assigned_user_ids.filter((id) => !added.includes(id));
      for (const id of removed) if (!ids.includes(id)) ids.push(id);
      return { assigned_user_ids: ids };
    }
    default:
      return null;
  }
}

export default function TaskDetail({ asset, tenant, projectId, members, currentUser, onChanged, onClose }) {
  const notify = useToast();
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await getAssetHistory(tenant.id, projectId, asset.id));
    } catch (err) {
      notify(err.message);
    } finally {
      setLoadingHistory(false);
    }
  }, [tenant.id, projectId, asset.id, notify]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const run = async (action, successMessage) => {
    setBusy(true);
    try {
      const updated = await action();
      onChanged(updated);
      await loadHistory();
      if (successMessage) notify(successMessage, "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setBusy(false);
    }
  };

  const patch = (changes, message) => run(() => updateAsset(tenant.id, projectId, asset.id, changes), message);

  const toggleAssignee = (id) => {
    const ids = asset.assigned_user_ids.includes(id)
      ? asset.assigned_user_ids.filter((x) => x !== id)
      : [...asset.assigned_user_ids, id];
    patch({ assigned_user_ids: ids });
  };

  const isLocked = asset.locked_by_user_id !== null;
  const lockedByMe = asset.locked_by_user_id === currentUser?.id;
  const lockedByName =
    members.find((m) => m.id === asset.locked_by_user_id)?.username ?? `usuario #${asset.locked_by_user_id}`;
  const toggleLock = () =>
    run(
      () => (isLocked ? unlockAsset : lockAsset)(tenant.id, projectId, asset.id),
      isLocked ? "Archivo liberado" : "Archivo bloqueado para ti",
    );

  // Los últimos 3 cambios que se pueden restaurar.
  const undoable = history.filter((h) => REVERTIBLE.includes(h.action)).slice(0, UNDO_LIMIT);
  const undoableIds = new Set(undoable.map((h) => h.id));

  const restore = (entry) => {
    const changes = buildRevert(entry, asset, members);
    if (!changes) {
      notify("Ese cambio no se puede restaurar automáticamente.");
      return;
    }
    patch(changes, "Cambio restaurado");
  };

  const category = CATEGORIES[asset.category];

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="w-full max-w-lg h-full bg-[#151822] border-l border-[#272B3B] shadow-2xl flex flex-col">
        <header className="px-5 py-4 border-b border-[#272B3B] flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
                style={{ color: category?.color, borderColor: `${category?.color}55`, background: `${category?.color}15` }}
              >
                #{asset.id} · {category?.label}
              </span>
              {isLocked && (
                <span className="text-[10px] font-bold uppercase text-[#FF3D00] tracking-wider">Bloqueado</span>
              )}
            </div>
            <h2 className="text-lg font-semibold text-white break-words">{asset.original_name}</h2>
            <p className="text-xs text-gray-500 mt-1">
              Creada por {asset.created_by?.username ?? "—"} · {formatDateTime(asset.created_at)}
            </p>
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white rounded" aria-label="Cerrar">
            <X className="w-5 h-5" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <section className="grid grid-cols-2 gap-3">
            <div>
              <Label>Columna</Label>
              <select
                className={inputClass}
                value={asset.status}
                disabled={busy}
                onChange={(e) => patch({ status: e.target.value })}
              >
                {STATUSES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Tipo</Label>
              <select
                className={inputClass}
                value={asset.category}
                disabled={busy}
                onChange={(e) => patch({ category: e.target.value })}
              >
                {Object.entries(CATEGORIES).map(([id, c]) => (
                  <option key={id} value={id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </section>

          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-gray-400" /> Asignados
              </h3>
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  className="accent-[#00F0FF]"
                  checked={asset.assignment_mode === "restricted"}
                  disabled={busy}
                  onChange={(e) => patch({ assignment_mode: e.target.checked ? "restricted" : "open" })}
                />
                Solo ellos pueden moverla
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              {members.map((m) => {
                const active = asset.assigned_user_ids.includes(m.id);
                return (
                  <button
                    key={m.id}
                    disabled={busy}
                    onClick={() => toggleAssignee(m.id)}
                    className={`flex items-center gap-2 pl-1 pr-3 py-1 rounded-full border text-sm transition-colors disabled:opacity-60 ${
                      active ? "border-[#00F0FF] bg-[#00F0FF]/10 text-white" : "border-[#272B3B] text-gray-500 hover:text-white"
                    }`}
                  >
                    <Avatar user={m} />
                    {m.username}
                  </button>
                );
              })}
            </div>
          </section>

          <section className="rounded-lg border border-[#272B3B] bg-[#0B0D14] p-4 flex items-center justify-between gap-3">
            <div className="text-sm">
              <p className="text-white font-medium">Bloqueo de archivo</p>
              <p className="text-xs text-gray-500">
                {isLocked
                  ? `Bloqueado por ${lockedByMe ? "ti" : lockedByName} ${timeAgo(asset.locked_at)}`
                  : "Bloquéalo mientras lo editas para que nadie más lo modifique."}
              </p>
            </div>
            <button
              disabled={busy || (isLocked && !lockedByMe)}
              onClick={toggleLock}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium shrink-0 disabled:opacity-40 disabled:cursor-not-allowed ${
                isLocked ? "bg-[#FF3D00]/15 text-[#FF3D00] hover:bg-[#FF3D00]/25" : "bg-[#1C202D] text-gray-200 hover:bg-[#272B3B]"
              }`}
            >
              {isLocked ? <Unlock className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
              {isLocked ? "Liberar" : "Bloquear"}
            </button>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-1">
              <History className="w-4 h-4 text-gray-400" /> Historial de cambios
            </h3>
            <p className="text-xs text-gray-500 mb-3">
              Puedes restaurar cualquiera de los últimos {UNDO_LIMIT} cambios si alguien se equivocó.
            </p>
            {loadingHistory ? (
              <p className="text-xs text-gray-500">Cargando...</p>
            ) : history.length === 0 ? (
              <p className="text-xs text-gray-500">Sin cambios todavía.</p>
            ) : (
              <ol className="relative border-l border-[#272B3B] ml-2 space-y-4">
                {history.map((entry) => (
                  <li key={entry.id} className="ml-4">
                    <span className="absolute -left-[5px] mt-1.5 w-2.5 h-2.5 rounded-full bg-[#272B3B] border border-[#3a3f55]" />
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-gray-300">
                        <span className="text-white font-medium">{entry.actor_username}</span> {describeChange(entry)}
                      </p>
                      {undoableIds.has(entry.id) && (
                        <button
                          disabled={busy}
                          onClick={() => restore(entry)}
                          title="Volver al valor anterior a este cambio"
                          className="flex items-center gap-1 text-xs text-[#00F0FF] hover:text-white px-2 py-0.5 rounded border border-[#00F0FF]/30 hover:bg-[#00F0FF]/10 shrink-0 disabled:opacity-40"
                        >
                          <RotateCcw className="w-3 h-3" /> Restaurar
                        </button>
                      )}
                    </div>
                    <time className="text-[11px] font-mono text-gray-500" title={formatDateTime(entry.created_at)}>
                      {formatDateTime(entry.created_at)} · {timeAgo(entry.created_at)}
                    </time>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </aside>
    </div>
  );
}
