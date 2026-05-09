'use strict';

const API = '';
let TOKEN = localStorage.getItem('dd_token');
let currentUser = null;

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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const d = await r.json();

    if (d.mfa_required) {
      document.getElementById('mfabox').style.display = 'block';
      document.getElementById('totp').focus();
      err.textContent = 'Introduce el código MFA de Google Authenticator.';
      return;
    }
    if (d.access_token) {
      TOKEN = d.access_token;
      localStorage.setItem('dd_token', TOKEN);
      currentUser = { username: usr, role: d.role || 'viewer' };
      showApp();
      loadSection('dashboard');
    } else {
      err.textContent = d.error || d.msg || 'Credenciales incorrectas.';
    }
  } catch (e) {
    err.textContent = 'No se puede conectar con la API.';
  }
}

function doLogout() {
  localStorage.removeItem('dd_token');
  TOKEN = null;
  location.reload();
}

async function apiReq(method, path, body) {
  const opts = {
    method,
    headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' }
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (r.status === 401) { doLogout(); return null; }
  return r.json();
}
const apiGet    = (p)    => apiReq('GET',    p);
const apiPost   = (p, b) => apiReq('POST',   p, b);
const apiDelete = (p)    => apiReq('DELETE', p);
const apiPut    = (p, b) => apiReq('PUT',    p, b);

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  if (currentUser) document.getElementById('topbar-username').textContent = currentUser.username;
}

function setActiveNav(section) {
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.section === section);
  });
}

async function loadSection(section) {
  setActiveNav(section);
  document.getElementById('content').innerHTML = '<div class="empty"><div class="spinner"></div></div>';
  switch (section) {
    case 'dashboard': await renderDashboard(); break;
    case 'users':     await renderUsers();     break;
    case 'groups':    await renderGroups();    break;
    case 'ous':       await renderOUs();       break;
  }
}

async function renderDashboard() {
  const [users, groups, ous] = await Promise.all([
    apiGet('/api/users/'), apiGet('/api/groups/'), apiGet('/api/ous/')
  ]);
  const u = users?.users || [];
  const g = groups?.groups || [];
  const o = ous?.ous || [];
  const active = u.filter(x => x.enabled).length;

  document.getElementById('content').innerHTML = `
    <div class="stats">
      <div class="stat-card"><div class="stat-n">${u.length}</div><div class="stat-l">Usuarios totales</div></div>
      <div class="stat-card"><div class="stat-n">${active}</div><div class="stat-l">Usuarios activos</div></div>
      <div class="stat-card"><div class="stat-n">${u.length - active}</div><div class="stat-l">Deshabilitados</div></div>
      <div class="stat-card"><div class="stat-n">${g.length}</div><div class="stat-l">Grupos</div></div>
      <div class="stat-card"><div class="stat-n">${o.length}</div><div class="stat-l">OUs</div></div>
    </div>
    <div class="section-header"><h2>Últimos usuarios</h2></div>
    <div class="table-wrap"><table>
      <thead><tr><th>Usuario</th><th>Nombre</th><th>Email</th><th>Estado</th></tr></thead>
      <tbody>${u.slice(0,8).map(u => `
        <tr>
          <td><strong>${esc(u.username)}</strong></td>
          <td>${esc(u.name||'-')}</td>
          <td>${esc(u.email||'-')}</td>
          <td>${badge(u.enabled)}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
}

async function renderUsers(filter = '') {
  const data = await apiGet('/api/users/');
  const users = (data?.users || []).filter(u =>
    !filter || u.username.toLowerCase().includes(filter) || (u.name||'').toLowerCase().includes(filter)
  );
  document.getElementById('content').innerHTML = `
    <div id="alert-users" class="alert"></div>
    <div class="section-header">
      <h2>Usuarios del AD <span style="color:var(--muted);font-size:14px;font-weight:400">(${users.length})</span></h2>
      <div style="display:flex;gap:10px">
        <input class="search-input" placeholder="Buscar..." oninput="renderUsers(this.value.toLowerCase())" value="${esc(filter)}">
        <button class="btn btn-ghost btn-sm" onclick="openCreateUser()">+ Nuevo usuario</button>
      </div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Usuario</th><th>Nombre</th><th>Email</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody>${users.length === 0 ? '<tr><td colspan="5"><div class="empty">Sin resultados</div></td></tr>' :
        users.map(u => `<tr>
          <td><strong>${esc(u.username)}</strong></td>
          <td>${esc(u.name||'-')}</td>
          <td>${esc(u.email||'-')}</td>
          <td>${badge(u.enabled)}</td>
          <td><div class="actions">
            <button class="btn btn-ghost btn-sm" onclick="openEditUser('${esc(u.username)}')">Editar</button>
            <button class="btn btn-danger btn-sm" onclick="deleteUser('${esc(u.username)}')">Eliminar</button>
          </div></td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
}

function openCreateUser() {
  document.getElementById('modal-title').textContent = 'Nuevo usuario';
  document.getElementById('modal-body').innerHTML = `
    <div class="field"><label>Usuario *</label><input id="m-username" placeholder="juan.perez"></div>
    <div class="field"><label>Contraseña *</label><input id="m-password" type="password"></div>
    <div class="field"><label>Nombre</label><input id="m-firstname" placeholder="Juan"></div>
    <div class="field"><label>Apellido</label><input id="m-lastname" placeholder="Perez"></div>
    <div class="field"><label>Email</label><input id="m-email" type="email"></div>`;
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      username:   document.getElementById('m-username').value.trim(),
      password:   document.getElementById('m-password').value,
      first_name: document.getElementById('m-firstname').value.trim(),
      last_name:  document.getElementById('m-lastname').value.trim(),
      email:      document.getElementById('m-email').value.trim()
    };
    if (!body.username || !body.password) { showAlert('users','err','Usuario y contraseña obligatorios.'); closeModal(); return; }
    const r = await apiPost('/api/users/', body);
    closeModal();
    if (r?.message) { showAlert('users','ok', r.message); renderUsers(); }
    else showAlert('users','err', r?.error || 'Error al crear.');
  };
  openModal();
}

async function openEditUser(username) {
  const data = await apiGet(`/api/users/${username}`);
  if (!data) return;
  document.getElementById('modal-title').textContent = `Editar: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <div class="field"><label>Nombre</label><input id="m-firstname" value="${esc(data.first_name||'')}"></div>
    <div class="field"><label>Apellido</label><input id="m-lastname" value="${esc(data.last_name||'')}"></div>
    <div class="field"><label>Email</label><input id="m-email" type="email" value="${esc(data.email||'')}"></div>
    <div class="field"><label>Nueva contraseña (vacío = no cambiar)</label><input id="m-password" type="password"></div>`;
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      first_name: document.getElementById('m-firstname').value.trim(),
      last_name:  document.getElementById('m-lastname').value.trim(),
      email:      document.getElementById('m-email').value.trim()
    };
    const pwd = document.getElementById('m-password').value;
    if (pwd) body.password = pwd;
    const r = await apiPut(`/api/users/${username}`, body);
    closeModal();
    if (r?.message) { showAlert('users','ok', r.message); renderUsers(); }
    else showAlert('users','err', r?.error || 'Error al editar.');
  };
  openModal();
}

async function deleteUser(username) {
  if (!confirm(`¿Eliminar "${username}"? No se puede deshacer.`)) return;
  const r = await apiDelete(`/api/users/${username}`);
  if (r?.message) { showAlert('users','ok', r.message); renderUsers(); }
  else showAlert('users','err', r?.error || 'Error al eliminar.');
}

async function renderGroups(filter = '') {
  const data = await apiGet('/api/groups/');
  const groups = (data?.groups || []).filter(g => !filter || g.name.toLowerCase().includes(filter));
  document.getElementById('content').innerHTML = `
    <div id="alert-groups" class="alert"></div>
    <div class="section-header">
      <h2>Grupos del AD <span style="color:var(--muted);font-size:14px;font-weight:400">(${groups.length})</span></h2>
      <div style="display:flex;gap:10px">
        <input class="search-input" placeholder="Buscar..." oninput="renderGroups(this.value.toLowerCase())" value="${esc(filter)}">
        <button class="btn btn-ghost btn-sm" onclick="openCreateGroup()">+ Nuevo grupo</button>
      </div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Nombre</th><th>Descripcion</th><th>Miembros</th><th>Acciones</th></tr></thead>
      <tbody>${groups.length === 0 ? '<tr><td colspan="4"><div class="empty">Sin resultados</div></td></tr>' :
        groups.map(g => `<tr>
          <td><strong>${esc(g.name)}</strong></td>
          <td style="color:var(--muted)">${esc(g.description||'-')}</td>
          <td><span class="tag">${g.members?.length||0} miembros</span></td>
          <td><button class="btn btn-danger btn-sm" onclick="deleteGroup('${esc(g.name)}')">Eliminar</button></td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
}

function openCreateGroup() {
  document.getElementById('modal-title').textContent = 'Nuevo grupo';
  document.getElementById('modal-body').innerHTML = `
    <div class="field"><label>Nombre *</label><input id="m-name" placeholder="Informatica"></div>
    <div class="field"><label>Descripcion</label><input id="m-desc"></div>`;
  document.getElementById('modal-ok').onclick = async () => {
    const body = { name: document.getElementById('m-name').value.trim(), description: document.getElementById('m-desc').value.trim() };
    if (!body.name) { showAlert('groups','err','El nombre es obligatorio.'); closeModal(); return; }
    const r = await apiPost('/api/groups/', body);
    closeModal();
    if (r?.message) { showAlert('groups','ok', r.message); renderGroups(); }
    else showAlert('groups','err', r?.error || 'Error al crear.');
  };
  openModal();
}

async function deleteGroup(name) {
  if (!confirm(`¿Eliminar el grupo "${name}"?`)) return;
  const r = await apiDelete(`/api/groups/${name}`);
  if (r?.message) { showAlert('groups','ok', r.message); renderGroups(); }
  else showAlert('groups','err', r?.error || 'Error.');
}

async function renderOUs() {
  const data = await apiGet('/api/ous/');
  const ous = data?.ous || [];
  document.getElementById('content').innerHTML = `
    <div id="alert-ous" class="alert"></div>
    <div class="section-header">
      <h2>Unidades Organizativas <span style="color:var(--muted);font-size:14px;font-weight:400">(${ous.length})</span></h2>
      <button class="btn btn-ghost btn-sm" onclick="openCreateOU()">+ Nueva OU</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Nombre</th><th>Descripcion</th><th>DN</th><th>Acciones</th></tr></thead>
      <tbody>${ous.length === 0 ? '<tr><td colspan="4"><div class="empty">Sin OUs definidas</div></td></tr>' :
        ous.map(o => `<tr>
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
  document.getElementById('modal-ok').onclick = async () => {
    const body = { name: document.getElementById('m-name').value.trim(), description: document.getElementById('m-desc').value.trim() };
    if (!body.name) { showAlert('ous','err','El nombre es obligatorio.'); closeModal(); return; }
    const r = await apiPost('/api/ous/', body);
    closeModal();
    if (r?.message) { showAlert('ous','ok', r.message); renderOUs(); }
    else showAlert('ous','err', r?.error || 'Error al crear.');
  };
  openModal();
}

async function deleteOU(name) {
  if (!confirm(`¿Eliminar la OU "${name}"?`)) return;
  const r = await apiDelete(`/api/ous/${name}`);
  if (r?.message) { showAlert('ous','ok', r.message); renderOUs(); }
  else showAlert('ous','err', r?.error || 'Error.');
}

function openModal()  { document.getElementById('modal').classList.add('open'); }
function closeModal() { document.getElementById('modal').classList.remove('open'); }

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function badge(enabled) {
  return enabled
    ? '<span class="badge badge-green">Activo</span>'
    : '<span class="badge badge-red">Inactivo</span>';
}
function showAlert(section, type, msg) {
  const el = document.getElementById(`alert-${section}`);
  if (!el) return;
  el.className = `alert ${type}`;
  el.textContent = msg;
  setTimeout(() => { el.className = 'alert'; }, 4000);
}

document.addEventListener('DOMContentLoaded', () => {
  if (TOKEN) {
    currentUser = { username: 'admin', role: 'admin' };
    showApp();
    loadSection('dashboard');
  }
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
    if (e.key === 'Enter' && document.getElementById('login-screen').style.display !== 'none') doLogin();
  });
});
