import { useCallback, useEffect, useMemo, useState } from "react";
import { Code, FolderKanban, LayoutDashboard, LogOut, Package, Plus, RefreshCw, Search, Table2, Users } from "lucide-react";
import ApiStatus from "./ApiStatus";
import AssetVault from "./AssetVault";
import BuildHistory from "./BuildHistory";
import KanbanBoard from "./KanbanBoard";
import NotificationsBell from "./NotificationsBell";
import TaskDetail from "./TaskDetail";
import TeamPanel from "./TeamPanel";
import { CreateBuildForm, CreateProjectForm, CreateStudioForm, CreateTaskForm } from "./forms";
import { Avatar, Modal, useToast } from "./ui";
import { listAssets, listBuilds, listMembers, listMyTenants, listProjects, updateAsset } from "../api/studio";
import { CATEGORIES, ROLES, initials, statusLabel } from "../utils/labels";
import { canBuild, canMove, isManager } from "../utils/permissions";

const REFRESH_MS = 30000; // recarga el tablero cada 30 s para ver cambios del equipo

const store = {
  get: (key) => {
    try {
      return Number(localStorage.getItem(key)) || null;
    } catch {
      return null;
    }
  },
  set: (key, value) => {
    try {
      localStorage.setItem(key, String(value));
    } catch {
      // sin almacenamiento: no se recuerda la selección
    }
  },
};

const selectClass =
  "bg-[#0B0D14] border border-[#272B3B] text-white text-sm rounded-md pl-2 pr-7 py-1.5 focus:outline-none focus:border-[#00F0FF] max-w-[240px]";

function Onboarding({ step, tenant, onStudio, onProject, onLogout }) {
  if (step === "project" && !isManager(tenant.role)) {
    return (
      <div className="min-h-screen bg-[#0B0D14] flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-[#151822] border border-[#272B3B] rounded-xl p-8 text-center">
          <h1 className="text-xl font-bold text-white mb-2">{tenant.name} aún no tiene proyectos</h1>
          <p className="text-sm text-gray-400 mb-6">Pídele al dueño o a un admin que cree el primero.</p>
          <button onClick={() => window.location.reload()} className="text-sm text-[#00F0FF] hover:underline">
            Volver a revisar
          </button>
          <button onClick={onLogout} className="block mx-auto mt-4 text-xs text-gray-500 hover:text-white">
            Cerrar sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0D14] flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute top-[10%] left-[20%] w-96 h-96 bg-[#00F0FF]/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="z-10 w-full max-w-md bg-[#151822] border border-[#272B3B] rounded-xl p-8 shadow-2xl">
        <p className="text-xs font-mono text-[#00F0FF] uppercase tracking-widest mb-2">
          Paso {step === "studio" ? 1 : 2} de 2
        </p>
        <h1 className="text-2xl font-bold text-white mb-1">
          {step === "studio" ? "Crea tu estudio" : "Crea tu primer proyecto"}
        </h1>
        <p className="text-sm text-gray-400 mb-6">
          {step === "studio"
            ? "Tu estudio agrupa a tu equipo y sus juegos. Si te van a invitar a uno existente, pídele al dueño que te agregue."
            : `Dentro de ${tenant?.name} cada juego tiene su propio tablero, archivos y builds.`}
        </p>
        {step === "studio" && (
          <button
            onClick={() => window.location.reload()}
            className="w-full mb-4 text-xs text-[#00F0FF] border border-[#00F0FF]/30 rounded-lg py-2 hover:bg-[#00F0FF]/10"
          >
            Ya me agregaron a un estudio, volver a revisar
          </button>
        )}
        {step === "studio" ? (
          <CreateStudioForm onCreated={onStudio} />
        ) : (
          <CreateProjectForm tenantId={tenant.id} onCreated={onProject} />
        )}
        <button onClick={onLogout} className="mt-6 text-xs text-gray-500 hover:text-white">
          Cerrar sesión
        </button>
      </div>
    </div>
  );
}

export default function Workspace({ currentUser, onLogout }) {
  const notify = useToast();
  const [tenants, setTenants] = useState(null);
  const [tenantId, setTenantId] = useState(() => store.get("indiedev_tenant"));
  const [projects, setProjects] = useState(null);
  const [projectId, setProjectId] = useState(() => store.get("indiedev_project"));
  const [members, setMembers] = useState([]);
  const [assets, setAssets] = useState([]);
  const [builds, setBuilds] = useState([]);
  const [loadingBoard, setLoadingBoard] = useState(false);

  const [tab, setTab] = useState("board");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [onlyMine, setOnlyMine] = useState(false);
  const [modal, setModal] = useState(null); // "studio" | "project" | "task" | "build"
  const [openAssetId, setOpenAssetId] = useState(null);

  const tenant = tenants?.find((t) => t.id === tenantId) ?? null;
  const project = projects?.find((p) => p.id === projectId) ?? null;

  // 1) Estudios del usuario
  useEffect(() => {
    listMyTenants()
      .then((list) => {
        setTenants(list);
        setTenantId((current) => (list.some((t) => t.id === current) ? current : list[0]?.id ?? null));
      })
      .catch((err) => {
        setTenants([]);
        if (err.status !== 401) notify(err.message);
      });
  }, [notify]);

  // 2) Proyectos e integrantes del estudio elegido
  useEffect(() => {
    if (!tenantId) return;
    store.set("indiedev_tenant", tenantId);
    setProjects(null);
    Promise.all([listProjects(tenantId), listMembers(tenantId)])
      .then(([projectList, memberList]) => {
        setProjects(projectList);
        setMembers(memberList);
        setProjectId((current) =>
          projectList.some((p) => p.id === current) ? current : projectList[0]?.id ?? null,
        );
      })
      .catch((err) => {
        setProjects([]);
        if (err.status !== 401) notify(err.message);
      });
  }, [tenantId, notify]);

  // 3) Tareas y builds del proyecto elegido
  const loadBoard = useCallback(
    async (silent = false) => {
      if (!tenantId || !projectId) return;
      if (!silent) setLoadingBoard(true);
      try {
        const [assetList, buildList] = await Promise.all([
          listAssets(tenantId, projectId),
          listBuilds(tenantId, projectId),
        ]);
        setAssets(assetList);
        setBuilds(buildList);
      } catch (err) {
        if (err.status !== 401 && !silent) notify(err.message);
      } finally {
        setLoadingBoard(false);
      }
    },
    [tenantId, projectId, notify],
  );

  useEffect(() => {
    if (!projectId) return undefined;
    store.set("indiedev_project", projectId);
    loadBoard();
    const timer = setInterval(() => loadBoard(true), REFRESH_MS);
    return () => clearInterval(timer);
  }, [projectId, loadBoard]);

  const replaceAsset = (updated) => setAssets((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));

  const changeStatus = async (asset, status) => {
    if (!canMove(tenant?.role, asset, status, currentUser?.id)) {
      notify(`Tu rol (${ROLES[tenant?.role] ?? tenant?.role}) no puede mover esta tarea a ${statusLabel(status)}.`);
      return;
    }
    const previous = asset;
    replaceAsset({ ...asset, status }); // movimiento inmediato en pantalla
    try {
      replaceAsset(await updateAsset(tenantId, projectId, asset.id, { status }));
    } catch (err) {
      replaceAsset(previous);
      if (err.status !== 401) notify(err.message);
    }
  };

  const filteredAssets = useMemo(() => {
    const term = search.trim().toLowerCase();
    return assets.filter(
      (a) =>
        (categoryFilter === "all" || a.category === categoryFilter) &&
        (!onlyMine || a.assigned_user_ids.includes(currentUser?.id)) &&
        (!term || a.original_name.toLowerCase().includes(term) || String(a.id) === term),
    );
  }, [assets, search, categoryFilter, onlyMine, currentUser]);

  const openAsset = assets.find((a) => a.id === openAssetId) ?? null;
  const lockedCount = assets.filter((a) => a.locked_by_user_id !== null).length;
  const mineCount = assets.filter((a) => a.assigned_user_ids.includes(currentUser?.id) && a.status !== "done").length;

  // ---- Pantallas de carga / primeros pasos ----
  if (tenants === null || (tenantId && projects === null)) {
    return (
      <div className="min-h-screen bg-[#0B0D14] flex items-center justify-center text-sm font-mono text-gray-500">
        Cargando tu espacio de trabajo...
      </div>
    );
  }

  if (!tenant) {
    return (
      <Onboarding
        step="studio"
        onLogout={onLogout}
        onStudio={(created) => {
          setTenants([{ ...created, role: "owner" }]);
          setTenantId(created.id);
        }}
      />
    );
  }

  if (!project) {
    return (
      <Onboarding
        step="project"
        tenant={tenant}
        onLogout={onLogout}
        onProject={(created) => {
          setProjects([created]);
          setProjectId(created.id);
        }}
      />
    );
  }

  const tabs = [
    { id: "board", label: "Tablero Kanban", icon: FolderKanban },
    { id: "vault", label: "Asset Vault", icon: Table2 },
    { id: "builds", label: "Build History", icon: Package },
    { id: "team", label: `Equipo (${members.length})`, icon: Users },
  ];
  const manager = isManager(tenant.role);
  const latestBuild = [...builds].sort((a, b) => b.id - a.id)[0];

  return (
    <div className="h-screen bg-[#0B0D14] text-gray-300 font-sans flex flex-col selection:bg-[#00F0FF] selection:text-black">
      <header className="min-h-14 bg-[#151822] border-b border-[#272B3B] flex flex-wrap items-center justify-between gap-3 px-4 md:px-6 py-2 shrink-0">
        <div className="flex flex-wrap items-center gap-3 md:gap-5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-gradient-to-br from-[#00F0FF] to-blue-600 flex items-center justify-center text-xs font-bold text-black">
              {initials(tenant.name)}
            </div>
            <select
              aria-label="Estudio"
              className={selectClass}
              value={tenant.id}
              onChange={(e) => (e.target.value === "new" ? setModal("studio") : setTenantId(Number(e.target.value)))}
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
              <option value="new">+ Nuevo estudio</option>
            </select>
            <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border border-[#00F0FF]/30 text-[#00F0FF] bg-[#00F0FF]/10">
              {ROLES[tenant.role] ?? tenant.role}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <LayoutDashboard className="w-5 h-5 text-[#00F0FF]" />
            <select
              aria-label="Proyecto"
              className={`${selectClass} font-semibold`}
              value={project.id}
              onChange={(e) => (e.target.value === "new" ? setModal("project") : setProjectId(Number(e.target.value)))}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
              {manager && <option value="new">+ Nuevo proyecto</option>}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-3 md:gap-4">
          <div className="hidden lg:block text-xs font-mono text-gray-400">
            <ApiStatus />
          </div>
          {latestBuild && (
            <div className="hidden md:flex items-center gap-2 bg-[#0B0D14] border border-[#272B3B] px-3 py-1 rounded text-xs font-mono text-gray-400">
              <span
                className={`w-2 h-2 rounded-full ${
                  latestBuild.status === "success" ? "bg-[#00FF66]" : latestBuild.status === "failed" ? "bg-[#FF3D00]" : "bg-yellow-400"
                }`}
              />
              Build: {latestBuild.version}
            </div>
          )}
          <NotificationsBell
            onOpen={(n) => {
              if (!tenants.some((t) => t.id === n.tenant_id)) return;
              setTenantId(n.tenant_id);
              if (n.project_id) setProjectId(n.project_id);
              setTab("board");
              setOpenAssetId(n.asset_id);
            }}
          />
          <div className="flex items-center gap-2 pl-3 border-l border-[#272B3B]">
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium text-white">{currentUser?.username ?? currentUser?.email}</div>
              <div className="text-[10px] font-mono text-gray-500">{currentUser?.email}</div>
            </div>
            <Avatar user={currentUser} size="w-8 h-8 text-xs" />
          </div>
          <button
            onClick={onLogout}
            title="Cerrar sesión"
            className="p-2 text-gray-400 hover:text-[#FF3D00] hover:bg-[#FF3D00]/10 rounded transition-colors"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      <div className="bg-[#0B0D14] border-b border-[#272B3B] flex flex-wrap items-center justify-between gap-3 px-4 md:px-6 py-2 shrink-0">
        <nav className="flex gap-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded transition-colors ${
                tab === id ? "bg-[#1C202D] text-white border border-[#272B3B]" : "text-gray-400 hover:text-white hover:bg-[#151822] border border-transparent"
              }`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </nav>

        {(tab === "board" || tab === "vault") && (
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2 w-4 h-4 text-gray-500" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar tarea o #id"
                className="bg-[#151822] border border-[#272B3B] text-sm text-white rounded-md pl-8 pr-3 py-1.5 w-44 focus:outline-none focus:border-[#00F0FF]"
              />
            </div>
            <div className="flex bg-[#151822] border border-[#272B3B] rounded-md p-0.5">
              {[["all", "Todo", null], ["code", "Código", CATEGORIES.code.color], ["art", "Arte", CATEGORIES.art.color]].map(
                ([id, label, color]) => (
                  <button
                    key={id}
                    onClick={() => setCategoryFilter(id)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded ${
                      categoryFilter === id ? "bg-[#1C202D] text-white" : "text-gray-500 hover:text-white"
                    }`}
                  >
                    {color && <span className="w-2 h-2 rounded-full" style={{ background: color }} />}
                    {label}
                  </button>
                ),
              )}
            </div>
            <button
              onClick={() => setOnlyMine((v) => !v)}
              className={`px-2.5 py-1.5 text-xs rounded-md border ${
                onlyMine ? "border-[#00FF66]/50 bg-[#00FF66]/10 text-[#00FF66]" : "border-[#272B3B] text-gray-400 hover:text-white"
              }`}
            >
              Mis tareas {mineCount > 0 && `(${mineCount})`}
            </button>
            <button
              onClick={() => loadBoard()}
              title="Recargar"
              className="p-1.5 text-gray-400 hover:text-white rounded-md border border-[#272B3B]"
            >
              <RefreshCw className={`w-4 h-4 ${loadingBoard ? "animate-spin" : ""}`} />
            </button>
            {manager && (
              <button
                onClick={() => setModal("task")}
                className="flex items-center gap-1.5 bg-[#00F0FF] hover:bg-cyan-300 text-black font-semibold rounded-md px-3 py-1.5 text-sm"
              >
                <Plus className="w-4 h-4" /> Nueva tarea
              </button>
            )}
          </div>
        )}
      </div>

      <main className="flex-1 min-h-0 overflow-auto p-4 md:p-6">
        {tab === "board" && assets.length === 0 && !loadingBoard ? (
          <div className="max-w-md mx-auto mt-16 text-center">
            <Code className="w-10 h-10 mx-auto text-[#00F0FF] mb-3" />
            <h2 className="text-white text-lg font-semibold mb-1">Tu tablero está vacío</h2>
            {manager ? (
              <>
                <p className="text-sm text-gray-500 mb-5">Crea la primera tarea de {project.name} y asígnala a tu equipo.</p>
                <button
                  onClick={() => setModal("task")}
                  className="inline-flex items-center gap-2 bg-[#00F0FF] hover:bg-cyan-300 text-black font-semibold rounded-lg px-4 py-2.5 text-sm"
                >
                  <Plus className="w-4 h-4" /> Nueva tarea
                </button>
              </>
            ) : (
              <p className="text-sm text-gray-500">El dueño o un admin todavía no crean tareas para {project.name}.</p>
            )}
          </div>
        ) : tab === "board" ? (
          <>
            {lockedCount > 0 && (
              <p className="text-xs text-[#FF3D00] mb-3 font-mono">
                {lockedCount} {lockedCount === 1 ? "archivo bloqueado" : "archivos bloqueados"} en este momento
              </p>
            )}
            <KanbanBoard
              assets={filteredAssets}
              currentUser={currentUser}
              canMoveTo={(asset, status) => canMove(tenant.role, asset, status, currentUser?.id)}
              onOpen={(a) => setOpenAssetId(a.id)}
              onChangeStatus={changeStatus}
            />
          </>
        ) : tab === "vault" ? (
          <AssetVault assets={filteredAssets} members={members} onOpen={(a) => setOpenAssetId(a.id)} />
        ) : tab === "builds" ? (
          <BuildHistory builds={builds} onNew={canBuild(tenant.role) ? () => setModal("build") : null} />
        ) : (
          <TeamPanel
            tenant={tenant}
            members={members}
            assets={assets}
            currentUser={currentUser}
            onMembersChange={(list) => {
              setMembers(list);
              loadBoard(true); // quitar a alguien libera sus tareas y bloqueos
            }}
          />
        )}
      </main>

      {openAsset && (
        <TaskDetail
          asset={openAsset}
          tenant={tenant}
          projectId={project.id}
          members={members}
          currentUser={currentUser}
          role={tenant.role}
          onChanged={replaceAsset}
          onClose={() => setOpenAssetId(null)}
        />
      )}

      {modal === "task" && (
        <Modal title="Nueva tarea" onClose={() => setModal(null)}>
          <CreateTaskForm
            tenant={tenant}
            projectId={project.id}
            members={members}
            onCreated={(asset) => {
              setAssets((prev) => [...prev, asset]);
              setModal(null);
              notify("Tarea creada", "success");
            }}
          />
        </Modal>
      )}
      {modal === "build" && (
        <Modal title="Registrar build" onClose={() => setModal(null)}>
          <CreateBuildForm
            tenantId={tenant.id}
            projectId={project.id}
            onCreated={(build) => {
              setBuilds((prev) => [...prev, build]);
              setModal(null);
              notify("Build registrada", "success");
            }}
          />
        </Modal>
      )}
      {modal === "project" && (
        <Modal title={`Nuevo proyecto en ${tenant.name}`} onClose={() => setModal(null)}>
          <CreateProjectForm
            tenantId={tenant.id}
            onCreated={(created) => {
              setProjects((prev) => [...prev, created]);
              setProjectId(created.id);
              setModal(null);
            }}
          />
        </Modal>
      )}
      {modal === "studio" && (
        <Modal title="Nuevo estudio" onClose={() => setModal(null)}>
          <CreateStudioForm
            onCreated={(created) => {
              setTenants((prev) => [...prev, { ...created, role: "owner" }]);
              setTenantId(created.id);
              setModal(null);
            }}
          />
        </Modal>
      )}
    </div>
  );
}
