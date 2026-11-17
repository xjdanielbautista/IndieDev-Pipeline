// Archivo de una tarea: vista previa, subir versión, historial de versiones,
// restaurar y comparar dos versiones.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Columns2, Download, Eye, FileUp, GitCompare, Layers, RotateCcw } from "lucide-react";
import {
  downloadAssetFile,
  fetchAssetPreview,
  getAssetStreamSource,
  listAssetVersions,
  restoreAssetVersion,
  uploadAssetFile,
} from "../api/studio";
import { formatBytes, formatDateTime, timeAgo } from "../utils/labels";
import { canLock } from "../utils/permissions";
import { isTextKind, looksLikeText, previewKind, safeBlobType } from "../utils/fileTypes";
import { collapseUnchanged, lineDiff } from "../utils/textDiff";
import CodeView from "./CodeView";
import { Modal, inputClass, useToast } from "./ui";

// Carga el contenido de una versión (o la actual si versionId es null) listo para mostrar.
function usePreview({ tenantId, projectId, assetId, versionId, fileName, contentType, revision, enabled = true }) {
  const { kind, language } = previewKind(fileName, contentType);
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    if (!enabled || kind === "other") return undefined;
    let cancelled = false;
    let objectUrl = null;
    setState({ status: "loading" });
    (async () => {
      try {
        const blob = await fetchAssetPreview(tenantId, projectId, assetId, versionId);
        if (isTextKind(kind)) {
          const bytes = new Uint8Array(await blob.arrayBuffer());
          if (!looksLikeText(bytes)) {
            if (!cancelled) setState({ status: "unsupported" });
            return;
          }
          const text = new TextDecoder().decode(bytes);
          if (!cancelled) setState({ status: "ready", text });
          return;
        }
        objectUrl = URL.createObjectURL(new Blob([blob], { type: safeBlobType(kind, contentType) }));
        if (!cancelled) setState({ status: "ready", url: objectUrl });
      } catch (err) {
        // Muy grande para la vista previa: audio y video se pueden reproducir desde la descarga.
        if (err.status === 413 && (kind === "video" || kind === "audio" || kind === "image")) {
          try {
            const { url, blob } = await getAssetStreamSource(tenantId, projectId, assetId, versionId);
            if (blob) objectUrl = URL.createObjectURL(new Blob([blob], { type: safeBlobType(kind, contentType) }));
            if (!cancelled) setState({ status: "ready", url: url || objectUrl });
            return;
          } catch (inner) {
            if (!cancelled) setState({ status: "error", message: inner.message });
            return;
          }
        }
        if (!cancelled) setState({ status: err.status === 413 ? "too-big" : "error", message: err.message });
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [tenantId, projectId, assetId, versionId, kind, contentType, revision, enabled]);

  // Sin vista previa posible no hace falta pedir nada al backend.
  return kind === "other" ? { kind, language, status: "unsupported" } : { kind, language, ...state };
}

function PreviewBody({ preview, fileName, compact = false }) {
  const { kind, language, status } = preview;
  if (status === "loading") return <p className="text-xs text-gray-500 p-3">Cargando vista previa...</p>;
  if (status === "unsupported") {
    return <p className="text-xs text-gray-500 p-3">No hay vista previa para este tipo de archivo. Descárgalo para abrirlo.</p>;
  }
  if (status === "too-big") return <p className="text-xs text-gray-500 p-3">{preview.message}. Descárgalo para verlo.</p>;
  if (status === "error") return <p className="text-xs text-[#FF3D00] p-3">{preview.message}</p>;
  if (kind === "image") {
    return (
      <div className="flex items-center justify-center rounded-lg border border-[#272B3B] p-2 bg-[repeating-conic-gradient(#1C202D_0%_25%,#151822_0%_50%)] bg-[length:16px_16px]">
        <img
          src={preview.url}
          alt={fileName}
          className={`max-w-full object-contain [image-rendering:pixelated] ${compact ? "max-h-56" : "max-h-80"}`}
        />
      </div>
    );
  }
  if (kind === "audio") return <audio controls src={preview.url} className="w-full" />;
  if (kind === "video") return <video controls src={preview.url} className="w-full max-h-80 rounded-lg bg-black" />;
  if (kind === "pdf") return <iframe title={fileName} src={preview.url} className="w-full h-96 rounded-lg bg-white" />;
  return <CodeView text={preview.text} language={language} maxHeight={compact ? "max-h-64" : "max-h-96"} />;
}

// ---------- Comparar versiones ----------
function DiffView({ oldText, newText }) {
  const [full, setFull] = useState(false);
  const diff = useMemo(() => lineDiff(oldText, newText), [oldText, newText]);
  const rows = full ? diff.rows : collapseUnchanged(diff.rows);
  const tone = {
    added: "bg-[#00FF66]/10 text-[#b4ffd0]",
    removed: "bg-[#FF3D00]/10 text-[#ffb8a3]",
    same: "text-gray-300",
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-2 text-xs">
        <p className="font-mono">
          <span className="text-[#00FF66]">+{diff.added}</span> <span className="text-[#FF3D00]">−{diff.removed}</span>{" "}
          <span className="text-gray-500">{diff.added + diff.removed === 1 ? "línea" : "líneas"}</span>
        </p>
        <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
          <input type="checkbox" className="accent-[#00F0FF]" checked={full} onChange={(e) => setFull(e.target.checked)} />
          Mostrar todo el archivo
        </label>
      </div>
      {diff.added === 0 && diff.removed === 0 ? (
        <p className="text-sm text-gray-400">Las dos versiones tienen el mismo contenido.</p>
      ) : (
        <div className="max-h-[60vh] overflow-auto rounded-lg border border-[#272B3B] bg-[#0d1117] text-xs font-mono">
          <table className="w-full border-collapse">
            <tbody>
              {rows.map((row, i) =>
                row.type === "gap" ? (
                  <tr key={i}>
                    <td colSpan={4} className="text-center text-gray-600 py-1 bg-[#151822]">
                      ··· {row.count} {row.count === 1 ? "línea" : "líneas"} sin cambios ···
                    </td>
                  </tr>
                ) : (
                  <tr key={i} className={`${tone[row.type]} align-top`}>
                    <td className="select-none text-right px-2 text-gray-600 w-px">{row.oldLine ?? ""}</td>
                    <td className="select-none text-right px-2 text-gray-600 w-px">{row.newLine ?? ""}</td>
                    <td className="select-none px-1 w-px">{row.type === "added" ? "+" : row.type === "removed" ? "−" : " "}</td>
                    <td className="pr-3 whitespace-pre">{row.text || " "}</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ImageCompare({ before, after, fileName }) {
  const [mode, setMode] = useState("side"); // "side" | "overlay"
  const [mix, setMix] = useState(50);
  const ready = before.status === "ready" && after.status === "ready";
  return (
    <div>
      <div className="flex gap-1 mb-3">
        {[["side", "Lado a lado", Columns2], ["overlay", "Superponer", Layers]].map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded border ${
              mode === id ? "border-[#00F0FF]/50 bg-[#00F0FF]/10 text-white" : "border-[#272B3B] text-gray-400 hover:text-white"
            }`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>
      {mode === "side" || !ready ? (
        <div className="grid sm:grid-cols-2 gap-3">
          <PreviewBody preview={before} fileName={fileName} compact />
          <PreviewBody preview={after} fileName={fileName} compact />
        </div>
      ) : (
        <div>
          <div className="relative flex items-center justify-center rounded-lg border border-[#272B3B] p-2 min-h-40 bg-[repeating-conic-gradient(#1C202D_0%_25%,#151822_0%_50%)] bg-[length:16px_16px]">
            <img src={before.url} alt="Versión anterior" className="max-h-80 max-w-full object-contain [image-rendering:pixelated]" />
            <img
              src={after.url}
              alt="Versión nueva"
              style={{ opacity: mix / 100 }}
              className="absolute inset-0 m-auto max-h-80 max-w-full object-contain [image-rendering:pixelated] p-2"
            />
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={mix}
            onChange={(e) => setMix(Number(e.target.value))}
            className="w-full mt-3 accent-[#00F0FF]"
            aria-label="Mezcla entre versiones"
          />
          <div className="flex justify-between text-[11px] text-gray-500 font-mono">
            <span>Anterior</span>
            <span>Nueva</span>
          </div>
        </div>
      )}
    </div>
  );
}

function CompareVersions({ tenantId, projectId, asset, versions }) {
  const [oldId, setOldId] = useState(versions[1]?.id);
  const [newId, setNewId] = useState(versions[0]?.id);
  const oldVersion = versions.find((v) => v.id === oldId);
  const newVersion = versions.find((v) => v.id === newId);
  const common = { tenantId, projectId, assetId: asset.id };
  const before = usePreview({ ...common, versionId: oldId, fileName: oldVersion?.file_name, contentType: oldVersion?.content_type });
  const after = usePreview({ ...common, versionId: newId, fileName: newVersion?.file_name, contentType: newVersion?.content_type });

  const label = (v) => `v${v.version} · ${v.uploaded_by?.username ?? "—"} · ${formatDateTime(v.uploaded_at)}`;
  const picker = (value, onChange, title) => (
    <div className="flex-1 min-w-0">
      <p className="text-xs font-mono text-gray-400 mb-1">{title}</p>
      <select className={inputClass} value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {versions.map((v) => (
          <option key={v.id} value={v.id}>
            {label(v)}
          </option>
        ))}
      </select>
    </div>
  );

  let body;
  if (before.status !== "ready" || after.status !== "ready") {
    body = (
      <div className="grid sm:grid-cols-2 gap-3">
        <PreviewBody preview={before} fileName={oldVersion?.file_name} compact />
        <PreviewBody preview={after} fileName={newVersion?.file_name} compact />
      </div>
    );
  } else if (isTextKind(before.kind) && isTextKind(after.kind)) {
    body = <DiffView oldText={before.text} newText={after.text} />;
  } else if (before.kind === "image" && after.kind === "image") {
    body = <ImageCompare before={before} after={after} fileName={asset.original_name} />;
  } else {
    body = (
      <div className="grid sm:grid-cols-2 gap-3">
        <PreviewBody preview={before} fileName={oldVersion?.file_name} compact />
        <PreviewBody preview={after} fileName={newVersion?.file_name} compact />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        {picker(oldId, setOldId, "Anterior")}
        {picker(newId, setNewId, "Nueva")}
      </div>
      {oldVersion && newVersion && (
        <p className="text-xs text-gray-500">
          {formatBytes(oldVersion.file_size)} → {formatBytes(newVersion.file_size)}
        </p>
      )}
      {body}
    </div>
  );
}

// ---------- Panel principal ----------
export default function FilePanel({ tenant, projectId, asset, role, currentUser, onChanged }) {
  const notify = useToast();
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [loadedVersions, setVersions] = useState([]);
  const [busyVersion, setBusyVersion] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [viewing, setViewing] = useState(null); // versión anterior abierta en grande

  const hasFile = asset.file_size !== null && asset.file_size !== undefined;
  const lockedByMe = asset.locked_by_user_id === currentUser?.id;
  const allowedRole = canLock(role, asset.category);
  const canChange = lockedByMe && allowedRole;
  const versions = hasFile ? loadedVersions : [];
  const current = versions[0];

  const loadVersions = useCallback(async () => {
    try {
      setVersions(await listAssetVersions(tenant.id, projectId, asset.id));
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    }
  }, [tenant.id, projectId, asset.id, notify]);

  useEffect(() => {
    if (hasFile) loadVersions();
  }, [hasFile, asset.file_uploaded_at, loadVersions]);

  const preview = usePreview({
    tenantId: tenant.id,
    projectId,
    assetId: asset.id,
    versionId: null,
    fileName: current?.file_name ?? asset.original_name,
    contentType: asset.content_type,
    revision: asset.file_uploaded_at,
    enabled: hasFile,
  });

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      onChanged(await uploadAssetFile(tenant.id, projectId, asset.id, file));
      notify("Nueva versión subida", "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const download = async (version = null) => {
    try {
      await downloadAssetFile(tenant.id, projectId, asset.id, version?.file_name ?? asset.original_name, version?.id ?? null);
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    }
  };

  const restore = async (version) => {
    setBusyVersion(version.id);
    try {
      onChanged(await restoreAssetVersion(tenant.id, projectId, asset.id, version.id));
      notify(`Se restauró la versión ${version.version}`, "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setBusyVersion(null);
    }
  };

  const hint = !allowedRole
    ? "Tu rol no puede subir archivos de este tipo."
    : !lockedByMe
      ? "Bloquéalo para subir una nueva versión o restaurar una anterior."
      : null;

  return (
    <section>
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-2">
        <FileUp className="w-4 h-4 text-gray-400" /> Archivo
        {versions.length > 0 && <span className="text-[10px] font-mono text-gray-500">v{current?.version}</span>}
      </h3>

      <div className="rounded-lg border border-[#272B3B] bg-[#0B0D14] p-3 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs min-w-0">
            {hasFile ? (
              <>
                <p className="text-white truncate">{current?.file_name ?? asset.original_name}</p>
                <p className="text-gray-500">
                  {formatBytes(asset.file_size)} · subido {timeAgo(asset.file_uploaded_at)}
                  {current?.uploaded_by && ` por ${current.uploaded_by.username}`}
                </p>
              </>
            ) : (
              <p className="text-gray-500">Todavía no hay archivo.</p>
            )}
            {hint && <p className="text-gray-600 mt-1">{hint}</p>}
          </div>
          <div className="flex gap-2 shrink-0">
            {hasFile && (
              <button
                onClick={() => download()}
                title="Descargar"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-[#1C202D] text-gray-200 hover:bg-[#272B3B]"
              >
                <Download className="w-4 h-4" /> <span className="hidden sm:inline">Descargar</span>
              </button>
            )}
            <input ref={inputRef} type="file" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
            <button
              disabled={!canChange || uploading}
              onClick={() => inputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-[#00F0FF]/15 text-[#00F0FF] hover:bg-[#00F0FF]/25 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <FileUp className="w-4 h-4" /> {uploading ? "Subiendo..." : "Subir versión"}
            </button>
          </div>
        </div>

        {hasFile && <PreviewBody preview={preview} fileName={current?.file_name ?? asset.original_name} />}
      </div>

      {versions.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-mono text-gray-400">Versiones ({versions.length})</p>
            {versions.length > 1 && (
              <button
                onClick={() => setComparing(true)}
                className="flex items-center gap-1.5 text-xs text-[#00F0FF] hover:text-white px-2 py-1 rounded border border-[#00F0FF]/30 hover:bg-[#00F0FF]/10"
              >
                <GitCompare className="w-3.5 h-3.5" /> Comparar
              </button>
            )}
          </div>
          <ul className="space-y-1.5">
            {versions.map((v, i) => (
              <li key={v.id} className="flex items-center justify-between gap-2 text-xs rounded-md border border-[#272B3B] px-2.5 py-1.5">
                <div className="min-w-0">
                  <p className="text-gray-200 truncate">
                    <span className="font-mono text-white">v{v.version}</span> · {v.file_name}
                    {i === 0 && <span className="ml-1.5 text-[10px] text-[#00FF66]">actual</span>}
                  </p>
                  <p className="text-gray-500 truncate">
                    {v.uploaded_by?.username ?? "—"} · {formatDateTime(v.uploaded_at)} · {formatBytes(v.file_size)}
                    {v.restored_from_version && ` · restaurada de v${v.restored_from_version}`}
                  </p>
                </div>
                <div className="flex gap-1 shrink-0">
                  {i > 0 && (
                    <button onClick={() => setViewing(v)} title="Ver" className="p-1.5 text-gray-400 hover:text-white rounded">
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button onClick={() => download(v)} title="Descargar" className="p-1.5 text-gray-400 hover:text-white rounded">
                    <Download className="w-3.5 h-3.5" />
                  </button>
                  {i > 0 && (
                    <button
                      onClick={() => restore(v)}
                      disabled={!canChange || busyVersion !== null}
                      title={canChange ? "Volver a esta versión" : hint ?? ""}
                      className="p-1.5 text-gray-400 hover:text-[#00F0FF] rounded disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {comparing && (
        <Modal title={`Comparar versiones de ${asset.original_name}`} onClose={() => setComparing(false)} width="max-w-5xl">
          <CompareVersions tenantId={tenant.id} projectId={projectId} asset={asset} versions={versions} />
        </Modal>
      )}
      {viewing && (
        <Modal title={`v${viewing.version} · ${viewing.file_name}`} onClose={() => setViewing(null)} width="max-w-3xl">
          <VersionViewer tenantId={tenant.id} projectId={projectId} asset={asset} version={viewing} />
        </Modal>
      )}
    </section>
  );
}

function VersionViewer({ tenantId, projectId, asset, version }) {
  const preview = usePreview({
    tenantId,
    projectId,
    assetId: asset.id,
    versionId: version.id,
    fileName: version.file_name,
    contentType: version.content_type,
  });
  return <PreviewBody preview={preview} fileName={version.file_name} />;
}
