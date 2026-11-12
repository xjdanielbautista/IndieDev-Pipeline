// Panel de resumen del proyecto: se calcula con los datos que ya carga el tablero
// (tareas, integrantes y builds), así que no necesita endpoints nuevos.
import { AlertTriangle, CheckCircle2, Clock, Lock, Package, UserX, XCircle } from "lucide-react";
import { CATEGORIES, STATUSES, statusLabel, timeAgo } from "../utils/labels";
import { Avatar } from "./ui";

// Escala ordinal de un solo tono (Backlog → Terminado), validada contra el fondo
// oscuro #151822 con el validador de paletas: tono único, luminosidad creciente.
const STATUS_FILL = {
  backlog: "#2b6777",
  in_progress: "#1597b3",
  review: "#3fd0e8",
  done: "#b5f6ff",
};
const PENDING = ["backlog", "in_progress", "review"];

const pct = (part, total) => (total ? Math.round((part / total) * 100) : 0);

function Card({ title, children, className = "" }) {
  return (
    <section className={`bg-[#151822] border border-[#272B3B] rounded-lg p-4 ${className}`}>
      {title && <h3 className="text-sm font-semibold text-white mb-3">{title}</h3>}
      {children}
    </section>
  );
}

function StatTile({ label, value, hint, icon: Icon }) {
  return (
    <div className="bg-[#151822] border border-[#272B3B] rounded-lg p-4">
      <div className="flex items-center justify-between text-xs text-gray-400">
        {label}
        {Icon && <Icon className="w-4 h-4 text-gray-500" />}
      </div>
      <p className="text-2xl font-semibold text-white mt-1 tabular-nums">{value}</p>
      {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
    </div>
  );
}

// Barra apilada por columna. Cada segmento tiene tooltip y el conteo va en la leyenda.
function StackedBar({ counts, total, height = "h-3", label }) {
  if (!total) return <div className={`${height} rounded bg-[#0B0D14]`} aria-label={`${label}: sin tareas`} />;
  return (
    <div className={`flex gap-[2px] ${height}`} role="img" aria-label={label}>
      {STATUSES.filter((s) => counts[s.id]).map((s, i, arr) => (
        <div
          key={s.id}
          title={`${statusLabel(s.id)}: ${counts[s.id]} (${pct(counts[s.id], total)}%)`}
          className={`${i === 0 ? "rounded-l" : ""} ${i === arr.length - 1 ? "rounded-r" : ""} transition-opacity hover:opacity-80`}
          style={{ width: `${(counts[s.id] / total) * 100}%`, background: STATUS_FILL[s.id], minWidth: 4 }}
        />
      ))}
    </div>
  );
}

function Legend({ counts, total }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs">
      {STATUSES.map((s) => (
        <li key={s.id} className="flex items-center gap-1.5 text-gray-400">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: STATUS_FILL[s.id] }} />
          {s.label}
          <span className="text-gray-200 tabular-nums">{counts[s.id] ?? 0}</span>
          <span className="text-gray-600 tabular-nums">({pct(counts[s.id] ?? 0, total)}%)</span>
        </li>
      ))}
    </ul>
  );
}

function countByStatus(list) {
  return list.reduce((acc, a) => ({ ...acc, [a.status]: (acc[a.status] ?? 0) + 1 }), {});
}

function TaskLink({ asset, onOpen, children }) {
  return (
    <li>
      <button
        onClick={() => onOpen(asset)}
        className="w-full text-left flex items-center gap-2 px-2 py-1.5 -mx-2 rounded hover:bg-[#1C202D] text-sm"
      >
        <span className="text-[10px] font-mono" style={{ color: CATEGORIES[asset.category]?.color }}>
          #{asset.id}
        </span>
        <span className="text-gray-200 truncate flex-1">{asset.original_name}</span>
        <span className="text-xs text-gray-500 shrink-0">{children}</span>
      </button>
    </li>
  );
}

export default function ProjectSummary({ project, assets, members, builds, onOpen }) {
  const total = assets.length;
  const counts = countByStatus(assets);
  const done = counts.done ?? 0;
  const locked = assets.filter((a) => a.locked_by_user_id !== null);
  const unassigned = assets.filter((a) => a.status !== "done" && a.assigned_user_ids.length === 0);
  const inReview = assets.filter((a) => a.status === "review");
  const nameOf = (id) => members.find((m) => m.id === id)?.username ?? `#${id}`;

  // Carga por persona: tareas pendientes (no terminadas) asignadas a cada integrante.
  const workload = members
    .map((m) => {
      const mine = assets.filter((a) => a.assigned_user_ids.includes(m.id));
      const pending = mine.filter((a) => a.status !== "done");
      return { member: m, counts: countByStatus(pending), pending: pending.length, done: mine.length - pending.length };
    })
    .sort((a, b) => b.pending - a.pending);
  const maxPending = Math.max(1, ...workload.map((w) => w.pending), unassigned.length);

  const buildCounts = builds.reduce((acc, b) => ({ ...acc, [b.status]: (acc[b.status] ?? 0) + 1 }), {});
  const latestBuild = [...builds].sort((a, b) => b.id - a.id)[0];

  if (total === 0 && builds.length === 0) {
    return (
      <p className="text-sm text-gray-500 text-center mt-16">
        Todavía no hay datos de {project.name}. Crea tareas en el tablero para ver el resumen.
      </p>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Tareas" value={total} hint={`${total - done} pendientes`} icon={Clock} />
        <StatTile label="Avance" value={`${pct(done, total)}%`} hint={`${done} terminadas`} icon={CheckCircle2} />
        <StatTile label="En revisión" value={inReview.length} hint="esperan a un tester" icon={AlertTriangle} />
        <StatTile label="Bloqueadas" value={locked.length} hint="archivos en edición" icon={Lock} />
      </div>

      <Card title="Avance del proyecto">
        <StackedBar counts={counts} total={total} height="h-4" label={`Avance: ${pct(done, total)}% terminado`} />
        <Legend counts={counts} total={total} />
        <div className="grid sm:grid-cols-2 gap-4 mt-5">
          {Object.entries(CATEGORIES).map(([id, cat]) => {
            const list = assets.filter((a) => a.category === id);
            const c = countByStatus(list);
            return (
              <div key={id}>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="flex items-center gap-1.5 text-gray-300">
                    <span className="w-2 h-2 rounded-full" style={{ background: cat.color }} /> {cat.label}
                  </span>
                  <span className="text-gray-400 tabular-nums">
                    {c.done ?? 0} de {list.length} · {pct(c.done ?? 0, list.length)}%
                  </span>
                </div>
                <StackedBar counts={c} total={list.length} label={`${cat.label}: ${pct(c.done ?? 0, list.length)}%`} />
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid lg:grid-cols-[3fr_2fr] gap-4">
        <Card title="Carga de trabajo pendiente">
          <ul className="space-y-3">
            {workload.map(({ member, counts: c, pending, done: memberDone }) => (
              <li key={member.id} className="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3">
                <span className="flex items-center gap-2 min-w-0">
                  <Avatar user={member} />
                  <span className="text-sm text-gray-300 truncate">{member.username}</span>
                </span>
                <div style={{ width: `${(pending / maxPending) * 100}%` }} className={pending ? "" : "hidden"}>
                  <StackedBar counts={c} total={pending} label={`${member.username}: ${pending} pendientes`} />
                </div>
                {!pending && <span className="text-xs text-gray-600">Sin pendientes</span>}
                <span className="text-xs text-gray-400 tabular-nums text-right whitespace-nowrap">
                  {pending} pend. · {memberDone} hechas
                </span>
              </li>
            ))}
            {unassigned.length > 0 && (
              <li className="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3">
                <span className="flex items-center gap-2 text-sm text-gray-500">
                  <UserX className="w-5 h-5" /> Sin asignar
                </span>
                <div style={{ width: `${(unassigned.length / maxPending) * 100}%` }}>
                  <StackedBar
                    counts={countByStatus(unassigned)}
                    total={unassigned.length}
                    label={`Sin asignar: ${unassigned.length}`}
                  />
                </div>
                <span className="text-xs text-gray-400 tabular-nums text-right">{unassigned.length} pend.</span>
              </li>
            )}
          </ul>
          <p className="text-[11px] text-gray-600 mt-3">
            Cada barra muestra sus pendientes por columna (pasa el cursor para ver el detalle). Una tarea con varios
            asignados cuenta para cada uno.
          </p>
        </Card>

        <Card title="Builds">
          {builds.length === 0 ? (
            <p className="text-xs text-gray-500">Aún no hay builds registradas.</p>
          ) : (
            <>
              <ul className="grid grid-cols-3 gap-2 text-center">
                {[
                  ["success", "Exitosas", CheckCircle2, "text-[#00FF66]"],
                  ["failed", "Fallidas", XCircle, "text-[#FF3D00]"],
                  ["pending", "Pendientes", Clock, "text-yellow-400"],
                ].map(([id, label, Icon, color]) => (
                  <li key={id} className="bg-[#0B0D14] border border-[#272B3B] rounded-md py-2">
                    <Icon className={`w-4 h-4 mx-auto ${color}`} />
                    <p className="text-lg font-semibold text-white tabular-nums">{buildCounts[id] ?? 0}</p>
                    <p className="text-[11px] text-gray-500">{label}</p>
                  </li>
                ))}
              </ul>
              {latestBuild && (
                <p className="text-xs text-gray-400 mt-3 flex items-center gap-1.5">
                  <Package className="w-3.5 h-3.5" /> Última: <span className="font-mono text-white">{latestBuild.version}</span>{" "}
                  {timeAgo(latestBuild.created_at)}
                </p>
              )}
            </>
          )}
        </Card>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <Card title={`Sin asignar (${unassigned.length})`}>
          {unassigned.length ? (
            <ul>
              {unassigned.slice(0, 6).map((a) => (
                <TaskLink key={a.id} asset={a} onOpen={onOpen}>
                  {statusLabel(a.status)}
                </TaskLink>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-500">Todo el trabajo pendiente tiene responsable.</p>
          )}
        </Card>
        <Card title={`Esperando revisión (${inReview.length})`}>
          {inReview.length ? (
            <ul>
              {inReview.slice(0, 6).map((a) => (
                <TaskLink key={a.id} asset={a} onOpen={onOpen}>
                  {a.assigned_users.map((u) => u.username).join(", ") || "—"}
                </TaskLink>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-500">Nada en revisión.</p>
          )}
        </Card>
        <Card title={`Archivos bloqueados (${locked.length})`}>
          {locked.length ? (
            <ul>
              {locked.slice(0, 6).map((a) => (
                <TaskLink key={a.id} asset={a} onOpen={onOpen}>
                  {nameOf(a.locked_by_user_id)} · {timeAgo(a.locked_at)}
                </TaskLink>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-500">Ningún archivo bloqueado.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
