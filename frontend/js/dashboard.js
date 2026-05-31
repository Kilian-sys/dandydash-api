'use strict';

// ══════════════════════════════════════════════════════════════════
// DASHBOARD.JS — Vista general con estadísticas del dominio
// ══════════════════════════════════════════════════════════════════

/**
 * renderDashboard — Carga y muestra la vista principal del dashboard.
 * Hace 3 peticiones en paralelo para obtener usuarios, grupos y OUs.
 * Muestra estadísticas rápidas y una tabla con los últimos 10 usuarios.
 */
async function renderDashboard() {
  // Obtener datos de usuarios, grupos y OUs en paralelo para mayor velocidad
  const [ud, gd, od] = await Promise.all([
    apiGet('/api/users/'),   // Lista completa de usuarios del AD
    apiGet('/api/groups/'),  // Lista completa de grupos del AD
    apiGet('/api/ous/')      // Lista completa de Unidades Organizativas
  ]);

  // Extraer arrays de cada respuesta (con fallback a array vacío si hay error)
  const u = ud?.users  || [];
  const g = gd?.groups || [];
  const o = od?.ous    || [];

  // Calcular usuarios activos (habilitados)
  const active = u.filter(x => x.enabled).length;

  // Renderizar el HTML del dashboard en el área de contenido
  document.getElementById('content').innerHTML = `
    <h2 style="margin-bottom:20px;color:var(--purple-light)">Dashboard — dandydash.local</h2>

    <!-- Tarjetas de estadísticas rápidas -->
    <div class="stats">
      <!-- Total de usuarios registrados en el AD -->
      <div class="stat-card">
        <div class="stat-n">${u.length}</div>
        <div class="stat-l">Usuarios totales</div>
      </div>

      <!-- Usuarios habilitados (pueden iniciar sesión) -->
      <div class="stat-card">
        <div class="stat-n" style="color:var(--green)">${active}</div>
        <div class="stat-l">Activos</div>
      </div>

      <!-- Usuarios deshabilitados (bloqueados) -->
      <div class="stat-card">
        <div class="stat-n" style="color:var(--red)">${u.length - active}</div>
        <div class="stat-l">Deshabilitados</div>
      </div>

      <!-- Total de grupos en el dominio -->
      <div class="stat-card">
        <div class="stat-n">${g.length}</div>
        <div class="stat-l">Grupos</div>
      </div>

      <!-- Total de Unidades Organizativas -->
      <div class="stat-card">
        <div class="stat-n">${o.length}</div>
        <div class="stat-l">OUs</div>
      </div>
    </div>

    <!-- Tabla con los 10 usuarios más recientes -->
    <div class="section-header"><h2>Últimos usuarios</h2></div>
    <div class="table-wrap"><table>
      <thead>
        <tr>
          <th>Usuario</th>
          <th>Nombre</th>
          <th>Email</th>
          <th>Estado</th>
        </tr>
      </thead>
      <tbody>
        ${u.slice(0, 10).map(u => `
          <tr>
            <td><strong>${esc(u.username)}</strong></td>
            <td>${esc(u.name || '-')}</td>
            <td>${esc(u.email || '-')}</td>
            <td>${badge(u.enabled)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table></div>
  `;
}
