"""Siembra 2 estudios (tenants) de ejemplo para la demo multi-tenant.

Usa la API real (no escribe directo en la BD), así que pasa por las mismas
validaciones de autenticación, membresía y roles. Funciona igual contra el
backend local o el desplegado. Solo usa la librería estándar de Python.

Uso:
    python scripts/seed_demo.py                         # http://localhost:8000
    python scripts/seed_demo.py https://tu-api.onrender.com

Se puede correr varias veces: si un usuario, estudio o proyecto ya existe,
lo reutiliza en lugar de duplicarlo.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
PASSWORD = "Demo12345"

STUDIOS = [
    {
        "name": "Pixel Forge Studio",
        "slug": "pixel-forge",
        "owner": "dueno_pixel",
        "members": [("dev_pixel", "developer"), ("artista_pixel", "artist"), ("tester_pixel", "tester")],
        "project": ("Dungeon Runner", "Roguelike 2D en pixel art"),
        "assets": [
            ("player_controller.cs", "code", "in_progress"),
            ("enemy_ai.cs", "code", "backlog"),
            ("hero_sprite.png", "art", "review"),
            ("tileset_dungeon.png", "art", "done"),
        ],
        "build": ("0.1.0-alpha", "Primer build jugable"),
    },
    {
        "name": "Nebula Games",
        "slug": "nebula-games",
        "owner": "dueno_nebula",
        "members": [("dev_nebula", "developer"), ("artista_nebula", "artist")],
        "project": ("Star Drift", "Shooter espacial 3D"),
        "assets": [
            ("ship_physics.py", "code", "review"),
            ("spaceship_model.fbx", "art", "in_progress"),
            ("skybox_nebula.png", "art", "backlog"),
        ],
        "build": ("0.0.3-prealpha", "Prueba de físicas"),
    },
]


def call(method, path, token=None, body=None, form=None):
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode()
            return response.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as error:
        text = error.read().decode()
        try:
            return error.code, json.loads(text)
        except ValueError:
            return error.code, text


def user(username):
    status, _ = call("POST", "/api/auth/register", body={
        "username": username, "email": f"{username}@indiedev.demo", "password": PASSWORD,
    })
    if status not in (201, 409):
        sys.exit(f"No se pudo registrar {username}: {status}")
    status, data = call("POST", "/api/auth/token", form={"username": username, "password": PASSWORD})
    if status != 200:
        sys.exit(f"No se pudo iniciar sesión como {username} (¿ya existía con otra contraseña?): {data}")
    return data["access_token"]


def main():
    status, _ = call("GET", "/health")
    if status != 200:
        sys.exit(f"El backend no responde en {API} (si es Render, ábrelo primero para despertarlo)")

    created = []
    for studio in STUDIOS:
        token = user(studio["owner"])
        mine = {t["slug"]: t for t in call("GET", "/api/tenants", token)[1]}
        tenant = mine.get(studio["slug"])
        if tenant is None:
            status, tenant = call("POST", "/api/tenants", token, {"name": studio["name"], "slug": studio["slug"]})
            if status != 201:
                sys.exit(f"No se pudo crear {studio['slug']}: {tenant}")
        tid = tenant["id"]

        member_ids = []
        for username, role in studio["members"]:
            user(username)
            status, member = call("POST", f"/api/tenants/{tid}/members", token, {"identifier": username, "role": role})
            if status == 201:
                member_ids.append(member["id"])

        projects = {p["name"]: p for p in call("GET", f"/api/tenants/{tid}/projects", token)[1]}
        name, description = studio["project"]
        project = projects.get(name)
        if project is None:
            project = call("POST", f"/api/tenants/{tid}/projects", token, {"name": name, "description": description})[1]
            pid = project["id"]
            for file_name, category, asset_status in studio["assets"]:
                call("POST", f"/api/tenants/{tid}/projects/{pid}/assets", token, {
                    "original_name": file_name,
                    "storage_key": file_name,
                    "category": category,
                    "status": asset_status,
                })
            version, notes = studio["build"]
            call("POST", f"/api/tenants/{tid}/projects/{pid}/builds", token,
                 {"version": version, "notes": notes, "status": "success"})
        created.append((studio, tid, project["id"]))

    # Comprobación de aislamiento: el dueño de un estudio no puede leer el otro.
    (a, tid_a, _), (b, tid_b, _) = created
    token_b = user(b["owner"])
    status, _ = call("GET", f"/api/tenants/{tid_a}/projects", token_b)

    print(f"\nListo en {API}\n")
    for studio, tid, pid in created:
        print(f"  {studio['name']} (tenant_id={tid}, project_id={pid})")
        print(f"    dueño: {studio['owner']}")
        for username, role in studio["members"]:
            print(f"    {role}: {username}")
    print(f"\n  Contraseña de todos: {PASSWORD}")
    print(f"\n  Aislamiento: {b['owner']} pidiendo proyectos de {a['name']} -> HTTP {status}"
          f" {'(correcto, bloqueado)' if status == 403 else '(¡REVISAR!)'}")


if __name__ == "__main__":
    main()
