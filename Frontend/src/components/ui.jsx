import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { X } from "lucide-react";
import { initials } from "../utils/labels";

// ---------- Avisos (toasts) ----------
const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const notify = useCallback((message, type = "error") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4500);
  }, []);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`px-4 py-3 rounded-lg border text-sm shadow-xl whitespace-pre-line ${
              t.type === "error"
                ? "bg-[#1a1111] border-[#FF3D00]/50 text-[#ffb8a3]"
                : "bg-[#0f1a14] border-[#00FF66]/40 text-[#b4ffd0]"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

// ---------- Ventana modal ----------
export function Modal({ title, onClose, children, width = "max-w-md" }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className={`w-full ${width} bg-[#151822] border border-[#272B3B] rounded-xl shadow-2xl`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#272B3B]">
          <h3 className="text-white font-semibold">{title}</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white rounded" aria-label="Cerrar">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

// ---------- Formularios ----------
export const inputClass =
  "w-full bg-[#0B0D14] border border-[#272B3B] text-white text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF] transition-colors";

export function Label({ children, hint }) {
  return (
    <label className="block text-xs font-mono text-gray-400 mb-1">
      {children}
      {hint && <span className="ml-2 text-gray-600 normal-case">{hint}</span>}
    </label>
  );
}

export function PrimaryButton({ children, loading, className = "", ...props }) {
  return (
    <button
      {...props}
      disabled={loading || props.disabled}
      className={`bg-[#00F0FF] hover:bg-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold rounded-lg px-4 py-2.5 text-sm transition-colors ${className}`}
    >
      {loading ? "Guardando..." : children}
    </button>
  );
}

export function GhostButton({ children, className = "", ...props }) {
  return (
    <button
      {...props}
      className={`px-3 py-2 text-sm rounded-lg border border-[#272B3B] text-gray-300 hover:text-white hover:bg-[#1C202D] disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${className}`}
    >
      {children}
    </button>
  );
}

// ---------- Avatar ----------
const AVATAR_COLORS = ["#00F0FF", "#FF0055", "#00FF66", "#FFC400", "#A78BFA", "#FF8A00"];

export function Avatar({ user, size = "w-6 h-6 text-[10px]", ring = false }) {
  const name = user?.username || user?.email || "?";
  const color = AVATAR_COLORS[(user?.id ?? 0) % AVATAR_COLORS.length];
  return (
    <div
      title={name}
      style={{ backgroundColor: color }}
      className={`${size} rounded-full flex items-center justify-center font-bold text-black shrink-0 ${
        ring ? "ring-2 ring-[#151822]" : ""
      }`}
    >
      {initials(name)}
    </div>
  );
}
