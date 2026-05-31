from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import subprocess, os, glob
from datetime import datetime

backups_bp = Blueprint('backups', __name__)
BACKUP_DIR = '/opt/dandydash-backups'
SAMBA_HOST = 'admin-kk@192.168.30.10'
SSH_KEY    = '/opt/dandydash-api/.ssh/id_rsa'

def require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Acceso denegado'}), 403

def run_ssh(cmd):
    r = subprocess.run(['/usr/bin/ssh','-i',SSH_KEY,'-o','StrictHostKeyChecking=no',SAMBA_HOST,cmd],
        capture_output=True, text=True, timeout=300)
    return r.stdout, r.returncode

@backups_bp.route('/', methods=['GET'])
@jwt_required()
def list_backups():
    err = require_admin()
    if err: return err
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        files = sorted(glob.glob(f'{BACKUP_DIR}/*.tar.gz') + glob.glob(f'{BACKUP_DIR}/*.ldb'), reverse=True)
        backups = []
        for f in files:
            stat = os.stat(f)
            backups.append({
                'name':     os.path.basename(f),
                'size':     round(stat.st_size / 1024 / 1024, 2),
                'created':  datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'type':     'AD' if 'samba' in f.lower() or 'ad_' in f.lower() else 'Config',
            })
        return jsonify({'backups': backups})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

@backups_bp.route('/create', methods=['POST'])
@jwt_required()
def create_backup():
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    btype = data.get('type', 'full')
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        if btype == 'ad':
            # Backup AD: exportar LDB + sysvol via SSH
            local_file = f'{BACKUP_DIR}/ad_backup_{ts}.tar.gz'
            out, rc = run_ssh(
                f'sudo /bin/tar --use-compress-program=/usr/bin/gzip -cf /tmp/ad_backup_{ts}.tar.gz '
                f'/var/lib/samba/private/*.ldb /var/lib/samba/sysvol 2>&1 && echo OK'
            )
            if 'OK' in out:
                r = subprocess.run(['/usr/bin/scp','-i',SSH_KEY,'-o','StrictHostKeyChecking=no',
                    f'admin-kk@192.168.30.10:/tmp/ad_backup_{ts}.tar.gz', local_file],
                    capture_output=True, timeout=300)
                run_ssh(f'sudo rm -f /tmp/ad_backup_{ts}.tar.gz')
                if r.returncode == 0:
                    size = round(os.path.getsize(local_file)/1024/1024, 2)
                    return jsonify({'message': f'Backup AD creado: ad_backup_{ts}.tar.gz ({size}MB)'})
            return jsonify({'error': f'Error creando backup AD: {out[:300]}'}), 400

        elif btype == 'config':
            # Backup configuración API y scripts
            local_file = f'{BACKUP_DIR}/config_backup_{ts}.tar.gz'
            r = subprocess.run(['/bin/tar','--use-compress-program=/bin/gzip','-cf', local_file,
                '/opt/dandydash-api/app/routes/',
                '/opt/dandydash-api/app/ldap_utils.py',
                '/var/www/dandydash/'],
                capture_output=True, timeout=120)
            if r.returncode == 0:
                size = round(os.path.getsize(local_file)/1024/1024, 2)
                return jsonify({'message': f'Backup config creado: config_backup_{ts}.tar.gz ({size}MB)'})
            return jsonify({'error': r.stderr.decode()}), 400

        elif btype == 'smb':
            # Backup shares Samba
            out, rc = run_ssh(f'sudo tar -czf /tmp/shares_backup_{ts}.tar.gz /srv/samba/ 2>&1 && echo OK')
            if 'OK' in out:
                local_file = f'{BACKUP_DIR}/shares_backup_{ts}.tar.gz'
                subprocess.run(['/usr/bin/scp','-i',SSH_KEY,'-o','StrictHostKeyChecking=no',
                    f'admin-kk@192.168.30.10:/tmp/shares_backup_{ts}.tar.gz', local_file],
                    capture_output=True, timeout=300)
                run_ssh(f'sudo rm -f /tmp/shares_backup_{ts}.tar.gz')
                size = round(os.path.getsize(local_file)/1024/1024, 2)
                return jsonify({'message': f'Backup shares creado: shares_backup_{ts}.tar.gz ({size}MB)'})
            return jsonify({'error': f'Error: {out}'}), 400

        return jsonify({'error': 'Tipo no válido'}), 400
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

@backups_bp.route('/delete/<name>', methods=['DELETE'])
@jwt_required()
def delete_backup(name):
    err = require_admin()
    if err: return err
    try:
        path = f'{BACKUP_DIR}/{name}'
        if not os.path.exists(path):
            return jsonify({'error': 'Backup no encontrado'}), 404
        os.remove(path)
        return jsonify({'message': f'{name} eliminado'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

SCHEDULES = {}

@backups_bp.route('/schedules', methods=['GET'])
@jwt_required()
def get_schedules():
    err = require_admin()
    if err: return err
    result = {}
    for btype in ['ad','config','smb']:
        cron_file = f'/etc/cron.d/dandydash-backup-{btype}'
        try:
            if os.path.exists(cron_file):
                c = open(cron_file).read().strip()
                real_lines = [x for x in c.split(chr(10)) if x.strip() and not x.strip().startswith('#')]
                if not real_lines:
                    result[btype] = {'enabled': False}
                else:
                    parts = real_lines[0].split()
                    hour = parts[1] if len(parts) > 1 else '2'
                    fw = 'daily' if 'daily' in c else 'weekly' if 'weekly' in c else 'monthly'
                    if fw == 'daily': desc = f'Cada dia a las {str(hour).zfill(2)}:00'
                    elif fw == 'weekly': desc = f'Cada semana a las {str(hour).zfill(2)}:00'
                    else: desc = f'Cada mes a las {str(hour).zfill(2)}:00'
                    result[btype] = {'enabled': True, 'desc': desc}
            else:
                result[btype] = {'enabled': False}
        except:
            result[btype] = {'enabled': False}
    return jsonify({'schedules': result})

@backups_bp.route('/schedule', methods=['POST'])
@jwt_required()
def set_schedule():
    err = require_admin()
    if err: return err
    data   = request.get_json() or {}
    btype  = data.get('type','')
    freq   = data.get('freq','')
    cron_file = f'/etc/cron.d/dandydash-backup-{btype}'
    try:
        if not freq:
            if os.path.exists(cron_file):
                os.remove(cron_file)
            return jsonify({'message': f'Programación de {btype} desactivada'})
        hour = str(data.get('hour', 2))
        day  = str(data.get('day', 1))
        if freq == 'daily':   cron_time = f'{hour} * * *'.replace(' ','  ',1); cron_time = f'0 {hour} * * *'
        elif freq == 'weekly': cron_time = f'0 {hour} * * {day}'
        elif freq == 'monthly': cron_time = f'0 {hour} {day} * *'
        else: cron_time = f'0 {hour} * * *'
        api_url = 'https://localhost/api'
        script = f'''#!/bin/bash
# dandydash-backup-{btype} - {freq}
TOKEN=$(curl -sk -X POST {api_url}/auth/login -H "Content-Type: application/json" -d '{{"username":"admin","password":"Admin_DandyDash2026!"}}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -sk -X POST {api_url}/backups/create -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{{"type":"{btype}"}}'
# Keep only last 7 backups of this type
ls -t /opt/dandydash-backups/{btype}_*.* 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null
'''
        script_path = f'/opt/dandydash-backups/backup-{btype}.sh'
        with open(script_path, 'w') as f:
            f.write(script)
        os.chmod(script_path, 0o755)
        cron_content = f'# dandydash-backup-{btype} - {freq}\n{cron_time} root {script_path} >> /var/log/dandydash-backup-{btype}.log 2>&1\n'
        import subprocess as _sp
        result = _sp.run(['/usr/bin/sudo','/usr/bin/tee', cron_file], input=cron_content, capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({'error': 'No se pudo escribir el cron: ' + result.stderr}), 400
        _sp.run(['/usr/bin/sudo','/bin/chmod','644', cron_file])
        desc_map = {'daily':'Cada día a las 2:00 AM','weekly':'Cada semana (lunes)','monthly':'Cada mes (día 1)'}
        return jsonify({'message': f'Backup de {btype} programado: {desc_map.get(freq,freq)}'})
    except Exception as e:
        import logging; logging.getLogger('dandydash').error(str(e)); return jsonify({'error': 'Error interno del servidor'}), 400

@backups_bp.route('/restore', methods=['POST'])
@jwt_required()
def restore_backup():
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    name = data.get('name','')
    if not name: return jsonify({'error':'name requerido'}),400
    path = f'{BACKUP_DIR}/{name}'
    if not os.path.exists(path): return jsonify({'error':'Backup no encontrado'}),404
    try:
        btype = 'ad' if name.startswith('ad_') else 'config' if name.startswith('config_') else 'smb'
        if btype == 'config':
            r = subprocess.run(['/bin/tar','--use-compress-program=/usr/bin/gzip','-xf',path,'-C','/'],
                capture_output=True, timeout=120)
            if r.returncode != 0: return jsonify({'error': r.stderr.decode()}),400
            return jsonify({'message': f'Configuración restaurada desde {name}'})
        elif btype == 'smb':
            r = subprocess.run(['/usr/bin/scp','-i',SSH_KEY,'-o','StrictHostKeyChecking=no',path,f'admin-kk@192.168.30.10:/tmp/{name}'],
                capture_output=True, timeout=300)
            out, rc = run_ssh(f'sudo /bin/tar --use-compress-program=/usr/bin/gzip -xf /tmp/{name} -C / && sudo rm -f /tmp/{name}')
            return jsonify({'message': f'Carpetas Samba restauradas desde {name}'})
        elif btype == 'ad':
            return jsonify({'error': 'Restauración AD requiere parada del servicio. Hazlo manualmente en samba1.'}),400
    except Exception as e:
        return jsonify({'error': str(e)}),400
