'use strict';

// ══════════════════════════════════════════════════════════════════
// USERS.JS — Gestión completa de usuarios del Active Directory
// Incluye: listar, crear, editar, eliminar, habilitar/deshabilitar,
//          cambiar contraseña, horas de acceso, equipos permitidos
//          y gestión de membresía en grupos.
// ══════════════════════════════════════════════════════════════════


// ── LISTADO DE USUARIOS ───────────────────────────────────────────

/**
 * renderUsers — Obtiene todos los usuarios del AD y los muestra en tabla.
 * Permite filtrar por nombre de usuario o nombre completo.
 * @param {string} filter - Texto de búsqueda (opcional)
 */
async function renderUsers(filter = '') {
  const data = await apiGet('/api/users/');  // Obtener lista de usuarios de la API

  // Filtrar usuarios según el texto de búsqueda (case-insensitive)
  const users = (data?.users || []).filter(u =>
    !filter ||
    u.username.toLowerCase().includes(filter) ||
    (u.name || '').toLowerCase().includes(filter)
  );

  // Renderizar la sección de usuarios con tabla y controles
  document.getElementById('content').innerHTML = `
    <div id="alert-users" class="alert"></div>
    <div class="section-header">
      <h2>Usuarios del AD <span style="color:var(--muted);font-size:14px;font-weight:400">(${users.length})</span></h2>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <!-- Campo de búsqueda en tiempo real -->
        <input class="search-input" placeholder="Buscar..."
          oninput="renderUsers(this.value.toLowerCase())" value="${esc(filter)}">
        <!-- Botón para abrir modal de creación de usuario -->
        <button class="btn btn-ghost btn-sm" onclick="openCreateUser()">+ Nuevo</button>
        <!-- Botón para abrir modal de importación CSV -->
        <button class="btn btn-ghost btn-sm" onclick="openImportCSV()">⬆ CSV</button>
      </div>
    </div>

    <!-- Tabla principal de usuarios -->
    <div class="table-wrap"><table>
      <thead>
        <tr>
          <th>Usuario</th>
          <th>Nombre</th>
          <th>Email</th>
          <th>Grupos</th>
          <th>Estado</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        ${users.length === 0
          ? '<tr><td colspan="6"><div class="empty">Sin resultados</div></td></tr>'
          : users.map(u => `
            <tr>
              <!-- Nombre de usuario (sAMAccountName) -->
              <td><strong>${esc(u.username)}</strong></td>
              <!-- Nombre completo (displayName) -->
              <td>${esc(u.name || '-')}</td>
              <!-- Email del usuario -->
              <td>${esc(u.email || '-')}</td>
              <!-- Grupos del usuario — máximo 2 visibles + contador de extras -->
              <td>
                ${(u.groups || []).slice(0, 2).map(g =>
                  `<span class="tag">${esc(shortDN(g))}</span>`
                ).join('')}
                ${(u.groups || []).length > 2
                  ? `<span class="tag">+${u.groups.length - 2}</span>`
                  : ''}
              </td>
              <!-- Estado habilitado/deshabilitado -->
              <td>${badge(u.enabled)}</td>
              <!-- Botones de acción por usuario -->
              <td><div class="actions">
                <button class="btn btn-ghost btn-sm"
                  onclick="openUserDetail('${esc(u.username)}')">Ver</button>
                <button class="btn btn-ghost btn-sm"
                  onclick="openEditUser('${esc(u.username)}')">Editar</button>
                <button class="btn btn-ghost btn-sm"
                  onclick="toggleUser('${esc(u.username)}',${u.enabled})">
                  ${u.enabled ? '🔒 Deshabilitar' : '🔓 Habilitar'}
                </button>
                <button class="btn btn-danger btn-sm"
                  onclick="deleteUser('${esc(u.username)}')">Eliminar</button>
              </div></td>
            </tr>
          `).join('')}
      </tbody>
    </table></div>
  `;
}


// ── DETALLE DE USUARIO ────────────────────────────────────────────

/**
 * openUserDetail — Abre el modal con todos los detalles de un usuario.
 * Muestra sus grupos actuales con opción de añadir/quitar,
 * y accesos rápidos a acciones avanzadas.
 * @param {string} username - Nombre de usuario del AD
 */
async function openUserDetail(username) {
  // Obtener datos del usuario y lista de todos los grupos en paralelo
  const data = await apiGet(`/api/users/${username}`);
  if (!data) return;  // Abortar si la API devuelve error

  const gd = await apiGet('/api/groups/');
  const allGroups  = (gd?.groups || []).map(g => g.name);              // Todos los grupos del AD
  const userGroups = (data.groups || []).map(g => shortDN(g));         // Grupos del usuario (nombres cortos)

  // Construir el modal de detalle
  document.getElementById('modal-title').textContent = `Usuario: ${username}`;
  document.getElementById('modal-body').innerHTML = `

    <!-- Información básica del usuario en dos columnas -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
      <div>
        <div class="detail-label">Usuario</div>
        <div>${esc(data.username)}</div>
      </div>
      <div>
        <div class="detail-label">Nombre completo</div>
        <div>${esc(data.name || '-')}</div>
      </div>
      <div>
        <div class="detail-label">Email</div>
        <div>${esc(data.email || '-')}</div>
      </div>
      <div>
        <div class="detail-label">Estado</div>
        <div>${badge(data.enabled)}</div>
      </div>
      <div>
        <div class="detail-label">Home Dir</div>
        <div style="font-size:12px;color:var(--muted)">${esc(data.home_dir || '-')}</div>
      </div>
      <div>
        <div class="detail-label">Creado</div>
        <div style="font-size:12px;color:var(--muted)">${esc(data.created || '-')}</div>
      </div>
    </div>

    <!-- Sección de grupos del usuario -->
    <div style="margin-bottom:16px">
      <div class="detail-label" style="margin-bottom:8px">Grupos</div>

      <!-- Lista de grupos actuales con botón para quitar -->
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">
        ${userGroups.length === 0
          ? '<span style="color:var(--muted);font-size:13px">Sin grupos</span>'
          : userGroups.map(g => `
            <span class="tag" style="display:flex;align-items:center;gap:4px">
              ${esc(g)}
              <!-- Botón × para quitar al usuario de este grupo -->
              <span style="cursor:pointer;color:var(--red);font-size:14px;line-height:1"
                onclick="removeFromGroup('${esc(username)}','${esc(g)}')">×</span>
            </span>
          `).join('')}
      </div>

      <!-- Selector para añadir el usuario a un nuevo grupo -->
      <div style="display:flex;gap:8px">
        <select id="add-group-sel"
          style="flex:1;padding:8px;background:var(--bg);border:1px solid var(--border);
                 border-radius:6px;color:var(--text);font-size:13px">
          <option value="">-- Añadir a grupo --</option>
          <!-- Solo mostrar grupos en los que el usuario NO está ya -->
          ${allGroups
            .filter(g => !userGroups.includes(g))
            .map(g => `<option value="${esc(g)}">${esc(g)}</option>`)
            .join('')}
        </select>
        <button class="btn btn-ghost btn-sm"
          onclick="addToGroupFromDetail('${esc(username)}')">Añadir</button>
      </div>
    </div>

    <!-- Acciones avanzadas del usuario -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;padding-top:12px;border-top:1px solid var(--border)">
      <!-- Cambiar contraseña manualmente -->
      <button class="btn btn-ghost btn-sm"
        onclick="closeModal();openResetPassword('${esc(username)}')">🔑 Cambiar contraseña</button>
      <!-- Forzar cambio de contraseña en el próximo inicio de sesión -->
      <button class="btn btn-ghost btn-sm"
        onclick="forcePasswordChange('${esc(username)}')">⚠ Forzar cambio login</button>
      <!-- Configurar horas en las que el usuario puede iniciar sesión -->
      <button class="btn btn-ghost btn-sm"
        onclick="openLogonHours('${esc(username)}')">🕐 Horas de acceso</button>
      <!-- Restringir el usuario a equipos específicos -->
      <button class="btn btn-ghost btn-sm"
        onclick="openWorkstations('${esc(username)}')">🖥 Equipos permitidos</button>
    </div>
  `;

  document.getElementById('modal-ok').style.display = 'none';  // Ocultar botón OK en modo detalle
  openModal();
}


// ── CREAR USUARIO ─────────────────────────────────────────────────

/**
 * openCreateUser — Abre el modal con el formulario para crear un nuevo usuario.
 * Permite crear usuarios normales o administradores del dominio.
 */
function openCreateUser() {
  document.getElementById('modal-title').textContent = 'Nuevo usuario';
  document.getElementById('modal-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="field">
        <label>Usuario *</label>
        <input id="m-username" placeholder="juan.perez">
      </div>
      <div class="field">
        <label>Contraseña *</label>
        <input id="m-password" type="password">
      </div>
      <div class="field">
        <label>Nombre</label>
        <input id="m-firstname" placeholder="Juan">
      </div>
      <div class="field">
        <label>Apellido</label>
        <input id="m-lastname" placeholder="Perez">
      </div>
      <div class="field" style="grid-column:span 2">
        <label>Email</label>
        <input id="m-email" type="email" placeholder="juan@dandydash.local">
      </div>
    </div>
    <div class="field">
      <label>Descripcion</label>
      <input id="m-desc">
    </div>
    <!-- Selector de rol: usuario normal o administrador del dominio -->
    <div class="field">
      <label>Rol</label>
      <select id="m-role">
        <option value="user">Usuario normal</option>
        <option value="admin">Administrador del dominio</option>
      </select>
    </div>
  `;

  document.getElementById('modal-ok').style.display = '';

  // Al hacer clic en Aceptar, enviar el formulario de creación
  document.getElementById('modal-ok').onclick = async () => {
    // Recoger todos los valores del formulario
    const body = {
      username:    document.getElementById('m-username').value.trim(),
      password:    document.getElementById('m-password').value,
      first_name:  document.getElementById('m-firstname').value.trim(),
      last_name:   document.getElementById('m-lastname').value.trim(),
      email:       document.getElementById('m-email').value.trim(),
      description: document.getElementById('m-desc').value.trim()
    };

    // Validar campos obligatorios
    if (!body.username || !body.password) {
      showAlert('users', 'err', 'Usuario y contraseña obligatorios.');
      closeModal();
      return;
    }

    // Enviar petición de creación a la API
    const r = await apiPost('/api/users/', body);

    if (r?.message) {
      // Si el rol es admin, añadir al grupo Domain Admins
      if (document.getElementById('m-role')?.value === 'admin') {
        await apiPost(`/api/groups/Domain Admins/members`, { username: body.username });
      }
      closeModal();
      showAlert('users', 'ok', r.message);
      renderUsers();  // Recargar la lista de usuarios
    } else {
      closeModal();
      showAlert('users', 'err', r?.error || 'Error al crear.');
    }
  };

  openModal();
}


// ── EDITAR USUARIO ────────────────────────────────────────────────

/**
 * openEditUser — Abre el modal para editar los datos de un usuario existente.
 * Precarga los campos con los valores actuales del usuario.
 * @param {string} username - Nombre de usuario a editar
 */
async function openEditUser(username) {
  // Obtener datos actuales del usuario para precargar el formulario
  const data = await apiGet(`/api/users/${username}`);
  if (!data) return;

  document.getElementById('modal-title').textContent = `Editar: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <!-- Nombre — precargado con valor actual -->
      <div class="field">
        <label>Nombre</label>
        <input id="m-firstname" value="${esc(data.first_name || '')}">
      </div>
      <!-- Apellido — precargado con valor actual -->
      <div class="field">
        <label>Apellido</label>
        <input id="m-lastname" value="${esc(data.last_name || '')}">
      </div>
      <!-- Email — precargado con valor actual -->
      <div class="field" style="grid-column:span 2">
        <label>Email</label>
        <input id="m-email" type="email" value="${esc(data.email || '')}">
      </div>
    </div>
    <!-- Descripción — precargada con valor actual -->
    <div class="field">
      <label>Descripcion</label>
      <input id="m-desc" value="${esc(data.description || '')}">
    </div>
    <!-- Campo de contraseña opcional — vacío = no cambiar -->
    <div class="field">
      <label>Nueva contraseña (vacío = no cambiar)</label>
      <input id="m-password" type="password">
    </div>
  `;

  document.getElementById('modal-ok').style.display = '';

  // Al hacer clic en Guardar, enviar los cambios a la API
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      first_name:  document.getElementById('m-firstname').value.trim(),
      last_name:   document.getElementById('m-lastname').value.trim(),
      email:       document.getElementById('m-email').value.trim(),
      description: document.getElementById('m-desc').value.trim()
    };

    // Solo incluir contraseña si se ha introducido una nueva
    const pwd = document.getElementById('m-password').value;
    if (pwd) body.password = pwd;

    // Enviar actualización a la API
    const r = await apiPut(`/api/users/${username}`, body);
    closeModal();
    if (r?.message) {
      showAlert('users', 'ok', r.message);
      renderUsers();  // Recargar lista de usuarios
    } else {
      showAlert('users', 'err', r?.error || 'Error.');
    }
  };

  openModal();
}


// ── HABILITAR / DESHABILITAR USUARIO ──────────────────────────────

/**
 * toggleUser — Cambia el estado habilitado/deshabilitado de un usuario.
 * @param {string}  username - Nombre de usuario
 * @param {boolean} enabled  - Estado actual (true = habilitado)
 */
async function toggleUser(username, enabled) {
  // Enviar el estado contrario al actual
  const r = await apiPatch(`/api/users/${username}/toggle`, { enabled: !enabled });
  if (r?.message) {
    showAlert('users', 'ok', r.message);
    renderUsers();  // Recargar para reflejar el cambio
  } else {
    showAlert('users', 'err', r?.error || 'Error.');
  }
}


// ── ELIMINAR USUARIO ──────────────────────────────────────────────

/**
 * deleteUser — Elimina un usuario del AD tras pedir confirmación.
 * @param {string} username - Nombre de usuario a eliminar
 */
async function deleteUser(username) {
  // Confirmar antes de eliminar (acción irreversible)
  if (!confirm(`¿Eliminar "${username}"? No se puede deshacer.`)) return;

  const r = await apiDelete(`/api/users/${username}`);
  if (r?.message) {
    showAlert('users', 'ok', r.message);
    renderUsers();  // Recargar lista sin el usuario eliminado
  } else {
    showAlert('users', 'err', r?.error || 'Error.');
  }
}


// ── CAMBIAR CONTRASEÑA ────────────────────────────────────────────

/**
 * openResetPassword — Abre el modal para cambiar la contraseña de un usuario.
 * Requiere introducir la nueva contraseña dos veces para confirmar.
 * @param {string} username - Usuario cuya contraseña se va a cambiar
 */
function openResetPassword(username) {
  document.getElementById('modal-title').textContent = `Cambiar contraseña: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <div class="field">
      <label>Nueva contraseña *</label>
      <input id="m-newpwd" type="password">
    </div>
    <div class="field">
      <label>Confirmar *</label>
      <input id="m-confirmpwd" type="password">
    </div>
  `;

  document.getElementById('modal-ok').style.display = '';

  document.getElementById('modal-ok').onclick = async () => {
    const p1 = document.getElementById('m-newpwd').value;
    const p2 = document.getElementById('m-confirmpwd').value;

    // Validar que se ha introducido contraseña
    if (!p1) { showAlert('users', 'err', 'Introduce la contraseña.'); closeModal(); return; }
    // Validar que las dos contraseñas coinciden
    if (p1 !== p2) { showAlert('users', 'err', 'Las contraseñas no coinciden.'); closeModal(); return; }

    // Enviar nueva contraseña a la API
    const r = await apiPost(`/api/users/${username}/password`, { password: p1 });
    closeModal();
    if (r?.message) showAlert('users', 'ok', r.message);
    else showAlert('users', 'err', r?.error || 'Error.');
  };

  openModal();
}


// ── FORZAR CAMBIO DE CONTRASEÑA ───────────────────────────────────

/**
 * forcePasswordChange — Marca al usuario para que deba cambiar su contraseña
 * la próxima vez que inicie sesión en Windows.
 * @param {string} username - Nombre de usuario
 */
async function forcePasswordChange(username) {
  const r = await apiPost(`/api/users/${username}/force-password-change`, {});
  closeModal();
  if (r?.message) {
    showAlert('users', 'ok', `${username} deberá cambiar contraseña en el próximo inicio de sesión.`);
  } else {
    showAlert('users', 'err', r?.error || 'Error.');
  }
}


// ── HORAS DE ACCESO ───────────────────────────────────────────────

/**
 * openLogonHours — Abre un modal con una cuadrícula de 7 días × 24 horas
 * para configurar en qué momentos puede iniciar sesión el usuario.
 * Por defecto marca L-V de 8:00 a 20:00.
 * @param {string} username - Nombre de usuario
 */
function openLogonHours(username) {
  closeModal();  // Cerrar el modal de detalle antes de abrir éste

  const days = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];  // Nombres de los días

  // Construir la cabecera de la tabla (horas 0-23)
  let grid = '<div style="overflow-x:auto"><table style="font-size:11px;border-collapse:collapse"><thead><tr><th style="padding:4px 8px"></th>';
  for (let h = 0; h < 24; h++) {
    grid += `<th style="padding:2px 3px;color:var(--muted)">${h}</th>`;
  }
  grid += '</tr></thead><tbody>';

  // Construir una fila por cada día con checkboxes por hora
  days.forEach((day, di) => {
    grid += `<tr><td style="padding:4px 8px;color:var(--muted);white-space:nowrap">${day}</td>`;
    for (let h = 0; h < 24; h++) {
      // Marcar por defecto L-V (di < 5) en horario de 8:00 a 19:59
      const checked = (di < 5 && h >= 8 && h < 20) ? 'checked' : '';
      grid += `<td style="padding:2px"><input type="checkbox" id="lh-${di}-${h}" ${checked}
                style="accent-color:var(--purple)"></td>`;
    }
    grid += '</tr>';
  });
  grid += '</tbody></table></div>';

  document.getElementById('modal-title').textContent = `Horas de acceso: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <p style="font-size:13px;color:var(--muted);margin-bottom:12px">
      Marca las horas permitidas. Por defecto L-V 8:00-20:00.
    </p>
    ${grid}
  `;

  document.getElementById('modal-ok').style.display = '';

  // Al guardar, recoger todos los checkboxes marcados y enviarlos a la API
  document.getElementById('modal-ok').onclick = async () => {
    const hours = [];
    days.forEach((_, di) => {
      for (let h = 0; h < 24; h++) {
        if (document.getElementById(`lh-${di}-${h}`)?.checked) {
          hours.push(`${di}-${h}`);  // Formato: "día-hora" (ej: "0-9" = Lunes a las 9)
        }
      }
    });

    const r = await apiPost(`/api/users/${username}/logon-hours`, { hours });
    closeModal();
    if (r?.message) showAlert('users', 'ok', r.message);
    else showAlert('users', 'err', r?.error || 'Error.');
  };

  openModal();
}


// ── EQUIPOS PERMITIDOS ────────────────────────────────────────────

/**
 * openWorkstations — Abre el modal para restringir el usuario
 * a iniciar sesión solo en equipos específicos.
 * Si se deja vacío, el usuario puede iniciar sesión en cualquier equipo.
 * @param {string} username - Nombre de usuario
 */
function openWorkstations(username) {
  closeModal();  // Cerrar el modal de detalle antes de abrir éste

  document.getElementById('modal-title').textContent = `Equipos permitidos: ${username}`;
  document.getElementById('modal-body').innerHTML = `
    <p style="font-size:13px;color:var(--muted);margin-bottom:12px">
      Equipos donde puede iniciar sesión. Vacío = todos.
    </p>
    <div class="field">
      <label>Equipos (separados por comas)</label>
      <input id="m-workstations" placeholder="PC-ADMIN,LAPTOP-KILIAN">
    </div>
  `;

  document.getElementById('modal-ok').style.display = '';

  document.getElementById('modal-ok').onclick = async () => {
    const ws = document.getElementById('m-workstations').value.trim();
    // Convertir la cadena separada por comas en array, filtrando entradas vacías
    const workstations = ws ? ws.split(',').map(s => s.trim()).filter(Boolean) : [];

    const r = await apiPost(`/api/users/${username}/workstations`, { workstations });
    closeModal();
    if (r?.message) showAlert('users', 'ok', r.message);
    else showAlert('users', 'err', r?.error || 'Error.');
  };

  openModal();
}


// ── GESTIÓN DE GRUPOS DESDE DETALLE DE USUARIO ────────────────────

/**
 * addToGroupFromDetail — Añade el usuario al grupo seleccionado en el dropdown
 * del modal de detalle de usuario.
 * @param {string} username - Nombre de usuario a añadir
 */
async function addToGroupFromDetail(username) {
  const sel = document.getElementById('add-group-sel');
  if (!sel?.value) return;  // No hacer nada si no hay grupo seleccionado

  const r = await apiPost(`/api/groups/${sel.value}/members`, { username });
  if (r?.message) {
    closeModal();
    openUserDetail(username);  // Reabrir detalle para reflejar el nuevo grupo
  } else {
    showAlert('users', 'err', r?.error || 'Error.');
  }
}

/**
 * removeFromGroup — Quita al usuario de un grupo tras pedir confirmación.
 * @param {string} username  - Nombre de usuario
 * @param {string} groupName - Nombre del grupo del que se va a quitar
 */
async function removeFromGroup(username, groupName) {
  if (!confirm(`¿Quitar a ${username} del grupo ${groupName}?`)) return;

  const r = await apiDelete(`/api/groups/${groupName}/members/${username}`);
  if (r?.message) {
    closeModal();
    openUserDetail(username);  // Reabrir detalle para reflejar el cambio
  } else {
    showAlert('users', 'err', r?.error || 'Error.');
  }
}
