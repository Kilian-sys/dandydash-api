from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timedelta
import bcrypt, pyotp
from .. import db
from ..models import AppUser, AuditLog

auth_bp = Blueprint("auth", __name__)

def _log(username, action, target="", detail="", success=True):
    entry = AuditLog(
        username=username, action=action, target=target,
        detail=detail, ip_address=request.remote_addr, success=success
    )
    db.session.add(entry)
    db.session.commit()

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username","").strip()
    password = data.get("password","")
    totp_code = data.get("totp_code","")

    user = AppUser.query.filter_by(username=username).first()
    if not user or not user.active:
        _log(username, "LOGIN_FAILED", detail="User not found or inactive", success=False)
        return jsonify({"error": "Credenciales incorrectas"}), 401

    # Comprobar bloqueo
    if user.locked_until and datetime.utcnow() < user.locked_until:
        mins = int((user.locked_until - datetime.utcnow()).seconds / 60)
        return jsonify({"error": f"Cuenta bloqueada. Espera {mins} minutos."}), 423

    # Verificar contraseña
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()
        _log(username, "LOGIN_FAILED", detail="Wrong password", success=False)
        return jsonify({"error": "Credenciales incorrectas"}), 401

    # Verificar MFA si está habilitado
    if user.mfa_enabled:
        if not totp_code:
            return jsonify({"error": "Se requiere código MFA", "mfa_required": True}), 202
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(totp_code):
            _log(username, "LOGIN_FAILED", detail="Invalid MFA code", success=False)
            return jsonify({"error": "Código MFA incorrecto"}), 401

    # Login OK
    user.failed_logins = 0
    user.locked_until  = None
    db.session.commit()

    token = create_access_token(
        identity=username,
        additional_claims={"role": user.role}
    )
    _log(username, "LOGIN_SUCCESS")
    return jsonify({
        "access_token": token,
        "username": username,
        "role": user.role,
        "mfa_enabled": user.mfa_enabled
    })

@auth_bp.route("/mfa/setup", methods=["POST"])
@jwt_required()
def mfa_setup():
    username = get_jwt_identity()
    user = AppUser.query.filter_by(username=username).first()
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.session.commit()
    issuer = current_app.config.get("MFA_ISSUER", "DandyDash")
    uri = pyotp.TOTP(secret).provisioning_uri(username, issuer_name=issuer)
    return jsonify({"secret": secret, "uri": uri})

@auth_bp.route("/mfa/verify", methods=["POST"])
@jwt_required()
def mfa_verify():
    username = get_jwt_identity()
    data = request.get_json()
    code = data.get("code","")
    user = AppUser.query.filter_by(username=username).first()
    totp = pyotp.TOTP(user.mfa_secret)
    if totp.verify(code):
        user.mfa_enabled = True
        db.session.commit()
        return jsonify({"message": "MFA activado correctamente"})
    return jsonify({"error": "Código incorrecto"}), 400

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    username = get_jwt_identity()
    claims   = get_jwt()
    user = AppUser.query.filter_by(username=username).first()
    return jsonify({
        "username":    username,
        "role":        claims.get("role"),
        "mfa_enabled": user.mfa_enabled if user else False,
    })

@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    username = get_jwt_identity()
    data = request.get_json()
    old_pw = data.get("old_password","")
    new_pw = data.get("new_password","")
    user = AppUser.query.filter_by(username=username).first()
    if not bcrypt.checkpw(old_pw.encode(), user.password_hash.encode()):
        return jsonify({"error": "Contraseña actual incorrecta"}), 400
    if len(new_pw) < 12:
        return jsonify({"error": "La contraseña debe tener al menos 12 caracteres"}), 400
    user.password_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    db.session.commit()
    _log(username, "CHANGE_PASSWORD")
    return jsonify({"message": "Contraseña actualizada"})
