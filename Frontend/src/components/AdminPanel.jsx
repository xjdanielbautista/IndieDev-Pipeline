// Panel de la plataforma (solo superadmin, definido en SUPERADMIN_EMAILS del backend):
// ver y eliminar usuarios y estudios.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, RefreshCw, Search, Shield, Trash2, Users } from "lucide-react";
import { adminDeleteTenant, adminDeleteUser, adminListTenants, adminListUsers } from "../api/studio";
import { formatDateTime } from "../utils/labels";
import { Avatar, useToast } from "./ui";

function ConfirmButton({ label, onConfirm, disabled, title }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!asking) {
    return (
      <button
        onClick={() => setAsking(true)}
        disabled={disabled}
        title={title}
        className="p-1.5 text-gray-400 hover:text-[#FF3D00] rounded disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label={label}
      >
        <Trash2 className="w-4 h-4" />
      </button>
    );
  }
  return (
    <span className="flex items-center gap-1 text-xs whitespace-nowrap">
      <span className="text-[#ffb8a3]">¿Eliminar?</span>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          await onConfirm();
          setBusy(false);
          setAsking(false);
        }}
        className="px-2 py-1 rounded bg-[#FF3D00] text-black font-semibold disabled:opacity-40"
      >
        Sí
      </button>
      <button onClick={() => setAsking(false)} className="px-2 py-1 rounded border border-[#272B3B] text-gray-300">
        No
      </button>
    </span>
  );
}

export default function AdminPanel({ currentUser, onTenantDeleted }) {
  const notify = useToast();
  const [users, setUsers] = useState(null);
  const [tenants, setTenants] = useState(null);
  const [view, setView] = useState("users");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      const [userList, tenantList] = await Promise.all([adminListUsers(), adminListTenants()]);
      setUsers(userList);
      setTenants(tenantList);
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    }
  }, [notify]);

  useEffect(() => {
    load();
  }, [load]);

  const term = search.trim().toLowerCase();
  const shownUsers = useMemo(
    () =>
      (users ?? []).filter(
        (u) => !term || u.username?.toLowerCase().includes(term) || u.email.toLowerCase().includes(term),
      ),
    [users, term],
  );
  const shownTenants = useMemo(
    () =>
      (tenants ?? []).filter(
        (t) => !term || t.name.toLowerCase().includes(term) || t.slug.includes(term) || t.owner_username?.includes(term),
      ),
    [tenants, term],
  );

  const removeUser = async (user) => {
    try {
      await adminDeleteUser(user.id);
      notify(`Se eliminó a ${user.username ?? user.email}`, "success");
      await load();
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    }
  };

  const removeTenant = async (tenant) => {
    try {
      await adminDeleteTenant(tenant.id);
      notify(`Se eliminó el estudio ${tenant.name}`, "success");
      onTenantDeleted?.(tenant.id);
      await load();
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    }
  };

  if (users === null) return <p className="text-sm text-gray-500">Cargando...</p>;

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-white text-lg font-semibold flex items-center gap-2">
            <Shield className="w-5 h-5 text-[#00F0FF]" /> Administración de la plataforma
          </h2>
          <p className="text-xs text-gray-500">
            {users.length} usuarios · {tenants.length} estudios. Para eliminar a un dueño, primero elimina su estudio.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2 w-4 h-4 text-gray-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar"
              className="bg-[#151822] border border-[#272B3B] text-sm text-white rounded-md pl-8 pr-3 py-1.5 w-40 focus:outline-none focus:border-[#00F0FF]"
            />
          </div>
          <div className="flex bg-[#151822] border border-[#272B3B] rounded-md p-0.5">
            {[["users", "Usuarios", Users], ["tenants", "Estudios", Building2]].map(([id, label, Icon]) => (
              <button
                key={id}
                onClick={() => setView(id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded ${
                  view === id ? "bg-[#1C202D] text-white" : "text-gray-500 hover:text-white"
                }`}
              >
                <Icon className="w-3.5 h-3.5" /> {label}
              </button>
            ))}
          </div>
          <button onClick={load} title="Recargar" className="p-1.5 text-gray-400 hover:text-white rounded-md border border-[#272B3B]">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[#272B3B]">
        {view === "users" ? (
          <table className="w-full text-sm">
            <thead className="bg-[#151822] text-xs font-mono text-gray-400 text-left">
              <tr>
                <th className="px-3 py-2">Usuario</th>
                <th className="px-3 py-2">Correo</th>
                <th className="px-3 py-2">Estudios</th>
                <th className="px-3 py-2 w-px" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#272B3B]">
              {shownUsers.map((u) => (
                <tr key={u.id} className="align-top">
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Avatar user={u} />
                      <span className="text-white">{u.username ?? "—"}</span>
                      <span className="text-[10px] font-mono text-gray-600">#{u.id}</span>
                      {u.is_superadmin && (
                        <span className="text-[10px] font-mono px-1 rounded border border-[#00F0FF]/30 text-[#00F0FF]">admin</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-gray-400">
                    {u.email}
                    {!u.email_verified && <span className="block text-[11px] text-yellow-500">sin confirmar</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-400 text-xs">
                    {u.studios.length ? u.studios.join(", ") : "—"}
                    {u.owned_studios.length > 0 && (
                      <span className="block text-[11px] text-gray-500">dueño de: {u.owned_studios.join(", ")}</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <ConfirmButton
                      label={`Eliminar a ${u.username}`}
                      onConfirm={() => removeUser(u)}
                      disabled={u.id === currentUser.id || u.owned_studios.length > 0}
                      title={
                        u.id === currentUser.id
                          ? "Tu propia cuenta se elimina desde Mi cuenta"
                          : u.owned_studios.length > 0
                            ? "Primero elimina los estudios de los que es dueño"
                            : "Eliminar usuario"
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-[#151822] text-xs font-mono text-gray-400 text-left">
              <tr>
                <th className="px-3 py-2">Estudio</th>
                <th className="px-3 py-2">Dueño</th>
                <th className="px-3 py-2 text-right">Integrantes</th>
                <th className="px-3 py-2 text-right">Proyectos</th>
                <th className="px-3 py-2 text-right">Tareas</th>
                <th className="px-3 py-2">Creado</th>
                <th className="px-3 py-2 w-px" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#272B3B]">
              {shownTenants.map((t) => (
                <tr key={t.id}>
                  <td className="px-3 py-2">
                    <span className="text-white">{t.name}</span>
                    <span className="block text-[11px] font-mono text-gray-500">{t.slug}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-400">{t.owner_username ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">{t.member_count}</td>
                  <td className="px-3 py-2 text-right font-mono">{t.project_count}</td>
                  <td className="px-3 py-2 text-right font-mono">{t.asset_count}</td>
                  <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">{formatDateTime(t.created_at)}</td>
                  <td className="px-3 py-2">
                    <ConfirmButton
                      label={`Eliminar ${t.name}`}
                      onConfirm={() => removeTenant(t)}
                      title="Eliminar el estudio con todos sus proyectos, tareas y archivos"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
