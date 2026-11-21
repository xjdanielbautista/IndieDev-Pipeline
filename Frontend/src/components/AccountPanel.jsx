// "Mi cuenta": estado del correo, cambiar contraseña, sesiones abiertas y eliminar la cuenta.
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, KeyRound, Laptop, MailWarning, MonitorSmartphone, Smartphone, Trash2 } from "lucide-react";
import {
  changePassword,
  deleteAccount,
  listSessions,
  resendVerification,
  revokeOtherSessions,
  revokeSession,
} from "../api/auth";
import { isNotImplemented } from "../api/client";
import { describeDevice, isMobileDevice } from "../utils/device";
import { formatDateTime, timeAgo } from "../utils/labels";
import { GhostButton, Label, PrimaryButton, inputClass, useToast } from "./ui";

// Aviso fijo para quien no ha confirmado su correo.
export function VerifyEmailBanner({ user }) {
  const notify = useToast();
  const [sending, setSending] = useState(false);
  const [hidden, setHidden] = useState(false);
  if (!user || user.email_verified || hidden) return null;
  const resend = async () => {
    setSending(true);
    try {
      await resendVerification(user.email);
      notify(`Te enviamos un enlace a ${user.email}`, "success");
    } catch (err) {
      notify(err.message);
    } finally {
      setSending(false);
    }
  };
  return (
    <div className="bg-yellow-500/10 border-b border-yellow-500/30 text-yellow-300 text-xs px-4 md:px-6 py-2 flex flex-wrap items-center gap-x-3 gap-y-1">
      <MailWarning className="w-4 h-4 shrink-0" />
      <span>Confirma tu correo ({user.email}) con el enlace que te enviamos.</span>
      <button onClick={resend} disabled={sending} className="underline hover:text-white disabled:opacity-50">
        {sending ? "Enviando..." : "Reenviar enlace"}
      </button>
      <button onClick={() => setHidden(true)} className="ml-auto text-yellow-500/70 hover:text-white" aria-label="Ocultar aviso">
        ✕
      </button>
    </div>
  );
}

function SessionsList({ reloadKey }) {
  const notify = useToast();
  const [sessions, setSessions] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);

  const load = useCallback(() => {
    listSessions()
      .then((items) => {
        setSessions(items);
        setError("");
      })
      .catch((err) => setError(isNotImplemented(err) ? "Próximamente" : err.message));
  }, []);

  useEffect(load, [load, reloadKey]);

  const close = async (session) => {
    setBusy(session.id);
    try {
      await revokeSession(session.id);
      setSessions((items) => items.filter((item) => item.id !== session.id));
      notify("Sesión cerrada", "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
      load();
    } finally {
      setBusy(null);
    }
  };

  const closeOthers = async () => {
    setBusy("others");
    try {
      await revokeOtherSessions();
      setSessions((items) => items.filter((item) => item.current));
      notify("Se cerraron las demás sesiones", "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setBusy(null);
    }
  };

  if (error) return <p className="text-xs text-gray-500">{error}</p>;
  if (!sessions) return <p className="text-xs text-gray-500">Cargando...</p>;
  const others = sessions.filter((item) => !item.current).length;

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {sessions.map((session) => {
          const Icon = isMobileDevice(session.user_agent) ? Smartphone : Laptop;
          return (
            <li
              key={session.id}
              className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm"
            >
              <Icon className="w-4 h-4 text-gray-400 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-white truncate">
                  {describeDevice(session.user_agent)}
                  {session.current && <span className="ml-2 text-[11px] text-[#00FF66]">esta sesión</span>}
                </p>
                <p className="text-[11px] text-gray-500 truncate" title={`Inició ${formatDateTime(session.created_at)}`}>
                  {session.ip_address ? `${session.ip_address} · ` : ""}
                  activa {timeAgo(session.last_seen_at)}
                </p>
              </div>
              {!session.current && (
                <button
                  onClick={() => close(session)}
                  disabled={busy !== null}
                  className="text-xs text-[#FF3D00] hover:underline disabled:opacity-40"
                >
                  {busy === session.id ? "Cerrando..." : "Cerrar"}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {others > 0 && (
        <GhostButton onClick={closeOthers} disabled={busy !== null}>
          {busy === "others" ? "Cerrando..." : `Cerrar las otras ${others}`}
        </GhostButton>
      )}
      {sessions.length === 1 && sessions[0].current && (
        <p className="text-[11px] text-gray-500">No tienes otras sesiones abiertas.</p>
      )}
    </div>
  );
}

function ChangePasswordForm({ onChanged }) {
  const notify = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next !== confirm) {
      notify("Las contraseñas nuevas no coinciden");
      return;
    }
    setSaving(true);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      onChanged?.();
      notify("Contraseña actualizada. Las demás sesiones se cerraron.", "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <Label>Contraseña actual</Label>
        <input
          type="password"
          className={inputClass}
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
          required
        />
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <Label>Nueva</Label>
          <input
            type="password"
            className={inputClass}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
        </div>
        <div>
          <Label>Confirmar nueva</Label>
          <input
            type="password"
            className={inputClass}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
        </div>
      </div>
      <PrimaryButton type="submit" loading={saving}>
        Cambiar contraseña
      </PrimaryButton>
    </form>
  );
}

function DeleteAccountForm({ user, onDeleted }) {
  const notify = useToast();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [typed, setTyped] = useState("");
  const [deleting, setDeleting] = useState(false);
  const expected = user.username ?? user.email;

  const submit = async (e) => {
    e.preventDefault();
    setDeleting(true);
    try {
      await deleteAccount(password);
      onDeleted();
    } catch (err) {
      if (err.status !== 401) notify(err.message);
      setDeleting(false);
    }
  };

  if (!open) {
    return (
      <GhostButton onClick={() => setOpen(true)} className="text-[#FF3D00] border-[#FF3D00]/40 hover:bg-[#FF3D00]/10">
        Eliminar mi cuenta
      </GhostButton>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-[#FF3D00]/40 bg-[#FF3D00]/5 p-3">
      <p className="text-xs text-[#ffb8a3] flex gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        Se te quitará de todos los estudios. Tus comentarios y cambios se conservan sin autor. Si eres dueño de un
        estudio, primero elimínalo desde Ajustes. No se puede deshacer.
      </p>
      <div>
        <Label>Escribe {expected} para confirmar</Label>
        <input className={inputClass} value={typed} onChange={(e) => setTyped(e.target.value)} />
      </div>
      <div>
        <Label>Tu contraseña</Label>
        <input
          type="password"
          className={inputClass}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={deleting || typed.trim() !== expected}
          className="px-4 py-2.5 rounded-lg text-sm font-semibold bg-[#FF3D00] text-black disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {deleting ? "Eliminando..." : "Eliminar para siempre"}
        </button>
        <GhostButton type="button" onClick={() => setOpen(false)}>
          Cancelar
        </GhostButton>
      </div>
    </form>
  );
}

export default function AccountPanel({ user, onDeleted }) {
  const notify = useToast();
  const [sessionsKey, setSessionsKey] = useState(0);
  const resend = async () => {
    try {
      await resendVerification(user.email);
      notify(`Te enviamos un enlace a ${user.email}`, "success");
    } catch (err) {
      notify(err.message);
    }
  };
  return (
    <div className="space-y-6">
      <section className="text-sm">
        <p className="text-white font-medium">{user.username}</p>
        <p className="text-gray-400 flex items-center gap-2 mt-0.5">
          {user.email}
          {user.email_verified ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-[#00FF66]">
              <CheckCircle2 className="w-3.5 h-3.5" /> confirmado
            </span>
          ) : (
            <button onClick={resend} className="text-[11px] text-yellow-400 underline hover:text-white">
              sin confirmar · reenviar enlace
            </button>
          )}
        </p>
      </section>
      <section>
        <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
          <KeyRound className="w-4 h-4 text-gray-400" /> Cambiar contraseña
        </h4>
        <ChangePasswordForm onChanged={() => setSessionsKey((key) => key + 1)} />
      </section>
      <section>
        <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
          <MonitorSmartphone className="w-4 h-4 text-gray-400" /> Sesiones abiertas
        </h4>
        <SessionsList reloadKey={sessionsKey} />
      </section>
      <section>
        <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
          <Trash2 className="w-4 h-4 text-gray-400" /> Eliminar cuenta
        </h4>
        <DeleteAccountForm user={user} onDeleted={onDeleted} />
      </section>
    </div>
  );
}
