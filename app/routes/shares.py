from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
import subprocess, re

shares_bp = Blueprint("shares", __name__)

SAMBA_HOST = "192.168.30.10"
SAMBA_USER = "admin-kk"
SSH_KEY    = "/opt/dandydash-api/.ssh/id_rsa"
SMB_CONF   = "/etc/samba/smb.conf"
SHARES_DIR = "/srv/samba"
SYSTEM_SHARES = {"sysvol", "netlogon", "homes-dandydash", "IPC$", "ADMIN$"}

def run_ssh(cmd, timeout=20):
    try:
        r = subprocess.run(
            ["/usr/bin/ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=5", f"{SAMBA_USER}@{SAMBA_HOST}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), 1

def clean_principal(p):
    """Normaliza nombre de usuario/grupo quitando prefijos DANDYDASH"""
    return re.sub(r'@?"?DANDYDASH[\\\/]+"?', '', p).strip('"').strip()

def parse_smb_shares():
    out, rc = run_ssh(f"sudo cat {SMB_CONF}")
    if rc != 0:
        return []
    shares = []
    seen = set()
    current = None
    for line in out.split("\n"):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            if current and current["name"] not in SYSTEM_SHARES and current["name"] != "global":
                if current["name"] not in seen:
                    seen.add(current["name"])
                    shares.append(current)
            current = {"name": m.group(1), "path": "", "readonly": False,
                       "browseable": True, "guest_ok": False, "comment": "",
                       "valid_users": [], "read_list": [], "write_list": [], "admin_users": []}
        elif current:
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip().lower()
            val = val.strip()
            if key == "path":               current["path"] = val
            elif key == "read only":        current["readonly"] = val.lower() == "yes"
            elif key == "browseable":       current["browseable"] = val.lower() == "yes"
            elif key == "guest ok":         current["guest_ok"] = val.lower() == "yes"
            elif key == "comment":          current["comment"] = val
            elif key == "valid users":      current["valid_users"] = [v.strip() for v in val.split(",") if v.strip()]
            elif key == "read list":        current["read_list"] = [v.strip() for v in val.split(",") if v.strip()]
            elif key == "write list":       current["write_list"] = [v.strip() for v in val.split(",") if v.strip()]
            elif key == "admin users":      current["admin_users"] = [v.strip() for v in val.split(",") if v.strip()]
    if current and current["name"] not in SYSTEM_SHARES and current["name"] != "global" and current["name"] not in seen:
        shares.append(current)

    # Build permissions per principal
    for s in shares:
        perms = []
        all_p = set()
        for lst in [s["valid_users"], s["read_list"], s["write_list"], s["admin_users"]]:
            for p in lst:
                all_p.add(clean_principal(p))
        for p in sorted(all_p):
            if not p:
                continue
            # Find raw version
            raw_admin  = [clean_principal(x) for x in s["admin_users"]]
            raw_write  = [clean_principal(x) for x in s["write_list"]]
            raw_read   = [clean_principal(x) for x in s["read_list"]]
            if p in raw_admin:   level = "full"
            elif p in raw_write: level = "rw"
            elif p in raw_read:  level = "ro"
            else:                level = "rw"
            # Detect if group
            is_group = any(clean_principal(x) == p for x in s["valid_users"] + s["read_list"] + s["write_list"] + s["admin_users"] if "@" in x or "Share-" in x or "Domain" in x)
            perms.append({"principal": p, "level": level, "is_group": is_group})
        s["permissions"] = perms
    return shares

def build_share_block(name, comment, path, readonly, browseable, guest_ok, perms):
    """Construye el bloque smb.conf para un share con permisos granulares"""
    valid_users = []
    read_list   = []
    write_list  = []
    admin_users = []

    for p in perms:
        principal = p["principal"]
        level     = p.get("level", "rw")
        is_group  = p.get("is_group", False)
        prefix    = "@DANDYDASH\\" if is_group else ""
        raw       = f"{prefix}{principal}"
        valid_users.append(raw)
        if level == "full":
            admin_users.append(raw)
            write_list.append(raw)
        elif level == "rw":
            write_list.append(raw)
        elif level == "ro":
            read_list.append(raw)

    lines = [f"\n[{name}]"]
    if comment: lines.append(f"    comment = {comment}")
    lines.append(f"    path = {path}")
    lines.append(f"    read only = {'yes' if readonly else 'no'}")
    lines.append(f"    browseable = {'yes' if browseable else 'no'}")
    lines.append(f"    guest ok = {'yes' if guest_ok else 'no'}")
    lines.append( "    create mask = 0660")
    lines.append( "    directory mask = 0770")
    if valid_users: lines.append(f"    valid users = {', '.join(valid_users)}")
    if write_list:  lines.append(f"    write list = {', '.join(write_list)}")
    if read_list:   lines.append(f"    read list = {', '.join(read_list)}")
    if admin_users: lines.append(f"    admin users = {', '.join(admin_users)}")
    return "\n".join(lines) + "\n"

def remove_share_from_conf(name):
    """Elimina el bloque de un share del smb.conf via python3 en samba1"""
    script = f"sudo python3 -c \"\nimport re\nwith open('/etc/samba/smb.conf','r') as f:\n    c=f.read()\nnew=re.sub(r'\\n\\[{re.escape(name)}\\][^\\[]*','',c)\nwith open('/etc/samba/smb.conf','w') as f:\n    f.write(new)\nprint('OK')\n\""
    return run_ssh(script)


@shares_bp.route("/", methods=["GET"])
@jwt_required()
def list_shares():
    shares = parse_smb_shares()
    if shares:
        paths = " ".join(s["path"] for s in shares if s["path"])
        if paths:
            out, _ = run_ssh(f"sudo du -sk {paths} 2>/dev/null")
            usage_map = {}
            for line in out.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) == 2:
                    try:
                        kb = int(parts[0])
                        usage_map[parts[1].strip()] = f"{round(kb/1024,1)}MB" if kb < 1024*1024 else f"{round(kb/1024/1024,1)}GB"
                    except: pass
            for s in shares:
                s["usage"] = usage_map.get(s["path"], "0MB")
    return jsonify({"shares": shares, "total": len(shares)})


@shares_bp.route("/<name>", methods=["GET"])
@jwt_required()
def get_share(name):
    for s in parse_smb_shares():
        if s["name"] == name:
            return jsonify(s)
    return jsonify({"error": f"Share {name} no encontrado"}), 404


@shares_bp.route("/", methods=["POST"])
@jwt_required()
def create_share():
    data = request.get_json() or {}
    name        = data.get("name","").strip()
    description = data.get("description","").strip()
    readonly    = data.get("readonly", False)
    browseable  = data.get("browseable", True)
    guest_ok    = data.get("guest_ok", False)
    perms       = data.get("permissions", [])  # [{principal, level, is_group}]

    if not name or not re.match(r'^[a-zA-Z0-9_\-]+$', name):
        return jsonify({"error": "Nombre inválido"}), 400

    path = f"{SHARES_DIR}/{name}"
    out, rc = run_ssh(f"sudo mkdir -p {path} && sudo chmod 777 {path} && sudo chmod 755 {SHARES_DIR}")
    if rc != 0:
        return jsonify({"error": f"Error creando directorio: {out}"}), 500

    block = build_share_block(name, description, path, readonly, browseable, guest_ok, perms)
    # Write block to temp file and append
    escaped = block.replace("'", "'\"'\"'")
    out, rc = run_ssh(f"printf '{escaped}' | sudo tee -a {SMB_CONF} > /dev/null")
    if rc != 0:
        return jsonify({"error": f"Error escribiendo smb.conf"}), 500

    run_ssh("sudo systemctl reload samba-ad-dc 2>/dev/null || sudo smbcontrol all reload-config 2>/dev/null")
    return jsonify({"message": f"Share '{name}' creado correctamente", "path": path})


@shares_bp.route("/<name>", methods=["DELETE"])
@jwt_required()
def delete_share(name):
    if name in SYSTEM_SHARES:
        return jsonify({"error": "No se puede eliminar share del sistema"}), 400
    remove_share_from_conf(name)
    run_ssh("sudo systemctl reload samba-ad-dc 2>/dev/null || sudo smbcontrol all reload-config 2>/dev/null")
    return jsonify({"message": f"Share '{name}' eliminado"})


@shares_bp.route("/<name>/permissions", methods=["PUT"])
@jwt_required()
def update_permissions(name):
    data     = request.get_json() or {}
    readonly = data.get("readonly", False)
    guest_ok = data.get("guest_ok", False)
    perms    = data.get("permissions", [])

    shares = parse_smb_shares()
    share  = next((s for s in shares if s["name"] == name), None)
    if not share:
        return jsonify({"error": f"Share {name} no encontrado"}), 404

    block = build_share_block(name, share.get("comment",""), share["path"],
                              readonly, share.get("browseable", True), guest_ok, perms)

    # Remove old block and append new
    remove_share_from_conf(name)
    escaped = block.replace("'", "'\"'\"'")
    run_ssh(f"printf '{escaped}' | sudo tee -a {SMB_CONF} > /dev/null")
    run_ssh("sudo systemctl reload samba-ad-dc 2>/dev/null || sudo smbcontrol all reload-config 2>/dev/null")
    return jsonify({"message": f"Permisos de '{name}' actualizados"})


@shares_bp.route("/groups", methods=["GET"])
@jwt_required()
def list_groups():
    out, _ = run_ssh("sudo samba-tool group list 2>/dev/null")
    groups = [g.strip() for g in out.split("\n") if g.strip()]
    return jsonify({"groups": groups})


@shares_bp.route("/users", methods=["GET"])
@jwt_required()
def list_users():
    out, _ = run_ssh("sudo samba-tool user list 2>/dev/null")
    users = [u.strip() for u in out.split("\n") if u.strip() and not u.strip().startswith("dns-")]
    return jsonify({"users": users})
