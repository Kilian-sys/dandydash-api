from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, MODIFY_ADD, MODIFY_DELETE, SUBTREE
from ldap3.core.exceptions import LDAPException
from flask import current_app
import subprocess
import struct
import datetime

# ── Conexion ──────────────────────────────────────────────────────────────────
def get_connection():
    """Crea y devuelve una conexion autenticada al AD de Samba4."""
    cfg = current_app.config
    srv = Server(cfg["LDAP_SERVER"], get_info=ALL)
    conn = Connection(
        srv,
        user="administrator@dandydash.local",
        password="DandyAdmin2026!",
        auto_bind=True
    )
    return conn

# ── UTILS internos ────────────────────────────────────────────────────────────
def _get_user_dn(username):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=user)(sAMAccountName={username}))",
                attributes=["distinguishedName"], search_scope=SUBTREE)
    if not conn.entries:
        raise LDAPException(f"Usuario '{username}' no encontrado")
    return str(conn.entries[0]["distinguishedName"].value)

def _get_group_dn(group_name):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=group)(cn={group_name}))",
                attributes=["distinguishedName"], search_scope=SUBTREE)
    if not conn.entries:
        raise LDAPException(f"Grupo '{group_name}' no encontrado")
    return str(conn.entries[0]["distinguishedName"].value)

def _encode_password(password):
    return ('"{}"'.format(password)).encode('utf-16-le')

# ── USUARIOS — Listar ─────────────────────────────────────────────────────────
def list_users(search=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = "(&(objectClass=user)(objectCategory=person)(!(objectClass=computer)))" if not search \
        else f"(&(objectClass=user)(objectCategory=person)(!(objectClass=computer))(sAMAccountName=*{search}*))"
    conn.search(base, f, attributes=[
        "sAMAccountName","cn","givenName","sn","mail","memberOf",
        "userAccountControl","distinguishedName","whenCreated","description"
    ], search_scope=SUBTREE)
    users = []
    for e in conn.entries:
        uac = (int(str(e["userAccountControl"].value)) if "userAccountControl" in e and e["userAccountControl"].value else 512)
        users.append({
            "username":    (str(e["sAMAccountName"].value) if "sAMAccountName" in e and e["sAMAccountName"].value else ""),
            "name":        (str(e["cn"].value)             if "cn" in e and e["cn"].value else ""),
            "first_name":  (str(e["givenName"].value)      if "givenName" in e and e["givenName"].value else ""),
            "last_name":   (str(e["sn"].value)             if "sn" in e and e["sn"].value else ""),
            "email":       (str(e["mail"].value)           if "mail" in e and e["mail"].value else ""),
            "groups":      ([str(g) for g in e["memberOf"].values] if "memberOf" in e and e["memberOf"].value else []),
            "enabled":     not bool(uac & 2),
            "dn":          (str(e["distinguishedName"].value) if "distinguishedName" in e and e["distinguishedName"].value else ""),
            "created":     (str(e["whenCreated"].value)    if "whenCreated" in e and e["whenCreated"].value else ""),
            "description": (str(e["description"].value)   if "description" in e and e["description"].value else ""),
        })
    return users

# ── USUARIOS — Obtener uno ────────────────────────────────────────────────────
def get_user(username):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=user)(sAMAccountName={username}))",
        attributes=["sAMAccountName","cn","givenName","sn","mail","memberOf",
                    "userAccountControl","distinguishedName","whenCreated",
                    "description","homeDirectory","lastLogon"], search_scope=SUBTREE)
    if not conn.entries:
        return None
    e = conn.entries[0]
    uac = (int(str(e["userAccountControl"].value)) if "userAccountControl" in e and e["userAccountControl"].value else 512)
    return {
        "username":    (str(e["sAMAccountName"].value)    if "sAMAccountName" in e and e["sAMAccountName"].value else ""),
        "name":        (str(e["cn"].value)                if "cn" in e and e["cn"].value else ""),
        "first_name":  (str(e["givenName"].value)         if "givenName" in e and e["givenName"].value else ""),
        "last_name":   (str(e["sn"].value)                if "sn" in e and e["sn"].value else ""),
        "email":       (str(e["mail"].value)              if "mail" in e and e["mail"].value else ""),
        "groups":      ([str(g) for g in e["memberOf"].values] if "memberOf" in e and e["memberOf"].value else []),
        "enabled":     not bool(uac & 2),
        "dn":          (str(e["distinguishedName"].value) if "distinguishedName" in e and e["distinguishedName"].value else ""),
        "created":     (str(e["whenCreated"].value)       if "whenCreated" in e and e["whenCreated"].value else ""),
        "description": (str(e["description"].value)      if "description" in e and e["description"].value else ""),
        "home_dir":    (str(e["homeDirectory"].value)     if "homeDirectory" in e and e["homeDirectory"].value else ""),
    }

# ── USUARIOS — Crear ──────────────────────────────────────────────────────────
def create_user(username, password, first_name="", last_name="", email="", ou=None, description=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    ou_dn = ou if ou else f"CN=Users,{base}"
    dn = f"CN={first_name} {last_name},{ou_dn}" if (first_name or last_name) else f"CN={username},{ou_dn}"
    attrs = {
        "objectClass":        ["top","person","organizationalPerson","user"],
        "sAMAccountName":     username,
        "userPrincipalName":  f"{username}@{current_app.config['LDAP_DOMAIN']}",
        "givenName":          first_name,
        "sn":                 last_name,
        "cn":                 f"{first_name} {last_name}".strip() or username,
        "displayName":        f"{first_name} {last_name}".strip() or username,
        "userAccountControl": "514",
    }
    if email:       attrs["mail"]        = email
    if description: attrs["description"] = description
    conn.add(dn, attributes=attrs)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    # Establecer contraseña y habilitar
    encoded_pw = _encode_password(password)
    conn.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [encoded_pw])]})
    conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, ["512"])]})
    return True

# ── USUARIOS — Modificar ──────────────────────────────────────────────────────
def modify_user(username, changes):
    conn = get_connection()
    dn = _get_user_dn(username)
    field_map = {
        "first_name":  "givenName",
        "last_name":   "sn",
        "email":       "mail",
        "description": "description",
    }
    mods = {}
    for k, v in changes.items():
        if k == "password":
            encoded_pw = _encode_password(v)
            conn.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [encoded_pw])]})
        elif k in field_map:
            mods[field_map[k]] = [(MODIFY_REPLACE, [v])]
    if mods:
        conn.modify(dn, mods)
    return True

# ── USUARIOS — Eliminar ───────────────────────────────────────────────────────
def delete_user(username):
    conn = get_connection()
    dn = _get_user_dn(username)
    conn.delete(dn)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── USUARIOS — Habilitar / Deshabilitar ──────────────────────────────────────
def set_user_enabled(username, enabled=True):
    conn = get_connection()
    dn = _get_user_dn(username)
    uac = "512" if enabled else "514"
    conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, [uac])]})
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── USUARIOS — Cambiar contraseña ─────────────────────────────────────────────
def set_password(username, new_password):
    import subprocess
    result = subprocess.run(
        ["/usr/bin/ssh", "-i", "/home/admin-kk/.ssh/id_rsa", "-o", "StrictHostKeyChecking=no",
         "admin-kk@192.168.30.10",
         f"sudo samba-tool user setpassword {username} --newpassword='{new_password}'"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or result.stdout.strip())
    return True

# ── USUARIOS — Forzar cambio de contraseña ────────────────────────────────────
def force_password_change(username):
    """Establece pwdLastSet=0 para forzar cambio en el próximo login."""
    conn = get_connection()
    dn = _get_user_dn(username)
    conn.modify(dn, {"pwdLastSet": [(MODIFY_REPLACE, [0])]})
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── USUARIOS — Horas de inicio de sesión ─────────────────────────────────────
def set_logon_hours(username, hours):
    """
    hours: lista de strings "dia-hora" ej ["0-8","0-9",...] donde dia 0=lun, 6=dom
    Construye el bitmap de 21 bytes (168 bits, 1 bit por hora semanal).
    """
    conn = get_connection()
    dn = _get_user_dn(username)
    bits = [0] * 168
    for h in hours:
        try:
            day, hour = map(int, h.split('-'))
            idx = day * 24 + hour
            if 0 <= idx < 168:
                bits[idx] = 1
        except Exception:
            continue
    # Convertir a 21 bytes
    bitmap = bytearray(21)
    for i, bit in enumerate(bits):
        if bit:
            bitmap[i // 8] |= (1 << (i % 8))
    conn.modify(dn, {"logonHours": [(MODIFY_REPLACE, [bytes(bitmap)])]})
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── USUARIOS — Equipos permitidos ─────────────────────────────────────────────
def set_workstations(username, workstations):
    """workstations: lista de nombres de equipo. [] = sin restricción."""
    conn = get_connection()
    dn = _get_user_dn(username)
    if workstations:
        value = ",".join(workstations)
        conn.modify(dn, {"userWorkstations": [(MODIFY_REPLACE, [value])]})
    else:
        conn.modify(dn, {"userWorkstations": [(MODIFY_REPLACE, [])]})
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── GRUPOS — Listar ───────────────────────────────────────────────────────────
def list_groups(search=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = "(&(objectClass=group))" if not search \
        else f"(&(objectClass=group)(cn=*{search}*))"
    conn.search(base, f, attributes=["cn","description","member","distinguishedName"],
                search_scope=SUBTREE)
    return [{
        "name":        (str(e["cn"].value)          if "cn" in e and e["cn"].value else ""),
        "description": (str(e["description"].value) if "description" in e and e["description"].value else ""),
        "members":     ([str(m) for m in e["member"].values] if "member" in e and e["member"].value else []),
        "dn":          (str(e["distinguishedName"].value) if "distinguishedName" in e and e["distinguishedName"].value else ""),
    } for e in conn.entries]

# ── GRUPOS — Obtener uno ──────────────────────────────────────────────────────
def get_group(name):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=group)(cn={name}))",
                attributes=["cn","description","member","distinguishedName"],
                search_scope=SUBTREE)
    if not conn.entries:
        return None
    e = conn.entries[0]
    return {
        "name":        (str(e["cn"].value)          if "cn" in e and e["cn"].value else ""),
        "description": (str(e["description"].value) if "description" in e and e["description"].value else ""),
        "members":     ([str(m) for m in e["member"].values] if "member" in e and e["member"].value else []),
        "dn":          (str(e["distinguishedName"].value) if "distinguishedName" in e and e["distinguishedName"].value else ""),
    }

# ── GRUPOS — Crear ────────────────────────────────────────────────────────────
def create_group(name, description="", ou=None):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    ou_dn = ou if ou else f"CN=Users,{base}"
    dn = f"CN={name},{ou_dn}"
    attrs = {
        "objectClass":    ["top","group"],
        "cn":             name,
        "sAMAccountName": name,
        "groupType":      "-2147483646",
    }
    if description: attrs["description"] = description
    conn.add(dn, attributes=attrs)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── GRUPOS — Eliminar ─────────────────────────────────────────────────────────
def delete_group(name):
    conn = get_connection()
    dn = _get_group_dn(name)
    conn.delete(dn)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── GRUPOS — Añadir miembro ───────────────────────────────────────────────────
def add_member_to_group(group_name, username):
    conn = get_connection()
    group_dn = _get_group_dn(group_name)
    user_dn  = _get_user_dn(username)
    conn.modify(group_dn, {"member": [(MODIFY_ADD, [user_dn])]})
    if conn.result["result"] not in (0, 68):  # 68 = ya existe
        raise LDAPException(conn.result["description"])
    return True

# ── GRUPOS — Quitar miembro ───────────────────────────────────────────────────
def remove_member_from_group(group_name, username):
    conn = get_connection()
    group_dn = _get_group_dn(group_name)
    user_dn  = _get_user_dn(username)
    conn.modify(group_dn, {"member": [(MODIFY_DELETE, [user_dn])]})
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── OUs — Listar ──────────────────────────────────────────────────────────────
def list_ous():
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, "(objectClass=organizationalUnit)",
                attributes=["ou","description","distinguishedName"],
                search_scope=SUBTREE)
    return [{
        "name":        (str(e["ou"].value)          if "ou" in e and e["ou"].value else ""),
        "description": (str(e["description"].value) if "description" in e and e["description"].value else ""),
        "dn":          (str(e["distinguishedName"].value) if "distinguishedName" in e and e["distinguishedName"].value else ""),
    } for e in conn.entries]

# ── OUs — Crear ───────────────────────────────────────────────────────────────
def create_ou(name, description="", parent_dn=None):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    parent = parent_dn if parent_dn else base
    dn = f"OU={name},{parent}"
    attrs = {"objectClass": ["top","organizationalUnit"], "ou": name}
    if description: attrs["description"] = description
    conn.add(dn, attributes=attrs)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── OUs — Eliminar ────────────────────────────────────────────────────────────
def delete_ou(name):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=organizationalUnit)(ou={name}))",
                attributes=["distinguishedName"], search_scope=SUBTREE)
    if not conn.entries:
        raise LDAPException("OU no encontrada")
    dn = str(conn.entries[0]["distinguishedName"].value)
    conn.delete(dn)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ── GPOs — Listar via samba-tool ──────────────────────────────────────────────
def list_gpos():
    try:
        result = subprocess.run(
            ["samba-tool","gpo","listall","--url",f"ldap://{current_app.config['LDAP_SERVER']}"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        gpos, current = [], {}
        for line in lines:
            if line.startswith("GPO"):
                if current: gpos.append(current)
                current = {"name": line.split(":")[-1].strip()}
            elif ":" in line:
                k, v = line.split(":", 1)
                current[k.strip().lower().replace(" ","_")] = v.strip()
        if current: gpos.append(current)
        return gpos
    except Exception:
        return []
