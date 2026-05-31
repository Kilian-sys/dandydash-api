'use strict';

// ══════════════════════════════════════════════════════════════════
// GROUPS.JS — Gestión de grupos del Active Directory
// Incluye: listar, crear, eliminar grupos y gestionar sus miembros
// ══════════════════════════════════════════════════════════════════


// ── LISTADO DE GRUPOS ─────────────────────────────────────────────

/**
 * renderGroups — Obtiene todos los grupos del AD y los muestra en tabla.
 * Permite filtrar por nombre del grupo.
 * @param {string} filter - Texto de búsqueda (opcional)
 */
async function renderGroups(filter = '') {
  const data = await apiGet('/api/groups/');  // Obtener lista de grupos de la API

  // Filtrar grupos según el texto de búsqueda
  const groups = (data?.groups || []).filter(g =>
    !filter || g.name.toLowerCase().includes(filter)
  );

  document.getElementById('content').innerHTML = `
    <div id="alert-groups" class="alert"></div>
    <div class="section-header">
      <h2>Grupos del AD <span style="color:var(--muted);font-size:14px;font-weight:400">(${groups.length})</span></h2>
      <div style="display:flex;gap:8px">
        <!-- Campo de búsqueda en tiempo real -->
        <input class="search-input" placeholder="Buscar..."
          oninput="renderGroups(this.value.toLowerCase())" value="${esc(filter)}">
        <!-- Botón para crear un nuevo grupo -->
        <button class="btn btn-ghost btn-sm" onclick="openCreateGroup()">+ Nuevo grupo</button>
      </div>
    </div>

    <!-- Tabla de grupos -->
    <div class="table-wrap"><table>
      <thead>
        <tr>
          <th>Nombre</th>
          <th>Descripcion</th>
          <th>Miembros</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        ${groups.length === 0
          ? '<tr><td colspan="4"><div class="empty">Sin resultados</div></td></tr>'
          : groups.map(g => `
            <tr>
              <!-- Nombre del grupo en el AD -->
              <td><strong>${esc(g.name)}</strong></td>
              <!-- Descripción del grupo (puede estar vacía) -->
              <td style="color:var(--muted)">${esc(g.description || '-')}</td>
              <!-- Número de miembros actual -->
              <td><span class="tag">${g.members?.length || 0} miembros</span></td>
              <!-- Acciones disponibles -->
              <td><div class="actions">
                <!-- Ver y gestionar miembros del grupo -->
                <button class="btn btn-ghost btn-sm"
                  onclick="openGroupDetail('${esc(g.name)}')">Ver miembros</button>
                <!-- Eliminar el grupo del AD -->
                <button class="btn btn-danger btn-sm"
                  onclick="deleteGroup('${esc(g.name)}')">Eliminar</button>
              </div></td>
            </tr>
          `).join('')}
      </tbody>
    </table></div>
  `;
}


// ── DETALLE / MIEMBROS DE GRUPO ───────────────────────────────────

/**
 * openGroupDetail — Abre el modal con la lista de miembros del grupo.
 * Permite añadir y quitar miembros directamente desde el modal.
 * @param {string} name - Nombre del grupo
 */
async function openGroupDetail(name) {
  const data = await apiGet(`/api/groups/${name}`);  // Obtener detalles del grupo
  if (!data) return;

  const members = data.members || [];  // Lista de miembros (DNs completos)

  document.getElementById('modal-title').textContent = `Grupo: ${name}`;
  document.getElementById('modal-body').innerHTML = `
    <!-- Descripción del grupo -->
    <p style="color:var(--muted);font-size:13px;margin-bottom:12px">
      ${esc(data.description || 'Sin descripción')}
    </p>

    <!-- Lista de miembros actuales con botón para quitar -->
    <div class="detail-label" style="margin-bottom:8px">Miembros (${members.length})</div>
    <div style="max-height:200px;overflow-y:auto;margin-bottom:16px">
      ${members.length === 0
        ? '<p style="color:var(--muted);font-size:13px">Sin miembros</p>'
        : members.map(m => `
          <div style="display:flex;justify-content:space-between;align-items:center;
                      padding:6px 0;border-bottom:1px solid var(--border)">
            <!-- Nombre corto del miembro (sin el DN completo) -->
            <span style="font-size:13px">${esc(shortDN(m))}</span>
            <!-- Botón para quitar el miembro del grupo -->
            <button class="btn btn-danger btn-sm"
              onclick="removeMemberFromGroup('${esc(name)}','${esc(shortDN(m))}')">Quitar</button>
          </div>
        `).join('')}
    </div>

    <!-- Campo para añadir un nuevo miembro -->
    <div style="display:flex;gap:8px">
      <input id="add-member-input" class="search-input" style="flex:1"
        placeholder="Usuario a añadir">
      <button class="btn btn-ghost btn-sm"
        onclick="addMemberToGroup('${esc(name)}')">Añadir</button>
    </div>
  `;

  document.getElementById('modal-ok').style.display = 'none';  // Ocultar botón OK
  openModal();
}


// ── AÑADIR MIEMBRO AL GRUPO ───────────────────────────────────────

/**
 * addMemberToGroup — Añade el usuario introducido en el campo de texto al grupo.
 * @param {string} groupName - Nombre del grupo al que añadir el miembro
 */
async function addMemberToGroup(groupName) {
  const username = document.getElementById('add-member-input').value.trim();
  if (!username) return;  // No hacer nada si el campo está vacío

  const r = await apiPost(`/api/groups/${groupName}/members`, { username });
  if (r?.message) {
    closeModal();
    openGroupDetail(groupName);  // Reabrir detalle para reflejar el cambio
  } else {
    showAlert('groups', 'err', r?.error || 'Error.');
  }
}


// ── QUITAR MIEMBRO DEL GRUPO ──────────────────────────────────────

/**
 * removeMemberFromGroup — Quita a un usuario del grupo tras pedir confirmación.
 * @param {string} groupName - Nombre del grupo
 * @param {string} username  - Nombre de usuario a quitar
 */
async function removeMemberFromGroup(groupName, username) {
  if (!confirm(`¿Quitar a ${username} del grupo ${groupName}?`)) return;

  const r = await apiDelete(`/api/groups/${groupName}/members/${username}`);
  if (r?.message) {
    closeModal();
    openGroupDetail(groupName);  // Reabrir detalle actualizado
  } else {
    showAlert('groups', 'err', r?.error || 'Error.');
  }
}


// ── CREAR GRUPO ───────────────────────────────────────────────────

/**
 * openCreateGroup — Abre el modal con el formulario para crear un nuevo grupo en el AD.
 */
function openCreateGroup() {
  document.getElementById('modal-title').textContent = 'Nuevo grupo';
  document.getElementById('modal-body').innerHTML = `
    <!-- Nombre del grupo (obligatorio) -->
    <div class="field">
      <label>Nombre *</label>
      <input id="m-name" placeholder="Informatica">
    </div>
    <!-- Descripción del grupo (opcional) -->
    <div class="field">
      <label>Descripcion</label>
      <input id="m-desc">
    </div>
  `;

  document.getElementById('modal-ok').style.display = '';

  // Al confirmar, enviar la petición de creación del grupo
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      name:        document.getElementById('m-name').value.trim(),
      description: document.getElementById('m-desc').value.trim()
    };

    // Validar que el nombre no está vacío
    if (!body.name) {
      showAlert('groups', 'err', 'El nombre es obligatorio.');
      closeModal();
      return;
    }

    const r = await apiPost('/api/groups/', body);
    closeModal();
    if (r?.message) {
      showAlert('groups', 'ok', r.message);
      renderGroups();  // Recargar la lista de grupos
    } else {
      showAlert('groups', 'err', r?.error || 'Error.');
    }
  };

  openModal();
}


// ── ELIMINAR GRUPO ────────────────────────────────────────────────

/**
 * deleteGroup — Elimina un grupo del AD tras pedir confirmación.
 * @param {string} name - Nombre del grupo a eliminar
 */
async function deleteGroup(name) {
  if (!confirm(`¿Eliminar el grupo "${name}"?`)) return;

  const r = await apiDelete(`/api/groups/${name}`);
  if (r?.message) {
    showAlert('groups', 'ok', r.message);
    renderGroups();  // Recargar la lista sin el grupo eliminado
  } else {
    showAlert('groups', 'err', r?.error || 'Error.');
  }
}
