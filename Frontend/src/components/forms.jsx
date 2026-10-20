import { useState } from "react";
import { createAsset, createBuild, createProject, createTenant } from "../api/studio";
import { CATEGORIES, STATUSES, slugify } from "../utils/labels";
import { Avatar, inputClass, Label, PrimaryButton, useToast } from "./ui";

// ---------- Crear estudio ----------
export function CreateStudioForm({ onCreated }) {
  const notify = useToast();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const tenant = await createTenant(name.trim(), slug);
      onCreated(tenant);
    } catch (err) {
      notify(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label>Nombre del estudio</Label>
        <input
          className={inputClass}
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!slugTouched) setSlug(slugify(e.target.value));
          }}
          placeholder="Pixel Ninja Studios"
          required
          maxLength={120}
          autoFocus
        />
      </div>
      <div>
        <Label hint="identificador único, solo minúsculas, números y guiones">Identificador</Label>
        <input
          className={`${inputClass} font-mono`}
          value={slug}
          onChange={(e) => {
            setSlugTouched(true);
            setSlug(slugify(e.target.value));
          }}
          placeholder="pixel-ninja"
          required
          minLength={2}
          maxLength={80}
        />
      </div>
      <p className="text-xs text-gray-500">Quedarás como dueño del estudio.</p>
      <PrimaryButton type="submit" loading={loading} className="w-full">
        Crear estudio
      </PrimaryButton>
    </form>
  );
}

// ---------- Crear proyecto ----------
export function CreateProjectForm({ tenantId, onCreated }) {
  const notify = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const project = await createProject(tenantId, name.trim(), description.trim());
      onCreated(project);
    } catch (err) {
      notify(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label>Nombre del juego / proyecto</Label>
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="CyberBlade: Neon City"
          required
          maxLength={160}
          autoFocus
        />
      </div>
      <div>
        <Label hint="opcional">Descripción</Label>
        <textarea
          className={`${inputClass} resize-none`}
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Plataformas 2D cyberpunk"
        />
      </div>
      <PrimaryButton type="submit" loading={loading} className="w-full">
        Crear proyecto
      </PrimaryButton>
    </form>
  );
}

// ---------- Crear tarea ----------
export function CreateTaskForm({ tenant, projectId, members, onCreated }) {
  const notify = useToast();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("code");
  const [status, setStatus] = useState("backlog");
  const [assigned, setAssigned] = useState([]);
  const [restricted, setRestricted] = useState(false);
  const [loading, setLoading] = useState(false);

  const toggleMember = (id) =>
    setAssigned((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const submit = async (e) => {
    e.preventDefault();
    if (restricted && assigned.length === 0) {
      notify("Para restringir la tarea, asigna al menos a un integrante.");
      return;
    }
    setLoading(true);
    try {
      const trimmed = name.trim();
      // storage_key: ruta interna donde vivirá el archivo cuando exista la subida a Firebase/S3.
      const storageKey = `studios/${tenant.slug}/projects/${projectId}/${slugify(trimmed) || "tarea"}-${Date.now()}`;
      const asset = await createAsset(tenant.id, projectId, {
        original_name: trimmed,
        storage_key: storageKey,
        category,
        status,
        assignment_mode: restricted ? "restricted" : "open",
        assigned_user_ids: assigned,
      });
      onCreated(asset);
    } catch (err) {
      notify(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label>Nombre de la tarea o archivo</Label>
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Sprites del enemigo Scavenger"
          required
          maxLength={255}
          autoFocus
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label>Tipo</Label>
          <div className="grid grid-cols-2 gap-1 p-1 bg-[#0B0D14] border border-[#272B3B] rounded-lg">
            {Object.entries(CATEGORIES).map(([id, c]) => (
              <button
                type="button"
                key={id}
                onClick={() => setCategory(id)}
                className={`py-1.5 text-sm rounded-md ${category === id ? "bg-[#1C202D] text-white" : "text-gray-500"}`}
                style={category === id ? { boxShadow: `inset 0 -2px 0 ${c.color}` } : undefined}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <Label>Columna</Label>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <Label hint="puedes elegir varios">Asignar a</Label>
        <div className="flex flex-wrap gap-2">
          {members.map((m) => {
            const active = assigned.includes(m.id);
            return (
              <button
                type="button"
                key={m.id}
                onClick={() => toggleMember(m.id)}
                className={`flex items-center gap-2 pl-1 pr-3 py-1 rounded-full border text-sm transition-colors ${
                  active ? "border-[#00F0FF] bg-[#00F0FF]/10 text-white" : "border-[#272B3B] text-gray-400 hover:text-white"
                }`}
              >
                <Avatar user={m} />
                {m.username}
              </button>
            );
          })}
        </div>
      </div>

      <label className="flex items-start gap-2 text-sm text-gray-300 cursor-pointer">
        <input
          type="checkbox"
          className="mt-0.5 accent-[#00F0FF]"
          checked={restricted}
          onChange={(e) => setRestricted(e.target.checked)}
        />
        <span>
          Solo los asignados pueden moverla
          <span className="block text-xs text-gray-500">Si no la marcas, cualquier integrante puede avanzarla.</span>
        </span>
      </label>

      <PrimaryButton type="submit" loading={loading} className="w-full">
        Crear tarea
      </PrimaryButton>
    </form>
  );
}

// ---------- Registrar build ----------
export function CreateBuildForm({ tenantId, projectId, onCreated }) {
  const notify = useToast();
  const [version, setVersion] = useState("");
  const [status, setStatus] = useState("pending");
  const [notes, setNotes] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const build = await createBuild(tenantId, projectId, {
        version: version.trim(),
        status,
        notes: notes.trim() || null,
        build_url: url.trim() || null,
      });
      onCreated(build);
    } catch (err) {
      notify(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label>Versión</Label>
          <input
            className={`${inputClass} font-mono`}
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="v0.9.5"
            required
            maxLength={60}
            autoFocus
          />
        </div>
        <div>
          <Label>Estado</Label>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="pending">Pendiente</option>
            <option value="success">Exitoso</option>
            <option value="failed">Fallido</option>
          </select>
        </div>
      </div>
      <div>
        <Label hint="opcional">Notas</Label>
        <textarea
          className={`${inputClass} resize-none`}
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Arreglado el dash aéreo, nuevas texturas del nivel 3"
        />
      </div>
      <div>
        <Label hint="opcional">URL de descarga</Label>
        <input
          className={inputClass}
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://..."
          maxLength={500}
        />
      </div>
      <PrimaryButton type="submit" loading={loading} className="w-full">
        Registrar build
      </PrimaryButton>
    </form>
  );
}
