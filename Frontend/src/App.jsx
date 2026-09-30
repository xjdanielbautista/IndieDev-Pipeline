import React, { useState } from 'react';
import { 
  Lock, Unlock, GitPullRequest, Code, Paintbrush, ArrowRight, 
  ArrowLeft, LogOut, FileImage, GitCommit, User, 
  LayoutDashboard, Server, ShieldAlert, CheckCircle2
} from 'lucide-react';

const INITIAL_TASKS = [
  {
    id: 'ART-101',
    title: 'Diseñar Sprites de Enemigo "Scavenger"',
    type: 'art',
    status: 'backlog',
    assignee: 'Sam Art',
    artData: { assetName: 'scavenger_sheet_v1.psd', size: '24 MB' },
    isLocked: false
  },
  {
    id: 'DEV-342',
    title: 'Refactorizar sistema de colisiones 2D',
    type: 'code',
    status: 'backlog',
    assignee: 'Alex Dev',
    priority: 'Alta'
  },
  {
    id: 'DEV-338',
    title: 'Implementar mecánica de "Dash Aéreo"',
    type: 'code',
    status: 'in-progress',
    assignee: 'Alex Dev',
    githubData: { pr: '#84', commit: 'f7a9c2b', msg: 'Added dash input logic', state: 'Review Rq.' }
  },
  {
    id: 'ART-098',
    title: 'Animación Idle Jefe Final',
    type: 'art',
    status: 'review',
    assignee: 'Sam Art',
    artData: { assetName: 'boss_idle_v3.mp4', size: '120 MB' },
    isLocked: false
  },
  {
    id: 'ART-105',
    title: 'Texturas Nivel 3 - Central Plaza',
    type: 'art',
    status: 'locked-assets',
    assignee: 'Sam Art',
    artData: { assetName: 'level3_albedo_8k.psd', size: '450 MB' },
    isLocked: true,
    lockedBy: 'Sam Art'
  },
  {
    id: 'DEV-301',
    title: 'Fix: memory leak en menú principal',
    type: 'code',
    status: 'done',
    assignee: 'Alex Dev',
    githubData: { pr: '#82', commit: 'a1b2c3d', msg: 'Fixed texture GC', state: 'Merged' }
  }
];

const COLUMNS = [
  { id: 'backlog', title: 'Backlog', color: 'text-gray-400', border: 'border-gray-600' },
  { id: 'in-progress', title: 'En progreso', color: 'text-[#00F0FF]', border: 'border-[#00F0FF]' },
  { id: 'review', title: 'Revisión', color: 'text-yellow-400', border: 'border-yellow-400' },
  { id: 'locked-assets', title: 'Bloqueo de Assets', color: 'text-[#FF3D00]', border: 'border-[#FF3D00]', isLock: true },
  { id: 'done', title: 'Terminado', color: 'text-[#00FF66]', border: 'border-[#00FF66]' }
];

const TaskCard = ({ task, onMove, onToggleLock }) => {
  const isCode = task.type === 'code';
  const isArt = task.type === 'art';
  
  const currentColIndex = COLUMNS.findIndex(c => c.id === task.status);
  const canMoveLeft = currentColIndex > 0 && !task.isLocked;
  const canMoveRight = currentColIndex < COLUMNS.length - 1 && !task.isLocked;

  const baseClasses = "rounded-lg shadow-lg p-3 mb-3 border border-[#272B3B] bg-[#151822] transition-all relative overflow-hidden group";
  const typeBorder = isCode ? 'border-l-4 border-l-[#00F0FF]' : 'border-l-4 border-l-[#FF0055]';
  const lockedClasses = task.isLocked ? '!border-[#FF3D00] shadow-[0_0_10px_rgba(255,61,0,0.2)] bg-[#1a1111]' : '';
  const hoverClasses = !task.isLocked ? 'hover:bg-[#1C202D] hover:-translate-y-1' : '';

  return (
    <div className={`${baseClasses} ${typeBorder} ${lockedClasses} ${hoverClasses}`}>
      {task.isLocked && (
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#FF3D00] to-orange-500"></div>
      )}

      <div className="flex items-center justify-between mb-2">
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
          isCode ? 'text-[#00F0FF] bg-[#00F0FF]/10 border-[#00F0FF]/20' : 
          task.isLocked ? 'text-[#FF3D00] bg-[#FF3D00]/10 border-[#FF3D00]/20' :
          'text-[#FF0055] bg-[#FF0055]/10 border-[#FF0055]/20'
        }`}>
          {task.id}
        </span>
        <div className="flex items-center gap-1">
          {task.isLocked && <span className="text-[9px] font-bold uppercase text-[#FF3D00] animate-pulse tracking-wider mr-1">LOCKED</span>}
          {isCode ? <Code className="w-4 h-4 text-[#00F0FF]" /> : <Paintbrush className={`w-4 h-4 ${task.isLocked ? 'text-[#FF3D00]' : 'text-[#FF0055]'}`} />}
        </div>
      </div>

      <h4 className={`text-sm font-medium leading-tight mb-3 ${task.isLocked ? 'text-white' : 'text-gray-100'}`}>
        {task.title}
      </h4>

      {isCode && task.githubData && (
        <div className="bg-[#0B0D14] border border-[#272B3B] rounded p-2 mb-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5 text-gray-400">
              <GitPullRequest className="w-3.5 h-3.5" />
              <span className="text-[10px] font-mono">{task.githubData.pr}</span>
            </div>
            <span className={`text-[9px] font-mono uppercase px-1 rounded border ${
              task.githubData.state === 'Merged' ? 'bg-[#00FF66]/20 text-[#00FF66] border-[#00FF66]/30' : 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30'
            }`}>
              {task.githubData.state}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <GitCommit className="w-3 h-3" />
            <span className="font-mono text-[10px]">{task.githubData.commit}</span>
            <span className="truncate max-w-[100px] text-[10px]">{task.githubData.msg}</span>
          </div>
        </div>
      )}

      {isArt && task.artData && (
        <div className={`border rounded p-2 mb-3 flex items-center gap-2 ${
          task.isLocked ? 'bg-[#151822] border-[#FF3D00]/30' : 'bg-[#0B0D14] border-[#272B3B]'
        }`}>
          <FileImage className={`w-4 h-4 ${task.isLocked ? 'text-[#FF3D00]' : 'text-gray-400'}`} />
          <div className="flex flex-col overflow-hidden">
            <span className="text-[10px] font-mono text-gray-300 truncate">{task.artData.assetName}</span>
            <span className="text-[9px] text-gray-400">{task.artData.size}</span>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#272B3B]/50">
        <div className="flex items-center gap-2 text-[10px] text-gray-400">
          <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-base ${isCode ? 'bg-[#00F0FF]' : 'bg-[#FF0055]'}`}>
            {task.assignee.charAt(0)}
          </div>
          <span className="truncate w-16">{task.assignee}</span>
        </div>

        <div className="flex gap-1">
          {isArt && (
            <button 
              onClick={() => onToggleLock(task.id)}
              className={`p-1 rounded transition-colors focus-visible:ring-2 focus-visible:ring-[#00F0FF] ${
                task.isLocked ? 'bg-[#FF3D00]/20 text-[#FF3D00] hover:bg-[#FF3D00]/40' : 'bg-gray-800 text-gray-400 hover:text-[#FF3D00] hover:bg-gray-700'
              }`}
              title={task.isLocked ? "Desbloquear Asset" : "Bloquear Asset Exclusivo"}
            >
              {task.isLocked ? <Unlock className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
            </button>
          )}

          <button 
            onClick={() => onMove(task.id, -1)}
            disabled={!canMoveLeft}
            className="p-1 bg-gray-800 text-gray-400 rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-700 hover:text-white focus-visible:ring-2 focus-visible:ring-[#00F0FF] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
          <button 
            onClick={() => onMove(task.id, 1)}
            disabled={!canMoveRight}
            className="p-1 bg-gray-800 text-gray-400 rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-700 hover:text-white focus-visible:ring-2 focus-visible:ring-[#00F0FF] transition-colors"
          >
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [tasks, setTasks] = useState(INITIAL_TASKS); // TODO: reemplazar con fetch al backend cuando esté listo

  const handleMoveTask = (taskId, direction) => {
    setTasks(prevTasks => prevTasks.map(task => {
      if (task.id === taskId) {
        const currentIndex = COLUMNS.findIndex(c => c.id === task.status);
        const newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < COLUMNS.length) {
          return { ...task, status: COLUMNS[newIndex].id };
        }
      }
      return task;
    }));
  };

   const API_BASE = import.meta.env.VITE_API_BASE_URL;
  const TENANT_ID = import.meta.env.VITE_TENANT_ID;
  const ASSET_ID = import.meta.env.VITE_ASSET_ID;
  const USER_ID = import.meta.env.VITE_USER_ID;

  const handleToggleLock = async (taskId) => {
    const task = tasks.find(t => t.id === taskId);
    const isCurrentlyLocked = task.isLocked;

    // Solo ART-105 está conectada a un asset real en el backend por ahora
    if (taskId === 'ART-105') {
      try {
        const url = `${API_BASE}/api/tenants/${TENANT_ID}/assets/${ASSET_ID}/lock`;
        const response = isCurrentlyLocked
          ? await fetch(`${url}?user_id=${USER_ID}`, { method: 'DELETE' })
          : await fetch(url, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ user_id: Number(USER_ID) }),
            });

        if (!response.ok) {
          const error = await response.json();
          alert(`Error del backend: ${error.detail}`);
          return;
        }
      } catch (err) {
        alert('No se pudo conectar con el backend. ¿Sigue corriendo uvicorn?');
        return;
      }
    }

    setTasks(prevTasks => prevTasks.map(t => {
      if (t.id === taskId) {
        return { 
          ...t, 
          isLocked: !isCurrentlyLocked,
          status: !isCurrentlyLocked ? 'locked-assets' : 'in-progress',
          lockedBy: !isCurrentlyLocked ? 'Alex Dev' : null
        };
      }
      return t;
    }));
  };

  const handleLogin = (e) => {
    e.preventDefault();
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-[#0B0D14] text-gray-300 font-sans flex items-center justify-center relative overflow-hidden selection:bg-[#00F0FF] selection:text-black">
        <div className="absolute top-[10%] left-[20%] w-96 h-96 bg-[#00F0FF]/10 rounded-full blur-[120px] pointer-events-none"></div>
        <div className="absolute bottom-[10%] right-[20%] w-96 h-96 bg-[#FF0055]/10 rounded-full blur-[120px] pointer-events-none"></div>
        
        <div className="z-10 w-full max-w-md p-8 bg-[#151822] border border-[#272B3B] rounded-xl shadow-2xl backdrop-blur-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-gradient-to-br from-[#151822] to-[#272B3B] border border-[#272B3B] shadow-[0_0_15px_rgba(0,240,255,0.2)] mb-4">
              <Code className="w-8 h-8 text-[#00F0FF]" />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">IndieDev <span className="text-[#00F0FF]">Pipeline</span></h1>
            <p className="text-xs text-gray-400 mt-2 font-mono uppercase tracking-widest">Workspace Gateway</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-xs font-mono text-gray-400 mb-1">tenant_id</label>
              <div className="relative">
                <Server className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
                <input type="text" value="pixel-ninja-studios" readOnly className="w-full bg-[#0B0D14] border border-[#272B3B] text-white font-mono text-sm rounded-lg pl-10 pr-4 py-2.5 focus:outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-mono text-gray-400 mb-1">user_email</label>
              <div className="relative">
                <User className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
                <input type="email" defaultValue="alex@pixelninja.dev" required className="w-full bg-[#0B0D14] border border-[#272B3B] text-white text-sm rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF] transition-colors" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-mono text-gray-400 mb-1">password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
                <input type="password" defaultValue="password" required className="w-full bg-[#0B0D14] border border-[#272B3B] text-white rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF] transition-colors" />
              </div>
            </div>
            
            <button type="submit" className="w-full mt-6 bg-[#00F0FF] hover:bg-cyan-400 text-black font-bold rounded-lg px-4 py-3 transition-colors shadow-[0_0_15px_rgba(0,240,255,0.4)] flex justify-center items-center gap-2 group focus-visible:ring-2 focus-visible:ring-white">
              <span>INICIAR SESIÓN</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0D14] text-gray-300 font-sans flex flex-col selection:bg-[#00F0FF] selection:text-black">
      
      <header className="h-14 bg-[#151822] border-b border-[#272B3B] flex items-center justify-between px-6 shrink-0 z-20">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2 border-r border-[#272B3B] pr-6">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-[#00F0FF] to-blue-600 flex items-center justify-center text-xs font-bold text-black shadow-[0_0_10px_rgba(0,240,255,0.3)]">PN</div>
            <span className="text-sm font-semibold text-white">Pixel Ninja Studios</span>
          </div>
          <div className="flex items-center space-x-2 text-white">
            <LayoutDashboard className="w-5 h-5 text-[#00F0FF]" />
            <h2 className="font-bold tracking-wide">CyberBlade: Neon City</h2>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="hidden md:flex items-center space-x-2 bg-[#0B0D14] border border-[#272B3B] px-3 py-1 rounded text-xs font-mono text-gray-400">
            <span className="w-2 h-2 rounded-full bg-[#00FF66] animate-pulse"></span>
            <span>Build: v0.9.4-rc2</span>
          </div>
          <div className="flex items-center space-x-3 pl-4 border-l border-[#272B3B]">
            <div className="text-right">
              <div className="text-sm font-medium text-white">Alex Dev</div>
              <div className="text-[10px] font-mono text-[#00F0FF] uppercase">Lead Programmer</div>
            </div>
            <div className="w-8 h-8 rounded-full bg-[#00F0FF] flex items-center justify-center text-black font-bold">A</div>
          </div>
          <button onClick={handleLogout} className="ml-2 p-2 text-gray-400 hover:text-[#FF3D00] hover:bg-[#FF3D00]/10 rounded transition-colors group focus-visible:ring-2 focus-visible:ring-[#00F0FF]">
            <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform" />
          </button>
        </div>
      </header>

      <div className="h-12 bg-[#0B0D14] border-b border-[#272B3B] flex items-center px-6 shrink-0 justify-between">
        <div className="flex space-x-2">
          <button className="px-4 py-1.5 text-sm font-medium bg-[#1C202D] text-white rounded shadow border border-[#272B3B]">Tablero Kanban</button>
          <button className="px-4 py-1.5 text-sm font-medium text-gray-400 hover:text-white hover:bg-[#151822] rounded transition-colors">Asset Vault</button>
          <button className="px-4 py-1.5 text-sm font-medium text-gray-400 hover:text-white hover:bg-[#151822] rounded transition-colors">Build History</button>
        </div>
        <div className="flex items-center space-x-4">
          <span className="flex items-center text-xs text-gray-400"><div className="w-2 h-2 rounded-full bg-[#00F0FF] mr-1.5 shadow-[0_0_5px_rgba(0,240,255,0.5)]"></div> Código</span>
          <span className="flex items-center text-xs text-gray-400"><div className="w-2 h-2 rounded-full bg-[#FF0055] mr-1.5 shadow-[0_0_5px_rgba(255,0,85,0.5)]"></div> Arte</span>
        </div>
      </div>

      <main className="flex-1 overflow-x-auto overflow-y-hidden p-6">
        <div className="grid grid-cols-5 gap-4 h-full pb-4">
          {COLUMNS.map(col => {
            const columnTasks = tasks.filter(t => t.status === col.id);
            
            return (
             <div key={col.id} className={`flex flex-col h-full bg-[#151822]/60 border ${col.isLock ? 'border-[#FF3D00]/30 shadow-[0_0_15px_rgba(255,61,0,0.1)]' : 'border-[#272B3B]'} rounded-lg`}>
                <div className={`p-3 border-b flex items-center justify-between bg-[#151822] rounded-t-lg ${col.isLock ? 'border-[#FF3D00]/30' : 'border-[#272B3B]'}`}>
                  <div className="flex items-center space-x-2">
                    {col.isLock ? (
                      <ShieldAlert className={`w-4 h-4 ${col.color} animate-pulse`} />
                    ) : col.id === 'done' ? (
                      <CheckCircle2 className={`w-4 h-4 ${col.color}`} />
                    ) : (
                      <div className={`w-2 h-2 rounded-full ${col.border.replace('border-', 'bg-')} shadow-[0_0_8px_currentColor]`}></div>
                    )}
                    <h3 className={`text-sm font-semibold ${col.color}`}>{col.title}</h3>
                    <span className="bg-[#0B0D14] border border-[#272B3B] text-gray-400 text-xs px-1.5 rounded font-mono">{columnTasks.length}</span>
                  </div>
                </div>

                <div className={`p-3 flex-1 overflow-y-auto ${col.isLock ? 'bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(255,61,0,0.03)_10px,rgba(255,61,0,0.03)_20px)]' : ''}`}>
                  {columnTasks.map(task => (
                    <TaskCard 
                      key={task.id} 
                      task={task} 
                      onMove={handleMoveTask}
                      onToggleLock={handleToggleLock}
                    />
                  ))}
                  
                  {columnTasks.length === 0 && (
                    <div className="h-24 border-2 border-dashed border-[#272B3B] rounded-lg flex items-center justify-center text-xs text-gray-600 font-mono">
                      Arrastra tareas aquí
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}