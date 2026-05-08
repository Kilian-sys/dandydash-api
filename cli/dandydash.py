#!/usr/bin/env python3
import sys, os, json, argparse, requests
import urllib3; urllib3.disable_warnings()

API   = "https://192.168.20.10"
TOKEN = os.path.expanduser("~/.dandydash/token")

# Colores
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; C = "\033[96m"; W = "\033[0m"; BD = "\033[1m"

def header(title):
    print(f"\n{BD}{B}{'─'*55}{W}")
    print(f"{BD}{C}  {title}{W}")
    print(f"{BD}{B}{'─'*55}{W}\n")

def ok(m):  print(f"  {G}✔{W}  {m}")
def fail(m): print(f"  {R}✘{W}  {m}"); sys.exit(1)

def get_token():
    if not os.path.exists(TOKEN): fail("No autenticado. Usa: dandydash login <user> <pass>")
    return open(TOKEN).read().strip()

def hdrs():
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}

def get(path):
    r = requests.get(f"{API}{path}", headers=hdrs(), verify=False, timeout=10)
    if r.status_code == 401: fail("Token expirado. Vuelve a hacer login.")
    return r.json()

def post(path, data):
    return requests.post(f"{API}{path}", headers=hdrs(), json=data, verify=False, timeout=10).json()

def delete(path):
    return requests.delete(f"{API}{path}", headers=hdrs(), verify=False, timeout=10).json()

# ── Comandos ──────────────────────────────────────────────────

def cmd_login(a):
    r = requests.post(f"{API}/api/auth/login",
        json={"username": a.username, "password": a.password}, verify=False, timeout=10).json()
    if "access_token" in r:
        os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
        open(TOKEN, "w").write(r["access_token"])
        os.chmod(TOKEN, 0o600)
        ok(f"Bienvenido {BD}{a.username}{W}  |  rol: {r.get('role','?')}")
    else:
        fail(f"Login fallido: {r}")

def cmd_users(a):
    header("USUARIOS DEL DOMINIO — dandydash.local")
    data = get("/api/users/").get("users", [])
    print(f"  {'USUARIO':<22} {'NOMBRE':<28} {'ESTADO'}")
    print(f"  {'─'*22} {'─'*28} {'─'*12}")
    for u in data:
        estado = f"{G}activo{W}" if u.get("enabled") else f"{R}desactivado{W}"
        print(f"  {u['username']:<22} {u.get('name',''):<28} {estado}")
    print(f"\n  {Y}Total: {len(data)} usuarios{W}\n")

def cmd_groups(a):
    header("GRUPOS DEL DOMINIO — dandydash.local")
    data = get("/api/groups/").get("groups", [])
    print(f"  {'GRUPO':<35} {'MIEMBROS'}")
    print(f"  {'─'*35} {'─'*10}")
    for g in data:
        print(f"  {g['name']:<35} {len(g.get('members',[]))}")
    print(f"\n  {Y}Total: {len(data)} grupos{W}\n")

def cmd_ous(a):
    header("UNIDADES ORGANIZATIVAS — dandydash.local")
    data = get("/api/ous/").get("ous", [])
    print(f"  {'OU':<30} {'DESCRIPCION'}")
    print(f"  {'─'*30} {'─'*30}")
    for o in data:
        print(f"  {o['name']:<30} {o.get('description','─')}")
    print(f"\n  {Y}Total: {len(data)} OUs{W}\n")

def cmd_user_add(a):
    r = post("/api/users/", {"username":a.username,"password":a.password,
                              "first_name":a.first_name,"last_name":a.last_name,"email":a.email})
    ok(r.get("message", str(r)))

def cmd_user_del(a):
    r = delete(f"/api/users/{a.username}")
    ok(r.get("message", str(r)))

def cmd_group_add(a):
    r = post("/api/groups/", {"name":a.name})
    ok(r.get("message", str(r)))

def cmd_group_del(a):
    r = delete(f"/api/groups/{a.name}")
    ok(r.get("message", str(r)))

# ── Parser ────────────────────────────────────────────────────

p = argparse.ArgumentParser(prog="dandydash", description="DandyDash CLI — Kevin & Kilian ASIR 2025-2026")
s = p.add_subparsers(title="comandos")

# login
c = s.add_parser("login", help="Autenticarse"); c.add_argument("username"); c.add_argument("password"); c.set_defaults(func=cmd_login)
# users
c = s.add_parser("users", help="Listar usuarios"); c.set_defaults(func=cmd_users)
# groups
c = s.add_parser("groups", help="Listar grupos"); c.set_defaults(func=cmd_groups)
# ous
c = s.add_parser("ous", help="Listar OUs"); c.set_defaults(func=cmd_ous)
# user add
c = s.add_parser("user-add", help="Crear usuario")
c.add_argument("username"); c.add_argument("password"); c.add_argument("first_name"); c.add_argument("last_name"); c.add_argument("--email", default=""); c.set_defaults(func=cmd_user_add)
# user del
c = s.add_parser("user-del", help="Eliminar usuario"); c.add_argument("username"); c.set_defaults(func=cmd_user_del)
# group add
c = s.add_parser("group-add", help="Crear grupo"); c.add_argument("name"); c.set_defaults(func=cmd_group_add)
# group del
c = s.add_parser("group-del", help="Eliminar grupo"); c.add_argument("name"); c.set_defaults(func=cmd_group_del)

args = p.parse_args()
if hasattr(args, "func"): args.func(args)
else: p.print_help()
