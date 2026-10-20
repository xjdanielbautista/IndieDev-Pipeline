import { useState } from "react";
import { Trash2, UserPlus } from "lucide-react";
import { addMember, removeMember, updateMemberRole } from "../api/studio";
import { ROLE_INFO, assignableRoles, canManageMember, isManager } from "../utils/permissions";
import { Avatar, inputClass, Label, PrimaryButton, useToast } from "./ui";

const ROLE_ORDER = ["owner", "admin", "developer", "artist", "tester"];

export default function TeamPanel({ tenant, members, assets, currentUser, onMembersChange }) {
  const notify = useToast();
  const myRole = tenant.role;
  const roles = assignableRoles(myRole);
  const [identifier, setIdentifier] = useState("");
  const [newRole, setNewRole] = useState(roles.includes("developer") ? "developer" : roles[0]);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const sorted = [...members].sort(
    (a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) || (a.username ?? "").localeCompare(b.username ?? ""),
  );

  // Tareas pendientes (no terminadas) por integrante en el proyecto actual.
  const workload = (id) => assets.filter((a) => a.status !== "done" && a.assigned_user_ids.includes(id)).length;

  const invite = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const member = await addMember(tenant.id, identifier.trim(), newRole);
      onMembersChange([...members, member]);
      setIdentifier("");
      notify(`${member.username} se unió como ${ROLE_INFO[member.role].label}`, "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setSaving(false);
    }
  };

  const changeRole = async (member, role) => {
    setBusyId(member.id);
    try {
      const updated = await updateMemberRole(tenant.id, member.id, role);
      onMembersChange(members.map((m) => (m.id === updated.id ? updated : m)));
      notify(`${updated.username} ahora es ${ROLE_INFO[updated.role].label}`, "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (member) => {
    if (!window.confirm(`¿Quitar a ${member.username} del estudio? Se le quitarán sus asignaciones y bloqueos.`)) return;
    setBusyId(member.id);
    try {
      await removeMember(tenant.id, member.id);
      onMembersChange(members.filter((m) => m.id !== member.id));
      notify(`${member.username} ya no es parte del estudio`, "success");
    } catch (err) {
      if (err.status !== 401) notify(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto grid gap-6 lg:grid-cols-[1fr_300px]">
      <section>
        <h2 className="text-lg font-semibold text-white">Equipo de {tenant.name}</h2>
        <p className="text-xs text-gray-500 mb-4">
          {isManager(myRole)
            ? "Agrega integrantes y elige su rol; el rol decide qué pueden hacer en el tablero."
            : `Tu rol es ${ROLE_INFO[myRole]?.label}. Solo el dueño o un admin pueden cambiar roles.`}
        </p>

        <ul className="divide-y divide-[#272B3B] border border-[#272B3B] rounded-lg bg-[#151822]">
          {sorted.map((m) => {
            const editable = canManageMember(myRole, m.role) && m.id !== currentUser.id;
            const pending = workload(m.id);
            return (
              <li key={m.id} className="flex items-center gap-3 px-4 py-3">
                <Avatar user={m} size="w-9 h-9 text-xs" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-white truncate">
                    {m.username}
                    {m.id === currentUser.id && <span className="text-gray-500"> (tú)</span>}
                  </p>
                  <p className="text-xs text-gray-500 truncate">
                    {m.email} · {pending} {pending === 1 ? "tarea pendiente" : "tareas pendientes"}
                  </p>
                </div>
                {editable ? (
                  <select
                    aria-label={`Rol de ${m.username}`}
                    value={m.role}
                    disabled={busyId === m.id}
                    onChange={(e) => changeRole(m, e.target.value)}
                    className="bg-[#0B0D14] border border-[#272B3B] text-white text-sm rounded-md px-2 py-1.5 focus:outline-none focus:border-[#00F0FF]"
                  >
                    {[...new Set([m.role, ...roles])].map((r) => (
                      <option key={r} value={r}>
                        {ROLE_INFO[r].label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="text-[11px] font-mono uppercase px-2 py-1 rounded border border-[#272B3B] text-gray-400">
                    {ROLE_INFO[m.role]?.label ?? m.role}
                  </span>
                )}
                {editable && (
                  <button
                    onClick={() => remove(m)}
                    disabled={busyId === m.id}
                    title={`Quitar a ${m.username}`}
                    className="p-2 text-gray-500 hover:text-[#FF3D00] hover:bg-[#FF3D00]/10 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <aside className="space-y-4">
        {isManager(myRole) && (
          <form onSubmit={invite} className="bg-[#151822] border border-[#272B3B] rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-[#00F0FF]" /> Agregar integrante
            </h3>
            <div>
              <Label>Usuario o email</Label>
              <input
                className={inputClass}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="sam_art o sam@correo.com"
                required
                minLength={3}
              />
            </div>
            <div>
              <Label>Rol</Label>
              <select className={inputClass} value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                {roles.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_INFO[r].label}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-[11px] text-gray-500">La persona debe haber creado su cuenta antes.</p>
            <PrimaryButton type="submit" loading={saving} className="w-full">
              Agregar
            </PrimaryButton>
          </form>
        )}

        <div className="bg-[#151822] border border-[#272B3B] rounded-lg p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Qué puede hacer cada rol</h3>
          <dl className="space-y-2.5">
            {ROLE_ORDER.map((r) => (
              <div key={r}>
                <dt className={`text-xs font-semibold ${r === myRole ? "text-[#00F0FF]" : "text-gray-300"}`}>
                  {ROLE_INFO[r].label}
                  {r === myRole && " (tu rol)"}
                </dt>
                <dd className="text-xs text-gray-500">{ROLE_INFO[r].description}</dd>
              </div>
            ))}
          </dl>
        </div>
      </aside>
    </div>
  );
}
