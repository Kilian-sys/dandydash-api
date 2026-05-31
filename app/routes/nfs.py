from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import subprocess, os

nfs_bp = Blueprint('nfs', __name__)
NFS_HOST = '192.168.30.20'
SSH_KEY  = '/opt/dandydash-api/.ssh/id_rsa'
NFS_USER = 'admin-kk'

def require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Acceso denegado'}), 403

def run_ssh(cmd):
    r = subprocess.run(['/usr/bin/ssh','-i',SSH_KEY,'-o','StrictHostKeyChecking=no',
        f'{NFS_USER}@{NFS_HOST}', cmd], capture_output=True, text=True, timeout=30)
    return r.stdout.strip(), r.returncode

@nfs_bp.route('/exports', methods=['GET'])
@jwt_required()
def get_exports():
    err = require_admin()
    if err: return err
    try:
        out, _ = run_ssh('sudo exportfs -v')
        exports = []
        current = None
        for line in out.split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith('/'):
                parts = line.split()
                if len(parts) >= 2:
                    current = {'path': parts[0], 'client': parts[1].split('(')[0], 'options': parts[1]}
                    exports.append(current)
                else:
                    current = {'path': parts[0], 'client': '', 'options': ''}
                    exports.append(current)
            elif current and current['client'] == '':
                current['client'] = line.split('(')[0]
                current['options'] = line
        # Get disk usage
        out2, _ = run_ssh('df -h /exports 2>/dev/null | tail -1')
        disk = {}
        if out2:
            parts = out2.split()
            if len(parts) >= 5:
                disk = {'size': parts[1], 'used': parts[2], 'avail': parts[3], 'percent': parts[4]}
        # Get mount count
        out3, _ = run_ssh('sudo ss -tn | grep :2049')
        mounts = []
        for l in out3.split('\n'):
            l = l.strip()
            if l and ':2049' in l:
                parts = l.split()
                if len(parts) >= 5:
                    ip = parts[4].rsplit(':',1)[0]
                    mounts.append(ip + ' montado en /exports')
        return jsonify({'exports': exports, 'disk': disk, 'active_mounts': len(mounts), 'mounts': mounts})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@nfs_bp.route('/exports', methods=['POST'])
@jwt_required()
def add_export():
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    path    = data.get('path','')
    client  = data.get('client','')
    options = data.get('options','rw,sync,no_subtree_check,root_squash')
    if not path or not client:
        return jsonify({'error': 'path y client requeridos'}), 400
    try:
        run_ssh(f'sudo mkdir -p {path} && sudo chmod 777 {path}')
        run_ssh(f'echo "{path}  {client}({options})" | sudo tee -a /etc/exports')
        run_ssh('sudo exportfs -ra')
        return jsonify({'message': f'Exportación {path} añadida para {client}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@nfs_bp.route('/exports', methods=['DELETE'])
@jwt_required()
def remove_export():
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    path   = data.get('path','')
    client = data.get('client','')
    if not path:
        return jsonify({'error': 'path requerido'}), 400
    try:
        run_ssh(f'sudo sed -i "\\|^{path}.*{client}|d" /etc/exports && sudo exportfs -ra')
        return jsonify({'message': f'Exportación {path} eliminada'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@nfs_bp.route('/status', methods=['GET'])
@jwt_required()
def get_status():
    err = require_admin()
    if err: return err
    try:
        _, rc = run_ssh('sudo systemctl is-active nfs-kernel-server')
        status = 'active' if rc == 0 else 'inactive'
        out, _ = run_ssh('sudo showmount -e 2>/dev/null')
        return jsonify({'status': status, 'showmount': out})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
