'use strict';

const API = '';
let TOKEN = localStorage.getItem('dd_token');
let currentUser = null;

/* ══════════════════════════════════════════════
   AUTH
══════════════════════════════════════════════ */
async function doLogin() {
  const usr  = document.getElementById('usr').value.trim();
  const pwd  = document.getElementById('pwd').value;
  const totp = document.getElementById('totp').value.trim();
  const err  = document.getElementById('errmsg');
  err.textContent = '';
  if (!usr || !pwd) { err.textContent = 'Introduce usuario y contraseña.'; return; }
  const body = { username: usr, password: pwd };
  if (totp) body.totp_code = totp;
  try {
    const r = await fetch(API + '/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if (d.mfa_required) {
      document.getElementById('mfabox').style.display = 'block';
      document.getElementById('totp').focus();
      err.textContent = 'Introduce el código MFA.'; return;
    }
    if (d.access_token) {
      TOKEN = d.access_token; localStorage.setItem('dd_token', TOKEN);
      currentUser = { username: usr, role: d.role || 'viewer' };
      showApp(); loadSection('dashboard');
    } else { err.textContent = d.error || d.msg || 'Credenciales incorrectas.'; }
  } catch (e) { err.textContent = 'No se puede conectar con la API.'; }
}

function doLogout() { localStorage.removeItem('dd_token'); TOKEN = null; location.reload(); }

/* ══════════════════════════════════════════════
   API HELPERS
══════════════════════════════════════════════ */
async function apiReq(method, path, body) {
  const opts = { method, headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (r.status === 401) { doLogout(); return null; }
  return r.json();
}
const apiGet    = p     => apiReq('GET',    p);
const apiPost   = (p,b) => apiReq('POST',   p, b);
const apiDelete = p     => apiReq('DELETE', p);
const apiPut    = (p,b) => apiReq('PUT',    p, b);
const apiPatch  = (p,b) => apiReq('PATCH',  p, b);

/* ══════════════════════════════════════════════
   LAYOUT
══════════════════════════════════════════════ */
function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  if (currentUser) document.getElementById('topbar-username').textContent = currentUser.username;
}
function setActiveNav(s) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.section === s));
}
async function loadSection(s) {
  setActiveNav(s);
  document.getElementById('content').innerHTML = '<div class="empty"><div class="spinner"></div></div>';
  const map = { dashboard: renderDashboard, users: renderUsers, groups: renderGroups, ous: renderOUs, gpos: renderGPOs };
  if (map[s]) await map[s]();
}

/* ══════════════════════════════════════════════
   DASHBOARD
══════════════════════════════════════════════ */
async function renderDashboard() {
  const [ud, gd, od] = await Promise.all([apiGet('/api/users/'), apiGet('/api/groups/'), apiGet('/api/ous/')]);
  const u = ud?.users||[], g = gd?.groups||[], o = od?.ous||[];
  const active = u.filter(x => x.enabled).length;
  document.getElementById('content').innerHTML = `
    <h2 style="margin-bottom:20px;color:var(--purple-light)">Dashboard — dandydash.local</h2>
    <div class="stats">
      <div class="stat-card"><div class="stat-n">${u.length}</div><div class="stat-l">Usuarios totales</div></div>
      <div class="stat-card"><div class="stat-n" style="color:var(--green)">${active}</div><div class="stat-l">Activos</div></div>
      <div class="stat-card"><div class="stat-n" style="color:var(--red)">${u.length-active}</div><div class="stat-l">Deshabilitados</div></div>
      <div class="stat-card"><div class="stat-n">${g.length}</div><div class="stat-l">Grupos</div></div>
      <div class="stat-card"><div class="stat-n">${o.length}</div><div class="stat-l">OUs</div></div>
    </div>
    <div class="section-header"><h2>Últimos usuarios</h2></div>
    <div class="table-wrap"><table>
      <thead><tr><th>Usuario</th><th>Nombre</th><th>Email</th><th>Estado</th></tr></thead>
      <tbody>${u.slice(0,10).map(u=>`<tr>
        <td><strong>${esc(u.username)}</strong></td><td>${esc(u.name||'-')}</td>
        <td>${esc(u.email||'-')}</td><td>${badge(u.enabled)}</td>
      </tr>`).join('')}</tbody>
    </table></div>`;
}

/* ══════════════════════════════════════════════
   USUARIOS
══════════════════════════════════════════════ */
async function renderUsers(filter='') {
  const data = await apiGet('/api/users/');
  const users = (data?.users||[]).filter(u =>
    !filter || u.username.toLowerCase().includes(filter) || (u.name||'').toLowerCase().includes(filter)
  );
  document.getElementById('content').innerHTML = `
    <div id="alert-users" class="alert"></div>
    <div class="section-header">
      <h2>Usuarios del AD <span style="color:var(--muted);font-size:14px;font-weight:400">(${users.length})</span></h2>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <input class="search-input" placeholder="Buscar..." oninput="renderUsers(this.value.toLowerCase())" value="${esc(filter)}">
        <button class="btn btn-ghost btn-sm" onclick="openCreateUser()">+ Nuevo</button>
        <button class="btn btn-ghost btn-sm" onclick="openImportCSV()">⬆ CSV</button>
      </div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Usuario</th><th>Nombre</th><th>Email</th><th>Grupos</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody>${users.length===0?'<tr><td colspan="6"><div class="empty">Sin resultados</div></td></tr>':
        users.map(u=>`<tr>
          <td><strong>${esc(u.username)}</strong></td>
          <td>${esc(u.name||'-')}</td>
          <td>${esc(u.email||'-')}</td>
          <td>${(u.groups||[]).slice(0,2).map(g=>`<span class="tag">${esc(shortDN(g))}</span>`).join('')}${(u.groups||[]).length>2?`<span class="tag">+${u.groups.length-2}</span>`:''}</td>
          <td>${badge(u.enabled)}</td>
          <td><div class="actions">
            <button class="btn btn-ghost btn-sm" onclick="openUserDetail('${esc(u.username)}')">Ver</button>
            <button class="btn btn-ghost btn-sm" onclick="openEditUser('${esc(u.username)}')">Editar</button>
            <button class="btn btn-ghost btn-sm" onclick="toggleUser('${esc(u.username)}',${u.enabled})">${u.enabled?'🔒 Deshabilitar':'🔓 Habilitar'}</button>
            <button class="btn btn-danger btn-sm" onclick="deleteUser('${esc(u.username)}')">Eliminar</button>
          </div></td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
}

async function openUserDetail(username) {
  const data = await apiGet(`/api/users/${username}`);
  if (!data) return;
  const gd = await apiGet('/api/groups/');
  const allGroups = (gd?.groups||[]).map(g=>g.name);
  const userGroups = (data.groups||[]).map(g=>shortDN(g));
  document.getElementById('modal-title').textContent = `Usuario: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
      <div><div class="detail-label">Usuario</div><div>${esc(data.username)}</div></div>
      <div><div class="detail-label">Nombre completo</div><div>${esc(data.name||'-')}</div></div>
      <div><div class="detail-label">Email</div><div>${esc(data.email||'-')}</div></div>
      <div><div class="detail-label">Estado</div><div>${badge(data.enabled)}</div></div>
      <div><div class="detail-label">Home Dir</div><div style="font-size:12px;color:var(--muted)">${esc(data.home_dir||'-')}</div></div>
      <div><div class="detail-label">Creado</div><div style="font-size:12px;color:var(--muted)">${esc(data.created||'-')}</div></div>
    </div>
    <div style="margin-bottom:16px">
      <div class="detail-label" style="margin-bottom:8px">Grupos</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">
        ${userGroups.length===0?'<span style="color:var(--muted);font-size:13px">Sin grupos</span>':
          userGroups.map(g=>`<span class="tag" style="display:flex;align-items:center;gap:4px">${esc(g)}
            <span style="cursor:pointer;color:var(--red);font-size:14px;line-height:1" onclick="removeFromGroup('${esc(username)}','${esc(g)}')">×</span>
          </span>`).join('')}
      </div>
      <div style="display:flex;gap:8px">
        <select id="add-group-sel" style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px">
          <option value="">-- Añadir a grupo --</option>
          ${allGroups.filter(g=>!userGroups.includes(g)).map(g=>`<option value="${esc(g)}">${esc(g)}</option>`).join('')}
        </select>
        <button class="btn btn-ghost btn-sm" onclick="addToGroupFromDetail('${esc(username)}')">Añadir</button>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;padding-top:12px;border-top:1px solid var(--border)">
      <button class="btn btn-ghost btn-sm" onclick="closeModal();openResetPassword('${esc(username)}')">🔑 Cambiar contraseña</button>
      <button class="btn btn-ghost btn-sm" onclick="forcePasswordChange('${esc(username)}')">⚠ Forzar cambio login</button>
      <button class="btn btn-ghost btn-sm" onclick="openLogonHours('${esc(username)}')">🕐 Horas de acceso</button>
      <button class="btn btn-ghost btn-sm" onclick="openWorkstations('${esc(username)}')">🖥 Equipos permitidos</button>
    </div>`;
  document.getElementById('modal-ok').style.display = 'none';
  openModal();
}

function openCreateUser() {
  document.getElementById('modal-title').textContent = 'Nuevo usuario';
  document.getElementById('modal-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="field"><label>Usuario *</label><input id="m-username" placeholder="juan.perez"></div>
      <div class="field"><label>Contraseña *</label><input id="m-password" type="password"></div>
      <div class="field"><label>Nombre</label><input id="m-firstname" placeholder="Juan"></div>
      <div class="field"><label>Apellido</label><input id="m-lastname" placeholder="Perez"></div>
      <div class="field" style="grid-column:span 2"><label>Email</label><input id="m-email" type="email" placeholder="juan@dandydash.local"></div>
    </div>
    <div class="field"><label>Descripcion</label><input id="m-desc"></div>
    <div class="field"><label>Rol</label>
      <select id="m-role">
        <option value="user">Usuario normal</option>
        <option value="admin">Administrador del dominio</option>
      </select>
    </div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      username: document.getElementById('m-username').value.trim(),
      password: document.getElementById('m-password').value,
      first_name: document.getElementById('m-firstname').value.trim(),
      last_name: document.getElementById('m-lastname').value.trim(),
      email: document.getElementById('m-email').value.trim(),
      description: document.getElementById('m-desc').value.trim()
    };
    if (!body.username||!body.password) { showAlert('users','err','Usuario y contraseña obligatorios.'); closeModal(); return; }
    const r = await apiPost('/api/users/', body);
    closeModal();
    if (r?.message) {
      if (document.getElementById('m-role')?.value === 'admin')
        await apiPost(`/api/groups/Domain Admins/members`, { username: body.username });
      showAlert('users','ok', r.message); renderUsers();
    } else showAlert('users','err', r?.error||'Error al crear.');
  };
  openModal();
}

async function openEditUser(username) {
  const data = await apiGet(`/api/users/${username}`);
  if (!data) return;
  document.getElementById('modal-title').textContent = `Editar: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="field"><label>Nombre</label><input id="m-firstname" value="${esc(data.first_name||'')}"></div>
      <div class="field"><label>Apellido</label><input id="m-lastname" value="${esc(data.last_name||'')}"></div>
      <div class="field" style="grid-column:span 2"><label>Email</label><input id="m-email" type="email" value="${esc(data.email||'')}"></div>
    </div>
    <div class="field"><label>Descripcion</label><input id="m-desc" value="${esc(data.description||'')}"></div>
    <div class="field"><label>Nueva contraseña (vacío = no cambiar)</label><input id="m-password" type="password"></div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      first_name: document.getElementById('m-firstname').value.trim(),
      last_name: document.getElementById('m-lastname').value.trim(),
      email: document.getElementById('m-email').value.trim(),
      description: document.getElementById('m-desc').value.trim()
    };
    const pwd = document.getElementById('m-password').value;
    if (pwd) body.password = pwd;
    const r = await apiPut(`/api/users/${username}`, body);
    closeModal();
    if (r?.message) { showAlert('users','ok', r.message); renderUsers(); }
    else showAlert('users','err', r?.error||'Error.');
  };
  openModal();
}

async function toggleUser(username, enabled) {
  const r = await apiPatch(`/api/users/${username}/toggle`, { enabled: !enabled });
  if (r?.message) { showAlert('users','ok', r.message); renderUsers(); }
  else showAlert('users','err', r?.error||'Error.');
}

async function deleteUser(username) {
  if (!confirm(`¿Eliminar "${username}"? No se puede deshacer.`)) return;
  const r = await apiDelete(`/api/users/${username}`);
  if (r?.message) { showAlert('users','ok', r.message); renderUsers(); }
  else showAlert('users','err', r?.error||'Error.');
}

function openResetPassword(username) {
  document.getElementById('modal-title').textContent = `Cambiar contraseña: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <div class="field"><label>Nueva contraseña *</label><input id="m-newpwd" type="password"></div>
    <div class="field"><label>Confirmar *</label><input id="m-confirmpwd" type="password"></div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const p1 = document.getElementById('m-newpwd').value;
    const p2 = document.getElementById('m-confirmpwd').value;
    if (!p1) { showAlert('users','err','Introduce la contraseña.'); closeModal(); return; }
    if (p1!==p2) { showAlert('users','err','Las contraseñas no coinciden.'); closeModal(); return; }
    const r = await apiPost(`/api/users/${username}/password`, { password: p1 });
    closeModal();
    if (r?.message) showAlert('users','ok', r.message);
    else showAlert('users','err', r?.error||'Error.');
  };
  openModal();
}

async function forcePasswordChange(username) {
  const r = await apiPost(`/api/users/${username}/force-password-change`, {});
  closeModal();
  if (r?.message) showAlert('users','ok', `${username} deberá cambiar contraseña en el próximo inicio de sesión.`);
  else showAlert('users','err', r?.error||'Error.');
}

function openLogonHours(username) {
  closeModal();
  const days = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];
  let grid = '<div style="overflow-x:auto"><table style="font-size:11px;border-collapse:collapse"><thead><tr><th style="padding:4px 8px"></th>';
  for (let h=0;h<24;h++) grid+=`<th style="padding:2px 3px;color:var(--muted)">${h}</th>`;
  grid+='</tr></thead><tbody>';
  days.forEach((day,di)=>{
    grid+=`<tr><td style="padding:4px 8px;color:var(--muted);white-space:nowrap">${day}</td>`;
    for (let h=0;h<24;h++){
      const checked = di<5&&h>=8&&h<20?'checked':'';
      grid+=`<td style="padding:2px"><input type="checkbox" id="lh-${di}-${h}" ${checked} style="accent-color:var(--purple)"></td>`;
    }
    grid+='</tr>';
  });
  grid+='</tbody></table></div>';
  document.getElementById('modal-title').textContent = `Horas de acceso: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <p style="font-size:13px;color:var(--muted);margin-bottom:12px">Marca las horas permitidas. Por defecto L-V 8:00-20:00.</p>${grid}`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const hours = [];
    days.forEach((_,di)=>{ for(let h=0;h<24;h++) if(document.getElementById(`lh-${di}-${h}`)?.checked) hours.push(`${di}-${h}`); });
    const r = await apiPost(`/api/users/${username}/logon-hours`, { hours });
    closeModal();
    if (r?.message) showAlert('users','ok', r.message);
    else showAlert('users','err', r?.error||'Error.');
  };
  openModal();
}

function openWorkstations(username) {
  closeModal();
  document.getElementById('modal-title').textContent = `Equipos permitidos: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <p style="font-size:13px;color:var(--muted);margin-bottom:12px">Equipos donde puede iniciar sesión. Vacío = todos.</p>
    <div class="field"><label>Equipos (separados por comas)</label><input id="m-workstations" placeholder="PC-ADMIN,LAPTOP-KILIAN"></div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const ws = document.getElementById('m-workstations').value.trim();
    const workstations = ws ? ws.split(',').map(s=>s.trim()).filter(Boolean) : [];
    const r = await apiPost(`/api/users/${username}/workstations`, { workstations });
    closeModal();
    if (r?.message) showAlert('users','ok', r.message);
    else showAlert('users','err', r?.error||'Error.');
  };
  openModal();
}

async function addToGroupFromDetail(username) {
  const sel = document.getElementById('add-group-sel');
  if (!sel?.value) return;
  const r = await apiPost(`/api/groups/${sel.value}/members`, { username });
  if (r?.message) { closeModal(); openUserDetail(username); }
  else showAlert('users','err', r?.error||'Error.');
}

async function removeFromGroup(username, groupName) {
  if (!confirm(`¿Quitar a ${username} del grupo ${groupName}?`)) return;
  const r = await apiDelete(`/api/groups/${groupName}/members/${username}`);
  if (r?.message) { closeModal(); openUserDetail(username); }
  else showAlert('users','err', r?.error||'Error.');
}

/* ══════════════════════════════════════════════
   IMPORTAR CSV
══════════════════════════════════════════════ */
function openImportCSV() {
  document.getElementById('modal-title').textContent = 'Importar usuarios desde CSV';
  document.getElementById('modal-body').innerHTML = `
    <p style="font-size:13px;color:var(--muted);margin-bottom:10px">Cabecera requerida:</p>
    <code style="display:block;background:var(--bg);padding:8px 12px;border-radius:6px;font-size:12px;margin-bottom:14px;color:var(--purple-light)">username,password,first_name,last_name,email,group,description</code>
    <div class="field"><label>Fichero CSV</label>
      <input type="file" id="csv-file" accept=".csv" style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:8px;color:var(--text);width:100%">
    </div>
    <div id="csv-preview"></div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').textContent = 'Importar todos';
  document.getElementById('csv-file').onchange = previewCSV;
  document.getElementById('modal-ok').onclick = importCSV;
  openModal();
}

function parseCSV(text) {
  const lines = text.trim().split('\n').filter(l=>l.trim());
  const headers = lines[0].split(',').map(h=>h.trim().toLowerCase().replace(/["\r]/g,''));
  return lines.slice(1).map(line => {
    const vals = line.split(',').map(v=>v.trim().replace(/["\r]/g,''));
    const obj = {};
    headers.forEach((h,i) => obj[h] = vals[i]||'');
    return obj;
  }).filter(r => r.username);
}

function previewCSV() {
  const file = document.getElementById('csv-file').files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const rows = parseCSV(e.target.result);
    const prev = document.getElementById('csv-preview');
    if (!rows.length) { prev.innerHTML = '<p style="color:var(--red);font-size:13px">CSV vacío o formato incorrecto.</p>'; return; }
    prev.innerHTML = `
      <p style="font-size:12px;color:var(--muted);margin-bottom:8px">${rows.length} usuarios encontrados:</p>
      <div class="table-wrap" style="max-height:180px;overflow-y:auto"><table>
        <thead><tr><th>Usuario</th><th>Nombre</th><th>Email</th><th>Grupo</th></tr></thead>
        <tbody>${rows.map(r=>`<tr>
          <td>${esc(r.username)}</td>
          <td>${esc((r.first_name+' '+r.last_name).trim()||'-')}</td>
          <td>${esc(r.email||'-')}</td>
          <td>${esc(r.group||'-')}</td>
        </tr>`).join('')}</tbody>
      </table></div>`;
  };
  reader.readAsText(file);
}

async function importCSV() {
  const file = document.getElementById('csv-file').files[0];
  if (!file) { showAlert('users','err','Selecciona un fichero CSV.'); closeModal(); return; }
  const text = await file.text();
  const rows = parseCSV(text);
  if (!rows.length) { showAlert('users','err','CSV vacío o formato incorrecto.'); closeModal(); return; }
  closeModal();
  showAlert('users','ok', `Importando ${rows.length} usuarios...`);
  let ok=0, errors=[];
  for (const row of rows) {
    const r = await apiPost('/api/users/', {
      username: row.username, password: row.password,
      first_name: row.first_name, last_name: row.last_name,
      email: row.email, description: row.description||''
    });
    if (r?.message) {
      ok++;
      if (row.group) await apiPost(`/api/groups/${row.group}/members`, { username: row.username });
    } else {
      errors.push(`${row.username}: ${r?.error||'error'}`);
    }
  }
  if (errors.length) showAlert('users','err', `${ok} creados, ${errors.length} errores: ${errors.slice(0,3).join(' | ')}`);
  else showAlert('users','ok', `✅ ${ok} usuarios importados correctamente.`);
  renderUsers();
}

/* ══════════════════════════════════════════════
   GRUPOS
══════════════════════════════════════════════ */
async function renderGroups(filter='') {
  const data = await apiGet('/api/groups/');
  const groups = (data?.groups||[]).filter(g => !filter || g.name.toLowerCase().includes(filter));
  document.getElementById('content').innerHTML = `
    <div id="alert-groups" class="alert"></div>
    <div class="section-header">
      <h2>Grupos del AD <span style="color:var(--muted);font-size:14px;font-weight:400">(${groups.length})</span></h2>
      <div style="display:flex;gap:8px">
        <input class="search-input" placeholder="Buscar..." oninput="renderGroups(this.value.toLowerCase())" value="${esc(filter)}">
        <button class="btn btn-ghost btn-sm" onclick="openCreateGroup()">+ Nuevo grupo</button>
      </div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Nombre</th><th>Descripcion</th><th>Miembros</th><th>Acciones</th></tr></thead>
      <tbody>${groups.length===0?'<tr><td colspan="4"><div class="empty">Sin resultados</div></td></tr>':
        groups.map(g=>`<tr>
          <td><strong>${esc(g.name)}</strong></td>
          <td style="color:var(--muted)">${esc(g.description||'-')}</td>
          <td><span class="tag">${g.members?.length||0} miembros</span></td>
          <td><div class="actions">
            <button class="btn btn-ghost btn-sm" onclick="openGroupDetail('${esc(g.name)}')">Ver miembros</button>
            <button class="btn btn-danger btn-sm" onclick="deleteGroup('${esc(g.name)}')">Eliminar</button>
          </div></td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
}

async function openGroupDetail(name) {
  const data = await apiGet(`/api/groups/${name}`);
  if (!data) return;
  const members = data.members||[];
  document.getElementById('modal-title').textContent = `Grupo: ${name}`;
  document.getElementById('modal-body').innerHTML = `
    <p style="color:var(--muted);font-size:13px;margin-bottom:12px">${esc(data.description||'Sin descripción')}</p>
    <div class="detail-label" style="margin-bottom:8px">Miembros (${members.length})</div>
    <div style="max-height:200px;overflow-y:auto;margin-bottom:16px">
      ${members.length===0?'<p style="color:var(--muted);font-size:13px">Sin miembros</p>':
        members.map(m=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border)">
          <span style="font-size:13px">${esc(shortDN(m))}</span>
          <button class="btn btn-danger btn-sm" onclick="removeMemberFromGroup('${esc(name)}','${esc(shortDN(m))}')">Quitar</button>
        </div>`).join('')}
    </div>
    <div style="display:flex;gap:8px">
      <input id="add-member-input" class="search-input" style="flex:1" placeholder="Usuario a añadir">
      <button class="btn btn-ghost btn-sm" onclick="addMemberToGroup('${esc(name)}')">Añadir</button>
    </div>`;
  document.getElementById('modal-ok').style.display = 'none';
  openModal();
}

async function addMemberToGroup(groupName) {
  const username = document.getElementById('add-member-input').value.trim();
  if (!username) return;
  const r = await apiPost(`/api/groups/${groupName}/members`, { username });
  if (r?.message) { closeModal(); openGroupDetail(groupName); }
  else showAlert('groups','err', r?.error||'Error.');
}

async function removeMemberFromGroup(groupName, username) {
  if (!confirm(`¿Quitar a ${username} del grupo ${groupName}?`)) return;
  const r = await apiDelete(`/api/groups/${groupName}/members/${username}`);
  if (r?.message) { closeModal(); openGroupDetail(groupName); }
  else showAlert('groups','err', r?.error||'Error.');
}

function openCreateGroup() {
  document.getElementById('modal-title').textContent = 'Nuevo grupo';
  document.getElementById('modal-body').innerHTML = `
    <div class="field"><label>Nombre *</label><input id="m-name" placeholder="Informatica"></div>
    <div class="field"><label>Descripcion</label><input id="m-desc"></div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const body = { name: document.getElementById('m-name').value.trim(), description: document.getElementById('m-desc').value.trim() };
    if (!body.name) { showAlert('groups','err','El nombre es obligatorio.'); closeModal(); return; }
    const r = await apiPost('/api/groups/', body);
    closeModal();
    if (r?.message) { showAlert('groups','ok', r.message); renderGroups(); }
    else showAlert('groups','err', r?.error||'Error.');
  };
  openModal();
}

async function deleteGroup(name) {
  if (!confirm(`¿Eliminar el grupo "${name}"?`)) return;
  const r = await apiDelete(`/api/groups/${name}`);
  if (r?.message) { showAlert('groups','ok', r.message); renderGroups(); }
  else showAlert('groups','err', r?.error||'Error.');
}

/* ══════════════════════════════════════════════
   OUs
══════════════════════════════════════════════ */
async function renderOUs() {
  const data = await apiGet('/api/ous/');
  const ous = data?.ous||[];
  document.getElementById('content').innerHTML = `
    <div id="alert-ous" class="alert"></div>
    <div class="section-header">
      <h2>Unidades Organizativas <span style="color:var(--muted);font-size:14px;font-weight:400">(${ous.length})</span></h2>
      <button class="btn btn-ghost btn-sm" onclick="openCreateOU()">+ Nueva OU</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Nombre</th><th>Descripcion</th><th>DN</th><th>Acciones</th></tr></thead>
      <tbody>${ous.length===0?'<tr><td colspan="4"><div class="empty">Sin OUs</div></td></tr>':
        ous.map(o=>`<tr>
          <td><strong>${esc(o.name)}</strong></td>
          <td style="color:var(--muted)">${esc(o.description||'-')}</td>
          <td class="dn-cell" title="${esc(o.dn)}">${esc(o.dn)}</td>
          <td><button class="btn btn-danger btn-sm" onclick="deleteOU('${esc(o.name)}')">Eliminar</button></td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
}

function openCreateOU() {
  document.getElementById('modal-title').textContent = 'Nueva OU';
  document.getElementById('modal-body').innerHTML = `
    <div class="field"><label>Nombre *</label><input id="m-name" placeholder="Departamento IT"></div>
    <div class="field"><label>Descripcion</label><input id="m-desc"></div>`;
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').onclick = async () => {
    const body = { name: document.getElementById('m-name').value.trim(), description: document.getElementById('m-desc').value.trim() };
    if (!body.name) { showAlert('ous','err','El nombre es obligatorio.'); closeModal(); return; }
    const r = await apiPost('/api/ous/', body);
    closeModal();
    if (r?.message) { showAlert('ous','ok', r.message); renderOUs(); }
    else showAlert('ous','err', r?.error||'Error.');
  };
  openModal();
}

async function deleteOU(name) {
  if (!confirm(`¿Eliminar la OU "${name}"?`)) return;
  const r = await apiDelete(`/api/ous/${name}`);
  if (r?.message) { showAlert('ous','ok', r.message); renderOUs(); }
  else showAlert('ous','err', r?.error||'Error.');
}

/* ══════════════════════════════════════════════
   GPOs
══════════════════════════════════════════════ */
async function renderGPOs() {
  const data = await apiGet('/api/gpos/');
  const gpos = data?.gpos||[];
  document.getElementById('content').innerHTML = `
    <div id="alert-gpos" class="alert"></div>
    <div class="section-header"><h2>Directivas de Grupo (GPO)</h2></div>
    ${gpos.length>0?`<div class="table-wrap" style="margin-bottom:24px"><table>
      <thead><tr><th>Nombre</th><th>GUID</th><th>Estado</th></tr></thead>
      <tbody>${gpos.map(g=>`<tr>
        <td><strong>${esc(g.name||'-')}</strong></td>
        <td style="color:var(--muted);font-size:11px">${esc(g.guid||'-')}</td>
        <td><span class="badge badge-green">Activa</span></td>
      </tr>`).join('')}</tbody>
    </table></div>`:''}
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px">
      <h3 style="color:var(--purple-light);margin-bottom:16px">GPOs frecuentes — comandos para samba1</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">
        ${[
          {name:'Bloquear Panel de Control',       cmd:'samba-tool gpo manage symlink create "Block-ControlPanel" -U administrator'},
          {name:'Bloquear Símbolo del Sistema',    cmd:'samba-tool gpo manage symlink create "Block-CMD" -U administrator'},
          {name:'Establecer página de inicio IE',  cmd:'samba-tool gpo manage browser homepage set "Block-Homepage" --url https://dandydash.local -U administrator'},
          {name:'Forzar salvapantallas 10 min',    cmd:'samba-tool gpo manage smb_conf set "Screensaver" --setting "screensaver timeout" --value 600 -U administrator'},
          {name:'Deshabilitar dispositivos USB',   cmd:'samba-tool gpo manage diskstorage set "Block-USB" -U administrator'},
          {name:'Restringir instalación software', cmd:'samba-tool gpo manage software set "No-Install" -U administrator'},
          {name:'Cambiar fondo de pantalla',       cmd:'samba-tool gpo manage wallpaper set "Wallpaper" --wallpaper /netlogon/bg.jpg -U administrator'},
          {name:'Crear nueva GPO vacía',           cmd:'samba-tool gpo create "MiPolitica" -U administrator'}
        ].map(g=>`<div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px">
          <div style="font-size:13px;font-weight:600;margin-bottom:6px">${esc(g.name)}</div>
          <code style="font-size:10px;color:var(--muted);display:block;margin-bottom:10px;word-break:break-all;line-height:1.5">${esc(g.cmd)}</code>
          <button class="btn btn-ghost btn-sm" onclick="copyAndNotify('${esc(g.cmd)}','gpos')">📋 Copiar</button>
        </div>`).join('')}
      </div>
    </div>`;
}

function copyAndNotify(cmd, section) {
  navigator.clipboard.writeText(cmd).then(()=>{
    showAlert(section,'ok','Comando copiado. Ejecútalo en samba1.');
  }).catch(()=>{
    const ta=document.createElement('textarea');
    ta.value=cmd; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    showAlert(section,'ok','Comando copiado.');
  });
}

/* ══════════════════════════════════════════════
   MODAL
══════════════════════════════════════════════ */
function openModal()  { document.getElementById('modal').classList.add('open'); }
function closeModal() {
  document.getElementById('modal').classList.remove('open');
  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').textContent = 'Guardar';
}

/* ══════════════════════════════════════════════
   UTILS
══════════════════════════════════════════════ */
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function badge(enabled) {
  return enabled ? '<span class="badge badge-green">Activo</span>' : '<span class="badge badge-red">Inactivo</span>';
}
function shortDN(dn) {
  const m = String(dn||'').match(/^CN=([^,]+)/i);
  return m ? m[1] : dn;
}
function showAlert(section, type, msg) {
  const el = document.getElementById(`alert-${section}`);
  if (!el) return;
  el.className = `alert ${type}`; el.textContent = msg;
  setTimeout(() => { el.className = 'alert'; }, 5000);
}

/* ══════════════════════════════════════════════
   INIT
══════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  if (TOKEN) { currentUser = { username: 'admin', role: 'admin' }; showApp(); loadSection('dashboard'); }
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
    if (e.key === 'Enter' && document.getElementById('login-screen').style.display !== 'none') doLogin();
  });
});
