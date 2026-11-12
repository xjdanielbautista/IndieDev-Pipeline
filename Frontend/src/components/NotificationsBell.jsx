// Campana de notificaciones. Depende de /api/notifications (ver docs/PENDIENTES_BACKEND.md):
// mientras no exista, el menú muestra "Próximamente".
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { isNotImplemented } from "../api/client";
import { listNotifications, markNotificationsRead } from "../api/studio";
import { formatDateTime, timeAgo } from "../utils/labels";
import { ComingSoon } from "./TaskExtras";

const POLL_MS = 30000;

export default function NotificationsBell({ onOpen }) {
  const [status, setStatus] = useState("loading"); // loading | ready | unavailable
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);

  const load = useCallback(async () => {
    try {
      setItems(await listNotifications());
      setStatus("ready");
      return true;
    } catch (err) {
      if (isNotImplemented(err)) {
        setStatus("unavailable");
        return false; // no seguir consultando una ruta que no existe
      }
      return true;
    }
  }, []);

  useEffect(() => {
    let timer;
    let cancelled = false;
    const tick = async () => {
      const keepPolling = await load();
      if (keepPolling && !cancelled) timer = setTimeout(tick, POLL_MS);
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [load]);

  // Cerrar al hacer clic fuera
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => boxRef.current && !boxRef.current.contains(e.target) && setOpen(false);
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  const unread = items.filter((n) => !n.read).length;

  const markRead = async (ids) => {
    setItems((prev) => prev.map((n) => (ids === "all" || ids.includes(n.id) ? { ...n, read: true } : n)));
    try {
      await markNotificationsRead(ids);
    } catch {
      load();
    }
  };

  const openNotification = (n) => {
    if (!n.read) markRead([n.id]);
    setOpen(false);
    if (n.asset_id) onOpen(n);
  };

  return (
    <div className="relative" ref={boxRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        title="Notificaciones"
        aria-label={unread ? `Notificaciones, ${unread} sin leer` : "Notificaciones"}
        className="relative p-2 text-gray-400 hover:text-white hover:bg-[#1C202D] rounded transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-[#FF0055] text-white text-[10px] font-bold flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] z-50 bg-[#151822] border border-[#272B3B] rounded-lg shadow-2xl">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#272B3B]">
            <span className="text-sm font-semibold text-white">Notificaciones</span>
            {unread > 0 && (
              <button onClick={() => markRead("all")} className="text-xs text-[#00F0FF] hover:underline">
                Marcar todo como leído
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {status === "unavailable" ? (
              <div className="p-3">
                <ComingSoon>
                  Te avisaremos cuando te asignen una tarea, comenten en una tuya o algo pase a revisión.
                </ComingSoon>
              </div>
            ) : items.length === 0 ? (
              <p className="p-4 text-xs text-gray-500">No tienes notificaciones.</p>
            ) : (
              <ul>
                {items.map((n) => (
                  <li key={n.id}>
                    <button
                      onClick={() => openNotification(n)}
                      className={`w-full text-left px-4 py-3 border-b border-[#272B3B]/60 hover:bg-[#1C202D] flex gap-2 ${
                        n.read ? "opacity-60" : ""
                      }`}
                    >
                      <span
                        className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${n.read ? "bg-transparent" : "bg-[#00F0FF]"}`}
                      />
                      <span className="min-w-0">
                        <span className="block text-sm text-gray-200 break-words">{n.message}</span>
                        <span className="block text-[11px] text-gray-500" title={formatDateTime(n.created_at)}>
                          {timeAgo(n.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
