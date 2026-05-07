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
def health():
    return jsonify({"status": "ok", "service": "DandyDash API"})
