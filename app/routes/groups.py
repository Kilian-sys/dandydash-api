from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app import ldap_utils as lu
from app.models import AuditLog, db

groups_bp = Blueprint('groups', __name__)

def require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Se requiere rol admin'}), 403
    return None

def audit(action, target, details=''):
    claims = get_jwt()
    log = AuditLog(username=claims.get('sub','?'), action=action, target=target, detail=details)
    db.session.add(log); db.session.commit()

# ── Listar grupos ─────────────────────────────────────────
@groups_bp.route('/', methods=['GET'])
@jwt_required()
def list_groups():
    search = request.args.get('search', '')
    return jsonify({'groups': lu.list_groups(search)})

# ── Crear grupo ───────────────────────────────────────────
@groups_bp.route('/', methods=['POST'])
@jwt_required()
def create_group():
    err = require_admin()
    if err: return err
    data = request.get_json()
    name = data.get('name','').strip()
    if not name:
        return jsonify({'error': 'El nombre del grupo es obligatorio'}), 400
    try:
        lu.create_group(name, description=data.get('description',''))
        audit('CREATE_GROUP', name)
        return jsonify({'message': f'Grupo {name} creado'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

# ── Ver grupo ─────────────────────────────────────────────
@groups_bp.route('/<name>', methods=['GET'])
@jwt_required()
def get_group(name):
    group = lu.get_group(name)
    if not group:
        return jsonify({'error': 'Grupo no encontrado'}), 404
    return jsonify(group)

# ── Eliminar grupo ────────────────────────────────────────
@groups_bp.route('/<name>', methods=['DELETE'])
@jwt_required()
def delete_group(name):
    err = require_admin()
    if err: return err
    try:
        lu.delete_group(name)
        audit('DELETE_GROUP', name)
        return jsonify({'message': f'Grupo {name} eliminado'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

# ── Añadir miembro al grupo ───────────────────────────────
@groups_bp.route('/<name>/members', methods=['POST'])
@jwt_required()
def add_member(name):
    err = require_admin()
    if err: return err
    data = request.get_json()
    username = data.get('username','').strip()
    if not username:
        return jsonify({'error': 'username es obligatorio'}), 400
    try:
        lu.add_member_to_group(name, username)
        audit('ADD_GROUP_MEMBER', name, username)
        return jsonify({'message': f'{username} añadido al grupo {name}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

# ── Quitar miembro del grupo ──────────────────────────────
@groups_bp.route('/<name>/members/<username>', methods=['DELETE'])
@jwt_required()
def remove_member(name, username):
    err = require_admin()
    if err: return err
    try:
        lu.remove_member_from_group(name, username)
        audit('REMOVE_GROUP_MEMBER', name, username)
        return jsonify({'message': f'{username} eliminado del grupo {name}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

@groups_bp.route('/<name>/move', methods=['POST'])
@jwt_required()
def move_group(name):
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    ou_dn = data.get('ou_dn','')
    if not ou_dn:
        return jsonify({'error': 'ou_dn es obligatorio'}), 400
    try:
        from app import ldap_utils as lu
        group = lu.get_group(name)
        if not group:
            return jsonify({'error': f'Grupo {name} no encontrado'}), 404
        lu.move_object(group['dn'], ou_dn, 'group')
        return jsonify({'message': f'Grupo {name} movido a {ou_dn}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400
