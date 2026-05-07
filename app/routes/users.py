from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ldap3.core.exceptions import LDAPException
from .. import db
from ..models import AuditLog
from ..ldap_utils import list_users, get_user, create_user, delete_user, modify_user, set_password, enable_user

users_bp = Blueprint("users", __name__)

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

@users_bp.route("/", methods=["GET"])
@jwt_required()
def get_users():
    search = request.args.get("search", "")
    try:
        users = list_users(search)
        return jsonify({"users": users, "total": len(users)})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@users_bp.route("/<username>", methods=["GET"])
@jwt_required()
def get_one_user(username):
    try:
        user = get_user(username)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        return jsonify(user)
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@users_bp.route("/", methods=["POST"])
@jwt_required()
def add_user():
    err = require_admin()
    if err: return err
    data = request.get_json()
    required = ["username","password","first_name","last_name"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"Campo requerido: {f}"}), 400
    try:
        create_user(
            username=data["username"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data.get("email",""),
            ou=data.get("ou"),
            description=data.get("description","")
        )
        _log("CREATE_USER", target=data["username"], detail=f"email={data.get('email','')}")
        return jsonify({"message": f"Usuario {data['username']} creado correctamente"}), 201
    except LDAPException as e:
        _log("CREATE_USER", target=data["username"], detail=str(e), success=False)
        return jsonify({"error": str(e)}), 500

@users_bp.route("/<username>", methods=["PUT"])
@jwt_required()
def update_user(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    try:
        modify_user(username, data)
        _log("MODIFY_USER", target=username, detail=str(data))
        return jsonify({"message": f"Usuario {username} actualizado"})
    except LDAPException as e:
        _log("MODIFY_USER", target=username, detail=str(e), success=False)
        return jsonify({"error": str(e)}), 500

@users_bp.route("/<username>", methods=["DELETE"])
@jwt_required()
def remove_user(username):
    err = require_admin()
    if err: return err
    try:
        delete_user(username)
        _log("DELETE_USER", target=username)
        return jsonify({"message": f"Usuario {username} eliminado"})
    except LDAPException as e:
        _log("DELETE_USER", target=username, detail=str(e), success=False)
        return jsonify({"error": str(e)}), 500

@users_bp.route("/<username>/password", methods=["POST"])
@jwt_required()
def change_user_password(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    new_pw = data.get("password","")
    if len(new_pw) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400
    try:
        set_password(username, new_pw)
        _log("SET_PASSWORD", target=username)
        return jsonify({"message": "Contraseña actualizada"})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500

@users_bp.route("/<username>/enable", methods=["POST"])
@jwt_required()
def toggle_user(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    enable = data.get("enable", True)
    try:
        enable_user(username, enable)
        action = "ENABLE_USER" if enable else "DISABLE_USER"
        _log(action, target=username)
        state = "habilitado" if enable else "deshabilitado"
        return jsonify({"message": f"Usuario {username} {state}"})
    except LDAPException as e:
        return jsonify({"error": str(e)}), 500
