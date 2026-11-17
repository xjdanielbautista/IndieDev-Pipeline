"""Siembra 2 estudios (tenants) de ejemplo para la demo multi-tenant.

Usa la API real (no escribe directo en la BD), así que pasa por las mismas
validaciones de autenticación, membresía y roles. Funciona igual contra el
backend local o el desplegado. Solo usa la librería estándar de Python.

Uso:
    python scripts/seed_demo.py                         # http://localhost:8000
    python scripts/seed_demo.py https://tu-api.onrender.com

Se puede correr varias veces: si un usuario, estudio o proyecto ya existe,
lo reutiliza en lugar de duplicarlo.

Al crear un proyecto también sube archivos reales para lucir la vista previa:
sprites PNG (con dos versiones para compararlas), scripts con cambios entre
versiones, un modelo .fbx de ejemplo (sin vista previa) y comentarios.
"""

import json
import struct
import sys
import urllib.error
import uuid
import zlib
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
        "comments": [("hero_sprite.png", "tester_pixel", "Se ve muy bien. ¿Podemos probar la capa en rojo más oscuro?")],
        "build": ("0.1.0-alpha", "Primer build jugable"),
    },
    {
        "name": "Nebula Games",
        "slug": "nebula-games",
        "owner": "dueno_nebula",
        "members": [("dev_nebula", "developer"), ("artista_nebula", "artist")],
        "comments": [("ship_physics.py", "dueno_nebula", "Revisa que el impulso no se acumule al chocar.")],
        "project": ("Star Drift", "Shooter espacial 3D"),
        "assets": [
            ("ship_physics.py", "code", "review"),
            ("spaceship_model.fbx", "art", "in_progress"),
            ("skybox_nebula.png", "art", "backlog"),
        ],
        "build": ("0.0.3-prealpha", "Prueba de físicas"),
    },
]


def call(method, path, token=None, body=None, form=None, file=None):
    headers = {"Accept": "application/json"}
    data = None
    if file is not None:
        name, content, content_type = file
        boundary = uuid.uuid4().hex
        data = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif form is not None:
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


# ---------- Archivos de ejemplo ----------
def png(pixels, scale=8):
    """PNG RGBA a partir de una matriz de caracteres (cada carácter es un color)."""
    palette = {
        ".": (0, 0, 0, 0), "k": (20, 20, 30, 255), "s": (255, 205, 160, 255), "h": (90, 50, 30, 255),
        "c": (200, 30, 60, 255), "C": (120, 10, 40, 255), "b": (40, 90, 200, 255), "w": (240, 240, 240, 255),
        "g": (60, 160, 70, 255), "G": (30, 100, 40, 255), "y": (240, 200, 40, 255), "d": (110, 110, 130, 255),
        "D": (70, 70, 90, 255),
    }
    rows = []
    for line in pixels:
        row = b"".join(bytes(palette[ch]) * scale for ch in line)
        rows.extend([b"\x00" + row] * scale)
    width, height = len(pixels[0]) * scale, len(pixels) * scale

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


HERO = [
    "....kkkk....", "...khhhhk...", "..khsssshk..", "..ksksskssk.", "..kssssssk..", "...kcccck...",
    "..kcwccwck..", ".kscccccsk..", "..kccccck...", "..kbbkbbk...", "..kbk.kbk...", "..kk...kk...",
]


def hero(cape):
    return png([row.replace("c", cape) for row in HERO])


def tileset():
    tile = ["ddddDddd", "dDdddddD", "ddddddDd", "Dddddddd", "dddDdddd", "ddddddDd", "dDdddddd", "dddddDdd"]
    grass = ["gggGgggg", "gGgggggG", "ggggggGg", "Gggggggg", "gggGgggg", "ggggggGg", "gGgggggg", "gggggGgg"]
    return png([a + b for a, b in zip(tile, grass)] + [b + a for a, b in zip(tile, grass)], scale=6)


def skybox():
    return png(["kkbkkkkwkkkk", "kkkkykkkkbkk", "kbkkkkkkkkkk", "kkkkkkwkkkyk", "kkwkkkkkkkkk", "kkkkkbkkkkwk"], scale=10)


PLAYER_V1 = """using UnityEngine;

public class PlayerController : MonoBehaviour
{
    public float speed = 5f;
    private Rigidbody2D body;

    void Start()
    {
        body = GetComponent<Rigidbody2D>();
    }

    void Update()
    {
        float x = Input.GetAxis("Horizontal");
        body.velocity = new Vector2(x * speed, body.velocity.y);
    }
}
"""

PLAYER_V2 = PLAYER_V1.replace(
    "    public float speed = 5f;\n", "    public float speed = 6.5f;\n    public float jumpForce = 12f;\n"
).replace(
    "        body.velocity = new Vector2(x * speed, body.velocity.y);\n",
    "        body.velocity = new Vector2(x * speed, body.velocity.y);\n\n"
    "        // Salto: solo si está tocando el suelo\n"
    "        if (Input.GetButtonDown(\"Jump\") && Mathf.Abs(body.velocity.y) < 0.01f)\n"
    "            body.AddForce(Vector2.up * jumpForce, ForceMode2D.Impulse);\n",
)

ENEMY = """using UnityEngine;

public enum EnemyState { Patrol, Chase, Attack }

public class EnemyAI : MonoBehaviour
{
    public Transform player;
    public float visionRange = 6f;
    private EnemyState state = EnemyState.Patrol;

    void Update()
    {
        float distance = Vector2.Distance(transform.position, player.position);
        state = distance < 1.2f ? EnemyState.Attack : distance < visionRange ? EnemyState.Chase : EnemyState.Patrol;
    }
}
"""

SHIP_V1 = """class Ship:
    def __init__(self, mass=1200.0):
        self.mass = mass
        self.velocity = [0.0, 0.0, 0.0]

    def apply_thrust(self, force, dt):
        for axis in range(3):
            self.velocity[axis] += force[axis] / self.mass * dt
"""

SHIP_V2 = SHIP_V1 + """
    def collide(self, normal, restitution=0.4):
        # Rebota solo la componente que va hacia la superficie
        dot = sum(v * n for v, n in zip(self.velocity, normal))
        if dot < 0:
            for axis in range(3):
                self.velocity[axis] -= (1 + restitution) * dot * normal[axis]
"""

# nombre -> versiones (contenido, tipo MIME) en orden
FILES = {
    "player_controller.cs": [(PLAYER_V1.encode(), "text/plain"), (PLAYER_V2.encode(), "text/plain")],
    "enemy_ai.cs": [(ENEMY.encode(), "text/plain")],
    "hero_sprite.png": [(hero("c"), "image/png"), (hero("C"), "image/png")],
    "tileset_dungeon.png": [(tileset(), "image/png")],
    "ship_physics.py": [(SHIP_V1.encode(), "text/x-python"), (SHIP_V2.encode(), "text/x-python")],
    "spaceship_model.fbx": [(b"Kaydara FBX Binary  \x00\x1a\x00" + bytes(200), "application/octet-stream")],
    "skybox_nebula.png": [(skybox(), "image/png")],
}


def upload_files(tid, pid, asset, token):
    """Sube las versiones de ejemplo del asset. Devuelve False si el storage falla."""
    versions = FILES.get(asset["original_name"], [])
    if not versions:
        return True
    url = f"/api/tenants/{tid}/projects/{pid}/assets/{asset['id']}"
    call("PATCH", f"{url}/lock", token, {})
    ok = True
    for content, content_type in versions:
        status, data = call("POST", f"{url}/file", token, file=(asset["original_name"], content, content_type))
        if status != 200:
            print(f"  ! No se pudo subir {asset['original_name']}: HTTP {status} {data}")
            ok = False
            break
    call("DELETE", f"{url}/lock", token)
    return ok


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

        tokens = {studio["owner"]: token}
        uploader = {"code": token, "art": token}
        for username, role in studio["members"]:
            tokens[username] = user(username)
            call("POST", f"/api/tenants/{tid}/members", token, {"identifier": username, "role": role})
            # Cada archivo lo sube quien trabaja ese tipo de tarea.
            if role == "developer":
                uploader["code"] = tokens[username]
            if role == "artist":
                uploader["art"] = tokens[username]

        projects = {p["name"]: p for p in call("GET", f"/api/tenants/{tid}/projects", token)[1]}
        name, description = studio["project"]
        project = projects.get(name)
        if project is None:
            project = call("POST", f"/api/tenants/{tid}/projects", token, {"name": name, "description": description})[1]
            pid = project["id"]
            assets = {}
            for file_name, category, asset_status in studio["assets"]:
                status, asset = call("POST", f"/api/tenants/{tid}/projects/{pid}/assets", token, {
                    "original_name": file_name,
                    "storage_key": file_name,
                    "category": category,
                    "status": asset_status,
                })
                if status == 201:
                    assets[file_name] = asset
            storage_ok = True
            for asset in assets.values():
                if storage_ok:
                    storage_ok = upload_files(tid, pid, asset, uploader[asset["category"]])
            if not storage_ok:
                print("  ! Revisa ASSET_STORAGE_PROVIDER y sus credenciales en el backend; se omiten los demás archivos.")
            for file_name, author, body in studio.get("comments", []):
                if file_name in assets and author in tokens:
                    call("POST", f"/api/tenants/{tid}/projects/{pid}/assets/{assets[file_name]['id']}/comments",
                         tokens[author], {"body": body})
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
