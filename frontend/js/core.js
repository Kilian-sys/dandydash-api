'use strict';

// ══════════════════════════════════════════════════════════════════
// CORE.JS — Módulo principal: configuración, autenticación,
//           helpers de API, layout y utilidades compartidas
// ══════════════════════════════════════════════════════════════════

// ── Configuración global ──────────────────────────────────────────

const API = '';                                   // Base URL de la API (vacío = mismo dominio)
let TOKEN = localStorage.getItem('dd_token');     // Token JWT almacenado en localStorage
let currentUser = null;                           // Usuario autenticado actualmente
window._importing = false;                        // Flag para bloquear logout durante importación CSV


// ══════════════════════════════════════════════════════════════════
// AUTENTICACIÓN
// ══════════════════════════════════════════════════════════════════

/**
 * doLogin — Envía las credenciales al endpoint /api/auth/login.
 * Si el servidor requiere MFA, muestra el campo TOTP.
 * Si el login es correcto, guarda el token y muestra la app.
 */
async function doLogin() {
  const usr  = document.getElementById('usr').value.trim();   // Nombre de usuario del formulario
  const pwd  = document.getElementById('pwd').value;          // Contraseña del formulario
  const totp = document.getElementById('totp').value.trim();  // Código MFA (opcional)
  const err  = document.getElementById('errmsg');             // Elemento donde mostrar errores

  err.textContent = '';                                        // Limpiar mensajes de error anteriores

  // Validar que se han introducido usuario y contraseña
  if (!usr || !pwd) {
    err.textContent = 'Introduce usuario y contraseña.';
    return;
  }

  // Construir el cuerpo de la petición
  const body = { username: usr, password: pwd };
  if (totp) body.totp_code = totp;  // Añadir código MFA solo si se ha introducido

  try {
    // Enviar petición de login a la API
    const r = await fetch(API + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const d = await r.json();

    // Si el servidor pide MFA, mostrar el campo TOTP
    if (d.mfa_required) {
      document.getElementById('mfabox').style.display = 'block';
      document.getElementById('totp').focus();
      err.textContent = 'Introduce el código MFA.';
      return;
    }

    // Login correcto: guardar token y mostrar la aplicación
    if (d.access_token) {
      TOKEN = d.access_token;
      localStorage.setItem('dd_token', TOKEN);                               // Persistir token
      currentUser = { username: usr, role: d.role || 'viewer' };            // Guardar datos del usuario
      showApp();                                                              // Mostrar interfaz principal
      loadSection('dashboard');                                               // Cargar sección inicial
    } else {
      // Login fallido: mostrar mensaje de error de la API
      err.textContent = d.error || d.msg || 'Credenciales incorrectas.';
    }
  } catch (e) {
    // Error de red o la API no responde
    err.textContent = 'No se puede conectar con la API.';
  }
}

/**
 * doLogout — Elimina el token del localStorage y recarga la página
 * para volver a la pantalla de login.
 */
function doLogout() {
  localStorage.removeItem('dd_token');  // Borrar token guardado
  TOKEN = null;                          // Limpiar variable en memoria
  location.reload();                     // Recargar para mostrar pantalla de login
}


// ══════════════════════════════════════════════════════════════════
// API HELPERS
// ══════════════════════════════════════════════════════════════════

/**
 * apiReq — Función base para todas las peticiones a la API.
 * Incluye el token JWT en la cabecera Authorization.
 * Si recibe 401, cierra la sesión (excepto durante importación CSV).
 *
 * @param {string} method - Método HTTP (GET, POST, PUT, PATCH, DELETE)
 * @param {string} path   - Ruta del endpoint (ej: '/api/users/')
 * @param {object} body   - Cuerpo de la petición (opcional)
 * @returns {object|null} - Respuesta JSON o null si hay error
 */
async function apiReq(method, path, body) {
  // Construir cabeceras con el token de autenticación
  const opts = {
    method,
    headers: {
      Authorization: 'Bearer ' + TOKEN,
      'Content-Type': 'application/json'
    }
  };

  // Añadir cuerpo JSON si se ha proporcionado
  if (body) opts.body = JSON.stringify(body);

  const r = await fetch(API + path, opts);

  // Si el token ha expirado (401), cerrar sesión — excepto durante importación masiva
  if (r.status === 401) {
    if (!window._importing) doLogout();
    return null;
  }

  return r.json();  // Devolver respuesta como objeto JavaScript
}

// Atajos para cada método HTTP — simplifican las llamadas desde el resto del código
const apiGet    = p     => apiReq('GET',    p);        // Petición GET (leer datos)
const apiPost   = (p,b) => apiReq('POST',   p, b);    // Petición POST (crear)
const apiDelete = p     => apiReq('DELETE', p);        // Petición DELETE (eliminar)
const apiPut    = (p,b) => apiReq('PUT',    p, b);    // Petición PUT (reemplazar)
const apiPatch  = (p,b) => apiReq('PATCH',  p, b);   // Petición PATCH (actualizar parcialmente)


// ══════════════════════════════════════════════════════════════════
// LAYOUT Y NAVEGACIÓN
// ══════════════════════════════════════════════════════════════════

/**
 * showApp — Oculta la pantalla de login y muestra la aplicación principal.
 * También actualiza el nombre de usuario en la barra superior.
 */
function showApp() {
  document.getElementById('login-screen').style.display = 'none';  // Ocultar login
  document.getElementById('app').style.display = 'block';           // Mostrar app
  if (currentUser) {
    // Mostrar el nombre del usuario autenticado en el topbar
    document.getElementById('topbar-username').textContent = currentUser.username;
  }
}

/**
 * setActiveNav — Marca el botón de navegación activo en el menú lateral.
 * @param {string} s - Identificador de la sección activa
 */
function setActiveNav(s) {
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.section === s);  // Añadir/quitar clase 'active'
  });
}

/**
 * loadSection — Cambia la sección visible en el área de contenido principal.
 * Muestra un spinner mientras carga y llama a la función de renderizado correspondiente.
 * @param {string} s - Identificador de la sección a cargar
 */
async function loadSection(s) {
  setActiveNav(s);  // Actualizar navegación activa

  // Mostrar spinner de carga mientras se obtienen los datos
  document.getElementById('content').innerHTML = '<div class="empty"><div class="spinner"></div></div>';

  // Mapa de secciones → funciones de renderizado
  const map = {
    dashboard: renderDashboard,  // Vista general con estadísticas
    users:     renderUsers,       // Lista de usuarios del AD
    groups:    renderGroups,      // Lista de grupos del AD
    ous:       renderOUs,         // Lista de Unidades Organizativas
    gpos:      renderGPOs         // Lista de Directivas de Grupo
  };

  // Llamar a la función de renderizado si existe para esta sección
  if (map[s]) await map[s]();
}


// ══════════════════════════════════════════════════════════════════
// MODAL
// ══════════════════════════════════════════════════════════════════

/**
 * openModal — Abre el modal genérico añadiendo la clase CSS 'open'.
 */
function openModal() {
  document.getElementById('modal').classList.add('open');
}

/**
 * closeModal — Cierra el modal y restaura el botón de aceptar a su estado por defecto.
 */
function closeModal() {
  document.getElementById('modal').classList.remove('open');        // Ocultar modal
  document.getElementById('modal-ok').style.display = '';           // Mostrar botón OK
  document.getElementById('modal-ok').textContent = 'Guardar';      // Restaurar texto del botón
}


// ══════════════════════════════════════════════════════════════════
// UTILIDADES
// ══════════════════════════════════════════════════════════════════

/**
 * esc — Escapa caracteres HTML especiales para prevenir XSS.
 * Usar siempre al insertar datos del usuario en el DOM con innerHTML.
 * @param {*} s - Valor a escapar
 * @returns {string} - Cadena con caracteres HTML escapados
 */
function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')   // & → &amp;
    .replace(/</g, '&lt;')    // < → &lt;
    .replace(/>/g, '&gt;')    // > → &gt;
    .replace(/"/g, '&quot;'); // " → &quot;
}

/**
 * badge — Genera un badge HTML de color verde (activo) o rojo (inactivo).
 * @param {boolean} enabled - true = activo, false = inactivo
 * @returns {string} - HTML del badge
 */
function badge(enabled) {
  return enabled
    ? '<span class="badge badge-green">Activo</span>'
    : '<span class="badge badge-red">Inactivo</span>';
}

/**
 * shortDN — Extrae el nombre corto de un Distinguished Name LDAP.
 * Ejemplo: "CN=Juan Perez,OU=IT,DC=dandydash,DC=local" → "Juan Perez"
 * @param {string} dn - Distinguished Name completo
 * @returns {string} - Valor del primer componente CN
 */
function shortDN(dn) {
  const m = String(dn || '').match(/^CN=([^,]+)/i);
  return m ? m[1] : dn;  // Si no hay CN, devolver el DN completo
}

/**
 * showAlert — Muestra un mensaje de alerta en la sección activa.
 * El mensaje desaparece automáticamente a los 5 segundos.
 * @param {string} section - Identificador de la sección (ej: 'users', 'groups')
 * @param {string} type    - Tipo de alerta: 'ok' (verde), 'err' (rojo), 'warn' (naranja)
 * @param {string} msg     - Texto del mensaje
 */
function showAlert(section, type, msg) {
  const el = document.getElementById(`alert-${section}`);
  if (!el) return;                          // Si no existe el elemento, no hacer nada
  el.className = `alert ${type}`;           // Aplicar clase de color según tipo
  el.textContent = msg;                     // Mostrar mensaje
  setTimeout(() => { el.className = 'alert'; }, 5000);  // Ocultar tras 5 segundos
}


// ══════════════════════════════════════════════════════════════════
// INICIALIZACIÓN
// ══════════════════════════════════════════════════════════════════

/**
 * DOMContentLoaded — Se ejecuta cuando el DOM está completamente cargado.
 * Si hay un token guardado, muestra la app directamente sin pedir login.
 * También registra atajos de teclado globales.
 */
document.addEventListener('DOMContentLoaded', () => {
  // Si ya hay sesión guardada, mostrar la app directamente
  if (TOKEN) {
    currentUser = { username: 'admin', role: 'admin' };
    showApp();
    loadSection('dashboard');
  }

  // Atajos de teclado globales
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();  // ESC cierra el modal abierto
    // Enter en la pantalla de login envía el formulario
    if (e.key === 'Enter' && document.getElementById('login-screen').style.display !== 'none') {
      doLogin();
    }
  });
});
