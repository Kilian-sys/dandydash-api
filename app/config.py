import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-key")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hora
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # LDAP / Samba4
    LDAP_SERVER   = os.getenv("LDAP_SERVER", "192.168.30.10")
    LDAP_SERVER2  = os.getenv("LDAP_SERVER2", "192.168.30.11")
    LDAP_DOMAIN   = os.getenv("LDAP_DOMAIN", "dandydash.local")
    LDAP_BASE_DN  = os.getenv("LDAP_BASE_DN", "DC=dandydash,DC=local")
    LDAP_BIND_USER= os.getenv("LDAP_BIND_USER")
    LDAP_BIND_PASS= os.getenv("LDAP_BIND_PASS")

    # MFA
    MFA_ISSUER = os.getenv("MFA_ISSUER", "DandyDash")
