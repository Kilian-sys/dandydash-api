from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from .config import Config

db = SQLAlchemy()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)
    CORS(app)

    from .routes.auth    import auth_bp
    from .routes.users   import users_bp
    from .routes.groups  import groups_bp
    from .routes.ous     import ous_bp
    from .routes.gpos    import gpos_bp
    from .routes.audit   import audit_bp
    from .routes.health  import health_bp

    app.register_blueprint(auth_bp,   url_prefix="/api/auth")
    app.register_blueprint(users_bp,  url_prefix="/api/users")
    app.register_blueprint(groups_bp, url_prefix="/api/groups")
    app.register_blueprint(ous_bp,    url_prefix="/api/ous")
    app.register_blueprint(gpos_bp,   url_prefix="/api/gpos")
    app.register_blueprint(audit_bp,  url_prefix="/api/audit")
    app.register_blueprint(health_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()
        _seed_admin()

    return app

def _seed_admin():
    """Crea el usuario admin por defecto si no existe."""
    import bcrypt, os
    from .models import AppUser
    if AppUser.query.filter_by(username="admin").first():
        return
    pw = os.getenv("ADMIN_PASSWORD", "Admin_DandyDash2026!")
    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    admin = AppUser(username="admin", password_hash=hashed, role="admin")
    db.session.add(admin)
    db.session.commit()
