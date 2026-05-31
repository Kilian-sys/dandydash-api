from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import imaplib, email, smtplib
from email.header import decode_header
from email.mime.text import MIMEText

mail_bp = Blueprint('mail', __name__)
IMAP_HOST = '192.168.20.12'
IMAP_PORT = 993
SMTP_HOST = '192.168.20.12'
SMTP_PORT = 25
MAIL_USER = 'administrator'
MAIL_PASS = 'DandyAdmin2026!'
MAIL_FROM = 'administrator@dandydash.local'

def require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Acceso denegado'}), 403

def dec(s):
    if not s: return ''
    parts = decode_header(s)
    out = []
    for p, enc in parts:
        if isinstance(p, bytes):
            out.append(p.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(str(p))
    return ' '.join(out)

@mail_bp.route('/inbox', methods=['GET'])
@jwt_required()
def get_inbox():
    err = require_admin()
    if err: return err
    limit = int(request.args.get('limit', 30))
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
        m.login(MAIL_USER, MAIL_PASS)
        status, data2 = m.select('INBOX')
        if status != 'OK':
            return jsonify({'error': f'No se pudo abrir INBOX: {data2}'}), 400
        _, data = m.search(None, 'ALL')
        ids = data[0].split()[-limit:][::-1]
        msgs = []
        for uid in ids:
            _, md = m.fetch(uid, '(RFC822)')
            msg = email.message_from_bytes(md[0][1])
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='replace') if msg.get_payload() else ''
            msgs.append({'id': uid.decode(), 'from': dec(msg.get('From','')),
                'to': dec(msg.get('To','')), 'subject': dec(msg.get('Subject','(sin asunto)')),
                'date': msg.get('Date',''), 'body': body[:3000]})
        m.logout()
        return jsonify({'messages': msgs})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@mail_bp.route('/send', methods=['POST'])
@jwt_required()
def send_mail():
    err = require_admin()
    if err: return err
    data = request.get_json() or {}
    to = data.get('to',''); subject = data.get('subject',''); body = data.get('body','')
    if not to or not body: return jsonify({'error': 'to y body requeridos'}), 400
    try:
        from email.utils import formatdate
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject; msg['From'] = MAIL_FROM; msg['To'] = to
        msg['Date'] = formatdate(localtime=True)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.sendmail(MAIL_FROM, [to], msg.as_string())
        return jsonify({'message': 'Email enviado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
