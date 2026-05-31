'use strict';

// ══════════════════════════════════════════════════════════════════
// OUS.JS — Gestión de Unidades Organizativas (OUs)
// Las OUs permiten organizar usuarios, grupos y equipos del AD
// en contenedores jerárquicos para aplicar políticas diferenciadas.
// ══════════════════════════════════════════════════════════════════


// ── LISTADO DE OUs ────────────────────────────────────────────────

/**
 * renderOUs — Obtiene todas las OUs del AD y las muestra en tabla.
 * Muestra nombre, descripción y Distinguished Name completo de cada OU.
 */
async function renderOUs() {
  const data = await apiGet('/api/ous/');  // Obtener lista de OUs de la API
  const ous = data?.ous || [];             // Extraer array de OUs

  document.getElementById('content').innerHTML = `
    <div id="alert-ous" class="alert"></div>
    <div class="section-header">
      <h2>Unidades Organizativas <span style="color:var(--muted);font-size:14px;font-weight:400">(${ous.length})</span></h2>
      <!-- Botón para crear una nueva OU -->
      <button class="btn btn-ghost btn-sm" onclick="openCreateOU()">+ Nueva OU</button>
    </div>

    <!-- Tabla de OUs -->
    <div class="table-wrap"><table>
      <thead>
        <tr>
          <th>Nombre</th>
          <th>Descripcion</th>
          <th>DN</th>       <!-- Distinguished Name completo en LDAP -->
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        ${ous.length === 0
          ? '<tr><td colspan="4"><div class="empty">Sin OUs</div></td></tr>'
          : ous.map(o => `
            <tr>
              <!-- Nombre corto de la OU -->
              <td><strong>${esc(o.name)}</strong></td>
              <!-- Descripción de la OU -->
              <td style="color:var(--muted)">${esc(o.description || '-')}</td>
              <!-- DN completo — con title para ver el valor completo en hover -->
              <td class="dn-cell" title="${esc(o.dn)}">${esc(o.dn)}</td>
              <!-- Botón para eliminar la OU -->
              <td>
                <button class="btn btn-danger btn-sm"
                  onclick="deleteOU('${esc(o.name)}')">Eliminar</button>
              </td>
            </tr>
          `).join('')}
      </tbody>
    </table></div>
  `;
}


// ── CREAR OU ──────────────────────────────────────────────────────

/**
 * openCreateOU — Abre el modal con el formulario para crear una nueva OU.
 * La OU se crea directamente bajo la raíz del dominio (DC=dandydash,DC=local).
 */
function openCreateOU() {
  document.getElementById('modal-title').textContent = 'Nueva OU';
  document.getElementById('modal-body').innerHTML = `
    <!-- Nombre de la OU (obligatorio) — se usa para el DN -->
    <div class="field">
      <label>Nombre *</label>
      <input id="m-name" placeholder="Departamento IT">
    </div>
    <!-- Descripción de la OU (opcional) -->
    <div class="field">
      <label>Descripcion</label>
      <input id="m-desc">
    </div>
  `;

  document.getElementById('modal-ok').style.display = '';

  // Al confirmar, enviar la petición de creación de la OU
  document.getElementById('modal-ok').onclick = async () => {
    const body = {
      name:        document.getElementById('m-name').value.trim(),
      description: document.getElementById('m-desc').value.trim()
    };

    // Validar que el nombre no está vacío
    if (!body.name) {
      showAlert('ous', 'err', 'El nombre es obligatorio.');
      closeModal();
      return;
    }

    const r = await apiPost('/api/ous/', body);
    closeModal();
    if (r?.message) {
      showAlert('ous', 'ok', r.message);
      renderOUs();  // Recargar la lista de OUs
    } else {
      showAlert('ous', 'err', r?.error || 'Error.');
    }
  };

  openModal();
}


// ── ELIMINAR OU ───────────────────────────────────────────────────

/**
 * deleteOU — Elimina una OU del AD tras pedir confirmación.
 * Nota: solo se pueden eliminar OUs vacías (sin usuarios ni subOUs).
 * @param {string} name - Nombre de la OU a eliminar
 */
async function deleteOU(name) {
  if (!confirm(`¿Eliminar la OU "${name}"?`)) return;

  const r = await apiDelete(`/api/ous/${name}`);
  if (r?.message) {
    showAlert('ous', 'ok', r.message);
    renderOUs();  // Recargar la lista sin la OU eliminada
  } else {
    showAlert('ous', 'err', r?.error || 'Error.');
  }
}


// ══════════════════════════════════════════════════════════════════
// GPOS.JS — Visualización de GPOs y referencia de comandos Samba4
//
// Las GPOs (Group Policy Objects) en Samba4 se gestionan principalmente
// desde la línea de comandos con samba-tool. Esta sección muestra
// las GPOs activas y proporciona comandos de referencia listos para copiar.
// ══════════════════════════════════════════════════════════════════


// ── LISTADO DE GPOs ───────────────────────────────────────────────

/**
 * renderGPOs — Muestra las GPOs activas en el dominio y una
 * biblioteca de comandos frecuentes para gestionar políticas desde samba1.
 */
async function renderGPOs() {
  const data = await apiGet('/api/gpos/');  // Obtener GPOs del dominio
  const gpos = data?.gpos || [];            // Array de GPOs activas

  document.getElementById('content').innerHTML = `
    <div id="alert-gpos" class="alert"></div>
    <div class="section-header">
      <h2>Directivas de Grupo (GPO)</h2>
    </div>

    <!-- Tabla de GPOs activas (solo si hay alguna) -->
    ${gpos.length > 0 ? `
      <div class="table-wrap" style="margin-bottom:24px"><table>
        <thead>
          <tr>
            <th>Nombre</th>
            <th>GUID</th>        <!-- Identificador único de la GPO en el AD -->
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          ${gpos.map(g => `
            <tr>
              <td><strong>${esc(g.name || '-')}</strong></td>
              <!-- GUID en formato UUID — identificador interno de Samba4 -->
              <td style="color:var(--muted);font-size:11px">${esc(g.guid || '-')}</td>
              <td><span class="badge badge-green">Activa</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table></div>
    ` : ''}

    <!-- Biblioteca de comandos frecuentes para gestionar GPOs en samba1 -->
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px">
      <h3 style="color:var(--purple-light);margin-bottom:16px">
        GPOs frecuentes — comandos para ejecutar en samba1
      </h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">
        ${[
          // Lista de GPOs frecuentes con su nombre descriptivo y comando samba-tool
          {
            name: 'Bloquear Panel de Control',
            cmd:  'samba-tool gpo manage symlink create "Block-ControlPanel" -U administrator'
          },
          {
            name: 'Bloquear Símbolo del Sistema',
            cmd:  'samba-tool gpo manage symlink create "Block-CMD" -U administrator'
          },
          {
            name: 'Establecer página de inicio IE',
            cmd:  'samba-tool gpo manage browser homepage set "Block-Homepage" --url https://dandydash.local -U administrator'
          },
          {
            name: 'Forzar salvapantallas 10 min',
            cmd:  'samba-tool gpo manage smb_conf set "Screensaver" --setting "screensaver timeout" --value 600 -U administrator'
          },
          {
            name: 'Deshabilitar dispositivos USB',
            cmd:  'samba-tool gpo manage diskstorage set "Block-USB" -U administrator'
          },
          {
            name: 'Restringir instalación software',
            cmd:  'samba-tool gpo manage software set "No-Install" -U administrator'
          },
          {
            name: 'Cambiar fondo de pantalla',
            cmd:  'samba-tool gpo manage wallpaper set "Wallpaper" --wallpaper /netlogon/bg.jpg -U administrator'
          },
          {
            name: 'Crear nueva GPO vacía',
            cmd:  'samba-tool gpo create "MiPolitica" -U administrator'
          }
        ].map(g => `
          <div style="background:var(--bg);border:1px solid var(--border);
                      border-radius:8px;padding:14px">
            <!-- Nombre descriptivo de la política -->
            <div style="font-size:13px;font-weight:600;margin-bottom:6px">${esc(g.name)}</div>
            <!-- Comando samba-tool correspondiente -->
            <code style="font-size:10px;color:var(--muted);display:block;
                         margin-bottom:10px;word-break:break-all;line-height:1.5">
              ${esc(g.cmd)}
            </code>
            <!-- Botón para copiar el comando al portapapeles -->
            <button class="btn btn-ghost btn-sm"
              onclick="copyAndNotify('${esc(g.cmd)}','gpos')">📋 Copiar</button>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}


// ── COPIAR COMANDO AL PORTAPAPELES ────────────────────────────────

/**
 * copyAndNotify — Copia un texto al portapapeles y muestra una alerta de confirmación.
 * Usa la API moderna navigator.clipboard con fallback al método antiguo execCommand.
 * @param {string} cmd     - Texto a copiar (comando samba-tool)
 * @param {string} section - Sección donde mostrar la alerta de confirmación
 */
function copyAndNotify(cmd, section) {
  navigator.clipboard.writeText(cmd)
    .then(() => {
      // Portapapeles moderno — mostrar confirmación
      showAlert(section, 'ok', 'Comando copiado. Ejecútalo en samba1.');
    })
    .catch(() => {
      // Fallback para navegadores sin soporte de Clipboard API
      const ta = document.createElement('textarea');
      ta.value = cmd;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');       // Método deprecado pero con soporte universal
      document.body.removeChild(ta);
      showAlert(section, 'ok', 'Comando copiado.');
    });
}
