import pyotp
import qrcode
import io
import base64
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import AppUser

mfa_bp = Blueprint('mfa', __name__)

@mfa_bp.route('/setup', methods=['POST'])
@jwt_required()
def setup_mfa():
    username = get_jwt_identity()
    user = AppUser.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=f"{username}@dandydash.local",
        issuer_name="DandyDash"
    )
    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    user.mfa_secret = secret
    user.mfa_enabled = False
    db.session.commit()
    return jsonify({'qr': qr_b64, 'secret': secret})

@mfa_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_mfa():
    username = get_jwt_identity()
    code = request.get_json().get('code','')
    user = AppUser.query.filter_by(username=username).first()
    if not user or not user.mfa_secret:
        return jsonify({'error': 'MFA no configurado'}), 400
    totp = pyotp.TOTP(user.mfa_secret)
    if totp.verify(code):
        user.mfa_enabled = True
        db.session.commit()
        return jsonify({'message': 'MFA activado correctamente'})
    return jsonify({'error': 'Código incorrecto'}), 400

@mfa_bp.route('/status', methods=['GET'])
@jwt_required()
def mfa_status():
    username = get_jwt_identity()
    user = AppUser.query.filter_by(username=username).first()
    return jsonify({'enabled': bool(user and user.mfa_enabled)})

@mfa_bp.route('/disable', methods=['DELETE'])
@jwt_required()
def disable_mfa():
    username = get_jwt_identity()
    user = AppUser.query.filter_by(username=username).first()
    if user:
        user.mfa_enabled = False
        user.mfa_secret = None
        db.session.commit()
    return jsonify({'message': 'MFA desactivado'})
