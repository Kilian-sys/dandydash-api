from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app import ldap_utils as lu
from app.models import AuditLog, db

users_bp = Blueprint('users', __name__)

def require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Se requiere rol admin'}), 403
    return None

def audit(action, target, details=''):
    claims = get_jwt()
    log = AuditLog(username=claims.get('sub','?'), action=action, target=target, detail=details)
    db.session.add(log); db.session.commit()

# ── Listar usuarios ──────────────────────────────────────
@users_bp.route('/', methods=['GET'])
@jwt_required()
def list_users():
    search = request.args.get('search', '')
    return jsonify({'users': lu.list_users(search)})

# ── Crear usuario ────────────────────────────────────────
@users_bp.route('/', methods=['POST'])
@jwt_required()
def create_user():
    err = require_admin()
    if err: return err
    data = request.get_json()
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password:
        return jsonify({'error': 'username y password son obligatorios'}), 400
    try:
        lu.create_user(
            username=username, password=password,
            first_name=data.get('first_name',''),
            last_name=data.get('last_name',''),
            email=data.get('email',''),
            description=data.get('description','')
        )
        audit('CREATE_USER', username)
        return jsonify({'message': f'Usuario {username} creado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Ver usuario ──────────────────────────────────────────
@users_bp.route('/<username>', methods=['GET'])
@jwt_required()
def get_user(username):
    user = lu.get_user(username)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    return jsonify(user)

# ── Editar usuario ───────────────────────────────────────
@users_bp.route('/<username>', methods=['PUT'])
@jwt_required()
def update_user(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    try:
        lu.modify_user(username, data)
        audit('UPDATE_USER', username)
        return jsonify({'message': f'Usuario {username} actualizado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Eliminar usuario ─────────────────────────────────────
@users_bp.route('/<username>', methods=['DELETE'])
@jwt_required()
def delete_user(username):
    err = require_admin()
    if err: return err
    try:
        lu.delete_user(username)
        audit('DELETE_USER', username)
        return jsonify({'message': f'Usuario {username} eliminado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Habilitar / Deshabilitar ─────────────────────────────
@users_bp.route('/<username>/toggle', methods=['PATCH'])
@jwt_required()
def toggle_user(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    enabled = data.get('enabled', True)
    try:
        lu.set_user_enabled(username, enabled)
        action = 'ENABLE_USER' if enabled else 'DISABLE_USER'
        audit(action, username)
        state = 'habilitado' if enabled else 'deshabilitado'
        return jsonify({'message': f'Usuario {username} {state}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Cambiar contraseña ───────────────────────────────────
@users_bp.route('/<username>/password', methods=['POST'])
@jwt_required()
def change_password(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    password = data.get('password','')
    if not password:
        return jsonify({'error': 'La contraseña no puede estar vacía'}), 400
    try:
        lu.set_password(username, password)
        audit('CHANGE_PASSWORD', username)
        return jsonify({'message': f'Contraseña de {username} actualizada'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Forzar cambio de contraseña en próximo login ─────────
@users_bp.route('/<username>/force-password-change', methods=['POST'])
@jwt_required()
def force_password_change(username):
    err = require_admin()
    if err: return err
    try:
        lu.force_password_change(username)
        audit('FORCE_PWD_CHANGE', username)
        return jsonify({'message': f'{username} deberá cambiar contraseña al próximo inicio de sesión'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Horas de inicio de sesión ────────────────────────────
@users_bp.route('/<username>/logon-hours', methods=['POST'])
@jwt_required()
def set_logon_hours(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    hours = data.get('hours', [])
    try:
        lu.set_logon_hours(username, hours)
        audit('SET_LOGON_HOURS', username, f'{len(hours)} franjas configuradas')
        return jsonify({'message': f'Horas de acceso configuradas para {username}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ── Equipos permitidos ───────────────────────────────────
@users_bp.route('/<username>/workstations', methods=['POST'])
@jwt_required()
def set_workstations(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    workstations = data.get('workstations', [])
    try:
        lu.set_workstations(username, workstations)
        audit('SET_WORKSTATIONS', username, ','.join(workstations) if workstations else 'todos')
        msg = f'Equipos configurados: {", ".join(workstations)}' if workstations else 'Acceso permitido desde todos los equipos'
        return jsonify({'message': msg})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
