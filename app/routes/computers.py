from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from .. import db
from ..models import AuditLog
from ..ldap_utils import list_computers, get_computer

computers_bp = Blueprint("computers", __name__)

def _log(action, target="", detail="", success=True):
    username = get_jwt_identity()
    role = get_jwt().get("role", "viewer")
    entry = AuditLog(username=username, role=role, action=action,
                     target=target, detail=detail,
                     ip_address=request.remote_addr, success=success)
    db.session.add(entry)
    db.session.commit()

@computers_bp.route("/", methods=["GET"])
@jwt_required()
def get_computers():
    search = request.args.get("search", "")
    return jsonify({"computers": list_computers(search)})

@computers_bp.route("/<name>", methods=["GET"])
@jwt_required()
def get_computer_detail(name):
    c = get_computer(name)
    if not c:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify(c)
