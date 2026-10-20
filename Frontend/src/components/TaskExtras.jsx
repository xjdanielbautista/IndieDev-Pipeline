// Secciones del panel de una tarea que dependen de funciones pendientes del backend
// (ver docs/PENDIENTES_BACKEND.md). Mientras el endpoint no exista muestran
// "Próximamente"; se activan solas cuando el backend lo implemente.
import { useCallback, useEffect, useRef, useState } from "react";
import { Download, ExternalLink, FileUp, GitBranch, GitCommit, MessageSquare, Send, Trash2 } from "lucide-react";
import { isNotImplemented } from "../api/client";
import {
  addComment,
  connectGithub,
  deleteComment,
  downloadAssetFile,
  listComments,
  listCommits,
  uploadAssetFile,
} from "../api/studio";
import { formatBytes, formatDateTime, timeAgo } from "../utils/labels";
import { canLock, isManager } from "../utils/permissions";
import { Avatar, inputClass, useToast } from "./ui";

function SectionTitle({ icon: Icon, children, badge }) {
  return (
    <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-2">
      <Icon className="w-4 h-4 text-gray-400" /> {children}
      {badge}
    </h3>
  );
}

export function ComingSoon({ children }) {
  return (
    <div className="rounded-lg border border-dashed border-[#272B3B] p-3 text-xs text-gray-500">
      <span className="inline-block mb-1 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border border-yellow-500/30 text-yellow-400 bg-yellow-500/10">
        Próximamente
      </span>
      <p>{children}</p>
    </div>
  );
}

// Carga una lista desde el backend y distingue "no implementado" de un error real.
function useOptionalList(loader, deps) {
  const notify = useToast();
  const [state, setState] = useState({ status: "loading", items: [] });

  const reload = useCallback(async () => {
    try {
      setState({ status: "ready", items: await loader() });
    } catch (err) {
      if (isNotImplemented(err)) setState({ status: "unavailable", items: [] });
      else {
        setState({ status: "error", items: [] });
        if (err.status !== 401) notify(err.message);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return [state, reload, setState];
}

// ---------- Archivo ----------
export function FileSection({ tenant, projectId, asset, role, currentUser, onChanged }) {
  const notify = useToast();
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  // El backend activa esta función al agregar file_size/content_type/file_uploaded_at a AssetRead.
  const supported = "file_size" in asset && !unavailable;
  const hasFile = asset.file_size !== null && asset.file_size !== undefined;
  const lockedByMe = asset.locked_by_user_id === currentUser?.id;
  const canUpload = lockedByMe && canLock(role, asset.category);

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      onChanged(await uploadAssetFile(tenant.id, projectId, asset.id, file));
      notify("Nueva versión subida", "success");
    } catch (err) {
      if (isNotImplemented(err)) setUnavailable(true);
      else if (err.status !== 401) notify(err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const download = async () => {
    try {
      await downloadAssetFile(tenant.id, projectId, asset.id, asset.original_name);
    } catch (err) {
      if (isNotImplemented(err)) setUnavailable(true);
      else if (err.status !== 401) notify(err.message);
    }
  };

  return (
    <section>
      <SectionTitle icon={FileUp}>Archivo</SectionTitle>
      {!supported ? (
        <ComingSoon>
          Aquí se podrá subir el archivo real (sprite, modelo, script…) a la nube y descargar la última versión.
          Para subir, primero tendrás que bloquearlo.
        </ComingSoon>
      ) : (
        <div className="rounded-lg border border-[#272B3B] bg-[#0B0D14] p-3 flex items-center justify-between gap-3">
          <div className="text-xs min-w-0">
            {hasFile ? (
              <>
                <p className="text-white truncate">{asset.original_name}</p>
                <p className="text-gray-500">
                  {formatBytes(asset.file_size)} · subido {timeAgo(asset.file_uploaded_at)}
                </p>
              </>
            ) : (
              <p className="text-gray-500">Todavía no hay archivo.</p>
            )}
            {!canUpload && (
              <p className="text-gray-600 mt-1">
                {canLock(role, asset.category)
                  ? "Bloquéalo para subir una nueva versión."
                  : "Tu rol no puede subir archivos de este tipo."}
              </p>
            )}
          </div>
          <div className="flex gap-2 shrink-0">
            {hasFile && (
              <button
                onClick={download}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-[#1C202D] text-gray-200 hover:bg-[#272B3B]"
              >
                <Download className="w-4 h-4" /> Descargar
              </button>
            )}
            <input ref={inputRef} type="file" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
            <button
              disabled={!canUpload || uploading}
              onClick={() => inputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-[#00F0FF]/15 text-[#00F0FF] hover:bg-[#00F0FF]/25 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <FileUp className="w-4 h-4" /> {uploading ? "Subiendo..." : "Subir versión"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

// ---------- Commits de GitHub (solo tareas de código) ----------
function ConnectGithub({ tenant, projectId }) {
  const notify = useToast();
  const [repo, setRepo] = useState("");
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      setResult(await connectGithub(tenant.id, projectId, repo.trim()));
    } catch (err) {
      if (isNotImplemented(err)) notify("Conectar GitHub todavía no está disponible en el backend.");
      else if (err.status !== 401) notify(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (result) {
    return (
      <div className="rounded-lg border border-[#00FF66]/30 bg-[#00FF66]/5 p-3 text-xs space-y-2">
        <p className="text-[#00FF66] font-semibold">Repositorio {result.github_repo} conectado</p>
        <p className="text-gray-400">
          En GitHub ve a Settings → Webhooks → Add webhook, con Content type <code>application/json</code> y el
          evento push. Copia estos datos ahora; el secreto no se vuelve a mostrar.
        </p>
        <p className="text-gray-300 break-all">
          <span className="text-gray-500">Payload URL:</span> {result.webhook_url}
        </p>
        <p className="text-gray-300 break-all font-mono">
          <span className="text-gray-500 font-sans">Secret:</span> {result.secret}
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <input
        className={`${inputClass} py-2`}
        value={repo}
        onChange={(e) => setRepo(e.target.value)}
        placeholder="usuario/repositorio"
        pattern="[\w.\-]+/[\w.\-]+"
        title="Formato usuario/repositorio"
        required
      />
      <button
        disabled={saving}
        className="flex items-center gap-1.5 px-3 rounded-lg text-sm bg-[#1C202D] text-gray-200 hover:bg-[#272B3B] shrink-0"
      >
        <GitBranch className="w-4 h-4" /> Conectar
      </button>
    </form>
  );
}

export function CommitsSection({ tenant, projectId, asset, role }) {
  const [state] = useOptionalList(() => listCommits(tenant.id, projectId, asset.id), [tenant.id, projectId, asset.id]);
  const [showConnect, setShowConnect] = useState(false);

  return (
    <section>
      <SectionTitle icon={GitCommit}>Commits</SectionTitle>
      {state.status === "unavailable" ? (
        <ComingSoon>
          Aquí aparecerán los commits de GitHub que mencionen <code>#{asset.id}</code> en su mensaje, por ejemplo
          <code> &quot;Arregla colisiones #{asset.id}&quot;</code>.
        </ComingSoon>
      ) : state.status === "loading" ? (
        <p className="text-xs text-gray-500">Cargando...</p>
      ) : (
        <div className="space-y-2">
          {state.items.length === 0 ? (
            <p className="text-xs text-gray-500">
              Ningún commit menciona esta tarea. Escribe <code className="text-gray-300">#{asset.id}</code> en el
              mensaje del commit para vincularlo.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {state.items.map((c) => (
                <li key={c.sha} className="flex items-start gap-2 text-xs">
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono text-[#00F0FF] hover:underline shrink-0 inline-flex items-center gap-1"
                  >
                    {c.sha.slice(0, 7)} <ExternalLink className="w-3 h-3" />
                  </a>
                  <span className="text-gray-300 min-w-0 break-words">{c.message.split("\n")[0]}</span>
                  <span className="text-gray-600 shrink-0 ml-auto" title={formatDateTime(c.committed_at)}>
                    {c.author_name} · {timeAgo(c.committed_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {isManager(role) &&
            (showConnect ? (
              <ConnectGithub tenant={tenant} projectId={projectId} />
            ) : (
              <button onClick={() => setShowConnect(true)} className="text-xs text-gray-500 hover:text-[#00F0FF]">
                Conectar o cambiar el repositorio de GitHub del proyecto
              </button>
            ))}
        </div>
      )}
    </section>
  );
}

// ---------- Comentarios ----------
export function CommentsSection({ tenant, projectId, asset, role, currentUser }) {
  const notify = useToast();
  const [state, , setState] = useOptionalList(
    () => listComments(tenant.id, projectId, asset.id),
    [tenant.id, projectId, asset.id],
  );
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  const send = async (e) => {
    e.preventDefault();
    const body = text.trim();
    if (!body) return;
    setSending(true);
    try {
      const comment = await addComment(tenant.id, projectId, asset.id, body);
      setState((prev) => ({ ...prev, items: [...prev.items, comment] }));
      setText("");
    } catch (err) {
      if (isNotImplemented(err)) setState({ status: "unavailable", items: [] });
      else if (err.status !== 401) notify(err.message);
    } finally {
      setSending(false);
    }
  };

  const remove = async (comment) => {
    try {
      await deleteComment(tenant.id, projectId, asset.id, comment.id);
      setState((prev) => ({ ...prev, items: prev.items.filter((c) => c.id !== comment.id) }));
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    }
  };

  const count = state.status === "ready" ? state.items.length : null;

  return (
    <section>
      <SectionTitle
        icon={MessageSquare}
        badge={count ? <span className="text-xs font-mono text-gray-500">{count}</span> : null}
      >
        Comentarios
      </SectionTitle>
      {state.status === "unavailable" ? (
        <ComingSoon>Aquí el equipo podrá dejar comentarios y dudas sobre esta tarea.</ComingSoon>
      ) : state.status === "loading" ? (
        <p className="text-xs text-gray-500">Cargando...</p>
      ) : (
        <>
          <ul className="space-y-3 mb-3">
            {state.items.map((c) => (
              <li key={c.id} className="flex gap-2 group">
                <Avatar user={c.user} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-gray-500">
                    <span className="text-white font-medium">{c.user?.username ?? "usuario eliminado"}</span>{" "}
                    <span title={formatDateTime(c.created_at)}>{timeAgo(c.created_at)}</span>
                  </p>
                  <p className="text-sm text-gray-300 whitespace-pre-line break-words">{c.body}</p>
                </div>
                {(c.user?.id === currentUser?.id || isManager(role)) && (
                  <button
                    onClick={() => remove(c)}
                    title="Borrar comentario"
                    className="p-1 text-gray-600 hover:text-[#FF3D00] opacity-0 group-hover:opacity-100 focus:opacity-100 self-start"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </li>
            ))}
            {state.items.length === 0 && <p className="text-xs text-gray-500">Sin comentarios todavía.</p>}
          </ul>
          <form onSubmit={send} className="flex gap-2">
            <textarea
              className={`${inputClass} resize-none py-2`}
              rows={2}
              maxLength={2000}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(e);
              }}
              placeholder="Escribe un comentario (Ctrl+Enter para enviar)"
            />
            <button
              disabled={sending || !text.trim()}
              aria-label="Enviar comentario"
              className="px-3 rounded-lg bg-[#00F0FF] text-black hover:bg-cyan-300 disabled:opacity-40 shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </>
      )}
    </section>
  );
}
