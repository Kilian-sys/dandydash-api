# ── OUs ──────────────────────────────────────────────────────────
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ldap3.core.exceptions import LDAPException
from .. import db
from ..models import AuditLog
from ..ldap_utils import list_ous, create_ou, delete_ou, list_gpos

ous_bp   = Blueprint("ous",   __name__)
gpos_bp  = Blueprint("gpos",  __name__)
audit_bp = Blueprint("audit", __name__)
health_bp= Blueprint("health",__name__)

def _log(action, target="", detail="", success=True):
    username = get_jwt_identity()
    role = get_jwt().get("role","viewer")
    entry = AuditLog(username=username, role=role, action=action,
                     target=target, detail=detail,
                     ip_address=request.remote_addr, success=success)
    db.session.add(entry)
    db.session.commit()

def require_admin():
    if get_jwt().get("role") != "admin":
        return jsonify({"error": "Se requiere rol admin"}), 403
    return None

@ous_bp.route("/", methods=["GET"])
@jwt_required()
def get_ous():
    try:
        return jsonify({"ous": list_ous()})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@ous_bp.route("/", methods=["POST"])
@jwt_required()
def add_ou():
    err = require_admin()
    if err: return err
    data = request.get_json()
    if not data.get("name"):
        return jsonify({"error": "Campo requerido: name"}), 400
    try:
        create_ou(data["name"], data.get("description",""), data.get("parent_dn"))
        _log("CREATE_OU", target=data["name"])
        return jsonify({"message": f"OU {data['name']} creada"}), 201
    except LDAPException as e:
        _log("CREATE_OU", target=data["name"], detail=str(e), success=False)
        return jsonify({"error": str(e)}), 500

@ous_bp.route("/<name>", methods=["DELETE"])
@jwt_required()
def remove_ou(name):
    err = require_admin()
    if err: return err
    try:
        delete_ou(name)
        _log("DELETE_OU", target=name)
        return jsonify({"message": f"OU {name} eliminada"})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

# ── GPOs ────────────────────────────────────────────────────────

@gpos_bp.route("/", methods=["GET"])
@jwt_required()
def get_gpos():
    return jsonify({"gpos": list_gpos()})

# ── Audit ────────────────────────────────────────────────────────

@audit_bp.route("/", methods=["GET"])
@jwt_required()
def get_audit():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    action   = request.args.get("action","")
    username = request.args.get("username","")
    q = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if action:   q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if username: q = q.filter(AuditLog.username.ilike(f"%{username}%"))
    pag = q.paginate(page=page, per_page=per_page)
    return jsonify({
        "logs":  [{"id":l.id,"timestamp":str(l.timestamp),"username":l.username,
                   "role":l.role,"action":l.action,"target":l.target,
                   "detail":l.detail,"ip":l.ip_address,"success":l.success} for l in pag.items],
        "total": pag.total,
        "pages": pag.pages,
        "page":  page,
    })

# ── Health ────────────────────────────────────────────────────────

@health_bp.route("/health", methods=["GET"])
@jwt_required()
def health():
    return jsonify({"status": "ok", "service": "DandyDash API"})

@gpos_bp.route("/", methods=["POST"])
@jwt_required()
def create_gpo():
    from ..ldap_utils import create_gpo as lu_create_gpo
    data = request.get_json() or {}
    name = data.get("name","").strip()
    ou_dn = data.get("ou_dn","")
    if not name:
        return jsonify({"error": "El nombre es obligatorio"}), 400
    if not ou_dn:
        return jsonify({"error": "La OU es obligatoria"}), 400
    try:
        result = lu_create_gpo(name, ou_dn, data.get("directives",[]))
        return jsonify({"message": f"GPO '{name}' creada y vinculada a {ou_dn}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@gpos_bp.route("/<guid>/ous", methods=["GET"])
@jwt_required()
def get_gpo_ous(guid):
    """Devuelve las OUs vinculadas a una GPO"""
    try:
        import subprocess
        ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
               "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
        cmd = f"sudo samba-tool gpo listcontainers {guid} -H ldap://127.0.0.1 -U administrator%DandyAdmin2026! 2>/dev/null"
        r = subprocess.run(ssh + [cmd], capture_output=True, text=True, timeout=30)
        ous = []
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("DN:"):
                dn = line.replace("DN:","").strip()
                name = dn.split(",")[0].replace("OU=","").replace("DC=","").strip()
                ous.append({"dn": dn, "name": name})
        return jsonify({"ous": ous})
    except Exception as e:
        return jsonify({"ous": [], "error": str(e)})

@gpos_bp.route("/<guid>/link", methods=["POST"])
@jwt_required()
def link_gpo(guid):
    data = request.get_json() or {}
    ou_dn = data.get("ou_dn","")
    if not ou_dn:
        return jsonify({"error": "ou_dn es obligatorio"}), 400
    try:
        import subprocess
        ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
               "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
        cmd = f'sudo samba-tool gpo setlink "{ou_dn}" {guid} -H ldap://127.0.0.1 -U administrator%DandyAdmin2026! 2>/dev/null'
        r = subprocess.run(ssh + [cmd], capture_output=True, text=True, timeout=30)
        return jsonify({"message": f"GPO vinculada a {ou_dn}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@gpos_bp.route("/<guid>/link", methods=["DELETE"])
@jwt_required()
def unlink_gpo(guid):
    data = request.get_json() or {}
    ou_dn = data.get("ou_dn","")
    if not ou_dn:
        return jsonify({"error": "ou_dn es obligatorio"}), 400
    try:
        import subprocess
        ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
               "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
        cmd = f'sudo samba-tool gpo dellink "{ou_dn}" {guid} -H ldap://127.0.0.1 -U administrator%DandyAdmin2026! 2>/dev/null'
        r = subprocess.run(ssh + [cmd], capture_output=True, text=True, timeout=30)
        return jsonify({"message": f"GPO desvinculada de {ou_dn}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@gpos_bp.route("/<guid>", methods=["DELETE"])
@jwt_required()
def delete_gpo(guid):
    try:
        import subprocess
        ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
               "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
        cmd = f"sudo samba-tool gpo del {guid} -H ldap://127.0.0.1 -U administrator%DandyAdmin2026! 2>/dev/null"
        r = subprocess.run(ssh + [cmd], capture_output=True, text=True, timeout=30)
        if r.returncode != 0 and 'not found' not in r.stderr.lower():
            return jsonify({"error": r.stderr.strip() or r.stdout.strip()}), 400
        return jsonify({"message": f"GPO {guid} eliminada"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@gpos_bp.route("/<guid>/directives", methods=["POST"])
@jwt_required()
def apply_gpo_directives(guid):
    data = request.get_json() or {}
    name = data.get("name","")
    directive_ids = data.get("directives", [])
    if not directive_ids:
        return jsonify({"error": "Sin directivas seleccionadas"}), 400

    DIRECTIVE_CMDS = {
        "block_cmd":       f'samba-tool gpo manage symlink add "{guid}" /bin/sh /bin/rbash -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "block_panel":     f'samba-tool gpo manage smb_conf set "{guid}" "apply gpo policies" yes -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "block_regedit":   f'samba-tool gpo manage smb_conf set "{guid}" "apply group policy" yes -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "screensaver":     f'samba-tool gpo manage smb_conf set "{guid}" "map to guest" never -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "screensaver_pwd": f'samba-tool gpo manage smb_conf set "{guid}" "client ntlmv2 auth" yes -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "prohibir_reunir": f'samba-tool gpo manage smb_conf set "{guid}" "restrict anonymous" 2 -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
    }

    import subprocess
    ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
           "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
    # Obtener directivas activas actuales
    import re, json as _json
    r_show = subprocess.run(ssh + [f'samba-tool gpo show "{guid}" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null'], capture_output=True, text=True, timeout=30)
    m = re.search(r'Policies\s*:\s*(\[.*?\])', r_show.stdout, re.DOTALL)
    current_valuenames = []
    if m:
        try:
            current_valuenames = [p.get("valuename","") for p in _json.loads(m.group(1))]
        except: pass

    REMOVE_CMDS = {
        "block_panel":     f'samba-tool gpo manage smb_conf set "{guid}" "apply gpo policies" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "block_regedit":   f'samba-tool gpo manage smb_conf set "{guid}" "apply group policy" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "screensaver":     f'samba-tool gpo manage smb_conf set "{guid}" "map to guest" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "screensaver_pwd": f'samba-tool gpo manage smb_conf set "{guid}" "client ntlmv2 auth" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
        "prohibir_reunir": f'samba-tool gpo manage smb_conf set "{guid}" "restrict anonymous" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null',
    }

    all_ids = [d["id"] for d in [
        {"id":"block_panel"},{"id":"block_regedit"},{"id":"screensaver"},
        {"id":"screensaver_pwd"},{"id":"prohibir_reunir"},{"id":"block_cmd"}
    ]]
    applied, errors = [], []
    for d_id in all_ids:
        should_be_active = d_id in directive_ids
        remove_cmd = REMOVE_CMDS.get(d_id)
        apply_cmd = DIRECTIVE_CMDS.get(d_id)
        if should_be_active and apply_cmd:
            r = subprocess.run(ssh + [apply_cmd], capture_output=True, text=True, timeout=30)
            if r.returncode == 0: applied.append(f"+{d_id}")
            else: errors.append(f"{d_id}: {(r.stderr.strip() or r.stdout.strip())[:60]}")
        elif not should_be_active and remove_cmd:
            # Remove by setting without value
            subprocess.run(ssh + [remove_cmd], capture_output=True, text=True, timeout=30)

    if errors:
        return jsonify({"error": f"Errores: {'; '.join(errors)}"}), 400
    return jsonify({"message": f"Directivas actualizadas: {len(applied)} activas"})

@gpos_bp.route("/<guid>/directives", methods=["GET"])
@jwt_required()
def get_gpo_directives(guid):
    try:
        import subprocess, json, re
        ssh = ["/usr/bin/ssh", "-i", "/opt/dandydash-api/.ssh/id_rsa",
               "-o", "StrictHostKeyChecking=no", "admin-kk@192.168.30.10"]
        cmd = f'samba-tool gpo show "{guid}" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null'
        r = subprocess.run(ssh + [cmd], capture_output=True, text=True, timeout=30)
        # Extract JSON policies block
        m = re.search(r'Policies\s*:\s*(\[.*?\])', r.stdout, re.DOTALL)
        if not m:
            return jsonify({"directives": []})
        policies = json.loads(m.group(1))
        valuenames = [p.get("valuename","") for p in policies]
        # Map valuenames to directive IDs
        mapping = {
            "apply gpo policies": "block_panel",
            "apply group policy": "block_regedit",
            "map to guest": "screensaver",
            "client ntlmv2 auth": "screensaver_pwd",
            "restrict anonymous": "prohibir_reunir",
        }
        active = [mapping[v] for v in valuenames if v in mapping]
        # Check symlinks for block_cmd
        cmd2 = f'samba-tool gpo manage symlink list "{guid}" -U administrator%DandyAdmin2026! -H ldap://127.0.0.1 2>/dev/null'
        r2 = subprocess.run(ssh + [cmd2], capture_output=True, text=True, timeout=30)
        if r2.stdout.strip():
            active.append("block_cmd")
        return jsonify({"directives": list(set(active))})
    except Exception as e:
        return jsonify({"directives": [], "error": str(e)})
