from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

load_dotenv()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # OWASP 8 - Validación de inputs y headers sospechosos
    @app.before_request
    def validate_request():
        from flask import request, jsonify
        import re

        # Bloquear paths con path traversal
        if '..' in request.path or '//' in request.path:
            return jsonify({'error': 'Petición no válida'}), 400

        # Bloquear SQL injection básico en query params
        sqli_pattern = re.compile(r'(union|select|insert|drop|delete|update|exec|script)', re.IGNORECASE)
        for key, value in request.args.items():
            if sqli_pattern.search(str(value)):
                return jsonify({'error': 'Petición no válida'}), 400

        # Validar Content-Type en POST/PUT
        if request.method in ['POST', 'PUT'] and request.content_length:
            ct = request.content_type or ''
            if not ct.startswith('application/json'):
                return jsonify({'error': 'Content-Type debe ser application/json'}), 415

        # Bloquear User-Agents de scanners conocidos
        ua = request.headers.get('User-Agent', '').lower()
        blocked_ua = ['sqlmap', 'nikto', 'nmap', 'masscan', 'zgrab', 'nuclei', 'dirbuster']
        if any(b in ua for b in blocked_ua):
            return jsonify({'error': 'Acceso denegado'}), 403

    # Protección flujos sensibles — rate limiting por usuario autenticado
    @app.before_request
    def rate_limit_sensitive_flows():
        from flask import request, jsonify
        import time
        sensitive = [
            ('/api/users/', 'POST'),
            ('/api/users/', 'DELETE'),
            ('/api/auth/login', 'POST'),
        ]
        path = request.path
        method = request.method
        for s_path, s_method in sensitive:
            if path.startswith(s_path) and method == s_method:
                if not hasattr(app, '_flow_attempts'):
                    app._flow_attempts = {}
                ip = request.remote_addr
                key = f"{ip}:{path}:{method}"
                now = time.time()
                attempts = [t for t in app._flow_attempts.get(key, []) if now - t < 60]
                if len(attempts) >= 20:
                    return jsonify({'error': 'Demasiadas operaciones. Espera un momento.'}), 429
                app._flow_attempts[key] = attempts + [now]
                break

    # Bloquear HTTP Method Override (X-HTTP-Method-Override header)
    @app.before_request
    def block_method_override():
        from flask import request, jsonify
        if request.headers.get('X-HTTP-Method-Override'):
            return jsonify({'error': 'Method override no permitido'}), 405
        if request.headers.get('X-Method-Override'):
            return jsonify({'error': 'Method override no permitido'}), 405
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per minute", "1000 per hour"],
        storage_uri="memory://"
    )
    app.limiter = limiter

    # Soporta tanto DATABASE_URL como variables separadas DB_*
    db_url = os.getenv("DATABASE_URL") or (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["JWT_SECRET_KEY"]          = os.getenv("JWT_SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]  = __import__("datetime").timedelta(minutes=30)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = __import__("datetime").timedelta(hours=8)
    app.config["SECRET_KEY"]              = os.getenv("SECRET_KEY")
    app.config["LDAP_SERVER"]             = os.getenv("LDAP_SERVER",  "192.168.30.10")
    app.config["LDAP_DOMAIN"]             = os.getenv("LDAP_DOMAIN",  "dandydash.local")
    app.config["LDAP_BASE_DN"]            = os.getenv("LDAP_BASE_DN", "DC=dandydash,DC=local")

    db.init_app(app)
    JWTManager(app)

    with app.app_context():
        from .routes.auth      import auth_bp
        from .routes.users     import users_bp
        from .routes.groups    import groups_bp
        from .routes.nfs import nfs_bp
        from .routes.mail import mail_bp
        from .routes.backups import backups_bp
        from .routes.ous       import ous_bp, gpos_bp, audit_bp, health_bp
        from .routes.computers import computers_bp
        from .routes.quotas      import quotas_bp
        from .routes.monitoring  import monitoring_bp
        from .routes.mfa import mfa_bp
        from .routes.shares      import shares_bp

        app.register_blueprint(auth_bp,      url_prefix="/api/auth")
        app.register_blueprint(users_bp,     url_prefix="/api/users")
        app.register_blueprint(groups_bp,    url_prefix="/api/groups")
        app.register_blueprint(ous_bp,       url_prefix="/api/ous")
        app.register_blueprint(gpos_bp,      url_prefix="/api/gpos")
        app.register_blueprint(computers_bp, url_prefix="/api/computers")
        app.register_blueprint(quotas_bp,      url_prefix="/api/quotas")
        app.register_blueprint(monitoring_bp,  url_prefix="/api/monitoring")
        app.register_blueprint(shares_bp,      url_prefix="/api/shares")
        app.register_blueprint(nfs_bp, url_prefix="/api/nfs")
        app.register_blueprint(backups_bp, url_prefix="/api/backups")
        app.register_blueprint(mail_bp, url_prefix="/api/mail")
        app.register_blueprint(audit_bp,     url_prefix="/api/audit")
        app.register_blueprint(mfa_bp,       url_prefix="/api/mfa")
        app.register_blueprint(health_bp,    url_prefix="/api")

        # Bloquear endpoint /static en produccion
        @app.route('/static/<path:filename>')
        def block_static(filename):
            from flask import jsonify
            return jsonify({'error': 'No disponible'}), 404

        db.create_all()

    return app
