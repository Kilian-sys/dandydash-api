from datetime import datetime
from . import db

class AppUser(db.Model):
    """Usuarios locales de DandyDash (no son usuarios AD, son las cuentas de acceso a la app)"""
    __tablename__ = "app_users"
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(64), unique=True, nullable=False)
    password_hash= db.Column(db.String(128), nullable=False)
    role         = db.Column(db.String(16), default="viewer")   # admin | viewer
    mfa_secret   = db.Column(db.String(32), nullable=True)
    mfa_enabled  = db.Column(db.Boolean, default=False)
    active       = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    failed_logins= db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

class AuditLog(db.Model):
    """Log de todas las acciones realizadas en la aplicación"""
    __tablename__ = "audit_logs"
    id         = db.Column(db.Integer, primary_key=True)
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    username   = db.Column(db.String(64), nullable=False)
    role       = db.Column(db.String(16))
    action     = db.Column(db.String(64), nullable=False)  # CREATE_USER, DELETE_GROUP...
    target     = db.Column(db.String(256))                 # objeto afectado
    detail     = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    success    = db.Column(db.Boolean, default=True)
