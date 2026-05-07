from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ldap3.core.exceptions import LDAPException
from .. import db
from ..models import AuditLog
from ..ldap_utils import list_groups, get_group, create_group, delete_group, add_member_to_group, remove_member_from_group

groups_bp = Blueprint("groups", __name__)

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

@groups_bp.route("/", methods=["GET"])
@jwt_required()
def get_groups():
    search = request.args.get("search","")
    try:
        return jsonify({"groups": list_groups(search)})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@groups_bp.route("/", methods=["POST"])
@jwt_required()
def add_group():
    err = require_admin()
    if err: return err
    data = request.get_json()
    if not data.get("name"):
        return jsonify({"error": "Campo requerido: name"}), 400
    try:
        create_group(data["name"], data.get("description",""), data.get("ou"))
        _log("CREATE_GROUP", target=data["name"])
        return jsonify({"message": f"Grupo {data['name']} creado"}), 201
    except LDAPException as e:
        _log("CREATE_GROUP", target=data["name"], detail=str(e), success=False)
        return jsonify({"error": str(e)}), 500

@groups_bp.route("/<name>", methods=["DELETE"])
@jwt_required()
def remove_group(name):
    err = require_admin()
    if err: return err
    try:
        delete_group(name)
        _log("DELETE_GROUP", target=name)
        return jsonify({"message": f"Grupo {name} eliminado"})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@groups_bp.route("/<name>/members", methods=["POST"])
@jwt_required()
def add_member(name):
    err = require_admin()
    if err: return err
    data = request.get_json()
    username = data.get("username","")
    try:
        add_member_to_group(name, username)
        _log("ADD_MEMBER", target=name, detail=f"user={username}")
        return jsonify({"message": f"{username} añadido a {name}"})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@groups_bp.route("/<name>/members/<username>", methods=["DELETE"])
@jwt_required()
def remove_member(name, username):
    err = require_admin()
    if err: return err
    try:
        remove_member_from_group(name, username)
        _log("REMOVE_MEMBER", target=name, detail=f"user={username}")
        return jsonify({"message": f"{username} eliminado de {name}"})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500
