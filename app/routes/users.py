import smtplib
from email.mime.text import MIMEText
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


def send_notification(subject, body):
    """Envía notificación por email al administrador."""
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[DandyDash] {subject}"
        msg["From"] = "dandydash@dandydash.local"
        msg["To"] = "administrator@dandydash.local"
        from email.utils import formatdate
        msg["Date"] = formatdate(localtime=True)
        with smtplib.SMTP("192.168.20.12", 25) as s:
            s.sendmail(msg["From"], [msg["To"]], msg.as_string())
    except Exception as e:
        print(f"Email error: {e}")

def audit(action, target, details=''):
    claims = get_jwt()
    admin = claims.get('sub','?')
    log = AuditLog(username=admin, action=action, target=target, detail=details)
    db.session.add(log); db.session.commit()
    import logging as _logging, datetime
    _logger = _logging.getLogger('dandydash.audit')
    if not _logger.handlers:
        _h = _logging.FileHandler('/var/log/dandydash/audit.log')
        _h.setFormatter(_logging.Formatter('%(message)s'))
        _logger.addHandler(_h)
        _logger.setLevel(_logging.INFO)
    _logger.info(f"{datetime.datetime.now().isoformat()} | {action} | target={target} | admin={admin} | {details}")

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
    password = data.get('password','') or data.get('new_password','')
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
        send_notification(f'Usuario creado: {username}', f'El administrador ha creado el usuario {username}.')
        # Sync quota folder
        import subprocess
        subprocess.Popen(['/usr/bin/ssh','-i','/opt/dandydash-api/.ssh/id_rsa','-o','StrictHostKeyChecking=no','admin-kk@192.168.30.10','sudo /usr/local/bin/dandydash-quota-sync.sh'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return jsonify({'message': f'Usuario {username} creado correctamente'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

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
        send_notification(f'Usuario modificado: {username}', f'El administrador ha modificado el usuario {username}.')
        return jsonify({'message': f'Usuario {username} actualizado'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

# ── Eliminar usuario ─────────────────────────────────────
@users_bp.route('/<username>', methods=['DELETE'])
@jwt_required()
def delete_user(username):
    err = require_admin()
    if err: return err
    try:
        lu.delete_user(username)
        audit('DELETE_USER', username)
        send_notification(f'Usuario eliminado: {username}', f'El administrador ha eliminado el usuario {username}.')
        return jsonify({'message': f'Usuario {username} eliminado'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

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
        send_notification(f'Usuario {state}: {username}', f'El usuario {username} ha sido {state} por el administrador.')
        return jsonify({'message': f'Usuario {username} {state}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

# ── Cambiar contraseña ───────────────────────────────────
@users_bp.route('/<username>/password', methods=['POST'])
@jwt_required()
def change_password(username):
    err = require_admin()
    if err: return err
    data = request.get_json()
    password = data.get('password','') or data.get('new_password','')
    if not password:
        return jsonify({'error': 'La contraseña no puede estar vacía'}), 400
    try:
        lu.set_password(username, password)
        audit('CHANGE_PASSWORD', username)
        send_notification(f'Contraseña cambiada: {username}', f'Se ha cambiado la contraseña del usuario {username}.')
        return jsonify({'message': f'Contraseña de {username} actualizada'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

# ── Forzar cambio de contraseña en próximo login ─────────
@users_bp.route('/<username>/force-password-change', methods=['POST'])
@jwt_required()
def force_password_change(username):
    err = require_admin()
    if err: return err
    try:
        lu.force_password_change(username)
        audit('FORCE_PWD_CHANGE', username)
        send_notification(f'Forzar cambio contraseña: {username}', f'Se ha forzado cambio de contraseña para {username} en el próximo inicio de sesión.')
        return jsonify({'message': f'{username} deberá cambiar contraseña al próximo inicio de sesión'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

@users_bp.route('/<username>/unforce-password-change', methods=['POST'])
@jwt_required()
def unforce_password_change(username):
    err = require_admin()
    if err: return err
    try:
        lu.unforce_password_change(username)
        audit('UNFORCE_PWD_CHANGE', username)
        return jsonify({'message': f'Cambio de contraseña desactivado para {username}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

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
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

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
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

@users_bp.route('/<username>/move', methods=['POST'])
@jwt_required()
def move_user(username):
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    ou_dn = data.get('ou_dn','')
    if not ou_dn:
        return jsonify({'error': 'ou_dn es obligatorio'}), 400
    try:
        user = lu.get_user(username)
        if not user:
            return jsonify({'error': f'Usuario {username} no encontrado'}), 404
        lu.move_object(user["dn"], ou_dn, "user", samaccountname=username)
        audit('MOVE_USER', username, ou_dn)
        return jsonify({'message': f'{username} movido a {ou_dn}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400


@jwt_required()
def move_user(username):
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    ou_dn = data.get('ou_dn','')
    if not ou_dn:
        return jsonify({'error': 'ou_dn es obligatorio'}), 400
    try:
        user = lu.get_user(username)
        if not user:
            return jsonify({'error': f'Usuario {username} no encontrado'}), 404
        lu.move_object(user["dn"], ou_dn, "user", samaccountname=username)
        audit('MOVE_USER', username, ou_dn)
        return jsonify({'message': f'{username} movido a {ou_dn}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); msg = str(e)
        if 'entryAlreadyExists' in msg or 'already in use' in msg:
            return jsonify({'error': 'El usuario ya existe en el directorio'}), 400
        if 'invalidDNSyntax' in msg:
            return jsonify({'error': 'Nombre de usuario no válido'}), 400
        if 'invalidCredentials' in msg:
            return jsonify({'error': 'Error de autenticación con el directorio'}), 500
        return jsonify({'error': msg}), 400

