"""A small admin UI at /ui: connections, saved queries and an ad-hoc SQL runner.

Self-contained (no build step, no external script or stylesheet - unlike /docs, which needs the real
Swagger UI library, this page is simple enough to write by hand). It is a client of the existing JSON API
only; there is no server-side logic here beyond serving this one static page. Query results are always
rendered through DOM APIs (createElement/textContent), never innerHTML, so a value coming back from a
database can never execute as markup.
"""

UI_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>SQL2API</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font-family: system-ui, sans-serif; font-size: 14px; }
  header { display: flex; align-items: center; gap: 16px; padding: 10px 16px; border-bottom: 1px solid #8884;
           flex-wrap: wrap; }
  header h1 { font-size: 18px; margin: 0; }
  header nav a { margin-right: 12px; }
  #key-bar { margin-left: auto; display: flex; align-items: center; gap: 6px; }
  #key-bar input { width: 220px; padding: 4px; }
  #tabs { display: flex; gap: 4px; padding: 8px 16px 0; border-bottom: 1px solid #8884; }
  #tabs button { border: 1px solid #8884; border-bottom: none; background: none; padding: 8px 14px;
                border-radius: 6px 6px 0 0; cursor: pointer; font: inherit; }
  #tabs button.active { border-bottom: 2px solid #4a90d9; font-weight: 600; }
  main { padding: 16px; max-width: 1100px; }
  section { display: none; }
  section.active { display: block; }
  table { border-collapse: collapse; width: 100%; margin: 10px 0; }
  th, td { border: 1px solid #8884; padding: 6px 8px; text-align: left; vertical-align: top; }
  th { background: #8881; }
  form.card, div.card { border: 1px solid #8884; border-radius: 6px; padding: 12px; margin: 10px 0; max-width: 640px; }
  form.card label, div.card label { display: block; margin: 8px 0 2px; font-weight: 600; }
  input, select, textarea { font: inherit; padding: 5px; width: 100%; box-sizing: border-box; }
  textarea { font-family: ui-monospace, monospace; min-height: 90px; }
  button { font: inherit; padding: 6px 12px; cursor: pointer; }
  button.primary { background: #4a90d9; color: #fff; border: 1px solid #4a90d9; border-radius: 4px; }
  button.danger { color: #c0392b; }
  button.link { border: none; background: none; text-decoration: underline; cursor: pointer; padding: 0 6px; }
  .row { display: flex; gap: 8px; align-items: end; flex-wrap: wrap; }
  .row > * { flex: 1; min-width: 120px; }
  .muted { opacity: .7; font-size: 12px; }
  #error-banner { display: none; background: #c0392b; color: #fff; padding: 8px 16px; }
  pre { background: #8881; padding: 10px; overflow: auto; white-space: pre-wrap; word-break: break-word; }
  .status-line { margin: 6px 0; font-size: 12px; opacity: .8; }
</style></head>
<body>
<div id="error-banner"></div>
<header>
  <h1>SQL2API</h1>
  <nav><a href="openapi.json">OpenAPI</a><a href="docs">API docs</a></nav>
  <div id="key-bar">
    <label for="key" class="muted">API key</label>
    <input id="key" type="password" autocomplete="off" placeholder="X-API-Key (kept for this tab only)">
    <button id="save-key">Apply</button>
  </div>
</header>
<div id="tabs">
  <button data-tab="connections" class="active">Connections</button>
  <button data-tab="queries">Saved Queries</button>
  <button data-tab="run">Run SQL</button>
</div>
<main>
  <section id="tab-connections" class="active">
    <button id="new-connection">+ New connection</button>
    <div id="connection-form-slot"></div>
    <div id="connections-table"></div>
  </section>

  <section id="tab-queries">
    <button id="new-query">+ New saved query</button>
    <div id="query-form-slot"></div>
    <div id="queries-table"></div>
  </section>

  <section id="tab-run">
    <form class="card" id="run-form">
      <label for="run-connection">Connection</label>
      <select id="run-connection" required></select>
      <label for="run-sql">SQL</label>
      <textarea id="run-sql" required placeholder="SELECT * FROM t WHERE id = :id"></textarea>
      <label for="run-params">Bound parameters (JSON object, optional)</label>
      <textarea id="run-params" placeholder='{"id": 1}'></textarea>
      <div class="row">
        <div><label for="run-format">Format</label>
          <select id="run-format">
            <option value="json">json</option><option value="ndjson">ndjson</option>
            <option value="csv">csv</option><option value="tsv">tsv</option>
            <option value="xml">xml</option><option value="yaml">yaml</option><option value="xlsx">xlsx</option>
          </select></div>
        <div><label for="run-page">Page</label><input id="run-page" type="number" min="1" value="1"></div>
        <div><label for="run-page-size">Page size</label>
          <input id="run-page-size" type="number" min="1" value="10"></div>
        <div><label for="run-timeout">Timeout (s, optional)</label>
          <input id="run-timeout" type="number" min="0" step="any"></div>
      </div>
      <p><button type="submit" class="primary">Run</button></p>
    </form>
    <div class="status-line" id="run-status"></div>
    <div id="run-results"></div>
  </section>
</main>
<footer style="padding:16px; opacity:.6; font-size:12px;">
  <span id="version"></span>
</footer>
<script>
'use strict';

// ---- tiny DOM builder: every text value goes through textContent, never innerHTML, so a value that
// came back from a database can never be interpreted as markup. -----------------------------------
function h(tag, attrs) {
  var node = document.createElement(tag);
  attrs = attrs || {};
  Object.keys(attrs).forEach(function (k) {
    var v = attrs[k];
    if (v === null || v === undefined) return;
    if (k === 'text') node.textContent = v;
    else if (k.slice(0, 2) === 'on') node[k] = v;
    else if (k === 'className') node.className = v;
    else node.setAttribute(k, v);
  });
  function append(child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) { child.forEach(append); return; }
    // a plain string becomes a text node (never markup), so callers can mix text with element children
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  for (var i = 2; i < arguments.length; i++) append(arguments[i]);
  return node;
}
function clear(node) { node.textContent = ''; return node; }

// ---- API key (per-tab only, same storage key /docs uses, so entering it once covers both pages) --
function getKey() { try { return sessionStorage.getItem('sql2api-key') || ''; } catch (e) { return ''; } }
function setKey(v) { try { sessionStorage.setItem('sql2api-key', v); } catch (e) {} }

function showError(message) {
  var banner = document.getElementById('error-banner');
  banner.textContent = message;
  banner.style.display = message ? 'block' : 'none';
}

async function apiFetch(path, opts) {
  opts = opts || {};
  var headers = Object.assign({}, opts.headers || {});
  var key = getKey();
  if (key) headers['X-API-Key'] = key;
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.json);
  }
  return fetch(path, { method: opts.method || 'GET', headers: headers, body: opts.body });
}

/** Call a JSON endpoint; on failure, show the server's error and return null. */
async function apiJson(path, opts) {
  showError('');
  var res;
  try {
    res = await apiFetch(path, opts);
  } catch (e) {
    showError('Network error: ' + e.message);
    return null;
  }
  var text = await res.text();
  var body = null;
  try { body = text ? JSON.parse(text) : null; } catch (e) { /* not JSON, e.g. an HTML error page */ }
  if (!res.ok) {
    showError((body && body.error) || ('HTTP ' + res.status));
    return null;
  }
  return body;
}

// ---- tabs -------------------------------------------------------------------------------------
document.querySelectorAll('#tabs button').forEach(function (btn) {
  btn.onclick = function () {
    document.querySelectorAll('#tabs button').forEach(function (b) { b.classList.remove('active'); });
    document.querySelectorAll('main > section').forEach(function (s) { s.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  };
});

document.getElementById('key').value = getKey();
document.getElementById('save-key').onclick = function () {
  setKey(document.getElementById('key').value);
  showError('');
  refreshAll();
};

// ---- connections --------------------------------------------------------------------------------
var DB_TYPES = ['mysql', 'postgres', 'clickhouse', 'sqlite', 'h2']; // mirrors config.SUPPORTED_DB_TYPES
var PASSWORD_MASK = '********'; // mirrors config.PASSWORD_MASK; sending it back unchanged keeps the stored password
var connectionsCache = {};

function connectionField(id, label, type, value) {
  return h('div', {}, h('label', { for: id, text: label }),
          h('input', { id: id, type: type || 'text', value: value === undefined ? '' : value }));
}

function openConnectionForm(name, existing) {
  var slot = clear(document.getElementById('connection-form-slot'));
  existing = existing || {};
  var isEdit = !!name;
  var nameInput = h('input', { id: 'c-name', value: name || '', disabled: isEdit ? 'disabled' : null });
  var dbSelect = h('select', { id: 'c-db' }, DB_TYPES.map(function (t) {
    return h('option', { value: t, text: t, selected: t === existing.db ? 'selected' : null });
  }));
  var form = h('form', { className: 'card', onsubmit: function (e) {
    e.preventDefault();
    saveConnection(name, {
      db: dbSelect.value,
      host: document.getElementById('c-host').value || undefined,
      port: document.getElementById('c-port').value ? Number(document.getElementById('c-port').value) : undefined,
      user: document.getElementById('c-user').value || undefined,
      password: document.getElementById('c-password').value,
      database: document.getElementById('c-database').value || undefined,
      active: document.getElementById('c-active').checked,
    }, nameInput.value.trim());
  } },
    h('label', { for: 'c-name', text: 'Name' }), nameInput,
    h('label', { for: 'c-db', text: 'Database type' }), dbSelect,
    connectionField('c-host', 'Host', 'text', existing.host),
    connectionField('c-port', 'Port', 'number', existing.port),
    connectionField('c-user', 'User', 'text', existing.user),
    connectionField('c-password', 'Password' + (isEdit ? ' (leave as-is to keep the current one)' : ''), 'password',
                    isEdit ? PASSWORD_MASK : ''),
    connectionField('c-database', 'Database / file path', 'text', existing.database),
    h('label', {}, h('input', { id: 'c-active', type: 'checkbox', style: 'width:auto',
                               checked: existing.active !== false ? 'checked' : null }), ' Active'),
    h('p', {}, h('button', { type: 'submit', className: 'primary', text: isEdit ? 'Save' : 'Create' }),
             h('button', { type: 'button', text: 'Cancel', onclick: function () { clear(slot); } })));
  slot.appendChild(form);
}
document.getElementById('new-connection').onclick = function () { openConnectionForm(null, {}); };

async function saveConnection(originalName, details, newName) {
  var name = originalName || newName;
  if (!name) { showError('A connection name is required.'); return; }
  var body = {};
  body[name] = details;
  var res = await apiJson('connections', { method: 'PATCH', json: { connections: body } });
  if (res) { clear(document.getElementById('connection-form-slot')); loadConnections(); }
}

async function deleteConnection(name) {
  if (!confirm("Delete connection '" + name + "'?")) return;
  var res = await apiJson('connections/' + encodeURIComponent(name), { method: 'DELETE' });
  if (res) loadConnections();
}

async function loadConnections() {
  var data = await apiJson('connections');
  var container = clear(document.getElementById('connections-table'));
  if (!data) return;
  connectionsCache = data.connections || {};
  populateConnectionSelect();
  var names = Object.keys(connectionsCache).sort();
  if (!names.length) { container.appendChild(h('p', { className: 'muted', text: 'No connections yet.' })); return; }
  var rows = names.map(function (name) {
    var c = connectionsCache[name];
    var editBtn = h('button', { className: 'link', text: 'Edit',
                              onclick: function () { openConnectionForm(name, c); } });
    var delBtn = h('button', { className: 'link danger', text: 'Delete',
                              onclick: function () { deleteConnection(name); } });
    return h('tr', {},
      h('td', { text: name }), h('td', { text: c.db }), h('td', { text: c.host || '' }),
      h('td', { text: c.database || '' }), h('td', { text: c.active ? 'yes' : 'no' }),
      h('td', {}, editBtn, delBtn));
  });
  var headings = ['Name', 'Type', 'Host', 'Database', 'Active', ''];
  container.appendChild(h('table', {},
    h('thead', {}, h('tr', {}, headings.map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, rows)));
}

function populateConnectionSelect() {
  var select = document.getElementById('run-connection');
  var current = select.value;
  clear(select);
  Object.keys(connectionsCache).sort().forEach(function (name) {
    select.appendChild(h('option', { value: name, text: name }));
  });
  if (Object.keys(connectionsCache).indexOf(current) !== -1) select.value = current;
}

// ---- saved queries --------------------------------------------------------------------------------
function openQueryForm() {
  var slot = clear(document.getElementById('query-form-slot'));
  var form = h('form', { className: 'card', onsubmit: function (e) {
    e.preventDefault();
    saveQuery();
  } },
    h('label', { for: 'q-filename', text: 'Filename' }), h('input', { id: 'q-filename', required: 'required' }),
    h('label', { for: 'q-sql', text: 'SQL (use :name for bound parameters)' }),
    h('textarea', { id: 'q-sql', required: 'required', placeholder: 'SELECT * FROM t WHERE id = :id' }),
    h('label', { for: 'q-author', text: 'Author' }), h('input', { id: 'q-author', required: 'required' }),
    h('label', { for: 'q-description', text: 'Description' }),
    h('input', { id: 'q-description', required: 'required' }),
    h('label', { for: 'q-tags', text: 'Tags (comma-separated, optional)' }), h('input', { id: 'q-tags' }),
    h('label', { for: 'q-connection', text: 'Default connection (optional)' }),
    h('select', { id: 'q-connection' }, [h('option', { value: '', text: '(none - must be given at run time)' })]
      .concat(Object.keys(connectionsCache).sort().map(function (n) { return h('option', { value: n, text: n }); }))),
    h('label', { for: 'q-params', text: 'query_parameters (JSON object, optional)' }),
    h('textarea', { id: 'q-params', placeholder: '{"id": {"type": "int", "min": 1}}' }),
    h('p', {}, h('button', { type: 'submit', className: 'primary', text: 'Save' }),
             h('button', { type: 'button', text: 'Cancel', onclick: function () { clear(slot); } })));
  slot.appendChild(form);
}
document.getElementById('new-query').onclick = openQueryForm;

async function saveQuery() {
  var paramsText = document.getElementById('q-params').value.trim();
  var queryParameters = {};
  if (paramsText) {
    try { queryParameters = JSON.parse(paramsText); }
    catch (e) { showError('query_parameters is not valid JSON: ' + e.message); return; }
  }
  var tags = document.getElementById('q-tags').value.split(',').map(function (t) { return t.trim(); })
    .filter(Boolean);
  var res = await apiJson('save_sql_to_file', { method: 'PATCH', json: {
    filename: document.getElementById('q-filename').value,
    sql_query: document.getElementById('q-sql').value,
    author: document.getElementById('q-author').value,
    description: document.getElementById('q-description').value,
    tags: tags,
    connection_name: document.getElementById('q-connection').value || undefined,
    query_parameters: queryParameters,
  } });
  if (res) { clear(document.getElementById('query-form-slot')); loadQueries(); }
}

async function deleteQuery(name) {
  if (!confirm("Delete saved query '" + name + "' (all versions)?")) return;
  var res = await apiJson('saved_sql/' + encodeURIComponent(name), { method: 'DELETE' });
  if (res) loadQueries();
}

async function viewQuery(name, container) {
  var data = await apiJson('view_file_content?filename=' + encodeURIComponent(name));
  clear(container);
  if (data) container.appendChild(h('pre', { text: data.content }));
}

/** The saved query's declared parameters, read from the OpenAPI catalogue (keeps one source of truth
 * with the server - see sql2api/app.py:describe_saved_queries - instead of re-deriving it here). */
async function fetchQueryParameters(name) {
  var spec = await apiJson('openapi.json');
  if (!spec) return [];
  var op = spec.paths && spec.paths['/q/' + encodeURIComponent(name)];
  return (op && op.get && op.get.parameters || []).filter(function (p) {
    return ['format', 'page', 'page_size', 'version', 'connection_name', 'timeout'].indexOf(p.name) === -1;
  });
}

async function openRunForm(name, container) {
  clear(container);
  var params = await fetchQueryParameters(name);
  var inputs = {};
  var fields = params.map(function (p) {
    var input = h('input', { id: 'run-q-' + p.name, placeholder: p.schema && p.schema.default !== undefined
      ? 'default: ' + p.schema.default : '', required: p.required ? 'required' : null });
    inputs[p.name] = input;
    return h('div', {}, h('label', { text: p.name + (p.required ? ' *' : '') }), input);
  });
  var formatSelect = h('select', {}, ['json', 'csv', 'tsv', 'xml', 'yaml', 'ndjson', 'xlsx'].map(function (f) {
    return h('option', { value: f, text: f });
  }));
  var resultsBox = h('div');
  var statusBox = h('div', { className: 'status-line' });
  var page = 1;
  function run() {
    var query = params.map(function (p) {
      var v = inputs[p.name].value;
      return v ? encodeURIComponent(p.name) + '=' + encodeURIComponent(v) : null;
    }).filter(Boolean);
    query.push('format=' + formatSelect.value, 'page=' + page);
    apiFetch('q/' + encodeURIComponent(name) + '?' + query.join('&')).then(function (res) {
      return renderResponse(res, resultsBox, statusBox, function () { page += 1; run(); });
    });
  }
  var runBtn = h('button', { type: 'button', className: 'primary', text: 'Run',
                            onclick: function () { page = 1; run(); } });
  container.appendChild(h('div', { className: 'card' }, fields,
    h('label', { text: 'Format' }), formatSelect, h('p', {}, runBtn), statusBox, resultsBox));
}

async function loadQueries() {
  var data = await apiJson('list_files');
  var container = clear(document.getElementById('queries-table'));
  if (!data) return;
  var files = data.files || [];
  if (!files.length) { container.appendChild(h('p', { className: 'muted', text: 'No saved queries yet.' })); return; }
  var rows = files.map(function (f) {
    var latest = f.versions[f.versions.length - 1] || {};
    var detail = h('td', { colspan: '6' });
    var detailRow = h('tr', {}, detail);
    detailRow.style.display = 'none';
    var row = h('tr', {},
      h('td', { text: f.filename }), h('td', { text: String(latest.version || '') }),
      h('td', { text: latest.description || '' }),
      h('td', { text: (latest.tags || []).join(', ') }),
      h('td', { text: latest.connection_name || '' }),
      h('td', {},
        h('button', { className: 'link', text: 'Run', onclick: function () {
          detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
          if (detailRow.style.display !== 'none') openRunForm(f.filename, clear(detail));
        } }),
        h('button', { className: 'link', text: 'View', onclick: function () {
          detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
          if (detailRow.style.display !== 'none') viewQuery(f.filename, clear(detail));
        } }),
        h('button', { className: 'link danger', text: 'Delete', onclick: function () { deleteQuery(f.filename); } })));
    return [row, detailRow];
  });
  container.appendChild(h('table', {},
    h('thead', {}, h('tr', {}, ['Filename', 'Latest v.', 'Description', 'Tags', 'Connection', ''].map(function (t) {
      return h('th', { text: t });
    }))),
    h('tbody', {}, [].concat.apply([], rows))));
}

// ---- shared result rendering (used by both "Saved Queries" run panels and "Run SQL") --------------
async function renderResponse(res, container, statusBox, onNext) {
  showError('');
  clear(container);
  if (statusBox) clear(statusBox);
  var contentType = (res.headers.get('content-type') || '').split(';')[0].trim();
  if (!res.ok) {
    var text = await res.text();
    try { showError(JSON.parse(text).error || text); } catch (e) { showError(text || ('HTTP ' + res.status)); }
    return;
  }
  if (contentType === 'application/json') {
    var data = await res.json();
    if (Array.isArray(data)) renderTable(container, data);
    else container.appendChild(h('pre', { text: JSON.stringify(data, null, 2) }));
  } else if (contentType.indexOf('text/') === 0 || contentType === 'application/xml'
            || contentType === 'application/x-yaml' || contentType === 'application/x-ndjson') {
    container.appendChild(h('pre', { text: await res.text() }));
  } else {
    var blob = await res.blob();
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'result.xlsx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    container.appendChild(h('p', { className: 'muted', text: 'Download started.' }));
  }
  if (statusBox) {
    var page = res.headers.get('x-page'), hasMore = res.headers.get('x-has-more') === 'true';
    var line = page ? h('span', { text: 'Page ' + page + (hasMore ? ' - more available' : '') }) : null;
    statusBox.appendChild(h('span', {}, line,
      hasMore && onNext ? h('button', { className: 'link', text: 'Next page', onclick: onNext }) : null));
  }
}

function renderTable(container, rows) {
  if (!rows.length) { container.appendChild(h('p', { className: 'muted', text: 'No rows returned.' })); return; }
  var cols = Object.keys(rows[0]);
  container.appendChild(h('table', {},
    h('thead', {}, h('tr', {}, cols.map(function (c) { return h('th', { text: c }); }))),
    h('tbody', {}, rows.map(function (row) {
      return h('tr', {}, cols.map(function (c) {
        var v = row[c];
        return h('td', { text: v === null || v === undefined ? '' : String(v) });
      }));
    }))));
}

// ---- run SQL tab ------------------------------------------------------------------------------
var runPage = 1;
document.getElementById('run-form').onsubmit = function (e) {
  e.preventDefault();
  runPage = Number(document.getElementById('run-page').value) || 1;
  runSql();
};
function runSql() {
  var paramsText = document.getElementById('run-params').value.trim();
  var params = {};
  if (paramsText) {
    try { params = JSON.parse(paramsText); }
    catch (e) { showError('Bound parameters must be valid JSON: ' + e.message); return; }
  }
  var format = document.getElementById('run-format').value;
  var pageSize = document.getElementById('run-page-size').value || 10;
  var timeout = document.getElementById('run-timeout').value;
  var qs = 'format=' + format + '&page=' + runPage + '&page_size=' + pageSize + (timeout ? '&timeout=' + timeout : '');
  apiFetch('execute_sql?' + qs, { method: 'POST', json: {
    sql: document.getElementById('run-sql').value,
    connection_name: document.getElementById('run-connection').value,
    params: params,
  } }).then(function (res) {
    return renderResponse(res, document.getElementById('run-results'), document.getElementById('run-status'),
                          function () { runPage += 1; runSql(); });
  });
}

// ---- startup ------------------------------------------------------------------------------------
function refreshAll() {
  loadConnections();
  loadQueries();
}
apiJson('health').then(function (info) {
  if (info) document.getElementById('version').textContent = 'sql2api ' + info.version;
});
refreshAll();
</script>
</body></html>
"""
