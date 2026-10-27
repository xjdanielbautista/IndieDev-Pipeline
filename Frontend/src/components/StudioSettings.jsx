import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, FolderKanban, ScrollText, Settings } from "lucide-react";
import { deleteProject, deleteTenant, listActivity, updateProject, updateTenant } from "../api/studio";
import { formatDateTime, slugify, timeAgo } from "../utils/labels";
import { GhostButton, inputClass, Label, PrimaryButton, useToast } from "./ui";

// Pestaña "Ajustes" (solo dueño/admin): editar el estudio y el proyecto actual,
// ver la bitácora del estudio y, solo el dueño, eliminar el estudio.

const ACTIONS = {
  tenant_created: { label: "Estudio", color: "#00F0FF" },
  tenant_updated: { label: "Estudio", color: "#00F0FF" },
  member_added: { label: "Equipo", color: "#00FF66" },
  member_role_changed: { label: "Equipo", color: "#00FF66" },
  member_removed: { label: "Equipo", color: "#FF8A00" },
  project_created: { label: "Proyecto", color: "#A78BFA" },
  project_updated: { label: "Proyecto", color: "#A78BFA" },
  project_deleted: { label: "Proyecto", color: "#FF3D00" },
  asset_created: { label: "Tarea", color: "#FFC400" },
  asset_deleted: { label: "Tarea", color: "#FF3D00" },
  github_connected: { label: "GitHub", color: "#9CA3AF" },
};

function Card({ icon: Icon, title, children, danger = false }) {
  return (
    <section
      className={`bg-[#151822] border rounded-xl p-5 ${danger ? "border-[#FF3D00]/40" : "border-[#272B3B]"}`}
    >
      <h3 className={`flex items-center gap-2 font-semibold mb-4 ${danger ? "text-[#FF3D00]" : "text-white"}`}>
        <Icon className="w-4 h-4" /> {title}
      </h3>
      {children}
    </section>
  );
}

function StudioForm({ tenant, onUpdated }) {
  const notify = useToast();
  const [name, setName] = useState(tenant.name);
  const [slug, setSlug] = useState(tenant.slug);
  const [saving, setSaving] = useState(false);

  const unchanged = name.trim() === tenant.name && slug === tenant.slug;

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateTenant(tenant.id, { name: name.trim(), slug });
      onUpdated(updated);
      notify("Estudio actualizado", "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label>Nombre del estudio</Label>
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
      </div>
      <div>
        <Label hint="único entre todos los estudios">Identificador</Label>
        <input
          className={`${inputClass} font-mono`}
          value={slug}
          onChange={(e) => setSlug(slugify(e.target.value))}
          required
          minLength={2}
          maxLength={80}
        />
      </div>
      <PrimaryButton type="submit" loading={saving} disabled={unchanged}>
        Guardar cambios
      </PrimaryButton>
    </form>
  );
}

function ProjectForm({ tenant, project, onUpdated, onDeleted }) {
  const notify = useToast();
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const unchanged = name.trim() === project.name && description.trim() === (project.description ?? "");

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateProject(tenant.id, project.id, { name: name.trim(), description: description.trim() || null });
      onUpdated(updated);
      notify("Proyecto actualizado", "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await deleteProject(tenant.id, project.id);
      notify(`Proyecto "${project.name}" eliminado`, "success");
      onDeleted(project.id);
    } catch (err) {
      if (err.status !== 401) notify(err.message);
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label>Nombre del proyecto</Label>
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} />
      </div>
      <div>
        <Label>Descripción</Label>
        <textarea
          className={`${inputClass} min-h-[72px]`}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <PrimaryButton type="submit" loading={saving} disabled={unchanged}>
          Guardar cambios
        </PrimaryButton>
        {!confirmDelete ? (
          <GhostButton type="button" onClick={() => setConfirmDelete(true)} className="hover:!text-[#FF3D00]">
            Eliminar proyecto
          </GhostButton>
        ) : (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[#ffb8a3]">Se borran sus tareas y builds. ¿Seguro?</span>
            <button
              type="button"
              onClick={remove}
              disabled={saving}
              className="px-3 py-1.5 rounded-lg bg-[#FF3D00] text-black font-semibold disabled:opacity-40"
            >
              Sí, eliminar
            </button>
            <GhostButton type="button" onClick={() => setConfirmDelete(false)}>
              Cancelar
            </GhostButton>
          </div>
        )}
      </div>
    </form>
  );
}

function ActivityLog({ tenantId, refreshKey }) {
  const notify = useToast();
  const [entries, setEntries] = useState(null);

  const load = useCallback(async () => {
    try {
      setEntries(await listActivity(tenantId));
    } catch (err) {
      setEntries([]);
      if (err.status !== 401) notify(err.message);
    }
  }, [tenantId, notify]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (entries === null) return <p className="text-sm text-gray-500 font-mono">Cargando bitácora...</p>;
  if (entries.length === 0) return <p className="text-sm text-gray-500">Todavía no hay actividad registrada.</p>;

  return (
    <ol className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
      {entries.map((entry) => {
        const info = ACTIONS[entry.action] ?? { label: "Otro", color: "#9CA3AF" };
        return (
          <li key={entry.id} className="flex gap-3">
            <span
              className="mt-0.5 h-fit text-[10px] font-mono px-1.5 py-0.5 rounded border shrink-0 w-16 text-center"
              style={{ color: info.color, borderColor: `${info.color}55`, background: `${info.color}15` }}
            >
              {info.label}
            </span>
            <div className="min-w-0">
              <p className="text-sm text-gray-300 break-words">
                <span className="text-white font-medium">{entry.actor_username}</span> · {entry.summary}
              </p>
              <time className="text-[11px] font-mono text-gray-500" title={formatDateTime(entry.created_at)}>
                {formatDateTime(entry.created_at)} · {timeAgo(entry.created_at)}
              </time>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function DeleteStudio({ tenant, onDeleted }) {
  const notify = useToast();
  const [typed, setTyped] = useState("");
  const [deleting, setDeleting] = useState(false);

  const remove = async (e) => {
    e.preventDefault();
    setDeleting(true);
    try {
      await deleteTenant(tenant.id, typed);
      notify(`Estudio "${tenant.name}" eliminado`, "success");
      onDeleted(tenant.id);
    } catch (err) {
      if (err.status !== 401) notify(err.message);
      setDeleting(false);
    }
  };

  return (
    <form onSubmit={remove} className="space-y-3">
      <p className="text-sm text-gray-400">
        Se eliminan para siempre todos sus proyectos, tareas, builds, comentarios e integrantes. Escribe{" "}
        <code className="text-[#ffb8a3] font-mono">{tenant.slug}</code> para confirmar.
      </p>
      <input
        className={`${inputClass} font-mono`}
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        placeholder={tenant.slug}
        aria-label="Identificador del estudio para confirmar"
      />
      <button
        type="submit"
        disabled={typed !== tenant.slug || deleting}
        className="bg-[#FF3D00] hover:bg-[#ff6a3d] disabled:opacity-40 disabled:cursor-not-allowed text-black font-semibold rounded-lg px-4 py-2.5 text-sm"
      >
        {deleting ? "Eliminando..." : "Eliminar estudio"}
      </button>
    </form>
  );
}

export default function StudioSettings({ tenant, project, onTenantUpdated, onTenantDeleted, onProjectUpdated, onProjectDeleted }) {
  // Cambia cada vez que se guarda algo para recargar la bitácora.
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = () => setRefreshKey((k) => k + 1);

  return (
    <div className="max-w-5xl mx-auto grid gap-5 lg:grid-cols-2">
      <div className="space-y-5">
        <Card icon={Settings} title="Estudio">
          {/* La key reinicia el formulario cuando cambian los datos guardados o el estudio. */}
          <StudioForm
            key={`${tenant.id}-${tenant.name}-${tenant.slug}`}
            tenant={tenant}
            onUpdated={(t) => {
              onTenantUpdated(t);
              bump();
            }}
          />
        </Card>
        <Card icon={FolderKanban} title={`Proyecto: ${project.name}`}>
          <ProjectForm
            key={`${project.id}-${project.name}-${project.description ?? ""}`}
            tenant={tenant}
            project={project}
            onUpdated={(p) => {
              onProjectUpdated(p);
              bump();
            }}
            onDeleted={(id) => {
              onProjectDeleted(id);
              bump();
            }}
          />
        </Card>
        {tenant.role === "owner" && (
          <Card icon={AlertTriangle} title="Zona de peligro" danger>
            <DeleteStudio tenant={tenant} onDeleted={onTenantDeleted} />
          </Card>
        )}
      </div>
      <Card icon={ScrollText} title="Bitácora del estudio">
        <p className="text-xs text-gray-500 mb-4">
          Quién cambió qué y cuándo: integrantes, roles, proyectos y tareas. Solo la ven el dueño y los admins.
        </p>
        <ActivityLog tenantId={tenant.id} refreshKey={refreshKey} />
      </Card>
    </div>
  );
}
