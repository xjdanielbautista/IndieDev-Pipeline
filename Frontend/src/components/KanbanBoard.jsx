import { useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Code, Lock, Paintbrush, ShieldCheck } from "lucide-react";
import { CATEGORIES, STATUSES, timeAgo } from "../utils/labels";
import { Avatar } from "./ui";

function TaskCard({ asset, currentUser, canMoveTo, onOpen, onMove, onDragStart }) {
  const category = CATEGORIES[asset.category] ?? CATEGORIES.art;
  const isCode = asset.category === "code";
  const isLocked = asset.locked_by_user_id !== null;
  const index = STATUSES.findIndex((s) => s.id === asset.status);
  const mine = asset.assigned_user_ids.includes(currentUser?.id);
  const prev = STATUSES[index - 1];
  const next = STATUSES[index + 1];
  const canDrag = STATUSES.some((s) => canMoveTo(asset, s.id));

  return (
    <div
      draggable={canDrag}
      onDragStart={(e) => onDragStart(e, asset)}
      onClick={() => onOpen(asset)}
      className={`relative rounded-lg p-3 mb-3 border bg-[#151822] cursor-pointer transition-all hover:bg-[#1C202D] hover:-translate-y-0.5 overflow-hidden ${
        isLocked ? "border-[#FF3D00]/70 shadow-[0_0_10px_rgba(255,61,0,0.15)]" : "border-[#272B3B]"
      }`}
      style={{ borderLeft: `4px solid ${category.color}` }}
    >
      {isLocked && <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-[#FF3D00] to-orange-500" />}

      <div className="flex items-center justify-between mb-2">
        <span
          className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
          style={{ color: category.color, borderColor: `${category.color}40`, background: `${category.color}12` }}
        >
          #{asset.id}
        </span>
        <div className="flex items-center gap-1.5">
          {mine && <span className="text-[9px] font-bold uppercase tracking-wider text-[#00FF66]">Tuya</span>}
          {asset.assignment_mode === "restricted" && (
            <ShieldCheck className="w-3.5 h-3.5 text-yellow-400" aria-label="Solo asignados" />
          )}
          {isLocked && <Lock className="w-3.5 h-3.5 text-[#FF3D00]" aria-label="Bloqueado" />}
          {isCode ? (
            <Code className="w-4 h-4" style={{ color: category.color }} />
          ) : (
            <Paintbrush className="w-4 h-4" style={{ color: category.color }} />
          )}
        </div>
      </div>

      <h4 className="text-sm font-medium leading-snug text-gray-100 mb-3 break-words">{asset.original_name}</h4>

      <div className="flex items-center justify-between pt-2 border-t border-[#272B3B]/60">
        <div className="flex items-center">
          {asset.assigned_users.length === 0 ? (
            <span className="text-[10px] text-gray-500">Sin asignar</span>
          ) : (
            <div className="flex -space-x-1.5">
              {asset.assigned_users.slice(0, 4).map((u) => (
                <Avatar key={u.id} user={u} ring />
              ))}
              {asset.assigned_users.length > 4 && (
                <span className="text-[10px] text-gray-400 pl-2">+{asset.assigned_users.length - 4}</span>
              )}
            </div>
          )}
          <span className="text-[10px] text-gray-600 ml-2">{timeAgo(asset.created_at)}</span>
        </div>
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onMove(asset, -1)}
            disabled={!prev || !canMoveTo(asset, prev.id)}
            aria-label="Mover a la izquierda"
            className="p-1 bg-gray-800 text-gray-400 rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-700 hover:text-white"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onMove(asset, 1)}
            disabled={!next || !canMoveTo(asset, next.id)}
            aria-label="Mover a la derecha"
            className="p-1 bg-gray-800 text-gray-400 rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-700 hover:text-white"
          >
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function KanbanBoard({ assets, currentUser, canMoveTo, onOpen, onChangeStatus }) {
  const [dragOver, setDragOver] = useState(null);

  const handleDragStart = (e, asset) => {
    e.dataTransfer.setData("text/plain", String(asset.id));
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = (e, statusId) => {
    e.preventDefault();
    setDragOver(null);
    const id = Number(e.dataTransfer.getData("text/plain"));
    const asset = assets.find((a) => a.id === id);
    if (asset && asset.status !== statusId) onChangeStatus(asset, statusId);
  };

  const move = (asset, direction) => {
    const index = STATUSES.findIndex((s) => s.id === asset.status);
    const next = STATUSES[index + direction];
    if (next) onChangeStatus(asset, next.id);
  };

  return (
    <div className="grid grid-flow-col auto-cols-[minmax(260px,1fr)] gap-4 h-full pb-2">
      {STATUSES.map((col) => {
        const columnAssets = assets.filter((a) => a.status === col.id);
        return (
          <div
            key={col.id}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(col.id);
            }}
            onDragLeave={() => setDragOver((current) => (current === col.id ? null : current))}
            onDrop={(e) => handleDrop(e, col.id)}
            data-column={col.id}
            className={`flex flex-col min-h-0 bg-[#151822]/60 border rounded-lg transition-colors ${
              dragOver === col.id ? "border-[#00F0FF]/60 bg-[#00F0FF]/5" : "border-[#272B3B]"
            }`}
          >
            <div className="p-3 border-b border-[#272B3B] flex items-center gap-2 bg-[#151822] rounded-t-lg">
              {col.id === "done" ? (
                <CheckCircle2 className={`w-4 h-4 ${col.color}`} />
              ) : (
                <span className={`w-2 h-2 rounded-full ${col.dot}`} />
              )}
              <h3 className={`text-sm font-semibold ${col.color}`}>{col.label}</h3>
              <span className="bg-[#0B0D14] border border-[#272B3B] text-gray-400 text-xs px-1.5 rounded font-mono">
                {columnAssets.length}
              </span>
            </div>
            <div className="p-3 flex-1 overflow-y-auto">
              {columnAssets.map((asset) => (
                <TaskCard
                  key={asset.id}
                  asset={asset}
                  currentUser={currentUser}
                  canMoveTo={canMoveTo}
                  onOpen={onOpen}
                  onMove={move}
                  onDragStart={handleDragStart}
                />
              ))}
              {columnAssets.length === 0 && (
                <div className="h-24 border-2 border-dashed border-[#272B3B] rounded-lg flex items-center justify-center text-xs text-gray-600 font-mono">
                  Arrastra tareas aquí
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
