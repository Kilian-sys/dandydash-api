'use strict';

// ══════════════════════════════════════════════════════════════════
// IMPORT.JS — Importación masiva de usuarios desde fichero CSV
//
// Flujo de importación:
//   1. El admin selecciona un fichero .csv
//   2. Se parsea y muestra una previsualización de los usuarios
//   3. Al confirmar, se crean los usuarios uno a uno via API
//   4. Para cada usuario creado, se añade al grupo si se especifica
//   5. Se muestra el progreso en tiempo real y el resumen final
//
// Formato del CSV:
//   username,password,first_name,last_name,email,group,ou,description,enabled
// ══════════════════════════════════════════════════════════════════


// ── ABRIR MODAL DE IMPORTACIÓN ────────────────────────────────────

/**
 * openImportCSV — Abre el modal con el formulario de importación CSV.
 * Muestra el formato requerido y permite seleccionar el fichero.
 */
function openImportCSV() {
  document.getElementById('modal-title').textContent = 'Importar usuarios desde CSV';
  document.getElementById('modal-body').innerHTML = `
    <!-- Descripción del formato CSV requerido -->
    <p style="font-size:13px;color:var(--muted);margin-bottom:10px">Cabecera requerida:</p>
    <code style="display:block;background:var(--bg);padding:8px 12px;border-radius:6px;
                 font-size:12px;margin-bottom:14px;color:var(--purple-light)">
      username,password,first_name,last_name,email,group,ou,description,enabled
    </code>

    <!-- Selector de fichero CSV -->
    <div class="field">
      <label>Fichero CSV</label>
      <input type="file" id="csv-file" accept=".csv"
        style="background:var(--bg);border:1px solid var(--border);border-radius:8px;
               padding:8px;color:var(--text);width:100%">
    </div>

    <!-- Área donde se mostrará la previsualización tras seleccionar el fichero -->
    <div id="csv-preview"></div>
  `;

  document.getElementById('modal-ok').style.display = '';
  document.getElementById('modal-ok').textContent = 'Importar todos';

  // Previsualizar el CSV cuando el usuario seleccione un fichero
  document.getElementById('csv-file').onchange = previewCSV;
  // Al hacer clic en Importar, iniciar el proceso de creación masiva
  document.getElementById('modal-ok').onclick = importCSV;

  openModal();
}


// ── PARSEAR CSV ───────────────────────────────────────────────────

/**
 * parseCSV — Convierte el texto de un fichero CSV en un array de objetos.
 * La primera línea se usa como cabecera para los nombres de los campos.
 * Filtra líneas vacías y registros sin nombre de usuario.
 *
 * @param {string} text - Contenido completo del fichero CSV como texto
 * @returns {Array<object>} - Array de objetos con un campo por columna
 */
function parseCSV(text) {
  // Dividir por líneas y eliminar líneas completamente vacías
  const lines = text.trim().split('\n').filter(l => l.trim());

  // La primera línea contiene los nombres de las columnas (normalizados a minúsculas)
  const headers = lines[0].split(',').map(h =>
    h.trim().toLowerCase().replace(/["\r]/g, '')  // Quitar comillas y retornos de carro
  );

  // Convertir cada línea de datos en un objeto usando los headers como claves
  return lines.slice(1).map(line => {
    const vals = line.split(',').map(v => v.trim().replace(/["\r]/g, ''));  // Valores limpios
    const obj = {};
    headers.forEach((h, i) => obj[h] = vals[i] || '');  // Asignar valor o cadena vacía
    return obj;
  }).filter(r => r.username);  // Ignorar filas sin nombre de usuario
}


// ── PREVISUALIZAR CSV ─────────────────────────────────────────────

/**
 * previewCSV — Parsea el fichero seleccionado y muestra una tabla
 * con los usuarios que se van a importar, para que el admin pueda
 * verificar los datos antes de confirmar.
 */
function previewCSV() {
  const file = document.getElementById('csv-file').files[0];
  if (!file) return;  // No hacer nada si no hay fichero seleccionado

  const reader = new FileReader();
  reader.onload = e => {
    const rows = parseCSV(e.target.result);
    const prev = document.getElementById('csv-preview');

    // Mensaje de error si el CSV está vacío o tiene formato incorrecto
    if (!rows.length) {
      prev.innerHTML = '<p style="color:var(--red);font-size:13px">CSV vacío o formato incorrecto.</p>';
      return;
    }

    // Tabla de previsualización con los usuarios encontrados
    prev.innerHTML = `
      <p style="font-size:12px;color:var(--muted);margin-bottom:8px">
        ${rows.length} usuarios encontrados:
      </p>
      <div class="table-wrap" style="max-height:180px;overflow-y:auto">
        <table>
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Nombre</th>
              <th>Email</th>
              <th>Grupo</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td>${esc(r.username)}</td>
                <td>${esc((r.first_name + ' ' + r.last_name).trim() || '-')}</td>
                <td>${esc(r.email || '-')}</td>
                <td>${esc(r.group || '-')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  };
  reader.readAsText(file);  // Leer el fichero como texto
}


// ── IMPORTAR USUARIOS ─────────────────────────────────────────────

/**
 * importCSV — Procesa el fichero CSV y crea los usuarios en el AD uno a uno.
 *
 * Para cada usuario:
 *   1. Llama a POST /api/users/ para crearlo
 *   2. Si tiene grupo asignado, lo añade al grupo (creándolo si no existe)
 *   3. Si tiene OU asignada, verifica que existe (creándola si es necesario)
 *   4. Actualiza el indicador de progreso en pantalla
 *
 * Al finalizar muestra un resumen con cuántos se crearon y cuáles fallaron.
 */
async function importCSV() {
  // Obtener el fichero seleccionado
  const file = document.getElementById('csv-file').files[0];
  if (!file) {
    showAlert('users', 'err', 'Selecciona un fichero CSV.');
    closeModal();
    return;
  }

  // Leer y parsear el CSV
  const text = await file.text();
  const rows = parseCSV(text);
  if (!rows.length) {
    showAlert('users', 'err', 'CSV vacío o formato incorrecto.');
    closeModal();
    return;
  }

  closeModal();  // Cerrar el modal de importación antes de empezar

  // ── Indicador de progreso ─────────────────────────────────────
  // Crear un elemento flotante verde que muestra el progreso en tiempo real
  const progressDiv = document.createElement('div');
  progressDiv.id = 'import-progress';
  progressDiv.style.cssText = `
    position:fixed; top:60px; right:20px; z-index:9999;
    padding:12px 20px; border-radius:8px; background:#48bb78;
    color:#fff; font-size:14px; font-family:Arial;
    box-shadow:0 4px 12px rgba(0,0,0,.3)
  `;
  progressDiv.textContent = `⏳ Importando 0/${rows.length}...`;
  document.body.appendChild(progressDiv);

  // Activar flag para evitar que un 401 durante la importación cierre la sesión
  window._importing = true;

  // ── Precargar datos de grupos y OUs ───────────────────────────
  // Se hace una sola vez antes del bucle para evitar llamadas repetidas a la API
  let grpData = null, ouData = null;
  try { grpData = await apiGet('/api/groups/'); } catch (e) { grpData = { groups: [] }; }
  try { ouData  = await apiGet('/api/ous/');    } catch (e) { ouData  = { ous: []    }; }

  // ── Bucle principal de importación ────────────────────────────
  let ok = 0;        // Contador de usuarios creados con éxito
  let errors = [];   // Lista de errores para el resumen final

  for (const row of rows) {
    // Actualizar el indicador de progreso con el usuario actual
    const pd = document.getElementById('import-progress');
    if (pd) pd.textContent = `⏳ Importando ${ok}/${rows.length}: ${row.username}`;

    try {
      // ── 1. Crear el usuario ─────────────────────────────────
      const r = await apiPost('/api/users/', {
        username:    row.username,
        password:    row.password,
        first_name:  row.first_name,
        last_name:   row.last_name,
        email:       row.email,
        description: row.description || ''
      });

      if (r?.message) {
        // Usuario creado correctamente
        ok++;

        // ── 2. Añadir al grupo si se ha especificado ──────────
        if (row.group) {
          // Verificar si el grupo ya existe en la lista precargada
          const grpExiste = (grpData?.groups || []).some(g => g.name === row.group);
          // Si no existe, crearlo antes de añadir al usuario
          if (!grpExiste) {
            await apiPost('/api/groups/', {
              name: row.group,
              description: 'Grupo creado al importar'
            });
          }
          // Añadir el usuario al grupo (encodeURIComponent por si el nombre tiene espacios)
          await apiPost(`/api/groups/${encodeURIComponent(row.group)}/members`, {
            username: row.username
          });
        }

        // ── 3. Verificar/crear OU si se ha especificado ───────
        if (row.ou) {
          // Verificar si la OU ya existe en la lista precargada
          const ouExiste = (ouData?.ous || []).some(o => o.name === row.ou);
          // Si no existe, crearla
          if (!ouExiste) {
            await apiPost('/api/ous/', {
              name: row.ou,
              description: 'OU creada al importar'
            }).catch(() => {});  // Ignorar errores de creación de OU (puede que ya exista)
          }
          // Nota: el movimiento del usuario a la OU se omite en importación masiva
          // por rendimiento — hacerlo manualmente si es necesario
        }

      } else {
        // La API devolvió un error al crear el usuario
        errors.push(`${row.username}: ${r?.error || 'error'}`);
      }

    } catch (err) {
      // Error inesperado (red, JSON inválido, etc.) — registrar y continuar
      console.error('Error importando', row.username, err);
      errors.push(`${row.username}: ${err.message}`);
    }
  }

  // ── Finalizar importación ──────────────────────────────────────
  window._importing = false;  // Desactivar flag de importación

  // Eliminar el indicador de progreso
  const pd2 = document.getElementById('import-progress');
  if (pd2) pd2.remove();

  // Mostrar resumen del resultado
  if (errors.length) {
    showAlert('users', 'err',
      `${ok} creados, ${errors.length} errores: ${errors.slice(0, 3).join(' | ')}`
    );
  } else {
    showAlert('users', 'ok', `✅ ${ok} usuarios importados correctamente.`);
  }

  renderUsers();  // Recargar la lista de usuarios con los nuevos
}
