from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
import subprocess

quotas_bp = Blueprint("quotas", __name__)

SAMBA_HOST = "192.168.30.10"
SAMBA_USER = "admin-kk"
SSH_KEY    = "/opt/dandydash-api/.ssh/id_rsa"

def run_ssh(cmd):
    try:
        result = subprocess.run(
            ["/usr/bin/ssh", "-i", SSH_KEY,
             "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=5",
             f"{SAMBA_USER}@{SAMBA_HOST}", cmd],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout, result.returncode
    except Exception as e:
        return str(e), 1

def get_quotas():
    out, rc = run_ssh("sudo /usr/local/bin/dandydash-quota-report.sh")
    if rc != 0:
        return None, out
    quotas = []
    for line in out.strip().split("\n"):
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        try:
            username = parts[0]
            if username in ("domain admins", "root", ""):
                continue
            used_kb = int(parts[1])
            soft_kb = int(parts[2])
            hard_kb = int(parts[3])
        except ValueError:
            continue
        if soft_kb == 0 and hard_kb == 0:
            continue
        percent = round(used_kb / soft_kb * 100, 1) if soft_kb > 0 else 0
        status = "exceeded" if percent >= 100 else "critical" if percent >= 90 else "warning" if percent >= 80 else "ok"
        quotas.append({
            "username": username,
            "used_kb": used_kb, "soft_kb": soft_kb, "hard_kb": hard_kb,
            "used_gb": round(used_kb/1024/1024, 2),
            "soft_gb": round(soft_kb/1024/1024, 2),
            "hard_gb": round(hard_kb/1024/1024, 2),
            "percent": percent, "status": status
        })
    return quotas, None

@quotas_bp.route("/", methods=["GET"])
@jwt_required()
def list_quotas():
    quotas, err = get_quotas()
    if err:
        return jsonify({"error": "Error obteniendo cuotas", "detail": err}), 500
    return jsonify({"quotas": quotas, "total": len(quotas)})

@quotas_bp.route("/<username>", methods=["GET"])
@jwt_required()
def get_quota(username):
    quotas, err = get_quotas()
    if err:
        return jsonify({"error": "Error"}), 500
    for q in quotas:
        if q["username"] == username:
            return jsonify(q)
    return jsonify({"error": f"Usuario {username} sin cuota"}), 404

@quotas_bp.route("/<username>", methods=["PUT"])
@jwt_required()
def set_quota(username):
    data = request.get_json() or {}
    soft_gb = data.get("soft_gb", 8)
    hard_gb = data.get("hard_gb", 10)
    soft_kb = int(float(soft_gb) * 1024 * 1024)
    hard_kb = int(float(hard_gb) * 1024 * 1024)
    uid_out, _ = run_ssh(f"id -u {username} 2>/dev/null")
    uid = uid_out.strip()
    if not uid:
        return jsonify({"error": f"Usuario {username} no encontrado"}), 404
    out, rc = run_ssh(f"sudo setquota -u {uid} {soft_kb} {hard_kb} 0 0 /")
    if rc != 0:
        return jsonify({"error": f"Error: {out}"}), 500
    return jsonify({"message": f"Cuota actualizada para {username}", "soft_gb": soft_gb, "hard_gb": hard_gb})

@quotas_bp.route("/apply-all", methods=["POST"])
@jwt_required()
def apply_all():
    out, rc = run_ssh("sudo /usr/local/bin/dandydash-quotas.sh 2>&1")
    if rc != 0:
        return jsonify({"error": "Error", "detail": out}), 500
    return jsonify({"message": "Cuotas aplicadas", "output": out})

@quotas_bp.route('/alert', methods=['POST'])
@jwt_required()
def log_quota_alert():
    data = request.get_json() or {}
    username = data.get('username','')
    percent  = data.get('percent', 0)
    used_gb  = data.get('used_gb', 0)
    hard_gb  = data.get('hard_gb', 0)
    if not username: return jsonify({'error':'username required'}),400
    try:
        from app.models import AuditLog, db
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        action = 'QUOTA_EXCEEDED' if percent>=95 else 'QUOTA_CRITICAL' if percent>=85 else 'QUOTA_WARNING'
        log = AuditLog(username=claims.get('sub','sistema'), action=action,
            target=username, detail=f'{percent}% — {used_gb}GB / {hard_gb}GB')
        db.session.add(log)
        db.session.commit()
        return jsonify({'message':'OK'})
    except Exception as e:
        return jsonify({'error':str(e)}),400
