import re

def sanitize_input(value, max_length=256):
    """Sanitiza inputs antes de pasarlos a samba-tool o LDAP"""
    if not isinstance(value, str):
        value = str(value)
    # Eliminar caracteres peligrosos para shell injection
    value = re.sub(r'[;&|`$(){}\\<>]', '', value)
    # Limitar longitud
    return value[:max_length].strip()

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
        user=current_app.config.get("LDAP_BIND_USER", "administrator@dandydash.local"),
        password=current_app.config.get("LDAP_BIND_PASS", "DandyAdmin2026!!"),
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
                    "description","homeDirectory","lastLogon","pwdLastSet"], search_scope=SUBTREE)
    if not conn.entries:
        return None
    e = conn.entries[0]
    uac = (int(str(e["userAccountControl"].value)) if "userAccountControl" in e and e["userAccountControl"].value else 512)
    try:
        raw = e["pwdLastSet"].value if "pwdLastSet" in e else None
        if raw is None:
            pwd_last_set = -1
        elif hasattr(raw, "timestamp"):
            # pwdLastSet=0 en LDAP = epoch 1601 = forzar cambio
            try:
                ts = int(raw.timestamp())
                pwd_last_set = 0 if ts < 0 or raw.year < 1970 else 1
            except:
                pwd_last_set = 1
    except:
        pwd_last_set = -1
    return {
        "username":           (str(e["sAMAccountName"].value)    if "sAMAccountName" in e and e["sAMAccountName"].value else ""),
        "name":               (str(e["cn"].value)                if "cn" in e and e["cn"].value else ""),
        "first_name":         (str(e["givenName"].value)         if "givenName" in e and e["givenName"].value else ""),
        "last_name":          (str(e["sn"].value)                if "sn" in e and e["sn"].value else ""),
        "email":              (str(e["mail"].value)              if "mail" in e and e["mail"].value else ""),
        "groups":             ([str(g) for g in e["memberOf"].values] if "memberOf" in e and e["memberOf"].value else []),
        "enabled":            not bool(uac & 2),
        "must_change_password": pwd_last_set == 0,
        "dn":                 (str(e["distinguishedName"].value) if "distinguishedName" in e and e["distinguishedName"].value else ""),
        "created":            (str(e["whenCreated"].value)       if "whenCreated" in e and e["whenCreated"].value else ""),
        "description":        (str(e["description"].value)      if "description" in e and e["description"].value else ""),
        "home_dir":           (str(e["homeDirectory"].value)     if "homeDirectory" in e and e["homeDirectory"].value else ""),
    }

# ── USUARIOS — Crear ──────────────────────────────────────────────────────────
def create_user(username, password, first_name="", last_name="", email="", ou=None, description=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    ou_dn = ou if ou else f"CN=Users,{base}"
    dn = f"CN={username},{ou_dn}"
    attrs = {
        "objectClass":        ["top","person","organizationalPerson","user"],
        "sAMAccountName":     username,
        "userPrincipalName":  f"{username}@{current_app.config['LDAP_DOMAIN']}",
        "givenName":          first_name,
        "sn":                 last_name,
        "cn":                 username,
        "displayName":        f"{first_name} {last_name}".strip() or username,
        "userAccountControl": "514",
    }
    if email:       attrs["mail"]        = email
    if description: attrs["description"] = description
    conn.add(dn, attributes=attrs)
    if conn.result["result"] != 0:
        raise LDAPException(f"{conn.result['description']} - DN: {dn} - result: {conn.result}")
    # Establecer contraseña via samba-tool (SSH) i habilitar compte
    import subprocess, time
    time.sleep(0.5)  # Esperar que el compte es creï
    r = subprocess.run(
        ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
         "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10",
         f"sudo samba-tool user setpassword {username} --newpassword={password}"],
        capture_output=True, text=True, timeout=15
    )
    if r.returncode != 0:
        err = r.stderr or r.stdout or ""
        # Borrar el usuario que quedó a medias
        conn2 = get_connection()
        conn2.delete(dn)
        if 'too short' in err or 'minimum' in err.lower():
            raise LDAPException("La contraseña no cumple la política del dominio (mínimo 10 caracteres, mayúsculas, números y símbolos)")
        if 'complexity' in err.lower() or 'complexity' in err:
            raise LDAPException("La contraseña no cumple los requisitos de complejidad")
        raise LDAPException(f"Error estableciendo contraseña: {err}")
    # Habilitar compte via samba-tool
    subprocess.run(
        ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
         "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10",
         f"sudo samba-tool user enable {username}"],
        capture_output=True, text=True, timeout=15
    )
    return True

# ── USUARIOS — Modificar ──────────────────────────────────────────────────────
def modify_user(username, changes):
    conn = get_connection()
    dn = _get_user_dn(username)
    field_map = {
        "first_name":    "givenName",
        "last_name":     "sn",
        "email":         "mail",
        "description":   "description",
        "display_name":  "displayName",
    }
    mods = {}
    for k, v in changes.items():
        if k == "password":
            encoded_pw = _encode_password(v)
            conn.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [encoded_pw])]})
        elif k in field_map and v is not None and v != '':
            mods[field_map[k]] = [(MODIFY_REPLACE, [v])]
    # Construir displayName desde givenName + sn
    fn = changes.get("first_name", "")
    ln = changes.get("last_name", "")
    if fn or ln:
        full = f"{fn} {ln}".strip()
        if full:
            mods["displayName"] = [(MODIFY_REPLACE, [full])]
    if mods:
        ok = conn.modify(dn, mods)
        if not ok:
            raise Exception(f"LDAP modify failed: {conn.result}")
    # Renombrar CN si cambió el nombre completo
    fn = changes.get("first_name", "")
    ln = changes.get("last_name", "")
    if fn or ln:
        full = f"{fn} {ln}".strip()
        if full:
            new_rdn = f"CN={full}"
            conn.modify_dn(dn, new_rdn)
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
    r = subprocess.run(
        ["/usr/bin/ssh","-i","/opt/dandydash-api/.ssh/id_rsa",
         "-o","StrictHostKeyChecking=no","admin-kk@192.168.30.10",
         f"sudo samba-tool user setpassword {username} --newpassword={new_password}"],
        capture_output=True, text=True, timeout=15
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "")
        if "too short" in err.lower() or "shorter" in err.lower():
            raise Exception("La contraseña es demasiado corta. Mínimo 7 caracteres.")
        elif "complexity" in err.lower() or "0000052D" in err:
            raise Exception("La contraseña no cumple los requisitos: mayúsculas, minúsculas, números y carácter especial.")
        elif "history" in err.lower() or "0000052E" in err or "already" in err.lower():
            raise Exception("Esta contraseña ya fue usada recientemente. Elige una diferente.")
        elif "minimum password age" in err.lower():
            raise Exception("Debes esperar al menos 1 día antes de cambiar la contraseña.")
        raise Exception("Error al cambiar la contraseña. Verifica que cumple todos los requisitos.")
# ── USUARIOS — Forzar cambio de contraseña ────────────────────────────────────
def force_password_change(username):
    import subprocess
    subprocess.run(["/usr/bin/ssh","-i","/opt/dandydash-api/.ssh/id_rsa",
        "-o","StrictHostKeyChecking=no","admin-kk@192.168.30.10",
        f"sudo /usr/local/bin/dandydash-force-pwd.sh force {username}"],
        capture_output=True, text=True, timeout=15)
    return True

def unforce_password_change(username):
    import subprocess
    subprocess.run(["/usr/bin/ssh","-i","/opt/dandydash-api/.ssh/id_rsa",
        "-o","StrictHostKeyChecking=no","admin-kk@192.168.30.10",
        f"sudo /usr/local/bin/dandydash-force-pwd.sh unforce {username}"],
        capture_output=True, text=True, timeout=15)
    return True

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
        import subprocess
        ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
               "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
        cmd = "sudo samba-tool gpo listall -H ldap://127.0.0.1 -U administrator%DandyAdmin2026! 2>/dev/null"
        r = subprocess.run(ssh + [cmd], capture_output=True, text=True, timeout=30)
        lines = r.stdout.strip().split("\n")
        gpos, current = [], {}
        for line in lines:
            if line.startswith("GPO"):
                if current and "name" in current: gpos.append(current)
                current = {"guid": line.split(":",1)[-1].strip()}
            elif "display name" in line:
                current["name"] = line.split(":",1)[-1].strip()
            elif line.strip().startswith("path"):
                current["path"] = line.split(":",1)[-1].strip()
            elif line.strip().startswith("dn"):
                current["dn"] = line.split(":",1)[-1].strip()
        if current and "name" in current: gpos.append(current)
        return gpos
    except Exception as e:
        return []

# ── GPOs — Crear via samba-tool ───────────────────────────────────────────────
def create_gpo(name, ou_dn="", directives=[]):
    """Crea una GPO en samba1 via SSH y la vincula a la OU."""
    import subprocess, re
    ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
           "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
    admin = "administrator%DandyAdmin2026!"
    # 1. Crear GPO
    r = subprocess.run(ssh + [f'sudo samba-tool gpo create "{name}" -H ldap://127.0.0.1 -U {admin}'],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        err = r.stderr.strip() or r.stdout.strip()
        if 'already existing' not in err.lower():
            raise Exception(f"Error creando GPO: {err}")
    m = re.search(r"\{[A-F0-9-]{36}\}", r.stdout, re.IGNORECASE)
    guid = m.group(0) if m else None
    # 2. Vincular a OU
    if guid and ou_dn:
        subprocess.run(ssh + [f'sudo samba-tool gpo link "{ou_dn}" {guid} -H ldap://127.0.0.1 -U {admin}'],
                       capture_output=True, text=True, timeout=30)
    return guid

# ── GPOs — Vincular a OU ──────────────────────────────────────────────────────
def link_gpo_to_ou(guid, ou_dn):
    """Vincula una GPO (por GUID) a una OU."""
    import subprocess
    result = subprocess.run(
        ["samba-tool", "gpo", "link", ou_dn, guid,
         "-U", "administrator%DandyAdmin2026!"],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise Exception(f"samba-tool link error: {result.stderr.strip()}")
    return True

# ── EQUIPOS — Listar ──────────────────────────────────────────────────────────
def list_computers(search=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = "(&(objectClass=computer))" if not search \
        else f"(&(objectClass=computer)(cn=*{search}*))"
    conn.search(base, f, attributes=[
        "cn","dNSHostName","operatingSystem","operatingSystemVersion",
        "distinguishedName","whenCreated","userAccountControl","memberOf",
        "lastLogon","description"
    ], search_scope=SUBTREE)
    result = []
    for e in conn.entries:
        uac = int(str(e["userAccountControl"].value)) if "userAccountControl" in e and e["userAccountControl"].value else 4096
        result.append({
            "name":       (str(e["cn"].value)                   if "cn" in e and e["cn"].value else ""),
            "dns":        (str(e["dNSHostName"].value)          if "dNSHostName" in e and e["dNSHostName"].value else ""),
            "os":         (str(e["operatingSystem"].value)      if "operatingSystem" in e and e["operatingSystem"].value else ""),
            "os_version": (str(e["operatingSystemVersion"].value) if "operatingSystemVersion" in e and e["operatingSystemVersion"].value else ""),
            "dn":         (str(e["distinguishedName"].value)    if "distinguishedName" in e and e["distinguishedName"].value else ""),
            "created":    (str(e["whenCreated"].value)          if "whenCreated" in e and e["whenCreated"].value else ""),
            "enabled":    not bool(uac & 2),
            "groups":     ([str(g) for g in e["memberOf"].values] if "memberOf" in e and e["memberOf"].value else []),
            "description":(str(e["description"].value)         if "description" in e and e["description"].value else ""),
        })
    return result

# ── EQUIPOS — Obtener uno ─────────────────────────────────────────────────────
def get_computer(name):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=computer)(cn={name}))",
        attributes=["cn","dNSHostName","operatingSystem","operatingSystemVersion",
                    "distinguishedName","whenCreated","userAccountControl",
                    "memberOf","description","lastLogon"],
        search_scope=SUBTREE)
    if not conn.entries:
        return None
    e = conn.entries[0]
    uac = int(str(e["userAccountControl"].value)) if "userAccountControl" in e and e["userAccountControl"].value else 4096
    return {
        "name":       (str(e["cn"].value)                   if "cn" in e and e["cn"].value else ""),
        "dns":        (str(e["dNSHostName"].value)          if "dNSHostName" in e and e["dNSHostName"].value else ""),
        "os":         (str(e["operatingSystem"].value)      if "operatingSystem" in e and e["operatingSystem"].value else ""),
        "os_version": (str(e["operatingSystemVersion"].value) if "operatingSystemVersion" in e and e["operatingSystemVersion"].value else ""),
        "dn":         (str(e["distinguishedName"].value)    if "distinguishedName" in e and e["distinguishedName"].value else ""),
        "created":    (str(e["whenCreated"].value)          if "whenCreated" in e and e["whenCreated"].value else ""),
        "enabled":    not bool(uac & 2),
        "groups":     ([str(g) for g in e["memberOf"].values] if "memberOf" in e and e["memberOf"].value else []),
        "description":(str(e["description"].value)         if "description" in e and e["description"].value else ""),
    }

def move_object(dn, new_ou_dn, obj_type="user", samaccountname=None):
    """Mueve usuario o grupo a nueva OU via samba-tool SSH."""
    import subprocess
    cn = dn.split(",")[0].split("=",1)[1] if "=" in dn else dn
    # For users use sAMAccountName if provided, else CN
    name = samaccountname if samaccountname and obj_type == "user" else cn
    if obj_type == "group":
        cmd = f"sudo samba-tool group move '{name}' '{new_ou_dn}' -U administrator%DandyAdmin2026!"
    else:
        cmd = f"sudo samba-tool user move '{name}' '{new_ou_dn}' -U administrator%DandyAdmin2026!"
    r = subprocess.run(
        ["/usr/bin/ssh","-i","/opt/dandydash-api/.ssh/id_rsa",
         "-o","StrictHostKeyChecking=no","admin-kk@192.168.30.10", cmd],
        capture_output=True, text=True, timeout=15
    )
    if r.returncode != 0:
        raise Exception(r.stderr or r.stdout or "Error al mover")
    return True

