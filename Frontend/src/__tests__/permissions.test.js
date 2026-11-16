import { describe, expect, it } from "vitest";
import { assignableRoles, canLock, canManageMember, canMove } from "../utils/permissions";

const asset = (overrides = {}) => ({
  category: "code",
  status: "review",
  assignment_mode: "open",
  assigned_user_ids: [],
  ...overrides,
});

describe("canMove", () => {
  it("deja a dueño y admin mover cualquier tarea", () => {
    expect(canMove("owner", asset(), "backlog", 1)).toBe(true);
    expect(canMove("admin", asset({ assignment_mode: "restricted", assigned_user_ids: [9] }), "done", 1)).toBe(true);
  });

  it("limita a cada rol a su tipo de tarea", () => {
    expect(canMove("developer", asset(), "in_progress", 1)).toBe(true);
    expect(canMove("artist", asset(), "in_progress", 1)).toBe(false);
    expect(canMove("artist", asset({ category: "art" }), "in_progress", 1)).toBe(true);
  });

  it("en modo restringido solo mueven los asignados", () => {
    const restricted = asset({ assignment_mode: "restricted", assigned_user_ids: [5] });
    expect(canMove("developer", restricted, "in_progress", 1)).toBe(false);
    expect(canMove("developer", restricted, "in_progress", 5)).toBe(true);
  });

  it("el tester revisa tareas restringidas sin estar asignado, pero solo con sus transiciones", () => {
    const restricted = asset({ assignment_mode: "restricted", assigned_user_ids: [5] });
    expect(canMove("tester", restricted, "done", 1)).toBe(true);
    expect(canMove("tester", restricted, "in_progress", 1)).toBe(true);
    expect(canMove("tester", restricted, "backlog", 1)).toBe(false);
    expect(canMove("tester", asset({ status: "backlog" }), "in_progress", 1)).toBe(false);
  });

  it("no cuenta como movimiento quedarse en la misma columna", () => {
    expect(canMove("owner", asset(), "review", 1)).toBe(false);
  });
});

describe("bloqueos e integrantes", () => {
  it("canLock sigue la categoría del rol", () => {
    expect(canLock("developer", "code")).toBe(true);
    expect(canLock("developer", "art")).toBe(false);
    expect(canLock("tester", "code")).toBe(false);
    expect(canLock("admin", "art")).toBe(true);
  });

  it("solo el dueño nombra admins y nadie toca al dueño", () => {
    expect(assignableRoles("owner")).toContain("admin");
    expect(assignableRoles("admin")).not.toContain("admin");
    expect(assignableRoles("developer")).toEqual([]);
    expect(canManageMember("admin", "admin")).toBe(false);
    expect(canManageMember("owner", "admin")).toBe(true);
    expect(canManageMember("owner", "owner")).toBe(false);
  });
});
