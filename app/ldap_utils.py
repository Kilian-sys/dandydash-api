from ldap3 import Server, Connection, ALL, NTLM, MODIFY_REPLACE, MODIFY_ADD, MODIFY_DELETE, SUBTREE
from ldap3.core.exceptions import LDAPException
from flask import current_app
import re

def get_connection():
    """Crea y devuelve una conexión autenticada al AD de Samba4."""
    cfg = current_app.config
    srv = Server(cfg["LDAP_SERVER"], get_info=ALL)
    conn = Connection(
        srv,
        user=cfg["LDAP_BIND_USER"],
        password=cfg["LDAP_BIND_PASS"],
        auto_bind=True
    )
    return conn

# ─────────────────────────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────────────────────────

def list_users(search=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = f"(&(objectClass=user)(objectCategory=person)(!(objectClass=computer))(sAMAccountName=*{search}*))"
    conn.search(base, f, attributes=[
        "sAMAccountName","cn","givenName","sn","mail",
        "memberOf","userAccountControl","distinguishedName",
        "whenCreated","lastLogon","description"
    ], search_scope=SUBTREE)
    users = []
    for e in conn.entries:
        uac = int(str(e.userAccountControl)) if e.userAccountControl else 512
        users.append({
            "username":    str(e.sAMAccountName),
            "name":        str(e.cn),
            "first_name":  str(e.givenName) if e.givenName else "",
            "last_name":   str(e.sn) if e.sn else "",
            "email":       str(e.mail) if e.mail else "",
            "groups":      [str(g) for g in e.memberOf] if e.memberOf else [],
            "enabled":     not bool(uac & 2),
            "dn":          str(e.distinguishedName),
            "created":     str(e.whenCreated) if e.whenCreated else "",
            "description": str(e.description) if e.description else "",
        })
    return users

def get_user(username):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = f"(&(objectClass=user)(sAMAccountName={username}))"
    conn.search(base, f, attributes=["*"], search_scope=SUBTREE)
    if not conn.entries:
        return None
    e = conn.entries[0]
    uac = int(str(e.userAccountControl)) if e.userAccountControl else 512
    return {
        "username":    str(e.sAMAccountName),
        "name":        str(e.cn),
        "first_name":  str(e.givenName) if e.givenName else "",
        "last_name":   str(e.sn) if e.sn else "",
        "email":       str(e.mail) if e.mail else "",
        "groups":      [str(g) for g in e.memberOf] if e.memberOf else [],
        "enabled":     not bool(uac & 2),
        "dn":          str(e.distinguishedName),
        "description": str(e.description) if e.description else "",
        "home_dir":    str(e.homeDirectory) if e.homeDirectory else "",
    }

def create_user(username, password, first_name, last_name, email="", ou=None, description=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    ou_dn = ou if ou else f"CN=Users,{base}"
    dn = f"CN={first_name} {last_name},{ou_dn}"
    attrs = {
        "objectClass":      ["top","person","organizationalPerson","user"],
        "sAMAccountName":   username,
        "userPrincipalName":f"{username}@{current_app.config['LDAP_DOMAIN']}",
        "givenName":        first_name,
        "sn":               last_name,
        "cn":               f"{first_name} {last_name}",
        "displayName":      f"{first_name} {last_name}",
        "userAccountControl": "514",   # deshabilitado inicialmente
    }
    if email:       attrs["mail"] = email
    if description: attrs["description"] = description
    conn.add(dn, attributes=attrs)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    # Establecer contraseña y habilitar cuenta
    encoded_pw = '"{}"'.format(password).encode("utf-16-le")
    conn.modify(dn, {"unicodePwd": [(MODIFY_REPLACE, [encoded_pw])]})
    conn.modify(dn, {"userAccountControl": [(MODIFY_REPLACE, ["512"])]})
    return True

def delete_user(username):
    conn = get_connection()
    user = get_user(username)
    if not user:
        raise LDAPException("User not found")
    conn.delete(user["dn"])
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

def modify_user(username, changes):
    conn = get_connection()
    user = get_user(username)
    if not user:
        raise LDAPException("User not found")
    dn = user["dn"]
    mods = {}
    field_map = {
        "email":       "mail",
        "first_name":  "givenName",
        "last_name":   "sn",
        "description": "description",
    }
    for k, v in changes.items():
        if k in field_map:
            mods[field_map[k]] = [(MODIFY_REPLACE, [v])]
    if mods:
        conn.modify(dn, mods)
    return True

def set_password(username, new_password):
    conn = get_connection()
    user = get_user(username)
    if not user:
        raise LDAPException("User not found")
    encoded_pw = '"{}"'.format(new_password).encode("utf-16-le")
    conn.modify(user["dn"], {"unicodePwd": [(MODIFY_REPLACE, [encoded_pw])]})
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

def enable_user(username, enable=True):
    conn = get_connection()
    user = get_user(username)
    if not user:
        raise LDAPException("User not found")
    uac = "512" if enable else "514"
    conn.modify(user["dn"], {"userAccountControl": [(MODIFY_REPLACE, [uac])]})
    return True

# ─────────────────────────────────────────────────────────────────
# GRUPOS
# ─────────────────────────────────────────────────────────────────

def list_groups(search=""):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = f"(&(objectClass=group)(cn=*{search}*))"
    conn.search(base, f, attributes=["cn","description","member","distinguishedName"], search_scope=SUBTREE)
    groups = []
    for e in conn.entries:
        groups.append({
            "name":        str(e.cn),
            "description": str(e.description) if e.description else "",
            "members":     [str(m) for m in e.member] if e.member else [],
            "dn":          str(e.distinguishedName),
        })
    return groups

def get_group(name):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    f = f"(&(objectClass=group)(cn={name}))"
    conn.search(base, f, attributes=["cn","description","member","distinguishedName"], search_scope=SUBTREE)
    if not conn.entries:
        return None
    e = conn.entries[0]
    return {
        "name":        str(e.cn),
        "description": str(e.description) if e.description else "",
        "members":     [str(m) for m in e.member] if e.member else [],
        "dn":          str(e.distinguishedName),
    }

def create_group(name, description="", ou=None):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    ou_dn = ou if ou else f"CN=Users,{base}"
    dn = f"CN={name},{ou_dn}"
    attrs = {
        "objectClass":  ["top","group"],
        "cn":           name,
        "sAMAccountName": name,
        "groupType":    "-2147483646",   # Global Security Group
    }
    if description: attrs["description"] = description
    conn.add(dn, attributes=attrs)
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

def delete_group(name):
    conn = get_connection()
    group = get_group(name)
    if not group:
        raise LDAPException("Group not found")
    conn.delete(group["dn"])
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

def add_member_to_group(group_name, username):
    conn = get_connection()
    group = get_group(group_name)
    user  = get_user(username)
    if not group: raise LDAPException("Group not found")
    if not user:  raise LDAPException("User not found")
    conn.modify(group["dn"], {"member": [(MODIFY_ADD, [user["dn"]])]})
    if conn.result["result"] not in (0, 68):  # 68 = already exists
        raise LDAPException(conn.result["description"])
    return True

def remove_member_from_group(group_name, username):
    conn = get_connection()
    group = get_group(group_name)
    user  = get_user(username)
    if not group: raise LDAPException("Group not found")
    if not user:  raise LDAPException("User not found")
    conn.modify(group["dn"], {"member": [(MODIFY_DELETE, [user["dn"]])]})
    return True

# ─────────────────────────────────────────────────────────────────
# UNIDADES ORGANIZATIVAS (OU)
# ─────────────────────────────────────────────────────────────────

def list_ous():
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, "(objectClass=organizationalUnit)",
                attributes=["ou","description","distinguishedName"], search_scope=SUBTREE)
    return [{
        "name":        str(e.ou),
        "description": str(e.description) if e.description else "",
        "dn":          str(e.distinguishedName),
    } for e in conn.entries]

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

def delete_ou(name):
    conn = get_connection()
    base = current_app.config["LDAP_BASE_DN"]
    conn.search(base, f"(&(objectClass=organizationalUnit)(ou={name}))",
                attributes=["distinguishedName"], search_scope=SUBTREE)
    if not conn.entries:
        raise LDAPException("OU not found")
    conn.delete(str(conn.entries[0].distinguishedName))
    if conn.result["result"] != 0:
        raise LDAPException(conn.result["description"])
    return True

# ─────────────────────────────────────────────────────────────────
# GPOs (básico — Samba4 gestiona GPOs via samba-tool)
# ─────────────────────────────────────────────────────────────────

import subprocess

def list_gpos():
    try:
        result = subprocess.run(
            ["samba-tool","gpo","listall","--url","ldap://192.168.30.10"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        gpos = []
        current = {}
        for line in lines:
            if line.startswith("GPO"):
                if current: gpos.append(current)
                current = {"name": line.split(":")[-1].strip()}
            elif ":" in line:
                k, v = line.split(":", 1)
                current[k.strip().lower().replace(" ","_")] = v.strip()
        if current: gpos.append(current)
        return gpos
    except Exception as e:
        return []
