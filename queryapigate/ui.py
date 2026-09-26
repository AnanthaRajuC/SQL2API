"""A small admin UI at /ui: connections, saved queries and an ad-hoc SQL runner.

Self-contained (no build step, no external script or stylesheet - unlike /docs, which needs the real
Swagger UI library, this page is simple enough to write by hand). It is a client of the existing JSON API
only; there is no server-side logic here beyond serving this one static page. Query results are always
rendered through DOM APIs (createElement/textContent), never innerHTML, so a value coming back from a
database can never execute as markup.
"""

UI_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>QueryAPIGate</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: light-dark(#f5f5f3, #131416);
    --surface: light-dark(#ffffff, #1a1b1e);
    --surface-2: light-dark(#f0f0ed, #212226);
    --surface-3: light-dark(#e8e8e4, #2a2b30);
    --line: light-dark(#e2e2de, #2b2c31);
    --line-strong: light-dark(#cdcdc8, #3a3b41);
    --ink: light-dark(#1b1c1f, #e7e7e4);
    --ink-2: light-dark(#56585e, #a6a7ac);
    --ink-3: light-dark(#85878d, #74767c);
    --accent: light-dark(oklch(0.52 0.11 170), oklch(0.78 0.11 170));
    --accent-ink: light-dark(#ffffff, #0c1714);
    --accent-soft: light-dark(oklch(0.52 0.11 170 / 0.1), oklch(0.78 0.11 170 / 0.13));
    --danger: light-dark(oklch(0.53 0.17 27), oklch(0.74 0.14 27));
    --danger-soft: light-dark(oklch(0.53 0.17 27 / 0.08), oklch(0.74 0.14 27 / 0.12));
    --warn: light-dark(oklch(0.6 0.13 75), oklch(0.8 0.12 80));
    --syn-kw: light-dark(oklch(0.48 0.14 265), oklch(0.78 0.1 265));
    --syn-str: light-dark(oklch(0.5 0.12 145), oklch(0.8 0.11 145));
    --syn-num: light-dark(oklch(0.55 0.13 55), oklch(0.8 0.11 65));
    --syn-param: light-dark(oklch(0.5 0.15 330), oklch(0.78 0.12 330));
    --syn-cmt: var(--ink-3);
    --shadow: light-dark(0 12px 40px rgb(0 0 0 / 0.12), 0 12px 40px rgb(0 0 0 / 0.5));
    --sans: system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html, body { height: 100%; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 13px/1.45 var(--sans); -webkit-font-smoothing: antialiased; }
  a { color: var(--ink-2); text-decoration: none; }
  a:hover { color: var(--accent); }
  code, .mono { font-family: var(--mono); font-size: 12px; }
  h2, h3 { margin: 0; font-weight: 600; letter-spacing: -0.005em; }
  ::selection { background: var(--accent-soft); }

  /* ---- top bar ---- */
  header.top { position: sticky; top: 0; z-index: 20; display: flex; align-items: stretch; gap: 16px; height: 48px;
    padding: 0 20px; background: var(--surface); border-bottom: 1px solid var(--line); }
  .brand { flex: none; display: flex; align-items: center; gap: 10px; }
  .wordmark { font: 700 13px/1 var(--mono); letter-spacing: 0.02em; }
  .wordmark b { color: var(--accent); font-weight: 700; }
  .health { display: inline-flex; align-items: center; gap: 6px; font: 11px/1 var(--mono); color: var(--ink-3);
    padding: 4px 7px; border: 1px solid var(--line); border-radius: 20px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-3); flex: none; display: inline-block; }
  .dot.ok { background: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  .dot.bad { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-soft); }
  .dot.off { background: transparent; border: 1.5px solid var(--ink-3); }
  /* When the header is tight, the tab row scrolls rather than squeezing the key bar off-screen. */
  #tabs { display: flex; align-items: stretch; gap: 2px; min-width: 0; overflow-x: auto; scrollbar-width: none; }
  #tabs button { position: relative; display: flex; align-items: center; gap: 7px; border: 0; background: none; padding: 0 9px;
    font: 500 13px var(--sans); color: var(--ink-2); cursor: pointer; white-space: nowrap; }
  #tabs button:hover { color: var(--ink); }
  #tabs button.active { color: var(--ink); }
  #tabs button.active::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: 0; height: 2px; background: var(--accent); border-radius: 2px 2px 0 0; }
  .count { font: 11px/1 var(--mono); color: var(--ink-3); background: var(--surface-2); padding: 3px 5px; border-radius: 4px; min-width: 18px; text-align: center; }
  .count:empty { display: none; }
  .top-end { flex: none; margin-left: auto; display: flex; align-items: center; gap: 14px; }
  .top-end > a { font-size: 12.5px; white-space: nowrap; }
  .chip { font: 11px/1 var(--mono); color: var(--ink-2); padding: 5px 7px; border-radius: 4px; background: var(--surface-2); white-space: nowrap; }
  .chip.low { color: var(--danger); background: var(--danger-soft); }
  #key-bar { flex: none; display: flex; align-items: center; gap: 0; border: 1px solid var(--line-strong); border-radius: 6px; background: var(--bg); height: 30px; overflow: hidden; }
  #key-bar label { font-size: 11.5px; color: var(--ink-3); padding: 0 4px 0 9px; white-space: nowrap; display: flex; align-items: center; gap: 6px; }
  #key-bar input { border: 0; background: transparent; width: 150px; height: 28px; padding: 0 6px; font: 12px var(--mono); color: var(--ink); outline: none; }
  #key-bar button { border: 0; border-left: 1px solid var(--line-strong); height: 100%; padding: 0 10px; background: var(--surface); font: 500 12px var(--sans); color: var(--ink); cursor: pointer; }
  #key-bar button:hover { background: var(--surface-2); }
  #key-bar:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }

  /* ---- error banner ---- */
  #error-banner { position: sticky; top: 48px; z-index: 19; background: var(--danger-soft); border-bottom: 1px solid var(--danger);
    color: var(--ink); padding: 9px 20px; backdrop-filter: blur(8px); background-color: light-dark(#fbeeed, #2a1a1a); }
  .eb-main { display: flex; align-items: baseline; gap: 10px; }
  .eb-code { font: 600 11px/1 var(--mono); color: var(--accent-ink); background: var(--danger); padding: 3px 6px; border-radius: 4px; }
  .eb-msg { flex: 1; font-weight: 500; overflow-wrap: anywhere; }
  .eb-close { border: 0; background: none; color: var(--ink-2); font-size: 16px; line-height: 1; cursor: pointer; padding: 0 2px; }
  .eb-fields { margin: 6px 0 0; padding: 0 0 0 0; list-style: none; display: flex; flex-direction: column; gap: 2px; font-size: 12.5px; color: var(--ink-2); }
  .eb-fields code { color: var(--danger); }

  /* ---- layout ---- */
  main { padding: 20px 20px 48px; max-width: 1480px; margin: 0 auto; }
  main > section { display: none; }
  main > section.active { display: block; }
  .toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .toolbar h2 { font-size: 15px; }
  .toolbar .sub { color: var(--ink-3); font-size: 12.5px; }
  .spacer { flex: 1; }
  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
  .search { height: 30px; width: 220px; padding: 0 9px; }
  .toolbar select { width: auto; }
  #connections-table, #apikeys-table, #roles-table, #auditlog-table { overflow-x: auto; }

  /* ---- controls ---- */
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 30px; padding: 0 12px;
    border: 1px solid var(--line-strong); border-radius: 6px; background: var(--surface); color: var(--ink);
    font: 500 12.5px var(--sans); cursor: pointer; white-space: nowrap; }
  .btn:hover { background: var(--surface-2); }
  .btn:disabled { opacity: 0.45; cursor: default; }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
  .btn.primary:hover { filter: brightness(1.06); }
  .btn.danger { color: var(--danger); }
  .btn.danger:hover { background: var(--danger-soft); border-color: var(--danger); }
  .btn.ghost { border-color: transparent; background: transparent; }
  .btn.ghost:hover { background: var(--surface-2); }
  .btn.sm { height: 24px; padding: 0 8px; font-size: 12px; border-radius: 5px; }
  .btn.icon { width: 30px; padding: 0; font-size: 17px; }
  kbd { font: 10.5px/1 var(--mono); padding: 2px 4px; border-radius: 3px; border: 1px solid currentColor; opacity: 0.7; }
  input, select, textarea { font: 13px var(--sans); color: var(--ink); background: var(--surface); border: 1px solid var(--line-strong);
    border-radius: 6px; padding: 0 9px; height: 30px; width: 100%; min-width: 0; }
  textarea { height: auto; padding: 8px 9px; font: 12.5px/1.5 var(--mono); resize: vertical; min-height: 84px; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  input:disabled { background: var(--surface-2); color: var(--ink-2); }
  input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); margin: 0; }
  input[type=number] { font-family: var(--mono); font-size: 12.5px; }
  input::placeholder, textarea::placeholder { color: var(--ink-3); }
  .field { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
  .field > label { font-size: 12px; font-weight: 500; color: var(--ink-2); display: flex; gap: 6px; align-items: baseline; }
  .field > label .req { color: var(--danger); }
  .field > label .type { font: 11px var(--mono); color: var(--ink-3); font-weight: 400; }
  .hint { font-size: 11.5px; color: var(--ink-3); }
  .grid2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
  .grid-host { display: grid; grid-template-columns: minmax(0, 1fr) 96px; gap: 12px; }
  .password-field { display: flex; align-items: center; gap: 6px; min-width: 0; }
  .password-field input { min-width: 0; }

  /* ---- tables ---- */
  table.grid { width: 100%; border-collapse: separate; border-spacing: 0; }
  table.grid th { position: sticky; top: 0; z-index: 1; text-align: left; font: 600 11px var(--sans); letter-spacing: 0.03em; text-transform: uppercase;
    color: var(--ink-3); background: var(--surface); padding: 8px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }
  table.grid td { padding: 7px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  table.grid tbody tr:last-child td { border-bottom: 0; }
  table.grid tbody tr:hover td { background: var(--surface-2); }
  .actions { display: flex; gap: 2px; justify-content: flex-end; opacity: 0.55; }
  tr:hover .actions, .actions:focus-within { opacity: 1; }
  .tag { display: inline-block; font: 11px/1.5 var(--mono); padding: 0 6px; border-radius: 4px; background: var(--surface-2); border: 1px solid var(--line); color: var(--ink-2); white-space: nowrap; }
  .tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .name { font: 600 12.5px var(--mono); }
  .dim { color: var(--ink-3); }
  .empty { padding: 44px 20px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--ink-2); }
  .empty strong { color: var(--ink); font-size: 14px; font-weight: 600; }
  .loading { padding: 28px 16px; color: var(--ink-3); display: flex; align-items: center; gap: 10px; justify-content: center; }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--line-strong); border-top-color: var(--accent); animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ---- saved queries ---- */
  .split { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 16px; align-items: start; }
  #queries-table { position: sticky; top: 64px; max-height: calc(100vh - 140px); overflow: auto; }
  .qitem { display: flex; flex-direction: column; gap: 3px; width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--line);
    background: none; color: inherit; font: inherit; padding: 10px 14px; cursor: pointer; border-left: 2px solid transparent; }
  .qitem:last-child { border-bottom: 0; }
  .qitem:hover { background: var(--surface-2); }
  .qitem.sel { background: var(--accent-soft); border-left-color: var(--accent); }
  .qi-top { display: flex; align-items: center; gap: 7px; min-width: 0; }
  .qi-top .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .qi-conn { margin-left: auto; font: 11px var(--mono); color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 45%; }
  .qi-desc { color: var(--ink-2); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .qgroup { display: flex; flex-direction: column; padding: 3px 8px 3px 10px; background: var(--surface-2); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 1; }
  .qg-meta { display: flex; align-items: center; gap: 4px; padding: 0 0 3px 16px; margin-left: -6px; }
  .qg-toggle { display: flex; align-items: center; gap: 6px; min-width: 0; border: 0; background: none; color: var(--ink-2); font: 600 11.5px var(--sans); text-transform: uppercase; letter-spacing: 0.04em; cursor: pointer; padding: 5px 0; text-align: left; }
  .qg-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .qg-reach { font-size: 11px; color: var(--ink-3); white-space: nowrap; margin-right: 4px; }
  .tag.coll { border-style: dashed; }
  .tag.example { border-color: var(--accent); color: var(--accent); margin-left: 6px; }
  #examples-strip { display: flex; align-items: center; gap: 10px; padding: 8px 12px; margin-bottom: 12px; font-size: 12.5px; color: var(--ink-2); }
  #examples-strip[hidden] { display: none; }
  .impact { display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface-2); }
  .detail { min-height: 360px; }
  .d-head { padding: 16px 18px 0; display: flex; flex-direction: column; gap: 10px; }
  .d-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .d-title h3 { font: 600 16px var(--mono); }
  .d-desc { color: var(--ink-2); margin: 0; text-wrap: pretty; }
  .versions { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden; }
  .versions button { border: 0; border-right: 1px solid var(--line-strong); background: var(--surface); color: var(--ink-2); font: 500 11.5px var(--mono);
    padding: 0 9px; height: 24px; cursor: pointer; }
  .versions button:last-child { border-right: 0; }
  .versions button:hover { background: var(--surface-2); }
  .versions button.on { background: var(--ink); color: var(--surface); }
  .meta { display: flex; flex-wrap: wrap; gap: 4px 20px; font-size: 12px; color: var(--ink-3); margin: 0; }
  .meta div { display: flex; gap: 6px; }
  .meta dt { color: var(--ink-3); }
  .meta dd { margin: 0; color: var(--ink); font-family: var(--mono); font-size: 11.5px; }
  .subtabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin: 0 -18px; padding: 0 12px; }
  .subtabs button { border: 0; background: none; font: 500 12.5px var(--sans); color: var(--ink-2); padding: 9px 8px; cursor: pointer; position: relative; display: flex; gap: 6px; align-items: center; }
  .subtabs button.on { color: var(--ink); }
  .subtabs button.on::after { content: ""; position: absolute; left: 6px; right: 6px; bottom: -1px; height: 2px; background: var(--ink); }
  .d-body { padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 14px; }
  .param-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
  .run-row { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
  .run-row .field { width: 150px; }
  .sub-h { font-size: 11px; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase; color: var(--ink-3); margin: 0; }
  .history-list { display: flex; flex-direction: column; gap: 2px; margin-top: 6px; max-height: 140px; overflow: auto; }
  .history-item { border: 0; background: none; color: var(--ink-2); font: 11.5px var(--mono); text-align: left; padding: 4px 6px; border-radius: 4px;
    cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .history-item:hover { background: var(--surface-2); color: var(--ink); }

  /* ---- SQL editor (hand-rolled highlighting: a <pre> painted behind a transparent <textarea>) ---- */
  .editor { position: relative; min-height: 220px; height: 260px; resize: vertical; overflow: hidden; background: var(--surface); }
  .editor .hl, .editor textarea { position: absolute; inset: 0; margin: 0; padding: 12px 14px; border: 0; border-radius: 0;
    font: 13px/1.6 var(--mono); tab-size: 2; white-space: pre; overflow: auto; letter-spacing: 0; }
  .editor .hl { pointer-events: none; color: var(--ink); overflow: hidden; }
  .editor textarea { color: transparent; caret-color: var(--ink); background: transparent; resize: none; min-height: 0; height: 100%; }
  .editor textarea:focus { box-shadow: none; }
  .editor textarea::selection { background: light-dark(oklch(0.52 0.11 170 / 0.22), oklch(0.78 0.11 170 / 0.25)); color: transparent; }
  .editor.boxed { border: 1px solid var(--line-strong); border-radius: 6px; height: 170px; min-height: 120px; }
  .editor.boxed:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  .code { margin: 0; padding: 12px 14px; font: 12.5px/1.6 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2);
    border: 1px solid var(--line); border-radius: 6px; max-height: 420px; overflow: auto; }
  .k { color: var(--syn-kw); font-weight: 600; }
  .s { color: var(--syn-str); }
  .n { color: var(--syn-num); }
  .p { color: var(--syn-param); font-weight: 600; }
  .c { color: var(--syn-cmt); font-style: italic; }

  /* ---- run SQL tab ---- */
  .runner { display: grid; grid-template-columns: minmax(0, 1fr) 280px; overflow: hidden; }
  .runner-main { display: flex; flex-direction: column; min-width: 0; border-right: 1px solid var(--line); }
  .runner-bar { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--line); background: var(--surface); flex-wrap: wrap; }
  .runner-bar select { width: auto; height: 28px; font-size: 12.5px; }
  .runner-bar .lbl { font-size: 11.5px; color: var(--ink-3); }
  .runner-side { padding: 12px; display: flex; flex-direction: column; gap: 12px; background: var(--surface); }
  .runner-side textarea { min-height: 96px; }
  .runner-side .grid2 input { height: 28px; }
  .refs { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; min-height: 18px; }

  /* ---- schema browser (click a table/column to insert it into the nearest SQL editor) ---- */
  .schema-browser { max-height: 220px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }
  .schema-browser .hint, .schema-browser .loading { padding: 9px 10px; }
  .schema-row { display: flex; align-items: center; gap: 0; }
  .schema-caret { flex: none; width: 20px; height: 26px; padding: 0; border: 0; background: none; color: var(--ink-3); font-size: 9px; cursor: pointer; }
  .schema-caret:hover { color: var(--ink); }
  .schema-table { flex: 1; display: flex; align-items: center; gap: 6px; min-width: 0; border: 0; background: none; color: inherit; font: inherit;
    text-align: left; padding: 4px 6px 4px 0; cursor: pointer; }
  .schema-table:hover { background: var(--surface-2); }
  .schema-preview { flex: none; width: 22px; height: 26px; padding: 0; border: 0; background: none; color: var(--ink-3); font-size: 9px; cursor: pointer; }
  .schema-preview:hover { color: var(--accent); }
  .schema-table .name { font: 600 12px var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .schema-cols { display: flex; flex-direction: column; padding-left: 22px; }
  .schema-col { display: flex; justify-content: space-between; gap: 8px; border: 0; background: none; color: inherit; font: 12px var(--mono);
    text-align: left; padding: 3px 6px; cursor: pointer; }
  .schema-col:hover { background: var(--surface-2); }

  /* ---- results ---- */
  .results { margin-top: 14px; }
  .results:empty { display: none; }
  .resbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 7px 10px; border-bottom: 1px solid var(--line); font-size: 12px; color: var(--ink-2); }
  .resbar:empty { display: none; }
  .resbar .stat { font: 11.5px var(--mono); color: var(--ink-2); display: flex; gap: 12px; align-items: center; }
  .resbar .stat b { color: var(--ink); font-weight: 600; }
  .resbar .stat b.stat-ok { color: var(--accent); }
  .pager { display: flex; align-items: center; gap: 4px; }
  .pager input { width: 52px; height: 24px; text-align: center; padding: 0 4px; }
  .pager select { width: auto; height: 24px; font-size: 12px; padding: 0 4px; }
  .res-body:empty { display: none; }
  .table-wrap { max-height: 62vh; overflow: auto; }
  table.rs { border-collapse: separate; border-spacing: 0; font: 12.5px/1.4 var(--mono); min-width: 100%; }
  table.rs th { position: sticky; top: 0; z-index: 1; background: var(--surface-2); text-align: left; font-weight: 600; color: var(--ink);
    padding: 6px 12px; border-bottom: 1px solid var(--line-strong); border-right: 1px solid var(--line); white-space: nowrap; }
  table.rs td { padding: 5px 12px; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line); white-space: nowrap;
    max-width: 380px; overflow: hidden; text-overflow: ellipsis; }
  table.rs tr:hover td { background: var(--accent-soft); }
  table.rs .rn { color: var(--ink-3); text-align: right; background: var(--surface); position: sticky; left: 0; font-size: 11px; padding: 5px 8px; }
  table.rs th.rn { z-index: 2; background: var(--surface-2); }
  table.rs .num { text-align: right; font-variant-numeric: tabular-nums; }
  table.rs .null { color: var(--ink-3); font-style: italic; font-size: 11px; }
  .res-pre { margin: 0; padding: 12px 14px; font: 12.5px/1.55 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 62vh; overflow: auto; }
  .res-note { padding: 22px 16px; color: var(--ink-2); display: flex; align-items: center; gap: 10px; justify-content: center; }
  .res-note.err { color: var(--danger); }

  /* ---- response headers panel ---- */
  .headers-panel { margin: 0 14px 12px; overflow: auto; max-height: 200px; }
  .headers-panel td { font-size: 11.5px; padding: 5px 10px; }
  .headers-panel td:first-child { color: var(--ink-3); white-space: nowrap; }
  .headers-panel td:last-child { overflow-wrap: anywhere; }

  /* ---- quick chart (current page only) ---- */
  .chart-panel { margin: 0 14px 12px; padding: 10px 12px; }
  .chart-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
  .chart-toolbar select { font: 11.5px var(--mono); background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 6px; padding: 3px 6px; }
  .chart-svg-slot svg { width: 100%; height: auto; display: block; }
  .chart-bar { fill: var(--accent); }
  .chart-bar:hover { opacity: 0.75; }
  .chart-axis { stroke: var(--line); stroke-width: 1; }
  .chart-label { font: 10px var(--mono); fill: var(--ink-3); }
  .chart-label-x { text-anchor: middle; }
  .chart-label-y { text-anchor: start; }

  /* ---- metrics tab ---- */
  .stat-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 14px; }
  .stat-tile { padding: 12px 14px; }
  .stat-tile .label { font-size: 11px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 4px; }
  .stat-tile .value { font: 600 22px var(--mono); color: var(--ink); }
  .stat-tile .value.warn { color: var(--danger); }
  .metrics-charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; margin-bottom: 14px; }
  .metrics-charts .chart-panel { margin: 0; }

  /* ---- collapsible JSON tree (non-tabular responses) ---- */
  .jt-root { padding: 12px 14px; max-height: 62vh; overflow: auto; }
  .jt-head { display: inline-flex; align-items: center; gap: 2px; }
  .jt-toggle { border: 0; background: none; color: var(--ink-3); font-size: 9px; cursor: pointer; padding: 0 3px; width: 16px; flex: none; }
  .jt-toggle:hover { color: var(--ink); }
  .jt-children { padding-left: 18px; border-left: 1px solid var(--line); margin-left: 6px; }
  .jt-item { display: flex; gap: 4px; align-items: flex-start; }
  .jt-key { color: var(--syn-param); flex: none; }
  .jt-punct { color: var(--ink-3); }
  .jt-str { color: var(--syn-str); overflow-wrap: anywhere; }
  .jt-num { color: var(--syn-num); }
  .jt-null { color: var(--ink-3); font-style: italic; }

  /* ---- drawer ---- */
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.28); z-index: 40; }
  .drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(500px, 100%); z-index: 41; background: var(--surface); border-left: 1px solid var(--line);
    box-shadow: var(--shadow); display: flex; flex-direction: column; transform: translateX(102%); transition: transform 0.18s ease; visibility: hidden; }
  .drawer.open { transform: none; visibility: visible; }
  .drawer-head { display: flex; align-items: flex-start; gap: 10px; padding: 16px 18px 14px; border-bottom: 1px solid var(--line); }
  .drawer-head h3 { font-size: 15px; }
  .kicker { font: 11px var(--mono); color: var(--ink-3); margin-bottom: 3px; }
  .kicker:empty { display: none; }
  .drawer-body { flex: 1; overflow: auto; }
  .form { display: flex; flex-direction: column; gap: 14px; padding: 18px; min-height: 100%; }
  .form-actions { position: sticky; bottom: 0; margin: auto -18px -18px; padding: 12px 18px; background: var(--surface); border-top: 1px solid var(--line); display: flex; gap: 8px; justify-content: flex-end; }
  .switch { display: flex; align-items: center; gap: 8px; font-weight: 500; font-size: 12.5px; cursor: pointer; }

  /* ---- toast ---- */
  #toasts { position: fixed; right: 20px; bottom: 20px; z-index: 60; display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
  .toast { background: var(--ink); color: var(--surface); padding: 8px 12px; border-radius: 6px; font-size: 12.5px; box-shadow: var(--shadow); transition: opacity 0.3s; }

  footer { padding: 0 20px 24px; color: var(--ink-3); font-size: 11.5px; max-width: 1480px; margin: 0 auto; }

  /* The header needs ~1320px on one row with every tab and two-digit counts on them; below 1360px (a little slack for
     a three-digit count) it drops the tabs onto a second row instead of clipping the last one. */
  @media (max-width: 1360px) {
    header.top { height: auto; flex-wrap: wrap; gap: 8px 16px; padding: 8px 14px; }
    #tabs { order: 3; width: 100%; height: 36px; margin: 0 -12px; }
    .top-end { flex: 1 1 auto; min-width: 0; flex-wrap: wrap; }
    #error-banner { top: 0; position: relative; }
  }
  @media (max-width: 980px) {
    main { padding: 14px; }
    .split, .runner { grid-template-columns: minmax(0, 1fr); }
    #queries-table { position: static; max-height: 280px; }
    .runner-main { border-right: 0; border-bottom: 1px solid var(--line); }
    .hide-sm { display: none; }
  }
</style></head>
<body>
<header class="top">
  <div class="brand">
    <span class="wordmark">Query<b>API</b>Gate</span>
    <span class="health" id="health" title="GET /health"><span class="dot" id="health-dot"></span><span id="version">…</span></span>
  </div>
  <nav id="tabs" role="tablist">
    <button type="button" role="tab" data-tab="connections" class="active">Connections <span class="count" id="count-connections"></span></button>
    <button type="button" role="tab" data-tab="queries">Saved Queries <span class="count" id="count-queries"></span></button>
    <button type="button" role="tab" data-tab="apikeys">API Keys <span class="count" id="count-apikeys"></span></button>
    <button type="button" role="tab" data-tab="roles">Roles <span class="count" id="count-roles"></span></button>
    <button type="button" role="tab" data-tab="auditlog">Audit Log</button>
    <button type="button" role="tab" data-tab="metrics">Metrics</button>
    <button type="button" role="tab" data-tab="run">Run SQL</button>
  </nav>
  <div class="top-end">
    <span class="chip" id="rate" hidden title="X-RateLimit-Remaining / X-RateLimit-Limit"></span>
    <a href="docs">API docs</a>
    <a href="openapi.json">OpenAPI</a>
    <form id="key-bar" autocomplete="off">
      <label for="key"><span class="dot off" id="key-dot"></span>API key</label>
      <input id="key" type="password" autocomplete="off" placeholder="X-API-Key · this tab only">
      <button id="save-key" type="submit">Apply</button>
    </form>
  </div>
</header>
<div id="error-banner" role="alert" hidden></div>

<main>
  <section id="tab-connections" class="active">
    <div class="toolbar">
      <h2>Connections</h2>
      <span class="sub" id="connections-sub"></span>
      <span class="spacer"></span>
      <input id="conn-filter" class="search" type="search" placeholder="Filter by name, type, host…">
      <button id="new-connection" type="button" class="btn primary">New connection</button>
    </div>
    <div id="connections-table" class="panel"><div class="loading"><span class="spin"></span>Loading connections…</div></div>
  </section>

  <section id="tab-queries">
    <div id="examples-strip" class="panel" hidden></div>
    <div class="toolbar">
      <h2>Saved queries</h2>
      <span class="sub" id="queries-sub"></span>
      <span class="spacer"></span>
      <input id="query-filter" class="search" type="search" placeholder="Filter by name, description, tag…">
      <button id="new-collection" type="button" class="btn">New collection</button>
      <button id="new-query" type="button" class="btn primary">New saved query</button>
    </div>
    <div class="split">
      <div id="queries-table" class="panel"><div class="loading"><span class="spin"></span>Loading…</div></div>
      <div id="query-detail" class="panel detail"><div class="empty"><strong>No query selected</strong><span>Pick a saved query to run it, read its SQL or see its history.</span></div></div>
    </div>
  </section>

  <section id="tab-apikeys">
    <div class="toolbar">
      <h2>API keys</h2>
      <span class="sub" id="apikeys-sub"></span>
      <span class="spacer"></span>
      <button id="new-apikey" type="button" class="btn primary">New API key</button>
    </div>
    <div id="apikeys-table" class="panel"><div class="loading"><span class="spin"></span>Loading API keys…</div></div>
  </section>

  <section id="tab-roles">
    <div class="toolbar">
      <h2>Roles</h2>
      <span class="sub" id="roles-sub"></span>
      <span class="spacer"></span>
      <button id="new-role" type="button" class="btn primary">New role</button>
    </div>
    <div id="roles-table" class="panel"><div class="loading"><span class="spin"></span>Loading roles…</div></div>
  </section>

  <section id="tab-auditlog">
    <div class="toolbar">
      <h2>Audit log</h2>
      <span class="sub" id="auditlog-sub"></span>
      <span class="spacer"></span>
      <select id="auditlog-action-filter"><option value="">All actions</option></select>
      <input id="auditlog-filter" class="search" type="search" placeholder="Filter by actor, target, time…">
      <button id="refresh-auditlog" type="button" class="btn ghost">Refresh</button>
    </div>
    <div id="auditlog-table" class="panel"><div class="loading"><span class="spin"></span>Loading audit log…</div></div>
  </section>

  <section id="tab-metrics">
    <div class="toolbar">
      <h2>Metrics</h2>
      <span class="sub">Live totals since this process started - no history, no trends. For that, scrape
        <code>/metrics</code> with Prometheus and import the bundled Grafana dashboard.</span>
      <span class="spacer"></span>
      <button id="refresh-metrics" type="button" class="btn ghost">Refresh</button>
    </div>
    <div id="metrics-body"><div class="loading"><span class="spin"></span>Loading metrics…</div></div>
  </section>

  <section id="tab-run">
    <form id="run-form" class="panel runner" novalidate>
      <div class="runner-main">
        <div class="runner-bar">
          <span class="lbl">Connection</span>
          <select id="run-connection" required aria-label="Connection"></select>
          <span class="lbl">Format</span>
          <select id="run-format" aria-label="Format">
            <option value="json">json</option><option value="ndjson">ndjson</option>
            <option value="csv">csv</option><option value="tsv">tsv</option>
            <option value="xml">xml</option><option value="yaml">yaml</option><option value="xlsx">xlsx</option>
          </select>
          <span class="spacer"></span>
          <span class="hint hide-sm"><kbd>Ctrl</kbd> <kbd>Enter</kbd></span>
          <button type="button" class="btn ghost" id="run-explain-button" title="Run EXPLAIN on this query">Explain</button>
          <button type="submit" class="btn primary" id="run-button">Run</button>
        </div>
        <div class="editor" id="run-editor">
          <pre class="hl" id="run-sql-hl" aria-hidden="true"></pre>
          <textarea id="run-sql" required spellcheck="false" wrap="off" autocomplete="off" aria-label="SQL" placeholder="SELECT * FROM t WHERE id = :id"></textarea>
        </div>
      </div>
      <div class="runner-side">
        <div id="run-history-slot"></div>
        <div class="field">
          <label for="run-params">Bound parameters <span class="type">JSON</span></label>
          <textarea id="run-params" spellcheck="false" placeholder='{"id": 1}'></textarea>
          <div class="refs" id="run-refs"></div>
        </div>
        <div class="grid2">
          <div class="field"><label for="run-page">Page</label><input id="run-page" type="number" min="1" value="1"></div>
          <div class="field"><label for="run-page-size">Page size</label><input id="run-page-size" type="number" min="1" value="10"></div>
        </div>
        <div class="field"><label for="run-timeout">Timeout <span class="type">seconds, optional</span></label><input id="run-timeout" type="number" min="0" step="any" placeholder="server default"></div>
        <div id="run-schema-slot"></div>
      </div>
    </form>
    <div class="panel results" id="run-results-panel">
      <div class="resbar" id="run-status"></div>
      <div class="res-body" id="run-results"></div>
    </div>
  </section>
</main>
<footer><span id="footer-note">Every request is sent to this server’s JSON API with the key above.</span></footer>

<div class="backdrop" id="drawer-backdrop" hidden></div>
<aside class="drawer" id="drawer" aria-hidden="true" role="dialog" aria-labelledby="drawer-title">
  <div class="drawer-head">
    <div><div class="kicker" id="drawer-kicker"></div><h3 id="drawer-title"></h3></div>
    <span class="spacer"></span>
    <button type="button" class="btn ghost icon" id="drawer-close" aria-label="Close">×</button>
  </div>
  <div class="drawer-body">
    <div id="connection-form-slot"></div>
    <div id="query-form-slot"></div>
    <div id="apikey-form-slot"></div>
    <div id="role-form-slot"></div>
  </div>
</aside>
<div id="toasts" aria-live="polite"></div>

<script>
'use strict';

// ---- DOM builder: every value goes through textContent / createTextNode / setAttribute, never as markup. ----
function h(tag, attrs) {
  var node = document.createElement(tag);
  attrs = attrs || {};
  Object.keys(attrs).forEach(function (k) {
    var v = attrs[k];
    if (v === null || v === undefined || v === false) return;
    if (k === 'text') node.textContent = v;
    else if (k.slice(0, 2) === 'on') node[k] = v;
    else if (k === 'className') node.className = v;
    else if (k === 'value') node.value = v;
    else node.setAttribute(k, v === true ? '' : v);
  });
  function append(child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) { child.forEach(append); return; }
    node.appendChild(typeof child === 'string' || typeof child === 'number' ? document.createTextNode(String(child)) : child);
  }
  for (var i = 2; i < arguments.length; i++) append(arguments[i]);
  return node;
}
function clear(node) { node.textContent = ''; return node; }
function $(id) { return document.getElementById(id); }
function enc(s) { return encodeURIComponent(s); }
function loadingNode(text) { return h('div', { className: 'loading' }, h('span', { className: 'spin' }), text || 'Loading…'); }

// ---- API key: per-tab, same sessionStorage key /docs uses ----
function getKey() { try { return sessionStorage.getItem('queryapigate-key') || ''; } catch (e) { return ''; } }
function setKey(v) { try { sessionStorage.setItem('queryapigate-key', v); } catch (e) {} }
function paintKeyState() { $('key-dot').className = 'dot ' + (getKey() ? 'ok' : 'off'); }

// ---- feedback ----
function showError(message, detail) {
  var banner = clear($('error-banner'));
  if (!message) { banner.hidden = true; return; }
  detail = detail || {};
  var fields = detail.errors && typeof detail.errors === 'object' ? Object.keys(detail.errors) : [];
  banner.appendChild(h('div', { className: 'eb-main' },
    detail.status ? h('span', { className: 'eb-code', text: String(detail.status) }) : null,
    h('span', { className: 'eb-msg', text: String(message) }),
    h('button', { type: 'button', className: 'eb-close', 'aria-label': 'Dismiss', text: '×', onclick: function () { showError(''); } })));
  if (fields.length) {
    banner.appendChild(h('ul', { className: 'eb-fields' }, fields.map(function (f) {
      return h('li', {}, h('code', { text: f }), ' — ', String(detail.errors[f]));
    })));
  }
  banner.hidden = false;
}
function errorMessage(status, body, text) {
  var msg = (body && body.error) || text || ('HTTP ' + status);
  if (status === 401 && !getKey()) msg += ' — enter an API key in the top bar.';
  return msg;
}
function toast(msg) {
  var t = h('div', { className: 'toast', text: msg });
  $('toasts').appendChild(t);
  setTimeout(function () { t.style.opacity = '0'; }, 2200);
  setTimeout(function () { t.remove(); }, 2600);
}
function noteRate(res) {
  var limit = res.headers.get('x-ratelimit-limit'), left = res.headers.get('x-ratelimit-remaining');
  if (limit === null || left === null) return;
  var chip = $('rate');
  chip.textContent = 'rate ' + left + '/' + limit;
  chip.className = 'chip' + (Number(left) <= Math.max(1, Number(limit) * 0.1) ? ' low' : '');
  chip.hidden = false;
}

// ---- API ----
async function apiFetch(path, opts) {
  opts = opts || {};
  var headers = Object.assign({}, opts.headers || {});
  var key = getKey();
  if (key) headers['X-API-Key'] = key;
  var body = opts.body;
  if (opts.json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.json); }
  var res = await fetch(path, { method: opts.method || 'GET', headers: headers, body: body });
  noteRate(res);
  return res;
}
/** Call a JSON endpoint; on failure show the server's error and return null. */
async function apiJson(path, opts) {
  var res;
  try { res = await apiFetch(path, opts); }
  catch (e) { showError('Network error: ' + e.message); return null; }
  var text = await res.text(), body = null;
  try { body = text ? JSON.parse(text) : null; } catch (e) { /* not JSON */ }
  if (!res.ok) { showError(errorMessage(res.status, body, ''), { status: res.status, errors: body && body.errors }); return null; }
  return body;
}

// ---- tabs ----
function showTab(name) {
  document.querySelectorAll('#tabs button').forEach(function (b) {
    var on = b.dataset.tab === name;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  document.querySelectorAll('main > section').forEach(function (s) { s.classList.toggle('active', s.id === 'tab-' + name); });
  try { sessionStorage.setItem('queryapigate-ui-tab', name); } catch (e) {}
}
document.querySelectorAll('#tabs button').forEach(function (btn) { btn.onclick = function () { showTab(btn.dataset.tab); }; });

$('key').value = getKey();
paintKeyState();
$('key-bar').onsubmit = function (e) {
  e.preventDefault();
  setKey($('key').value);
  paintKeyState();
  showError('');
  toast($('key').value ? 'API key applied to this tab' : 'API key cleared');
  refreshAll();
};

// ---- drawer (hosts the connection and saved-query forms) ----
function openDrawer(slotId, title, kicker) {
  clear($('connection-form-slot')); clear($('query-form-slot')); clear($('apikey-form-slot')); clear($('role-form-slot'));
  $('drawer-title').textContent = title;
  $('drawer-kicker').textContent = kicker || '';
  $('drawer').classList.add('open');
  $('drawer').setAttribute('aria-hidden', 'false');
  $('drawer-backdrop').hidden = false;
  return $(slotId);
}
function closeDrawer() {
  $('drawer').classList.remove('open');
  $('drawer').setAttribute('aria-hidden', 'true');
  $('drawer-backdrop').hidden = true;
  clear($('connection-form-slot')); clear($('query-form-slot')); clear($('apikey-form-slot')); clear($('role-form-slot'));
}
$('drawer-close').onclick = closeDrawer;
$('drawer-backdrop').onclick = closeDrawer;
document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && $('drawer').classList.contains('open')) closeDrawer(); });
function field(id, label, input, hint, extra) {
  return h('div', { className: 'field' }, h('label', { for: id }, label, extra || null), input,
    hint ? h('div', { className: 'hint', text: hint }) : null);
}
function formActions(submitText, onCancel) {
  var submit = h('button', { type: 'submit', className: 'btn primary', text: submitText });
  return { node: h('div', { className: 'form-actions' }, h('button', { type: 'button', className: 'btn', text: 'Cancel', onclick: onCancel }), submit), submit: submit };
}

// ---- SQL highlighting (tokens become spans via textContent) ----
var SQL_KW = {};
('select from where and or not in is null as join left right inner outer full cross on using group by order having limit offset union ' +
 'all distinct insert into values update set delete create table view index drop alter with recursive case when then else end asc desc ' +
 'like ilike between exists returning primary key default top fetch next rows only over partition window count sum avg min max ' +
 'coalesce cast true false interval date timestamp extract filter lateral intersect except nulls first last')
  .split(' ').forEach(function (w) { SQL_KW[w] = true; });
var SQL_TOKEN = /(--[^\n]*|\/\*[\s\S]*?(?:\*\/|$))|('(?:[^']|'')*'?)|("(?:[^"]|"")*"?|`[^`]*`?)|(::)|(:[A-Za-z_]\w*)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)/g;
function highlightInto(target, sql) {
  var frag = document.createDocumentFragment(), last = 0, m;
  SQL_TOKEN.lastIndex = 0;
  function span(cls, text) { var s = document.createElement('span'); s.className = cls; s.textContent = text; frag.appendChild(s); }
  while ((m = SQL_TOKEN.exec(sql))) {
    if (m.index > last) frag.appendChild(document.createTextNode(sql.slice(last, m.index)));
    if (m[1]) span('c', m[1]);
    else if (m[2]) span('s', m[2]);
    else if (m[5]) span('p', m[5]);
    else if (m[6]) span('n', m[6]);
    else if (m[7] && SQL_KW[m[7].toLowerCase()]) span('k', m[7]);
    else frag.appendChild(document.createTextNode(m[0]));
    last = SQL_TOKEN.lastIndex;
  }
  if (last < sql.length) frag.appendChild(document.createTextNode(sql.slice(last)));
  clear(target).appendChild(frag);
  return target;
}
function sqlParams(sql) {
  var seen = {}, out = [], m;
  SQL_TOKEN.lastIndex = 0;
  while ((m = SQL_TOKEN.exec(sql))) if (m[5] && !seen[m[5]]) { seen[m[5]] = true; out.push(m[5].slice(1)); }
  return out;
}
function bindEditor(textarea, pre, onChange) {
  function paint() {
    highlightInto(pre, textarea.value + '\n');
    pre.scrollTop = textarea.scrollTop; pre.scrollLeft = textarea.scrollLeft;
    if (onChange) onChange(textarea.value);
  }
  textarea.addEventListener('input', paint);
  textarea.addEventListener('scroll', function () { pre.scrollTop = textarea.scrollTop; pre.scrollLeft = textarea.scrollLeft; });
  textarea.addEventListener('keydown', function (e) {
    if (e.key === 'Tab' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      var s = textarea.selectionStart, en = textarea.selectionEnd;
      textarea.value = textarea.value.slice(0, s) + '  ' + textarea.value.slice(en);
      textarea.selectionStart = textarea.selectionEnd = s + 2;
      paint();
    }
  });
  textarea.repaint = paint;
  paint();
}
function makeEditor(attrs, value) {
  var ta = h('textarea', Object.assign({ spellcheck: 'false', wrap: 'off', autocomplete: 'off' }, attrs));
  ta.value = value || '';
  var pre = h('pre', { className: 'hl', 'aria-hidden': 'true' });
  var wrap = h('div', { className: 'editor boxed' }, pre, ta);
  bindEditor(ta, pre);
  return wrap;
}

// ---- schema browser: click a table or column to insert its name into a SQL editor ----
function insertAtCursor(textarea, text) {
  var start = textarea.selectionStart, end = textarea.selectionEnd;
  textarea.value = textarea.value.slice(0, start) + text + textarea.value.slice(end);
  var pos = start + text.length;
  textarea.selectionStart = textarea.selectionEnd = pos;
  textarea.focus();
  if (textarea.repaint) textarea.repaint();
}
var schemaCache = {}; // connection name -> {status: 'loading'|'ready'|'error', tables, truncated, message}
async function loadSchema(name, onDone) {
  schemaCache[name] = { status: 'loading' };
  var res;
  try { res = await apiFetch('connections/' + enc(name) + '/schema'); }
  catch (e) { schemaCache[name] = { status: 'error', message: 'Network error: ' + e.message }; onDone(); return; }
  if (!res.ok) {
    var body = null;
    try { body = await res.json(); } catch (e) {}
    schemaCache[name] = { status: 'error', message: (body && body.error) || ('HTTP ' + res.status) };
    onDone();
    return;
  }
  var data = await res.json();
  schemaCache[name] = { status: 'ready', tables: data.tables || [], truncated: !!data.truncated };
  onDone();
}
/** A self-contained, connection-aware schema tree. `insertFn(text)` is called with a table or column name
 * when the caller clicks one - errors (an unsupported connection type, no permission, ...) render inline
 * rather than through the page-wide error banner, since browsing the schema is optional, not the action the
 * user took. */
function schemaBrowser(insertFn, previewFn) {
  var box = h('div', { className: 'schema-browser' });
  var current = null;
  function paint() {
    clear(box);
    if (!current) { box.appendChild(h('div', { className: 'hint', text: 'Pick a connection to browse its schema.' })); return; }
    var entry = schemaCache[current];
    if (!entry) { loadSchema(current, paint); entry = { status: 'loading' }; }
    if (entry.status === 'loading') { box.appendChild(loadingNode('Loading schema…')); return; }
    if (entry.status === 'error') { box.appendChild(h('div', { className: 'hint', text: entry.message })); return; }
    if (!entry.tables.length) { box.appendChild(h('div', { className: 'hint', text: 'No tables found.' })); return; }
    entry.tables.forEach(function (t) {
      var colsBox = h('div', { className: 'schema-cols', hidden: true });
      var caret = h('button', { type: 'button', className: 'schema-caret', text: '▸', 'aria-label': 'Expand ' + t.name });
      caret.onclick = function () {
        var open = colsBox.hidden;
        colsBox.hidden = !open;
        caret.textContent = open ? '▾' : '▸';
        if (open && !colsBox.childNodes.length) {
          t.columns.forEach(function (c) {
            colsBox.appendChild(h('button', {
              type: 'button', className: 'schema-col', title: c.type + (c.nullable ? ' · nullable' : ' · not null'),
              onclick: function () { insertFn(c.name); }
            }, h('span', { text: c.name }), h('span', { className: 'dim', text: c.type })));
          });
        }
      };
      box.appendChild(h('div', { className: 'schema-row' }, caret,
        h('button', { type: 'button', className: 'schema-table', title: 'Insert ' + t.name, onclick: function () { insertFn(t.name); } },
          h('span', { className: 'name', text: t.name }), h('span', { className: 'tag', text: t.type })),
        previewFn ? h('button', { type: 'button', className: 'schema-preview', title: 'Preview ' + t.name + ' in Run SQL', 'aria-label': 'Preview ' + t.name,
          onclick: function () { previewFn(t.name); } }, '▶') : null));
      box.appendChild(colsBox);
    });
    if (entry.truncated) box.appendChild(h('div', { className: 'hint', text: 'Showing the first 5000 columns.' }));
  }
  paint();
  return {
    node: box,
    setConnection: function (name) { current = name || null; paint(); },
    refresh: function () { if (current) delete schemaCache[current]; paint(); }
  };
}
function schemaField(browser) {
  return field(null, 'Schema', browser.node, null,
    h('button', { type: 'button', className: 'btn ghost sm', text: '↻', title: 'Refresh', onclick: function () { browser.refresh(); } }));
}

// ---- connections ----
var DB_TYPES = ['mysql', 'postgres', 'clickhouse', 'sqlite', 'h2', 'duckdb']; // mirrors config.SUPPORTED_DB_TYPES
var PASSWORD_MASK = '********'; // mirrors config.PASSWORD_MASK; sending it back unchanged keeps the stored password
var connectionsCache = {};

function openConnectionForm(name, existing) {
  existing = existing || {};
  var isEdit = !!name;
  var slot = openDrawer('connection-form-slot', isEdit ? 'Edit connection' : 'New connection', isEdit ? name : 'PATCH /connections');
  function inp(id, type, value, ph) {
    return h('input', { id: id, type: type || 'text', value: value === undefined || value === null ? '' : String(value), placeholder: ph || null, autocomplete: 'off', spellcheck: 'false' });
  }
  function withRevealToggle(input) {
    var btn = h('button', { type: 'button', className: 'btn ghost sm', 'aria-label': 'Show password', text: 'Show' });
    btn.onclick = function () {
      var showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      btn.textContent = showing ? 'Show' : 'Hide';
      btn.setAttribute('aria-label', (showing ? 'Show' : 'Hide') + ' password');
    };
    return h('div', { className: 'password-field' }, input, btn);
  }
  var nameInput = inp('c-name', 'text', name || '', 'reporting-db');
  if (isEdit) nameInput.disabled = true;
  var dbSelect = h('select', { id: 'c-db' }, DB_TYPES.map(function (t) { return h('option', { value: t, text: t }); }));
  if (existing.db) dbSelect.value = existing.db;
  var active = h('input', { id: 'c-active', type: 'checkbox' });
  active.checked = existing.active !== false;
  var actions = formActions(isEdit ? 'Save' : 'Create', closeDrawer);
  var form = h('form', { className: 'form', novalidate: true, onsubmit: function (e) {
    e.preventDefault();
    var port = $('c-port').value;
    saveConnection(name, {
      db: dbSelect.value,
      host: $('c-host').value || undefined,
      port: port ? Number(port) : undefined,
      user: $('c-user').value || undefined,
      password: $('c-password').value,
      database: $('c-database').value || undefined,
      active: active.checked
    }, nameInput.value.trim(), actions.submit);
  } },
    field('c-name', 'Name', nameInput, isEdit ? 'Renaming isn’t supported — create a new connection instead.' : 'Referenced as connection_name by queries and the API.'),
    field('c-db', 'Database type', dbSelect),
    h('div', { className: 'grid-host' }, field('c-host', 'Host', inp('c-host', 'text', existing.host, 'localhost')),
      field('c-port', 'Port', inp('c-port', 'number', existing.port, ''))),
    h('div', { className: 'grid2' }, field('c-user', 'User', inp('c-user', 'text', existing.user, '')),
      field('c-password', 'Password', withRevealToggle(inp('c-password', 'password', isEdit ? (existing.password === undefined ? '' : existing.password) : '', '')),
        isEdit ? 'Leave the mask to keep the stored password.' : '${ENV_VAR} references are resolved on the server.')),
    field('c-database', 'Database / file path', inp('c-database', 'text', existing.database, 'SQLite, DuckDB and H2 take a file path'), null),
    h('label', { className: 'switch' }, active, 'Active', h('span', { className: 'hint', text: '— inactive connections refuse queries' })),
    actions.node);
  slot.appendChild(form);
  (isEdit ? $('c-host') : nameInput).focus();
}
$('new-connection').onclick = function () { openConnectionForm(null, {}); };

async function saveConnection(originalName, details, newName, btn) {
  var name = originalName || newName;
  if (!name) { showError('A connection name is required.', { errors: { name: 'This field is required' } }); $('c-name').focus(); return; }
  var body = {};
  body[name] = details;
  btn.disabled = true;
  var res = await apiJson('connections', { method: 'PATCH', json: { connections: body } });
  btn.disabled = false;
  if (res) { showError(''); closeDrawer(); toast((originalName ? 'Saved ' : 'Created ') + name); loadConnections(); }
}
async function deleteConnection(name) {
  if (!confirm("Delete connection '" + name + "'?")) return;
  var res = await apiJson('connections/' + enc(name), { method: 'DELETE' });
  if (res) { toast('Deleted ' + name); loadConnections(); }
}
async function loadConnections() {
  var data = await apiJson('connections');
  var box = $('connections-table');
  if (!data) {
    clear(box).appendChild(h('div', { className: 'empty' }, h('strong', { text: 'Couldn’t load connections' }),
      h('button', { type: 'button', className: 'btn sm', text: 'Retry', onclick: loadConnections })));
    return;
  }
  connectionsCache = data.connections || {};
  populateConnectionSelect();
  renderConnections();
}
// A key's usage has no avg_duration_ms (request/query latency isn't split by key - see metrics.py); a
// connection's does, since a connection has exactly one dialect and its latency histogram is keyed by it.
function usageCell(usage) {
  if (!usage || !usage.queries) return h('td', { className: 'dim', text: 'No activity yet' });
  var parts = [usage.queries + (usage.queries === 1 ? ' query' : ' queries')];
  if (usage.errors) parts.push(usage.errors + ' failed');
  if (usage.avg_duration_ms !== undefined && usage.avg_duration_ms !== null) parts.push(usage.avg_duration_ms + 'ms avg');
  var title = usage.rows + (usage.rows === 1 ? ' row' : ' rows') + ' returned in total · since this process started';
  return h('td', { title: title, text: parts.join(' · ') });
}
function renderConnections() {
  var box = clear($('connections-table'));
  var all = Object.keys(connectionsCache).sort();
  var activeCount = all.filter(function (n) { return connectionsCache[n].active; }).length;
  $('count-connections').textContent = all.length ? String(all.length) : '';
  $('connections-sub').textContent = all.length ? activeCount + ' active of ' + all.length : '';
  if (!all.length) {
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No connections yet' }),
      h('span', { text: 'Add a MySQL, PostgreSQL, ClickHouse, SQLite or H2 database to start running SQL.' }),
      h('button', { type: 'button', className: 'btn primary', text: 'New connection', onclick: function () { openConnectionForm(null, {}); } })));
    return;
  }
  var q = $('conn-filter').value.trim().toLowerCase();
  var names = all.filter(function (n) {
    var c = connectionsCache[n];
    return !q || [n, c.db, c.host, c.database, c.user].join(' ').toLowerCase().indexOf(q) !== -1;
  });
  if (!names.length) { box.appendChild(h('div', { className: 'empty' }, h('span', { text: 'No connections match “' + q + '”.' }))); return; }
  var rows = names.map(function (name) {
    var c = connectionsCache[name];
    var endpoint = c.host ? c.host + (c.port ? ':' + c.port : '') : '';
    return h('tr', {},
      h('td', { style: 'width:28px;padding-right:0' }, h('span', { className: 'dot ' + (c.active ? 'ok' : 'off'), title: c.active ? 'Active' : 'Inactive' })),
      h('td', {}, h('span', { className: 'name', text: name }), c.example ? exampleBadge() : null),
      h('td', {}, h('span', { className: 'tag', text: c.db || '?' })),
      h('td', { className: 'mono' }, endpoint || h('span', { className: 'dim', text: '—' })),
      h('td', { className: 'mono', text: c.database || '' }),
      h('td', { className: 'mono', text: c.user || '' }),
      h('td', { className: c.active ? '' : 'dim', text: c.active ? 'Active' : 'Inactive' }),
      usageCell(c.usage),
      h('td', {}, h('div', { className: 'actions' },
        h('button', { type: 'button', className: 'btn ghost sm', text: 'Query', disabled: !c.active, title: 'Open in Run SQL', onclick: function () {
          $('run-connection').value = name; showTab('run'); $('run-sql').focus(); } }),
        h('button', { type: 'button', className: 'btn ghost sm', text: 'Edit', onclick: function () { openConnectionForm(name, c); } }),
        h('button', { type: 'button', className: 'btn ghost sm danger', text: 'Delete', onclick: function () { deleteConnection(name); } }))));
  });
  box.appendChild(h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['', 'Name', 'Type', 'Host', 'Database', 'User', 'Status', 'Usage', ''].map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, rows)));
}
$('conn-filter').oninput = renderConnections;
function connectionOptions(select, includeBlank, blankText) {
  var current = select.value;
  clear(select);
  if (includeBlank) select.appendChild(h('option', { value: '', text: blankText }));
  Object.keys(connectionsCache).sort().forEach(function (name) {
    var c = connectionsCache[name];
    select.appendChild(h('option', { value: name, text: name + (c.active ? '' : ' (inactive)') }));
  });
  if (current && connectionsCache[current]) select.value = current;
}
function populateConnectionSelect() {
  var select = $('run-connection');
  var had = select.value;
  connectionOptions(select, false);
  if (!had) {
    var firstActive = Object.keys(connectionsCache).sort().filter(function (n) { return connectionsCache[n].active; })[0];
    if (firstActive) select.value = firstActive;
  }
  runSchema.setConnection(select.value);
}

// ---- API keys ----
// QUERYAPIGATE_API_KEY is a full-access admin key, unaffected by anything here. A scoped key created below is
// limited to the connections it's given (or every connection) and can be denied write access even when the
// server otherwise allows it - but only the admin key can reach this tab's endpoints at all, so a scoped
// key visiting /ui sees the same "couldn't load" state here as it does on Connections and Saved Queries.
var apiKeysCache = {};

async function loadApiKeys() {
  await loadCollections();
  var data = await apiJson('api_keys');
  var box = $('apikeys-table');
  if (!data) {
    apiKeysCache = {};
    $('count-apikeys').textContent = '';
    clear(box).appendChild(h('div', { className: 'empty' }, h('strong', { text: 'Couldn’t load API keys' }),
      h('span', { text: 'Only the admin key (QUERYAPIGATE_API_KEY) can manage API keys.' }),
      h('button', { type: 'button', className: 'btn sm', text: 'Retry', onclick: loadApiKeys })));
    return;
  }
  apiKeysCache = data.keys || {};
  renderApiKeys();
}
function renderApiKeys() {
  var box = clear($('apikeys-table'));
  var names = Object.keys(apiKeysCache).sort();
  $('count-apikeys').textContent = names.length ? String(names.length) : '';
  $('apikeys-sub').textContent = names.length ? names.length + (names.length === 1 ? ' key' : ' keys') : '';
  if (!names.length) {
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No scoped API keys yet' }),
      h('span', { text: 'QUERYAPIGATE_API_KEY is a full-access admin key. Create a scoped one to limit a caller to specific connections, read-only.' }),
      h('button', { type: 'button', className: 'btn primary', text: 'New API key', onclick: function () { openApiKeyForm(); } })));
    return;
  }
  var today = new Date().toISOString().slice(0, 10);
  var rows = names.map(function (name) {
    var k = apiKeysCache[name];
    var conns = k.connections === '*'
      ? h('span', { className: 'tag', text: 'all connections' })
      : h('div', { className: 'tags' }, (k.connections || []).length
          ? k.connections.map(function (c) { return h('span', { className: 'tag', text: c }); })
          : [h('span', { className: 'dim', text: 'none' })]);
    var queries = queryGrantNode(k);
    var expired = k.expires_at && k.expires_at < today;
    var expiry = k.expires_at
      ? h('span', { className: expired ? 'dim' : '', style: expired ? 'color:var(--danger)' : '', text: k.expires_at + (expired ? ' (expired)' : '') })
      : h('span', { className: 'dim', text: 'never' });
    var ips = (k.allowed_ips || []).length
      ? h('span', { title: k.allowed_ips.join(', '), text: k.allowed_ips.length + (k.allowed_ips.length === 1 ? ' IP' : ' IPs') })
      : h('span', { className: 'dim', text: 'any' });
    var writeOps = k.allow_writes && (k.allowed_write_ops || []).length;
    var access = !k.allow_writes
      ? h('td', { className: 'dim', text: 'Read-only' })
      : writeOps
        ? h('td', { title: k.allowed_write_ops.join(', '),
                   text: 'Read/write (' + k.allowed_write_ops.length + (k.allowed_write_ops.length === 1 ? ' op' : ' ops') + ')' })
        : h('td', { text: 'Read/write' });
    return h('tr', {},
      h('td', { style: 'width:28px;padding-right:0' }, h('span', { className: 'dot ' + (k.active && !expired ? 'ok' : 'off'), title: !k.active ? 'Revoked' : (expired ? 'Expired' : 'Active') })),
      h('td', {}, h('span', { className: 'name', text: name })),
      h('td', {}, conns),
      h('td', {}, queries),
      access,
      h('td', {}, expiry),
      h('td', { className: k.rate_limit ? 'mono' : 'mono dim', text: k.rate_limit || 'server default' }),
      h('td', {}, ips),
      h('td', { className: 'mono dim', text: k.created_at || '' }),
      h('td', { className: 'mono dim', text: k.last_used_at || 'never' }),
      usageCell(k.usage),
      h('td', {}, h('div', { className: 'actions' },
        h('button', { type: 'button', className: 'btn ghost sm', text: 'Edit', onclick: function () { openApiKeyForm(name, k); } }),
        h('button', { type: 'button', className: 'btn ghost sm danger', text: 'Revoke', onclick: function () { deleteApiKey(name); } }))));
  });
  box.appendChild(h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['', 'Name', 'Connections', 'Queries / collections', 'Access', 'Expires', 'Rate limit', 'IPs', 'Created', 'Last used', 'Usage', ''].map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, rows)));
}

// ---- roles ----
// A role is a reusable *template* for the grant fields below - copied onto a key once, at
// "create key from role" time. Editing or deleting a role afterward never touches a key already
// created from it; see the "Create from" picker in openApiKeyForm.
var rolesCache = {};

async function loadRoles() {
  await loadCollections();
  var data = await apiJson('roles');
  var box = $('roles-table');
  if (!data) {
    rolesCache = {};
    $('count-roles').textContent = '';
    clear(box).appendChild(h('div', { className: 'empty' }, h('strong', { text: 'Couldn’t load roles' }),
      h('span', { text: 'Only the admin key (QUERYAPIGATE_API_KEY) can manage roles.' }),
      h('button', { type: 'button', className: 'btn sm', text: 'Retry', onclick: loadRoles })));
    return;
  }
  rolesCache = data.roles || {};
  renderRoles();
}
function renderRoles() {
  var box = clear($('roles-table'));
  var names = Object.keys(rolesCache).sort();
  $('count-roles').textContent = names.length ? String(names.length) : '';
  $('roles-sub').textContent = names.length ? names.length + (names.length === 1 ? ' role' : ' roles') : '';
  if (!names.length) {
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No roles yet' }),
      h('span', { text: 'A role is a reusable template of connections, queries, write access, rate limit and allowed IPs — create an API key "from" a role instead of filling in every field by hand each time.' }),
      h('button', { type: 'button', className: 'btn primary', text: 'New role', onclick: function () { openRoleForm(); } })));
    return;
  }
  var rows = names.map(function (name) {
    var r = rolesCache[name];
    var conns = r.connections === '*'
      ? h('span', { className: 'tag', text: 'all connections' })
      : h('div', { className: 'tags' }, (r.connections || []).length
          ? r.connections.map(function (c) { return h('span', { className: 'tag', text: c }); })
          : [h('span', { className: 'dim', text: 'none' })]);
    var queries = queryGrantNode(r);
    var writeOps = r.allow_writes && (r.allowed_write_ops || []).length;
    var access = !r.allow_writes
      ? h('td', { className: 'dim', text: 'Read-only' })
      : writeOps
        ? h('td', { title: r.allowed_write_ops.join(', '),
                   text: 'Read/write (' + r.allowed_write_ops.length + (r.allowed_write_ops.length === 1 ? ' op' : ' ops') + ')' })
        : h('td', { text: 'Read/write' });
    var ips = (r.allowed_ips || []).length
      ? h('span', { title: r.allowed_ips.join(', '), text: r.allowed_ips.length + (r.allowed_ips.length === 1 ? ' IP' : ' IPs') })
      : h('span', { className: 'dim', text: 'any' });
    return h('tr', {},
      h('td', {}, h('span', { className: 'name', text: name }), r.example ? exampleBadge() : null),
      h('td', {}, conns),
      h('td', {}, queries),
      access,
      h('td', { className: r.rate_limit ? 'mono' : 'mono dim', text: r.rate_limit || 'server default' }),
      h('td', {}, ips),
      h('td', {}, h('div', { className: 'actions' },
        h('button', { type: 'button', className: 'btn ghost sm', text: 'New key from this', onclick: function () { openApiKeyForm(null, {}, name); } }),
        h('button', { type: 'button', className: 'btn ghost sm', text: 'Edit', onclick: function () { openRoleForm(name, r); } }),
        h('button', { type: 'button', className: 'btn ghost sm danger', text: 'Delete', onclick: function () { deleteRole(name); } }))));
  });
  box.appendChild(h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['Name', 'Connections', 'Queries / collections', 'Access', 'Rate limit', 'IPs', ''].map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, rows)));
}

function openRoleForm(name, existing) {
  existing = existing || {};
  var isEdit = !!name;
  var slot = openDrawer('role-form-slot', isEdit ? 'Edit role' : 'New role', isEdit ? name : 'POST /roles');
  var nameInput = h('input', { id: 'r-name', value: name || '', placeholder: 'reporting', autocomplete: 'off', spellcheck: 'false', required: isEdit ? null : true });
  if (isEdit) nameInput.disabled = true;
  var connNames = Object.keys(connectionsCache).sort();
  var wildcard = existing.connections === undefined || existing.connections === '*';
  var allCheckbox = h('input', { id: 'r-all', type: 'checkbox' });
  allCheckbox.checked = wildcard;
  var connChecks = {};
  var connBox = h('div', { className: 'tags' }, connNames.length ? connNames.map(function (cname) {
    var cb = h('input', { type: 'checkbox' });
    cb.checked = !wildcard && (existing.connections || []).indexOf(cname) !== -1;
    connChecks[cname] = cb;
    return h('label', { className: 'switch', style: 'font-weight:400' }, cb, cname);
  }) : h('span', { className: 'hint', text: 'No connections exist yet — add one on the Connections tab first.' }));
  function paintConnMode() { connBox.style.opacity = allCheckbox.checked ? '0.4' : '1'; connBox.style.pointerEvents = allCheckbox.checked ? 'none' : 'auto'; }
  allCheckbox.onchange = paintConnMode;
  paintConnMode();
  var queryNames = filesCache.map(function (f) { return f.filename; }).sort();
  var queryWildcard = existing.queries === '*';
  var existingQueryEntries = queryWildcard ? [] : (existing.queries || []);
  var existingQueryNames = existingQueryEntries.map(function (e) { return typeof e === 'string' ? e : e.name; });
  var existingWriteQueries = {};
  existingQueryEntries.forEach(function (e) { if (e && typeof e === 'object' && e.allow_writes) existingWriteQueries[e.name] = true; });
  var allQueriesCheckbox = h('input', { id: 'r-all-queries', type: 'checkbox' });
  allQueriesCheckbox.checked = queryWildcard;
  var queryChecks = {}, queryWriteChecks = {};
  var queryBox = h('div', { className: 'tags' }, queryNames.length ? queryNames.map(function (qname) {
    var cb = h('input', { type: 'checkbox' });
    cb.checked = !queryWildcard && existingQueryNames.indexOf(qname) !== -1;
    queryChecks[qname] = cb;
    var writeCb = h('input', { type: 'checkbox', title: 'Allow a key created from this role to write through ' + qname + ' specifically' });
    writeCb.checked = !!existingWriteQueries[qname];
    writeCb.disabled = !cb.checked;
    cb.onchange = function () { writeCb.disabled = !cb.checked; if (!cb.checked) writeCb.checked = false; };
    queryWriteChecks[qname] = writeCb;
    return h('label', { className: 'switch', style: 'font-weight:400' }, cb, qname,
      h('span', { className: 'switch', style: 'font-weight:400;margin-left:6px' }, writeCb, 'write'));
  }) : h('span', { className: 'hint', text: 'No saved queries exist yet — add one on the Saved Queries tab first.' }));
  function paintQueryMode() { queryBox.style.opacity = allQueriesCheckbox.checked ? '0.4' : '1'; queryBox.style.pointerEvents = allQueriesCheckbox.checked ? 'none' : 'auto'; }
  allQueriesCheckbox.onchange = paintQueryMode;
  paintQueryMode();
  var collectionField = collectionGrantField(existing.collections);
  var writesCheckbox = h('input', { id: 'r-writes', type: 'checkbox' });
  writesCheckbox.checked = !!existing.allow_writes;
  var rateLimitInput = h('input', { id: 'r-rate-limit', value: existing.rate_limit || '', placeholder: 'e.g. 100/minute', autocomplete: 'off', spellcheck: 'false' });
  var allowedIpsInput = h('input', { id: 'r-allowed-ips', value: (existing.allowed_ips || []).join(', '), placeholder: 'e.g. 203.0.113.5, 10.0.0.0/8', autocomplete: 'off', spellcheck: 'false' });
  var allowedWriteOpsInput = h('input', { id: 'r-allowed-write-ops', value: (existing.allowed_write_ops || []).join(', '), placeholder: 'e.g. insert, update', autocomplete: 'off', spellcheck: 'false' });
  var actions = formActions(isEdit ? 'Save' : 'Create role', closeDrawer);
  var form = h('form', { className: 'form', novalidate: true, onsubmit: function (e) {
    e.preventDefault();
    var connections = allCheckbox.checked ? '*' : Object.keys(connChecks).filter(function (c) { return connChecks[c].checked; });
    var queries = allQueriesCheckbox.checked ? '*' : Object.keys(queryChecks).filter(function (q) { return queryChecks[q].checked; })
      .map(function (q) { return queryWriteChecks[q].checked ? { name: q, allow_writes: true } : q; });
    var rateLimit = rateLimitInput.value.trim() || null;
    var allowedIps = allowedIpsInput.value.split(',').map(function (v) { return v.trim(); }).filter(Boolean);
    if (!allowedIps.length) allowedIps = null;
    var allowedWriteOps = allowedWriteOpsInput.value.split(',').map(function (v) { return v.trim().toLowerCase(); }).filter(Boolean);
    if (!allowedWriteOps.length) allowedWriteOps = null;
    var payload = { connections: connections, allow_writes: writesCheckbox.checked, queries: queries, collections: collectionField.value(), rate_limit: rateLimit, allowed_ips: allowedIps, allowed_write_ops: allowedWriteOps };
    if (isEdit) updateRole(name, payload, actions.submit);
    else createRole(nameInput.value.trim(), payload, actions.submit);
  } },
    field('r-name', 'Name', nameInput, isEdit ? null : 'Letters, digits, spaces, “.”, “_” and “-”.'),
    h('label', { className: 'switch' }, allCheckbox, 'All connections'),
    h('div', { className: 'field' }, h('label', {}, 'Allowed connections'), connBox),
    h('label', { className: 'switch' }, allQueriesCheckbox, 'All saved queries'),
    h('div', { className: 'field' }, h('label', {}, 'Additional saved-query access'), queryBox),
    collectionField.node,
    h('label', { className: 'switch' }, writesCheckbox, 'Allow writes', h('span', { className: 'hint', text: '— still capped by QUERYAPIGATE_ALLOW_WRITES' })),
    field('r-allowed-write-ops', 'Allowed write operations', allowedWriteOpsInput, 'Optional, comma-separated SQL keywords — e.g. "insert, update". Only takes effect when Allow writes is on.'),
    field('r-rate-limit', 'Rate limit', rateLimitInput, 'Optional — e.g. "100/minute". Leave blank for no limit of its own.'),
    field('r-allowed-ips', 'Allowed IPs', allowedIpsInput, 'Optional, comma-separated IP addresses or CIDR ranges. Leave blank to allow any address.'),
    h('div', { className: 'hint', text: 'A role is a template: it’s copied onto a key once, when the key is created "from" it. Editing or deleting this role afterward never changes a key already created from it.' }),
    actions.node);
  slot.appendChild(form);
  nameInput.focus();
}
$('new-role').onclick = function () { openRoleForm(); };

async function createRole(name, payload, btn) {
  if (!name) { showError('A role name is required.', { errors: { name: 'This field is required' } }); $('r-name').focus(); return; }
  btn.disabled = true;
  var res = await apiJson('roles', { method: 'POST', json: Object.assign({ name: name }, payload) });
  btn.disabled = false;
  if (res) { showError(''); closeDrawer(); toast('Created role ' + name); loadRoles(); }
}
async function updateRole(name, payload, btn) {
  btn.disabled = true;
  var res = await apiJson('roles/' + enc(name), { method: 'PATCH', json: payload });
  btn.disabled = false;
  if (res) { showError(''); closeDrawer(); toast('Updated ' + name); loadRoles(); }
}
async function deleteRole(name) {
  if (!confirm("Delete role '" + name + "'? Keys already created from it are unaffected — this only removes the template.")) return;
  var res = await apiJson('roles/' + enc(name), { method: 'DELETE' });
  if (res) { toast('Deleted role ' + name); loadRoles(); }
}

// ---- audit log ----
var auditLogCache = [];

async function loadAuditLog() {
  var box = $('auditlog-table');
  var data = await apiJson('audit_log');
  if (!data) {
    $('auditlog-sub').textContent = '';
    clear(box).appendChild(h('div', { className: 'empty' }, h('strong', { text: 'Couldn’t load the audit log' }),
      h('span', { text: 'Only the admin key (QUERYAPIGATE_API_KEY) can view the audit log.' }),
      h('button', { type: 'button', className: 'btn sm', text: 'Retry', onclick: loadAuditLog })));
    return;
  }
  auditLogCache = data.entries || [];
  var actionSelect = $('auditlog-action-filter');
  var currentAction = actionSelect.value;
  var actions = Array.from(new Set(auditLogCache.map(function (e) { return e.action; }).filter(Boolean))).sort();
  clear(actionSelect);
  actionSelect.appendChild(h('option', { value: '', text: 'All actions' }));
  actions.forEach(function (a) { actionSelect.appendChild(h('option', { value: a, text: a })); });
  if (actions.indexOf(currentAction) !== -1) actionSelect.value = currentAction;
  renderAuditLog();
}
$('refresh-auditlog').onclick = loadAuditLog;
$('auditlog-action-filter').onchange = renderAuditLog;
$('auditlog-filter').oninput = renderAuditLog;

function renderAuditLog() {
  var box = clear($('auditlog-table'));
  if (!auditLogCache.length) {
    $('auditlog-sub').textContent = '';
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No administrative changes recorded yet' }),
      h('span', { text: 'Creating or changing a connection, saved query or API key will appear here.' })));
    return;
  }
  var action = $('auditlog-action-filter').value;
  var q = $('auditlog-filter').value.trim().toLowerCase();
  var entries = auditLogCache.filter(function (e) {
    if (action && e.action !== action) return false;
    if (!q) return true;
    return [e.timestamp, e.actor, e.target].join(' ').toLowerCase().indexOf(q) !== -1;
  });
  $('auditlog-sub').textContent = entries.length === auditLogCache.length
    ? auditLogCache.length + (auditLogCache.length === 1 ? ' entry' : ' entries')
    : entries.length + ' of ' + auditLogCache.length + ' entries';
  if (!entries.length) {
    box.appendChild(h('div', { className: 'empty' }, h('span', { text: 'No entries match this filter.' })));
    return;
  }
  var rows = entries.map(function (e) {
    return h('tr', {},
      h('td', { className: 'mono dim', text: e.timestamp || '' }),
      h('td', {}, h('span', { className: 'name', text: e.actor || '-' })),
      h('td', {}, h('span', { className: 'tag', text: e.action || '' })),
      h('td', {}, h('span', { className: 'name', text: e.target || '' })),
      h('td', {}, renderAuditChanges(e.changes)));
  });
  box.appendChild(h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['Time', 'Actor', 'Action', 'Target', 'Changes'].map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, rows)));
}

function auditValueText(v) {
  if (v === null || v === undefined || v === '') return 'none';
  if (Array.isArray(v)) return v.length ? v.join(', ') : 'none';
  return String(v);
}

/** true for a value renderAuditChanges() should skip in a full snapshot (create/delete) - unset/empty, not
 * a real value like false or 0. A diff entry (an update) never has these in the first place - _dict_diff()
 * only ever includes a field that actually changed - so this only thins out snapshots. */
function auditValueIsEmpty(v) {
  return v === null || v === undefined || v === '' || (Array.isArray(v) && !v.length);
}

function renderAuditChanges(changes) {
  var keys = changes && typeof changes === 'object' ? Object.keys(changes).sort() : [];
  var shown = keys.filter(function (key) {
    var v = changes[key];
    var isDiff = v && typeof v === 'object' && !Array.isArray(v) && ('from' in v || 'to' in v);
    return isDiff || !auditValueIsEmpty(v);
  });
  if (!shown.length) return h('span', { className: 'dim', text: keys.length ? 'no other fields set' : '—' });
  return h('div', {}, shown.map(function (key) {
    var v = changes[key];
    var text = (v && typeof v === 'object' && !Array.isArray(v) && ('from' in v || 'to' in v))
      ? key + ': ' + auditValueText(v.from) + ' → ' + auditValueText(v.to)
      : key + ': ' + auditValueText(v);
    return h('div', { className: 'mono', style: 'font-size:12px', text: text });
  }));
}

// ---- metrics (a live snapshot of /metrics, parsed client-side - counters and gauges only, this process's
// own in-memory numbers since it started, deliberately no history or trends; see the tab's own subtitle
// and documentation/API.md#observability for why that stays Prometheus/Grafana's job, not this page's) ----
function parseMetricsText(text) {
  var series = [];
  text.split('\n').forEach(function (line) {
    if (!line || line.charAt(0) === '#') return;
    var m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([^}]*)\})?\s+([0-9eE+\-.]+)\s*$/);
    if (!m) return;
    var labels = {};
    (m[3] || '').replace(/([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g, function (_, k, v) {
      labels[k] = v.replace(/\\"/g, '"').replace(/\\\\/g, '\\');
      return '';
    });
    series.push({ name: m[1], labels: labels, value: Number(m[4]) });
  });
  return series;
}
function metricSum(series, name, filter) {
  return series.filter(function (s) { return s.name === name && (!filter || filter(s.labels)); })
    .reduce(function (a, s) { return a + s.value; }, 0);
}
function metricGauge(series, name) {
  var s = series.filter(function (s2) { return s2.name === name; })[0];
  return s ? s.value : 0;
}
function metricGroupSum(series, name, labelKey) {
  var totals = {};
  series.filter(function (s) { return s.name === name; }).forEach(function (s) {
    var key = s.labels[labelKey] || '(none)';
    totals[key] = (totals[key] || 0) + s.value;
  });
  return totals;
}

async function loadMetrics() {
  var box = $('metrics-body');
  var res;
  try { res = await apiFetch('metrics'); } catch (e) { res = null; }
  if (!res || !res.ok) {
    clear(box).appendChild(h('div', { className: 'empty' }, h('strong', { text: 'Couldn’t load metrics' }),
      h('button', { type: 'button', className: 'btn sm', text: 'Retry', onclick: loadMetrics })));
    return;
  }
  renderMetrics(parseMetricsText(await res.text()));
}
$('refresh-metrics').onclick = loadMetrics;

function statTile(label, value, warn) {
  return h('div', { className: 'panel stat-tile' },
    h('div', { className: 'label', text: label }),
    h('div', { className: 'value' + (warn ? ' warn' : ''), text: String(value) }));
}

function renderMetrics(series) {
  var box = clear($('metrics-body'));
  var totalRequests = metricSum(series, 'queryapigate_requests_total');
  var byStatusClass = {};
  series.filter(function (s) { return s.name === 'queryapigate_requests_total'; }).forEach(function (s) {
    var cls = (s.labels.status || '?').charAt(0) + 'xx';
    byStatusClass[cls] = (byStatusClass[cls] || 0) + s.value;
  });
  var errorCount = Object.keys(byStatusClass).filter(function (c) { return c === '4xx' || c === '5xx'; })
    .reduce(function (a, c) { return a + byStatusClass[c]; }, 0);
  var errorRate = totalRequests ? (100 * errorCount / totalRequests) : 0;

  box.appendChild(h('div', { className: 'stat-tiles' },
    statTile('Requests', totalRequests),
    statTile('Error rate', errorRate.toFixed(1) + '%', errorRate >= 5),
    statTile('Active queries', metricGauge(series, 'queryapigate_active_queries')),
    statTile('Pool idle connections', metricGauge(series, 'queryapigate_pool_idle_connections')),
    statTile('Rate limit rejections', metricGauge(series, 'queryapigate_rate_limit_rejections_total')),
    statTile('Rows returned', metricSum(series, 'queryapigate_rows_returned_total'))));

  var statusRows = ['2xx', '3xx', '4xx', '5xx'].map(function (c) { return { label: c, value: byStatusClass[c] || 0 }; })
    .filter(function (r) { return r.value > 0; });
  var byConnection = metricGroupSum(series, 'queryapigate_queries_total', 'connection');
  var connRows = Object.keys(byConnection).sort().map(function (c) { return { label: c, value: byConnection[c] }; });

  box.appendChild(h('div', { className: 'metrics-charts' },
    statusRows.length ? h('div', { className: 'panel chart-panel' }, h('h3', { style: 'font-size:13px;margin-bottom:8px', text: 'Requests by status' }),
      barChartSvg(statusRows, 'label', 'value')) : null,
    connRows.length ? h('div', { className: 'panel chart-panel' }, h('h3', { style: 'font-size:13px;margin-bottom:8px', text: 'Queries by connection' }),
      barChartSvg(connRows, 'label', 'value')) : null));

  var errorsByConnection = {};
  series.filter(function (s) { return s.name === 'queryapigate_queries_total' && s.labels.status === 'error'; })
    .forEach(function (s) { var c = s.labels.connection || '?'; errorsByConnection[c] = (errorsByConnection[c] || 0) + s.value; });
  var rowsByConnection = metricGroupSum(series, 'queryapigate_rows_returned_total', 'connection');
  var sumByConn = {}, countByConn = {};
  series.filter(function (s) { return s.name === 'queryapigate_query_duration_seconds_sum'; })
    .forEach(function (s) { sumByConn[s.labels.connection] = (sumByConn[s.labels.connection] || 0) + s.value; });
  series.filter(function (s) { return s.name === 'queryapigate_query_duration_seconds_count'; })
    .forEach(function (s) { countByConn[s.labels.connection] = (countByConn[s.labels.connection] || 0) + s.value; });
  var connNames = Object.keys(byConnection).sort();
  if (connNames.length) {
    var tRows = connNames.map(function (c) {
      var count = countByConn[c] || 0;
      var avgMs = count ? Math.round(1000 * (sumByConn[c] || 0) / count) : null;
      return h('tr', {},
        h('td', {}, h('span', { className: 'name', text: c })),
        h('td', { className: 'mono', style: 'text-align:right', text: String(byConnection[c] || 0) }),
        h('td', { className: 'mono', style: 'text-align:right', text: String(errorsByConnection[c] || 0) }),
        h('td', { className: 'mono', style: 'text-align:right', text: avgMs === null ? '—' : avgMs + ' ms' }),
        h('td', { className: 'mono', style: 'text-align:right', text: String(rowsByConnection[c] || 0) }));
    });
    box.appendChild(h('div', { className: 'panel' }, h('table', { className: 'grid' },
      h('thead', {}, h('tr', {}, ['Connection', 'Queries', 'Errors', 'Avg latency', 'Rows returned'].map(function (t) { return h('th', { text: t }); }))),
      h('tbody', {}, tRows))));
  }
}

function openApiKeyForm(name, existing, fromRole) {
  existing = existing || {};
  var isEdit = !!name;
  var slot = openDrawer('apikey-form-slot', isEdit ? 'Edit API key' : 'New API key', isEdit ? name : 'POST /api_keys');
  var nameInput = h('input', { id: 'k-name', value: name || '', placeholder: 'reporting', autocomplete: 'off', spellcheck: 'false', required: isEdit ? null : true });
  if (isEdit) nameInput.disabled = true;
  var roleNames = Object.keys(rolesCache).sort();
  var roleSelect = null, grantFields = null;
  if (!isEdit && roleNames.length) {
    roleSelect = h('select', { id: 'k-role' }, h('option', { value: '', text: 'Custom (choose grants below)' }),
      roleNames.map(function (r) { return h('option', { value: r, text: r }); }));
    if (fromRole) roleSelect.value = fromRole;
  }
  var connNames = Object.keys(connectionsCache).sort();
  var wildcard = existing.connections === undefined || existing.connections === '*';
  var allCheckbox = h('input', { id: 'k-all', type: 'checkbox' });
  allCheckbox.checked = wildcard;
  var connChecks = {};
  var connBox = h('div', { className: 'tags' }, connNames.length ? connNames.map(function (cname) {
    var cb = h('input', { type: 'checkbox' });
    cb.checked = !wildcard && (existing.connections || []).indexOf(cname) !== -1;
    connChecks[cname] = cb;
    return h('label', { className: 'switch', style: 'font-weight:400' }, cb, cname);
  }) : h('span', { className: 'hint', text: 'No connections exist yet — add one on the Connections tab first.' }));
  function paintConnMode() { connBox.style.opacity = allCheckbox.checked ? '0.4' : '1'; connBox.style.pointerEvents = allCheckbox.checked ? 'none' : 'auto'; }
  allCheckbox.onchange = paintConnMode;
  paintConnMode();
  var queryNames = filesCache.map(function (f) { return f.filename; }).sort();
  var queryWildcard = existing.queries === '*';
  var existingQueryEntries = queryWildcard ? [] : (existing.queries || []);
  var existingQueryNames = existingQueryEntries.map(function (e) { return typeof e === 'string' ? e : e.name; });
  var existingWriteQueries = {};
  existingQueryEntries.forEach(function (e) { if (e && typeof e === 'object' && e.allow_writes) existingWriteQueries[e.name] = true; });
  var allQueriesCheckbox = h('input', { id: 'k-all-queries', type: 'checkbox' });
  allQueriesCheckbox.checked = queryWildcard;
  var queryChecks = {}, queryWriteChecks = {};
  var queryBox = h('div', { className: 'tags' }, queryNames.length ? queryNames.map(function (qname) {
    var cb = h('input', { type: 'checkbox' });
    cb.checked = !queryWildcard && existingQueryNames.indexOf(qname) !== -1;
    queryChecks[qname] = cb;
    var writeCb = h('input', { type: 'checkbox', title: 'Allow this key to write through ' + qname + ' specifically' });
    writeCb.checked = !!existingWriteQueries[qname];
    writeCb.disabled = !cb.checked;
    cb.onchange = function () { writeCb.disabled = !cb.checked; if (!cb.checked) writeCb.checked = false; };
    queryWriteChecks[qname] = writeCb;
    return h('label', { className: 'switch', style: 'font-weight:400' }, cb, qname,
      h('span', { className: 'switch', style: 'font-weight:400;margin-left:6px' }, writeCb, 'write'));
  }) : h('span', { className: 'hint', text: 'No saved queries exist yet — add one on the Saved Queries tab first.' }));
  function paintQueryMode() { queryBox.style.opacity = allQueriesCheckbox.checked ? '0.4' : '1'; queryBox.style.pointerEvents = allQueriesCheckbox.checked ? 'none' : 'auto'; }
  allQueriesCheckbox.onchange = paintQueryMode;
  paintQueryMode();
  var collectionField = collectionGrantField(existing.collections);
  var writesCheckbox = h('input', { id: 'k-writes', type: 'checkbox' });
  writesCheckbox.checked = !!existing.allow_writes;
  var expiresInput = h('input', { id: 'k-expires', type: 'date', value: existing.expires_at || '' });
  var rateLimitInput = h('input', { id: 'k-rate-limit', value: existing.rate_limit || '', placeholder: 'e.g. 100/minute', autocomplete: 'off', spellcheck: 'false' });
  var allowedIpsInput = h('input', { id: 'k-allowed-ips', value: (existing.allowed_ips || []).join(', '), placeholder: 'e.g. 203.0.113.5, 10.0.0.0/8', autocomplete: 'off', spellcheck: 'false' });
  var allowedWriteOpsInput = h('input', { id: 'k-allowed-write-ops', value: (existing.allowed_write_ops || []).join(', '), placeholder: 'e.g. insert, update', autocomplete: 'off', spellcheck: 'false' });
  var activeCheckbox = isEdit ? h('input', { id: 'k-active', type: 'checkbox' }) : null;
  if (activeCheckbox) activeCheckbox.checked = existing.active !== false;
  grantFields = h('div', {},
    h('label', { className: 'switch' }, allCheckbox, 'All connections'),
    h('div', { className: 'field' }, h('label', {}, 'Allowed connections'), connBox),
    h('label', { className: 'switch' }, allQueriesCheckbox, 'All saved queries'),
    h('div', { className: 'field' }, h('label', {}, 'Additional saved-query access'), queryBox,
      h('span', { className: 'hint', text: '— independent of connections above: runnable by name even without connection access, for an external client that should only see its own approved queries. Check "write" on a query to let this key write through it specifically, even with no blanket write access — "All saved queries" above can never carry write access, only a specific enumerated list can.' })),
    collectionField.node,
    h('label', { className: 'switch' }, writesCheckbox, 'Allow writes', h('span', { className: 'hint', text: '— still capped by QUERYAPIGATE_ALLOW_WRITES' })),
    field('k-allowed-write-ops', 'Allowed write operations', allowedWriteOpsInput, 'Optional, comma-separated SQL keywords — e.g. "insert, update". Only takes effect when Allow writes is on; narrows which write statements this key may perform. Leave blank to allow any write.'),
    field('k-rate-limit', 'Rate limit', rateLimitInput, 'Optional, this key only — e.g. "100/minute". Checked in addition to QUERYAPIGATE_RATE_LIMIT, not instead of it. Leave blank for no limit of its own.'),
    field('k-allowed-ips', 'Allowed IPs', allowedIpsInput, 'Optional, comma-separated IP addresses or CIDR ranges — e.g. "203.0.113.5, 10.0.0.0/8". Leave blank to allow any address.'));
  function paintRoleMode() {
    var picked = roleSelect && roleSelect.value;
    grantFields.style.opacity = picked ? '0.4' : '1';
    grantFields.style.pointerEvents = picked ? 'none' : 'auto';
  }
  if (roleSelect) { roleSelect.onchange = paintRoleMode; paintRoleMode(); }
  var actions = formActions(isEdit ? 'Save' : 'Create key', closeDrawer);
  var form = h('form', { className: 'form', novalidate: true, onsubmit: function (e) {
    e.preventDefault();
    var expiresAt = expiresInput.value || null;
    var pickedRole = roleSelect && roleSelect.value;
    if (!isEdit && pickedRole) { createApiKey({ name: nameInput.value.trim(), role: pickedRole, expires_at: expiresAt }, actions.submit); return; }
    var connections = allCheckbox.checked ? '*' : Object.keys(connChecks).filter(function (c) { return connChecks[c].checked; });
    var queries = allQueriesCheckbox.checked ? '*' : Object.keys(queryChecks).filter(function (q) { return queryChecks[q].checked; })
      .map(function (q) { return queryWriteChecks[q].checked ? { name: q, allow_writes: true } : q; });
    var rateLimit = rateLimitInput.value.trim() || null;
    var allowedIps = allowedIpsInput.value.split(',').map(function (v) { return v.trim(); }).filter(Boolean);
    if (!allowedIps.length) allowedIps = null;
    var allowedWriteOps = allowedWriteOpsInput.value.split(',').map(function (v) { return v.trim().toLowerCase(); }).filter(Boolean);
    if (!allowedWriteOps.length) allowedWriteOps = null;
    if (isEdit) updateApiKey(name, { connections: connections, allow_writes: writesCheckbox.checked, active: activeCheckbox.checked, queries: queries, collections: collectionField.value(), expires_at: expiresAt, rate_limit: rateLimit, allowed_ips: allowedIps, allowed_write_ops: allowedWriteOps }, actions.submit);
    else createApiKey({ name: nameInput.value.trim(), connections: connections, allow_writes: writesCheckbox.checked, queries: queries, collections: collectionField.value(), expires_at: expiresAt, rate_limit: rateLimit, allowed_ips: allowedIps, allowed_write_ops: allowedWriteOps }, actions.submit);
  } },
    field('k-name', 'Name', nameInput, isEdit ? null : 'Letters, digits, spaces, “.”, “_” and “-”.'),
    roleSelect ? field('k-role', 'Create from', roleSelect, 'Optional — copies that role’s connections, queries, collections, write access, rate limit and allowed IPs onto this key once, at creation. Editing or deleting the role afterward never changes this key.') : null,
    grantFields,
    field('k-expires', 'Expires', expiresInput, 'Optional — valid through the end of this date. Leave blank for no expiry.'),
    activeCheckbox ? h('label', { className: 'switch' }, activeCheckbox, 'Active', h('span', { className: 'hint', text: '— unchecking revokes it immediately' })) : null,
    actions.node);
  slot.appendChild(form);
  nameInput.focus();
}
$('new-apikey').onclick = function () { openApiKeyForm(); };

async function createApiKey(payload, btn) {
  if (!payload.name) { showError('An API key name is required.', { errors: { name: 'This field is required' } }); $('k-name').focus(); return; }
  btn.disabled = true;
  var res = await apiJson('api_keys', { method: 'POST', json: payload });
  btn.disabled = false;
  if (res) { showError(''); revealApiKey(res.name, res.key); loadApiKeys(); }
}
async function updateApiKey(name, patch, btn) {
  btn.disabled = true;
  var res = await apiJson('api_keys/' + enc(name), { method: 'PATCH', json: patch });
  btn.disabled = false;
  if (res) { showError(''); closeDrawer(); toast('Updated ' + name); loadApiKeys(); }
}
async function deleteApiKey(name) {
  if (!confirm("Revoke API key '" + name + "'? Anything still using it will stop working immediately.")) return;
  var res = await apiJson('api_keys/' + enc(name), { method: 'DELETE' });
  if (res) { toast('Revoked ' + name); loadApiKeys(); }
}
/** Shown once, right after creation - the secret is never retrievable again after this. */
function revealApiKey(name, secret) {
  clear($('apikey-form-slot'));
  $('drawer-title').textContent = 'API key created';
  $('drawer-kicker').textContent = name;
  var input = h('input', { readonly: true, className: 'mono', onclick: function () { input.select(); } });
  input.value = secret;
  $('apikey-form-slot').appendChild(h('div', { className: 'form' },
    h('div', { className: 'field' }, h('label', {}, 'Secret key'), input,
      h('div', { className: 'hint', text: 'Store this now — it cannot be shown again. To rotate it, revoke this key and create a new one.' })),
    h('div', { className: 'form-actions' },
      h('button', { type: 'button', className: 'btn ghost', text: 'Copy', onclick: function () { copyText(secret); } }),
      h('button', { type: 'button', className: 'btn primary', text: 'Done', onclick: closeDrawer }))));
}

// ---- collections ----
// A collection is one named group a saved query belongs to, stored on the query file itself (so it cannot
// disagree with it). A key's `collections` grant is LIVE - it reaches whatever is in the collection now and
// whatever is filed there later - which is why moving a query shows who gains and loses access first.
var collectionsCache = { collections: {}, uncollected: [] };
var collectionsLoading = null;
var collapsedGroups = {};
function loadCollections() {
  if (!collectionsLoading) {
    collectionsLoading = apiJson('collections').then(function (data) {
      collectionsCache = data && data.collections ? data : { collections: {}, uncollected: [] };
    }).then(function () { collectionsLoading = null; }, function () { collectionsLoading = null; });
  }
  return collectionsLoading;
}
function collectionNames() { return Object.keys(collectionsCache.collections).sort(); }
function accessImpact(from, to) {
  function reaching(c, kind) { var e = c ? collectionsCache.collections[c] : null; return e ? e[kind] : []; }
  function minus(a, b) { return a.filter(function (x) { return b.indexOf(x) === -1; }); }
  return { keysGain: minus(reaching(to, 'keys'), reaching(from, 'keys')), keysLose: minus(reaching(from, 'keys'), reaching(to, 'keys')),
           rolesGain: minus(reaching(to, 'roles'), reaching(from, 'roles')), rolesLose: minus(reaching(from, 'roles'), reaching(to, 'roles')) };
}
/** The who-gains-who-loses summary shown before queries move (or are first filed) - the same arithmetic the server
 * records in the audit log. `moves` is a list of [fromCollection, toCollection]; one entry for a single query. */
function impactNodeMany(moves) {
  var box = h('div', { className: 'impact' });
  var acc = { keysGain: [], keysLose: [], rolesGain: [], rolesLose: [] };
  moves.forEach(function (m) {
    var i = accessImpact(m[0] || null, m[1] || null);
    Object.keys(acc).forEach(function (k) { i[k].forEach(function (x) { if (acc[k].indexOf(x) === -1) acc[k].push(x); }); });
  });
  var what = moves.length === 1 ? 'this query' : 'some of these queries';
  var lines = [];
  if (acc.keysGain.length) lines.push(['Keys that will gain access to ' + what + ': ', acc.keysGain.join(', '), true]);
  if (acc.keysLose.length) lines.push(['Keys that will lose access to ' + (moves.length === 1 ? 'it' : 'some of them') + ': ', acc.keysLose.join(', '), true]);
  if (acc.rolesGain.length) lines.push(['Roles that will include ' + (moves.length === 1 ? 'it' : 'them') + ' (affects only keys created from them later): ', acc.rolesGain.join(', '), false]);
  if (acc.rolesLose.length) lines.push(['Roles that will no longer include ' + (moves.length === 1 ? 'it' : 'some of them') + ' (keys already created from them are unaffected): ', acc.rolesLose.join(', '), false]);
  if (!lines.length) box.appendChild(h('span', { className: 'hint', text: 'No key’s access changes.' }));
  lines.forEach(function (l) {
    box.appendChild(h('div', { className: 'hint', style: l[2] ? 'color:var(--warn)' : null }, l[0], h('strong', { text: l[1] })));
  });
  return box;
}
function impactNode(from, to) { return impactNodeMany([[from, to]]); }
/** Query names plus collection grants for a key/role row - one renderer for both tables, so they cannot drift apart. */
function queryGrantNode(entry) {
  var tags = [];
  if (entry.queries === '*') tags.push(h('span', { className: 'tag', text: 'all queries' }));
  else (entry.queries || []).forEach(function (q) {
    var writable = q && typeof q === 'object' && q.allow_writes;
    var qname = writable ? q.name : q;
    tags.push(h('span', { className: 'tag', title: writable ? qname + ' — write access' : null, text: qname + (writable ? ' (write)' : '') }));
  });
  (entry.collections || []).forEach(function (c) {
    var known = collectionsCache.collections[c];
    var n = known ? known.queries.length : 0;
    tags.push(h('span', { className: 'tag coll', title: 'Every query in collection ' + c + ' (' + n + ' now, including any added later) — read-only', text: c + '/' }));
  });
  return tags.length ? h('div', { className: 'tags' }, tags) : h('span', { className: 'dim', text: '—' });
}
/** Checkboxes over the existing collections for a key/role form; a name the entry already holds stays listed even when it has emptied. */
function collectionGrantField(held) {
  var checks = {};
  var names = collectionNames();
  var box = h('div', { className: 'tags' }, names.length ? names.map(function (c) {
    var cb = h('input', { type: 'checkbox' });
    cb.checked = (held || []).indexOf(c) !== -1;
    checks[c] = cb;
    return h('label', { className: 'switch', style: 'font-weight:400' }, cb, c,
      h('span', { className: 'dim', text: ' (' + collectionsCache.collections[c].queries.length + ')' }));
  }) : h('span', { className: 'hint', text: 'No collections yet — file a saved query under one first.' }));
  return {
    node: h('div', { className: 'field' }, h('label', {}, 'Collections'), box,
      h('span', { className: 'hint', text: '— reaches every query in the collection, including ones filed there later; read-only, and never ad-hoc SQL. Moving a query into or out of a collection changes what this key can run.' })),
    value: function () { return Object.keys(checks).filter(function (c) { return checks[c].checked; }); }
  };
}

// ---- example APIs (installed by `queryapigate examples load`; everything they add is marked "example") ----
var examplesState = { loaded: false, partial: false, queries: [], collections: [] };
function exampleBadge() { return h('span', { className: 'tag example', title: 'Installed by the example APIs — removing the examples removes it', text: 'example' }); }
async function loadExamples() {
  var data = await apiJson('examples');
  examplesState = data || { loaded: false, partial: false, queries: [], collections: [] };
  renderExamplesStrip();
}
function renderExamplesStrip() {
  var box = clear($('examples-strip'));
  var st = examplesState;
  if (!st.loaded && !st.partial) { box.hidden = true; return; }
  box.hidden = false;
  box.appendChild(h('span', { text: st.partial
    ? 'The example APIs are only partly loaded (an interrupted load).'
    : 'Example APIs are loaded: ' + st.queries.length + ' queries in ' + st.collections.length + ' collections, four roles and an “examples” connection. Each is marked “example”; removing them touches nothing else.' }));
  box.appendChild(h('span', { className: 'spacer', style: 'flex:1' }));
  if (st.partial) box.appendChild(h('button', { type: 'button', className: 'btn sm', text: 'Finish loading', onclick: loadExampleData }));
  box.appendChild(h('button', { type: 'button', className: 'btn sm danger', text: 'Remove examples', onclick: removeExamples }));
}
async function loadExampleData() {
  var res = await apiJson('examples', { method: 'POST' });
  if (res) { showError(''); toast('Example APIs loaded'); refreshAll(); }
}
async function removeExamples() {
  if (!confirm('Remove the example APIs? This deletes exactly the queries, roles and connection marked “example” — nothing else.')) return;
  var res = await apiJson('examples', { method: 'DELETE' });
  if (!res) return;
  toast('Example APIs removed');
  if ((res.keys_still_granted || []).length) showError('These keys were granted an example collection, which no longer exists, so that grant now reaches nothing: ' + res.keys_still_granted.join(', '));
  refreshAll();
}

// ---- saved queries ----
var filesCache = [];
var selected = { name: null, version: null, tab: 'run' };
var contentCache = {};

function latestOf(f) { return f.versions[f.versions.length - 1] || {}; }
function findFile(name) { return filesCache.filter(function (f) { return f.filename === name; })[0] || null; }
function lastRun(v) { var hs = v.execution_history || []; return hs[hs.length - 1] || null; }

async function loadQueries(selectName) {
  await loadCollections();
  var data = await apiJson('list_files');
  if (!data) {
    clear($('queries-table')).appendChild(h('div', { className: 'empty' }, h('strong', { text: 'Couldn’t load saved queries' }),
      h('button', { type: 'button', className: 'btn sm', text: 'Retry', onclick: function () { loadQueries(); } })));
    return;
  }
  filesCache = (data.files || []).slice().sort(function (a, b) { return a.filename < b.filename ? -1 : 1; });
  contentCache = {};
  $('count-queries').textContent = filesCache.length ? String(filesCache.length) : '';
  $('queries-sub').textContent = filesCache.length ? filesCache.reduce(function (n, f) { return n + f.versions.length; }, 0) + ' versions' : '';
  if (selectName !== undefined) selected.name = selectName;
  var f = selected.name && findFile(selected.name);
  if (!f) { selected.name = null; selected.version = null; }
  else if (!f.versions.some(function (v) { return v.version === selected.version; })) selected.version = latestOf(f).version;
  renderQueryList();
  renderDetail();
}
function queryItem(f) {
  var l = latestOf(f), run = lastRun(l);
  return h('button', { type: 'button', className: 'qitem' + (f.filename === selected.name ? ' sel' : ''), onclick: function () {
    selected.name = f.filename; selected.version = l.version; renderQueryList(); renderDetail(); } },
    h('div', { className: 'qi-top' },
      h('span', { className: 'name', text: f.filename }),
      h('span', { className: 'tag', text: 'v' + l.version }),
      run ? h('span', { className: 'dot ' + (run.status === 'success' ? 'ok' : 'bad'), title: 'Last run ' + run.executed_at + ' · ' + run.status }) : null,
      h('span', { className: 'qi-conn', text: l.connection_name || '' })),
    l.description ? h('div', { className: 'qi-desc', text: l.description }) : null,
    (l.tags || []).length ? h('div', { className: 'tags' }, l.tags.map(function (t) { return h('span', { className: 'tag', text: t }); })) : null);
}
function groupHeader(name, count, open) {
  var known = name ? collectionsCache.collections[name] : null;
  var reach = known ? known.keys.length : 0;
  // Two rows - the name (never truncated by its own controls) and, for a real collection, a quiet line of actions.
  return h('div', { className: 'qgroup' },
    h('button', { type: 'button', className: 'qg-toggle', 'aria-expanded': open ? 'true' : 'false', onclick: function () {
      collapsedGroups[name] = open; renderQueryList(); } },
      h('span', { text: open ? '▾' : '▸' }), h('span', { className: 'qg-name', text: name || 'No collection' }), h('span', { className: 'count', text: String(count) })),
    name ? h('div', { className: 'qg-meta' },
      h('span', { className: 'qg-reach', title: reach ? 'Keys granted this collection: ' + known.keys.join(', ') : 'No key is granted this collection', text: reach + (reach === 1 ? ' key' : ' keys') }),
      h('button', { type: 'button', className: 'btn ghost sm', text: 'Postman', title: 'Download this collection as a Postman Collection file (one request per query; holds no API key)', onclick: function () { downloadPostman(name); } }),
      h('button', { type: 'button', className: 'btn ghost sm', text: 'Rename', title: 'Rename this collection, carrying every key and role grant with it', onclick: function () { openRenameCollectionForm(name); } })) : null);
}
function renderQueryList() {
  var box = clear($('queries-table'));
  if (!filesCache.length) {
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No saved queries yet' }),
      h('span', { text: 'Saved queries become GET /q/<name> endpoints with typed parameters.' }),
      h('button', { type: 'button', className: 'btn primary', text: 'New saved query', onclick: function () { openQueryForm(); } }),
      h('button', { type: 'button', className: 'btn', text: 'Load example APIs', title: 'Install four worked scenarios (reporting, dashboard, export, partner) you can try and remove again', onclick: loadExampleData })));
    return;
  }
  var q = $('query-filter').value.trim().toLowerCase();
  var list = filesCache.filter(function (f) {
    var l = latestOf(f);
    return !q || [f.filename, f.collection, l.description, (l.tags || []).join(' '), l.connection_name, l.author].join(' ').toLowerCase().indexOf(q) !== -1;
  });
  if (!list.length) { box.appendChild(h('div', { className: 'empty' }, h('span', { text: 'Nothing matches “' + q + '”.' }))); return; }
  // Grouping is decided from the whole list, not the filtered one, so the layout does not flip while typing.
  if (!filesCache.some(function (f) { return f.collection; })) { list.forEach(function (f) { box.appendChild(queryItem(f)); }); return; }
  var groups = {};
  list.forEach(function (f) { var c = f.collection || ''; (groups[c] = groups[c] || []).push(f); });
  var names = Object.keys(groups).filter(Boolean).sort();
  if (groups['']) names.push('');
  names.forEach(function (c) {
    var open = !!q || !collapsedGroups[c];
    box.appendChild(groupHeader(c, groups[c].length, open));
    if (open) groups[c].forEach(function (f) { box.appendChild(queryItem(f)); });
  });
}
$('query-filter').oninput = renderQueryList;

async function getContent(name) {
  if (contentCache[name]) return contentCache[name];
  var data = await apiJson('view_file_content?filename=' + enc(name));
  if (!data) return null;
  var parsed = null;
  try { parsed = JSON.parse(data.content); } catch (e) { parsed = null; }
  contentCache[name] = { raw: data.content, parsed: parsed };
  return contentCache[name];
}

function renderDetail() {
  var box = clear($('query-detail'));
  var f = selected.name && findFile(selected.name);
  if (!f) {
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No query selected' }),
      h('span', { text: 'Pick a saved query to run it, read its SQL or see its history.' })));
    return;
  }
  var latest = latestOf(f);
  var v = f.versions.filter(function (x) { return x.version === selected.version; })[0] || latest;
  var isLatest = v.version === latest.version;
  var history = v.execution_history || [];

  var versionSwitch = h('div', { className: 'versions', role: 'group', 'aria-label': 'Version' }, f.versions.map(function (x) {
    return h('button', { type: 'button', className: x.version === v.version ? 'on' : '', text: 'v' + x.version,
      title: x.version === latest.version ? 'Latest version' : 'Version ' + x.version,
      onclick: function () { selected.version = x.version; renderDetail(); } });
  }));
  var head = h('div', { className: 'd-head' },
    h('div', { className: 'd-title' },
      h('h3', { text: f.filename }),
      versionSwitch,
      isLatest ? h('span', { className: 'hint', text: 'latest' }) : h('span', { className: 'hint', text: 'older version' }),
      h('span', { className: 'spacer' }),
      h('button', { type: 'button', className: 'btn sm', text: 'New version', onclick: function () { openQueryForm(f.filename, v); } }),
      h('button', { type: 'button', className: 'btn sm', text: 'Move…', title: 'File this query under a collection (PUT /saved_sql/' + f.filename + '/collection)', onclick: function () { openMoveForm(f); } }),
      h('button', { type: 'button', className: 'btn sm danger', text: 'Delete v' + v.version, title: 'DELETE /saved_sql/' + f.filename + '?version=' + v.version,
        onclick: function () { deleteQueryVersion(f.filename, v.version, f.versions.length); } }),
      h('button', { type: 'button', className: 'btn sm danger', text: 'Delete query', onclick: function () { deleteQuery(f.filename); } })),
    v.description ? h('p', { className: 'd-desc', text: v.description }) : null,
    h('dl', { className: 'meta' },
      metaItem('connection', v.connection_name || '—'), metaItem('collection', f.collection || '—'), metaItem('author', v.author || '—'),
      metaItem('modified', v.last_modified_at || v.created_at || '—'), metaItem('status', v.status || '—'),
      (v.tags || []).length ? h('div', {}, h('dt', { text: 'tags' }), h('dd', {}, h('span', { className: 'tags' }, v.tags.map(function (t) { return h('span', { className: 'tag', text: t }); })))) : null),
    h('div', { className: 'subtabs', role: 'tablist' },
      subtab('run', 'Run'), subtab('sql', 'SQL'),
      subtab('history', 'History', h('span', { className: 'count', text: history.length ? String(history.length) : '' })),
      subtab('curl', 'Curl')));
  var body = h('div', { className: 'd-body' });
  box.appendChild(head);
  box.appendChild(body);
  if (selected.tab === 'sql') renderSqlTab(body, f, v);
  else if (selected.tab === 'history') renderHistoryTab(body, v);
  else if (selected.tab === 'curl') renderCurlTab(body, f, v, isLatest);
  else renderRunTab(body, f, v, isLatest);
}
function metaItem(k, val) { return h('div', {}, h('dt', { text: k }), h('dd', { text: String(val) })); }
function subtab(key, label, extra) {
  return h('button', { type: 'button', role: 'tab', 'data-subtab': key, className: selected.tab === key ? 'on' : '', onclick: function () { selected.tab = key; renderDetail(); } }, label, extra || null);
}

async function renderSqlTab(body, f, v) {
  body.appendChild(loadingNode());
  var c = await getContent(f.filename);
  clear(body);
  if (!c) return;
  var data = c.parsed && c.parsed[String(v.version)];
  var sql = data && data.sql_query;
  var codeEl = h('pre', { className: 'code' });
  if (sql !== undefined && sql !== null) highlightInto(codeEl, String(sql)); else codeEl.textContent = c.raw;
  var raw = h('pre', { className: 'code', text: c.raw });
  raw.hidden = true;
  var toggle = h('button', { type: 'button', className: 'btn sm ghost', text: 'Show raw file', onclick: function () {
    raw.hidden = !raw.hidden; toggle.textContent = raw.hidden ? 'Show raw file' : 'Hide raw file'; } });
  body.appendChild(h('div', { className: 'toolbar', style: 'margin:0' }, h('p', { className: 'sub-h', text: 'SQL · v' + v.version }), h('span', { className: 'spacer' }),
    h('button', { type: 'button', className: 'btn sm ghost', text: 'Copy', onclick: function () { copyText(sql || c.raw); } }), toggle));
  body.appendChild(codeEl);
  body.appendChild(raw);
  var qp = v.query_parameters || {};
  var keys = Object.keys(qp);
  body.appendChild(h('p', { className: 'sub-h', text: 'Parameters' }));
  if (!keys.length) { body.appendChild(h('div', { className: 'hint', text: 'This version declares no query_parameters.' })); return; }
  body.appendChild(h('div', { className: 'panel', style: 'overflow:auto' }, h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['Name', 'Type', 'Constraints', 'Description'].map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, keys.map(function (k) {
      var s = typeof qp[k] === 'string' ? { type: qp[k] } : (qp[k] || {});
      var cons = Object.keys(s).filter(function (x) { return x !== 'type' && x !== 'description'; })
        .map(function (x) { return x + '=' + JSON.stringify(s[x]); }).join('  ');
      return h('tr', {}, h('td', {}, h('span', { className: 'name', text: k })), h('td', { className: 'mono', text: String(s.type || '') }),
        h('td', { className: 'mono dim', text: cons }), h('td', { text: s.description ? String(s.description) : '' }));
    })))));
}

function renderHistoryTab(body, v) {
  var hs = (v.execution_history || []).slice().reverse();
  if (!hs.length) { body.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No runs recorded' }), h('span', { text: 'Runs of v' + v.version + ' through /q/ appear here.' }))); return; }
  var ok = hs.filter(function (x) { return x.status === 'success'; });
  var durations = ok.map(function (x) { return Number(x.duration_ms); }).filter(function (n) { return !isNaN(n); });
  body.appendChild(h('div', { className: 'resbar', style: 'border:0;padding:0' }, h('span', { className: 'stat' },
    h('span', {}, h('b', { text: String(hs.length) }), ' runs'),
    h('span', {}, h('b', { text: String(ok.length) }), ' ok · ', h('b', { text: String(hs.length - ok.length) }), ' failed'),
    durations.length ? h('span', {}, 'avg ', h('b', { text: Math.round(durations.reduce(function (a, b) { return a + b; }, 0) / durations.length) + ' ms' })) : null)));

  var statusSelect = h('select', {},
    h('option', { value: '', text: 'All statuses' }),
    h('option', { value: 'success', text: 'Success' }),
    h('option', { value: 'error', text: 'Failed' }));
  var searchInput = h('input', { className: 'search', type: 'search',
    placeholder: 'Filter by connection, caller, request id, error…' });
  body.appendChild(h('div', { className: 'toolbar', style: 'margin:0 0 10px' }, statusSelect, searchInput));
  var tableBox = h('div', { className: 'panel', style: 'overflow:auto;max-height:60vh' });
  body.appendChild(tableBox);

  function paint() {
    var status = statusSelect.value;
    var q = searchInput.value.trim().toLowerCase();
    var rows = hs.filter(function (x) {
      if (status && x.status !== status) return false;
      if (!q) return true;
      return [x.connection_name, x.key_name, x.request_id, x.error].join(' ').toLowerCase().indexOf(q) !== -1;
    });
    clear(tableBox);
    if (!rows.length) { tableBox.appendChild(h('div', { className: 'empty' }, h('span', { text: 'No runs match this filter.' }))); return; }
    tableBox.appendChild(h('table', { className: 'grid' },
      h('thead', {}, h('tr', {}, ['', 'Executed at', 'Connection', 'Caller', 'Rows', 'Duration', 'Request ID', 'Error'].map(function (t) { return h('th', { text: t }); }))),
      h('tbody', {}, rows.map(function (x) {
        var good = x.status === 'success';
        return h('tr', {},
          h('td', { style: 'width:28px;padding-right:0' }, h('span', { className: 'dot ' + (good ? 'ok' : 'bad'), title: String(x.status || '') })),
          h('td', { className: 'mono', text: String(x.executed_at || '') }),
          h('td', { className: 'mono', text: String(x.connection_name || '') }),
          h('td', { className: 'mono', text: String(x.key_name || '') }),
          h('td', { className: 'mono', style: 'text-align:right', text: x.rows === undefined ? '' : String(x.rows) }),
          h('td', { className: 'mono', style: 'text-align:right', text: x.duration_ms === undefined ? '' : x.duration_ms + ' ms' }),
          h('td', { className: 'mono dim', title: String(x.request_id || ''), style: 'max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: String(x.request_id || '') }),
          h('td', { style: 'color:var(--danger);white-space:normal;word-break:break-word;max-width:320px',
                   text: x.error ? String(x.error) : '' }));
      }))));
  }
  statusSelect.onchange = paint;
  searchInput.oninput = paint;
  paint();
}

/** The latest version's declared parameters come from the OpenAPI catalogue (one source of truth with the
 * server). Older versions aren't in the catalogue, so their own query_parameters are used instead. */
var RESERVED = ['format', 'page', 'page_size', 'version', 'connection_name', 'timeout'];
async function fetchQueryParameters(name) {
  var spec = await apiJson('openapi.json');
  if (!spec) return null;
  var op = spec.paths && spec.paths['/q/' + enc(name)];
  return (op && op.get && op.get.parameters || []).filter(function (p) { return RESERVED.indexOf(p.name) === -1; });
}
function paramsFromVersion(v) {
  var qp = v.query_parameters || {};
  return Object.keys(qp).map(function (k) {
    var s = typeof qp[k] === 'string' ? { type: qp[k] } : (qp[k] || {});
    return { name: k, required: s.default === undefined && s.required !== false, description: s.description,
      schema: { type: s.type, default: s.default, minimum: s.min, maximum: s.max } };
  });
}

async function renderRunTab(body, f, v, isLatest) {
  body.appendChild(loadingNode('Loading parameters…'));
  var params = isLatest ? await fetchQueryParameters(f.filename) : null;
  if (!params) params = paramsFromVersion(v);
  if (selected.name !== f.filename || selected.tab !== 'run') return;
  clear(body);
  var inputs = {};
  var grid = h('div', { className: 'param-grid' }, params.map(function (p) {
    var sch = p.schema || {};
    var bounds = [sch.minimum !== undefined ? '≥ ' + sch.minimum : null, sch.maximum !== undefined ? '≤ ' + sch.maximum : null].filter(Boolean).join(' ');
    var input = h('input', { id: 'run-q-' + p.name, spellcheck: 'false', autocomplete: 'off',
      placeholder: sch.default !== undefined ? 'default: ' + sch.default : (p.required ? 'required' : ''),
      required: p.required ? true : null, type: sch.type === 'integer' || sch.type === 'int' ? 'number' : 'text' });
    inputs[p.name] = input;
    return field('run-q-' + p.name, h('span', { className: 'mono', text: p.name }), input,
      [p.description, bounds].filter(Boolean).join(' · ') || null,
      [sch.type ? h('span', { className: 'type', text: String(sch.type) }) : null, p.required ? h('span', { className: 'req', text: '*' }) : null]);
  }));
  var connSelect = h('select', { id: 'rq-connection' });
  connectionOptions(connSelect, true, 'saved: ' + (v.connection_name || 'none'));
  var formatSelect = h('select', { id: 'rq-format' }, ['json', 'csv', 'tsv', 'xml', 'yaml', 'ndjson', 'xlsx'].map(function (x) { return h('option', { value: x, text: x }); }));
  var sizeSelect = h('select', { id: 'rq-page-size' }, [10, 25, 50, 100, 500].map(function (n) { return h('option', { value: String(n), text: String(n) }); }));
  var statusBox = h('div', { className: 'resbar' }), resultsBox = h('div', { className: 'res-body' });
  var resultsPanel = h('div', { className: 'panel' }, statusBox, resultsBox);
  resultsPanel.hidden = true;
  var page = 1;
  var runBtn = h('button', { type: 'submit', className: 'btn primary', text: 'Run' });
  var url = 'q/' + enc(f.filename);
  async function run() {
    var query = params.map(function (p) {
      var val = inputs[p.name].value;
      return val !== '' ? enc(p.name) + '=' + enc(val) : null;
    }).filter(Boolean);
    query.push('format=' + formatSelect.value, 'page=' + page, 'page_size=' + sizeSelect.value);
    if (!isLatest) query.push('version=' + v.version);
    if (connSelect.value) query.push('connection_name=' + enc(connSelect.value));
    resultsPanel.hidden = false;
    await execute(function () { return apiFetch(url + '?' + query.join('&')); }, {
      results: resultsBox, status: statusBox, button: runBtn, page: page, pageSize: Number(sizeSelect.value),
      filename: f.filename, format: formatSelect.value,
      onPage: function (n) { page = n; run(); },
      onPageSize: function (n) { sizeSelect.value = String(n); page = 1; run(); }
    });
    refreshHistorySilently(f.filename);
  }
  var form = h('form', { novalidate: true, style: 'display:flex;flex-direction:column;gap:14px', onsubmit: function (e) { e.preventDefault(); page = 1; run(); } },
    params.length ? grid : h('div', { className: 'hint', text: 'No parameters — this query runs as-is.' }),
    h('div', { className: 'run-row' },
      field('rq-connection', 'Connection', connSelect), field('rq-format', 'Format', formatSelect), field('rq-page-size', 'Page size', sizeSelect),
      h('span', { className: 'spacer' }),
      h('code', { className: 'dim hide-sm', style: 'align-self:center', text: 'GET /' + url + (isLatest ? '' : '?version=' + v.version) }),
      runBtn));
  body.appendChild(form);
  body.appendChild(resultsPanel);
}
async function refreshHistorySilently(name) {
  var res;
  try { res = await apiFetch('list_files'); } catch (e) { return; }
  if (!res.ok) return;
  var data = await res.json();
  filesCache = (data.files || []).slice().sort(function (a, b) { return a.filename < b.filename ? -1 : 1; });
  renderQueryList();
  var f = findFile(name);
  if (!f || selected.name !== name) return;
  var v = f.versions.filter(function (x) { return x.version === selected.version; })[0];
  var badge = document.querySelector('#query-detail .subtabs button[data-subtab="history"] .count');
  if (v && badge) badge.textContent = String((v.execution_history || []).length || '');
}

async function renderCurlTab(body, f, v, isLatest) {
  body.appendChild(loadingNode('Loading parameters…'));
  var params = isLatest ? await fetchQueryParameters(f.filename) : null;
  if (!params) params = paramsFromVersion(v);
  if (selected.name !== f.filename || selected.tab !== 'curl') return;
  clear(body);
  var cmd = asSavedQueryCurl(f.filename, params, isLatest ? null : v.version);
  body.appendChild(h('div', { className: 'toolbar', style: 'margin:0' }, h('p', { className: 'sub-h', text: 'curl' }), h('span', { className: 'spacer' }),
    h('button', { type: 'button', className: 'btn sm ghost', text: 'Copy', onclick: function () { copyText(cmd); } })));
  body.appendChild(h('pre', { className: 'code', text: cmd }));
  if (params.length) body.appendChild(h('div', { className: 'hint', text: 'Replace the <placeholder> value(s) with real parameters before running it.' }));
}

async function openQueryForm(baseName, baseVersion) {
  var slot = openDrawer('query-form-slot', baseName ? 'New version' : 'New saved query',
    baseName ? baseName + ' · from v' + baseVersion.version : 'PATCH /save_sql_to_file');
  var prefill = baseVersion || {};
  var sql = '';
  if (baseName) {
    slot.appendChild(loadingNode());
    var c = await getContent(baseName);
    var d = c && c.parsed && c.parsed[String(baseVersion.version)];
    sql = (d && d.sql_query) || '';
    clear(slot);
  }
  function inp(id, value, ph, req) {
    return h('input', { id: id, value: value || '', placeholder: ph || null, required: req ? true : null, autocomplete: 'off', spellcheck: 'false' });
  }
  var connSelect = h('select', { id: 'q-connection' });
  connectionOptions(connSelect, true, '(none — must be given at run time)');
  if (prefill.connection_name) connSelect.value = prefill.connection_name;
  var qp = prefill.query_parameters && Object.keys(prefill.query_parameters).length ? JSON.stringify(prefill.query_parameters, null, 2) : '';
  var paramsTa = h('textarea', { id: 'q-params', spellcheck: 'false', placeholder: '{"id": {"type": "int", "min": 1}}' });
  paramsTa.value = qp;
  var detected = h('div', { className: 'refs' });
  var editor = makeEditor({ id: 'q-sql', required: true, placeholder: 'SELECT * FROM t WHERE id = :id' }, sql);
  var sqlTa = editor.querySelector('textarea');
  function paintRefs() {
    clear(detected);
    var names = sqlParams(sqlTa.value);
    if (names.length) detected.appendChild(h('span', { className: 'hint', text: 'Bound in SQL:' }));
    names.forEach(function (n) { detected.appendChild(h('span', { className: 'tag', text: ':' + n })); });
  }
  sqlTa.addEventListener('input', paintRefs);
  paintRefs();
  var querySchema = schemaBrowser(function (text) { insertAtCursor(sqlTa, text); },
    function (tableName) { previewTable(connSelect.value, tableName); closeDrawer(); });
  querySchema.setConnection(connSelect.value);
  connSelect.onchange = function () { querySchema.setConnection(connSelect.value); };
  var collectionInput = h('input', { id: 'q-collection', list: 'q-collection-list', placeholder: 'optional — e.g. reporting', autocomplete: 'off', spellcheck: 'false' });
  var collectionImpact = h('div', {});
  collectionInput.addEventListener('input', function () { clear(collectionImpact).appendChild(collectionInput.value.trim() ? impactNode(null, collectionInput.value.trim()) : h('span')); });
  var collectionField = h('div', { className: 'field' }, h('label', { for: 'q-collection' }, 'Collection'), collectionInput,
    h('datalist', { id: 'q-collection-list' }, collectionNames().map(function (c) { return h('option', { value: c }); })),
    h('div', { className: 'hint', text: 'Optional. Lowercase letters, digits, “.”, “_” and “-”. Later, use “Move…” to change it.' }), collectionImpact);
  var actions = formActions(baseName ? 'Save as v' + (latestOf(findFile(baseName) || { versions: [baseVersion] }).version + 1) : 'Save', closeDrawer);
  var form = h('form', { className: 'form', novalidate: true, onsubmit: function (e) { e.preventDefault(); saveQuery(actions.submit); } },
    field('q-filename', 'Filename', inp('q-filename', baseName, 'films_by_rating', true), 'Letters, digits, spaces, “.”, “_” and “-”. Saving an existing name adds a version.'),
    h('div', { className: 'grid2' }, field('q-author', 'Author', inp('q-author', prefill.author, '', true)), field('q-connection', 'Default connection', connSelect)),
    h('div', { className: 'field' }, h('label', { for: 'q-sql' }, 'SQL', h('span', { className: 'type', text: 'use :name for bound parameters' })), editor, detected),
    schemaField(querySchema),
    field('q-description', 'Description', inp('q-description', prefill.description, '', true)),
    baseName ? null : collectionField,
    field('q-tags', 'Tags', inp('q-tags', (prefill.tags || []).join(', '), 'comma-separated')),
    field('q-params', 'query_parameters', paramsTa, 'JSON object: name → type, or {type, min, max, default, description}.'),
    actions.node);
  slot.appendChild(form);
  (baseName ? sqlTa : $('q-filename')).focus();
}
$('new-query').onclick = function () { openQueryForm(); };

async function saveQuery(btn) {
  var paramsText = $('q-params').value.trim();
  var queryParameters = {};
  if (paramsText) {
    try { queryParameters = JSON.parse(paramsText); }
    catch (e) { showError('query_parameters is not valid JSON: ' + e.message, { errors: { query_parameters: e.message } }); return; }
  }
  var tags = $('q-tags').value.split(',').map(function (t) { return t.trim(); }).filter(Boolean);
  var filename = $('q-filename').value.trim();
  var body = {
    filename: filename,
    sql_query: $('q-sql').value,
    author: $('q-author').value,
    description: $('q-description').value,
    tags: tags,
    connection_name: $('q-connection').value || undefined,
    query_parameters: queryParameters
  };
  var collectionEl = $('q-collection');
  var chosen = collectionEl ? collectionEl.value.trim() : '';
  if (chosen) {
    var already = findFile(filename);
    if (already && (already.collection || '') !== chosen) {
      showError('“' + filename + '” already exists' + (already.collection ? ' in collection ' + already.collection : ' with no collection') + '. Save it without a collection here, then use “Move…” — that shows which keys gain or lose access first.');
      return;
    }
    if (!already) body.collection = chosen;
  }
  btn.disabled = true;
  var res = await apiJson('save_sql_to_file', { method: 'PATCH', json: body });
  btn.disabled = false;
  if (res) {
    showError(''); closeDrawer();
    toast('Saved ' + filename + (res.version ? ' v' + res.version : ''));
    selected.version = res.version || null;
    showTab('queries');
    loadQueries(filename);
  }
}
async function downloadPostman(name) {
  var res;
  try { res = await apiFetch('collections/' + enc(name) + '/postman'); }
  catch (e) { showError('Network error: ' + e.message); return; }
  if (!res.ok) {
    var body = null; try { body = await res.json(); } catch (e) { /* not JSON */ }
    showError(errorMessage(res.status, body, ''), { status: res.status });
    return;
  }
  showError('');
  downloadBlob(await res.blob(), name + '.postman_collection.json');
  toast('Downloaded ' + name + '.postman_collection.json — set its apiKey variable after importing');
}
/** A collection exists only while a query is in it, so "new collection" means choosing its first queries. */
function openNewCollectionForm() {
  var slot = openDrawer('query-form-slot', 'New collection', 'file queries under a new group');
  var NAME_RE = /^[a-z0-9][a-z0-9._-]{0,62}$/;
  var nameInput = h('input', { id: 'nc-name', placeholder: 'e.g. reporting', autocomplete: 'off', spellcheck: 'false' });
  var nameHint = h('div', { className: 'hint', text: 'Lowercase letters, digits, “.”, “_” and “-”.' });
  var checks = {};
  var rows = filesCache.slice().sort(function (a, b) {
    return (a.collection ? 1 : 0) - (b.collection ? 1 : 0) || (a.filename < b.filename ? -1 : 1);
  }).map(function (f) {
    var cb = h('input', { type: 'checkbox' });
    checks[f.filename] = { box: cb, from: f.collection || null };
    cb.onchange = paint;
    return h('label', { className: 'switch', style: 'font-weight:400' }, cb, f.filename,
      f.collection ? h('span', { className: 'dim', text: ' (now in ' + f.collection + ')' }) : null);
  });
  var list = h('div', { className: 'tags', style: 'flex-direction:column;gap:6px' }, rows.length ? rows
    : h('span', { className: 'hint', text: 'No saved queries yet — create one first; a collection exists only while a query is in it.' }));
  var impact = h('div', {});
  var actions = formActions('Create collection', closeDrawer);
  function picked() { return Object.keys(checks).filter(function (n) { return checks[n].box.checked; }); }
  function paint() {
    var name = nameInput.value.trim();
    var existing = !!collectionsCache.collections[name];
    nameHint.textContent = !name ? 'Lowercase letters, digits, “.”, “_” and “-”.'
      : !NAME_RE.test(name) ? 'Not a valid name — use lowercase letters, digits, “.”, “_” and “-”, starting with a letter or digit.'
      : existing ? '“' + name + '” already exists — the ticked queries will be added to it.' : '';
    var chosen = picked();
    clear(impact);
    if (name && NAME_RE.test(name) && chosen.length) {
      impact.appendChild(impactNodeMany(chosen.map(function (n) { return [checks[n].from, name]; })));
    }
    actions.submit.disabled = !(NAME_RE.test(name) && chosen.length);
  }
  nameInput.oninput = paint;
  slot.appendChild(h('form', { className: 'form', novalidate: true, onsubmit: async function (e) {
    e.preventDefault();
    var name = nameInput.value.trim();
    var chosen = picked();
    if (!NAME_RE.test(name) || !chosen.length) return;
    actions.submit.disabled = true;
    var done = 0;
    for (var i = 0; i < chosen.length; i++) {
      var res = await apiJson('saved_sql/' + enc(chosen[i]) + '/collection', { method: 'PUT', json: { collection: name } });
      if (!res) break;  // apiJson has already shown why
      done++;
    }
    if (done === chosen.length) { showError(''); closeDrawer(); toast('Created ' + name + ' with ' + done + (done === 1 ? ' query' : ' queries')); }
    else { showError('Moved ' + done + ' of ' + chosen.length + ' queries into ' + name + ' before it stopped — the rest are unchanged.'); actions.submit.disabled = false; }
    if (done) loadQueries(selected.name);
  } },
    h('div', { className: 'hint', text: 'A collection exists only while a query is in it, so choose its first queries now. Moving them is not a new version.' }),
    field('nc-name', 'Name', nameInput, null), nameHint,
    h('div', { className: 'field' }, h('label', {}, 'Queries to file under it'), list),
    impact, actions.node));
  paint();
  nameInput.focus();
}
$('new-collection').onclick = openNewCollectionForm;
function openMoveForm(f) {
  var current = f.collection || '';
  var slot = openDrawer('query-form-slot', 'Move to a collection', f.filename);
  var select = h('select', { id: 'mv-select' }, h('option', { value: '', text: 'No collection' }),
    collectionNames().map(function (c) { return h('option', { value: c, text: c + ' (' + collectionsCache.collections[c].queries.length + ')' }); }),
    h('option', { value: '__new__', text: 'New collection…' }));
  select.value = current;
  var newInput = h('input', { id: 'mv-new', placeholder: 'e.g. reporting', autocomplete: 'off', spellcheck: 'false' });
  var newField = field('mv-new', 'New collection name', newInput, 'Lowercase letters, digits, “.”, “_” and “-”.');
  var impact = h('div', {});
  function target() { return select.value === '__new__' ? newInput.value.trim() : select.value; }
  function paint() {
    newField.style.display = select.value === '__new__' ? '' : 'none';
    clear(impact).appendChild(target() === current ? h('span', { className: 'hint', text: 'No change.' }) : impactNode(current, target()));
  }
  select.onchange = paint; newInput.oninput = paint;
  var actions = formActions('Move', closeDrawer);
  slot.appendChild(h('form', { className: 'form', novalidate: true, onsubmit: async function (e) {
    e.preventDefault();
    var to = target();
    if (select.value === '__new__' && !to) { showError('Enter a name for the new collection.'); newInput.focus(); return; }
    if (to === current) { closeDrawer(); return; }
    actions.submit.disabled = true;
    var res = await apiJson('saved_sql/' + enc(f.filename) + '/collection', { method: 'PUT', json: { collection: to || null } });
    actions.submit.disabled = false;
    if (res) { showError(''); closeDrawer(); toast(f.filename + (to ? ' → ' + to : ' removed from its collection')); loadQueries(f.filename); }
  } },
    h('div', { className: 'hint', text: 'Moving a query is not a new version. A key granted a collection can run every query in it — so this changes what other keys can reach:' }),
    field('mv-select', 'Collection', select), newField, impact, actions.node));
  paint();
}
function openRenameCollectionForm(name) {
  var known = collectionsCache.collections[name] || { queries: [], keys: [], roles: [] };
  var slot = openDrawer('query-form-slot', 'Rename collection', name);
  var input = h('input', { id: 'rn-name', value: name, autocomplete: 'off', spellcheck: 'false' });
  var mergeBox = h('input', { id: 'rn-merge', type: 'checkbox' });
  var mergeRow = h('label', { className: 'switch' }, mergeBox, 'Merge into the existing collection', h('span', { className: 'hint', text: '— also how to finish a rename that was interrupted part-way' }));
  function paint() { mergeRow.style.display = input.value.trim() !== name && collectionsCache.collections[input.value.trim()] ? '' : 'none'; }
  input.oninput = paint;
  var actions = formActions('Rename', closeDrawer);
  slot.appendChild(h('form', { className: 'form', novalidate: true, onsubmit: async function (e) {
    e.preventDefault();
    var to = input.value.trim();
    if (!to || to === name) { showError('Enter a different name.'); input.focus(); return; }
    if (collectionsCache.collections[to] && !mergeBox.checked) { showError('“' + to + '” already exists — tick “Merge” to combine them.'); return; }
    actions.submit.disabled = true;
    var res = await apiJson('collections/' + enc(name), { method: 'PATCH', json: { name: to, merge: mergeBox.checked } });
    actions.submit.disabled = false;
    if (res) { showError(''); closeDrawer(); toast('Renamed ' + name + ' → ' + to); loadQueries(selected.name); loadApiKeys(); loadRoles(); }
  } },
    h('div', { className: 'hint', text: 'Renames ' + known.queries.length + (known.queries.length === 1 ? ' query' : ' queries') + ' and updates ' + known.keys.length + (known.keys.length === 1 ? ' key' : ' keys') + ' and ' + known.roles.length + (known.roles.length === 1 ? ' role' : ' roles') + ' that are granted it. No key loses access at any point.' }),
    field('rn-name', 'New name', input), mergeRow, actions.node));
  paint();
  input.focus(); input.select();
}
async function deleteQuery(name) {
  if (!confirm("Delete saved query '" + name + "' (all versions)?")) return;
  var res = await apiJson('saved_sql/' + enc(name), { method: 'DELETE' });
  if (res) { toast('Deleted ' + name); loadQueries(null); }
}
async function deleteQueryVersion(name, version, count) {
  var msg = "Delete version " + version + " of '" + name + "'?" + (count === 1 ? ' It is the only version, so the query itself will be removed.' : '');
  if (!confirm(msg)) return;
  var res = await apiJson('saved_sql/' + enc(name) + '?version=' + enc(String(version)), { method: 'DELETE' });
  if (res) { toast('Deleted ' + name + ' v' + version); selected.version = null; loadQueries(count === 1 ? null : name); }
}

// ---- shared execution + result rendering (saved-query runs and Run SQL) ----
function copyText(text) {
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { toast('Copied'); }, function () { toast('Copy failed'); });
}
function downloadBlob(blob, name) {
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 5000);
}
var EXT = { json: 'json', ndjson: 'ndjson', csv: 'csv', tsv: 'tsv', xml: 'xml', yaml: 'yaml', xlsx: 'xlsx' };

async function execute(doFetch, o) {
  showError('');
  clear(o.status);
  clear(o.results).appendChild(h('div', { className: 'res-note' }, h('span', { className: 'spin' }), 'Running…'));
  if (o.button) o.button.disabled = true;
  var t0 = performance.now(), res;
  try { res = await doFetch(); }
  catch (e) {
    if (o.button) o.button.disabled = false;
    clear(o.results).appendChild(h('div', { className: 'res-note err', text: 'Network error: ' + e.message }));
    return;
  }
  o.elapsed = Math.round(performance.now() - t0);
  await renderResponse(res, o);
  if (o.button) o.button.disabled = false;
}

async function renderResponse(res, o) {
  var box = clear(o.results), bar = clear(o.status);
  var contentType = (res.headers.get('content-type') || '').split(';')[0].trim();
  if (!res.ok) {
    var text = await res.text(), body = null;
    try { body = JSON.parse(text); } catch (e) {}
    var msg = errorMessage(res.status, body, text);
    showError(msg, { status: res.status, errors: body && body.errors });
    box.appendChild(h('div', { className: 'res-note err' }, h('span', { className: 'eb-code', text: String(res.status) }), msg));
    return;
  }
  var page = Number(res.headers.get('x-page')) || o.page || 1;
  var size = Number(res.headers.get('x-page-size')) || o.pageSize || 10;
  var hasMore = res.headers.get('x-has-more') === 'true';
  var base = (o.filename || 'result') + (page > 1 ? '-p' + page : '');
  var payload = null, rowCount = null, format = o.format || 'json', tableData = null;
  if (contentType === 'application/json') {
    var data = await res.json();
    payload = JSON.stringify(data, null, 2);
    if (Array.isArray(data)) { rowCount = data.length; tableData = data; renderTable(box, data, (page - 1) * size); }
    else box.appendChild(h('div', { className: 'res-pre jt-root' }, jsonTree(data)));
  } else if (contentType.indexOf('text/') === 0 || contentType === 'application/xml' || contentType === 'application/x-yaml' || contentType === 'application/x-ndjson') {
    payload = await res.text();
    box.appendChild(h('pre', { className: 'res-pre', text: payload }));
  } else {
    var blob = await res.blob();
    var fname = base + '.' + (EXT[format] || 'bin');
    downloadBlob(blob, fname);
    box.appendChild(h('div', { className: 'res-note' }, 'Downloaded ', h('code', { text: fname }), ' (' + (blob.size < 1024 ? blob.size + ' B' : (blob.size / 1024).toFixed(1) + ' KB') + ')',
      h('button', { type: 'button', className: 'btn sm', text: 'Download again', onclick: function () { downloadBlob(blob, fname); } })));
  }
  var stat = h('span', { className: 'stat' },
    h('span', {}, h('b', { className: 'stat-ok', text: String(res.status) }), res.statusText ? ' ' + res.statusText : ''),
    rowCount !== null ? h('span', {}, h('b', { text: String(rowCount) }), rowCount === 1 ? ' row' : ' rows') : null,
    rowCount ? h('span', { text: 'rows ' + ((page - 1) * size + 1) + '–' + ((page - 1) * size + rowCount) }) : null,
    h('span', { text: format }),
    o.elapsed !== undefined ? h('span', { text: o.elapsed + ' ms' }) : null);
  bar.appendChild(stat);
  bar.appendChild(h('span', { className: 'spacer' }));
  if (o.onPage) bar.appendChild(pager(page, size, hasMore, o));
  var headersBox = headersPanel(res);
  headersBox.hidden = true;
  bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Headers', onclick: function () { headersBox.hidden = !headersBox.hidden; } }));
  if (payload !== null) {
    bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Copy', onclick: function () { copyText(payload); } }));
    bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Download', onclick: function () {
      downloadBlob(new Blob([payload], { type: contentType || 'text/plain' }), base + '.' + (EXT[format] || 'txt')); } }));
  }
  if (tableData) bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Copy as TSV', onclick: function () { copyText(rowsToTsv(tableData)); } }));
  if (o.sql !== undefined) bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Copy as curl', onclick: function () { copyText(asCurl(o)); } }));
  var chartPanel = null;
  if (tableData && tableData.length && numericColumns(tableData).length) {
    chartPanel = buildChartPanel(tableData);
    chartPanel.hidden = true;
    bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Chart', onclick: function () { chartPanel.hidden = !chartPanel.hidden; } }));
  }
  box.appendChild(headersBox);
  if (chartPanel) box.appendChild(chartPanel);
}

/** A collapsible list of every header the response actually carries - X-Page, X-RateLimit-*, X-Request-Id,
 * X-Cache, ETag, and whatever else the server sends, not a hand-picked subset. */
function headersPanel(res) {
  var rows = [];
  res.headers.forEach(function (v, k) { rows.push([k, v]); });
  rows.sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0; });
  return h('div', { className: 'panel headers-panel' }, h('table', { className: 'grid' },
    h('tbody', {}, rows.map(function (r) { return h('tr', {}, h('td', { className: 'mono dim' }, r[0]), h('td', { className: 'mono' }, r[1])); }))));
}

function columnsOf(rows) {
  var cols = [], seen = {};
  rows.forEach(function (r) { Object.keys(r || {}).forEach(function (c) { if (!seen[c]) { seen[c] = true; cols.push(c); } }); });
  return cols;
}

function rowsToTsv(rows) {
  var cols = columnsOf(rows);
  var lines = [cols.join('\t')];
  rows.forEach(function (row) {
    lines.push(cols.map(function (c) {
      var v = row[c];
      if (v === null || v === undefined) return '';
      var s = typeof v === 'object' ? JSON.stringify(v) : String(v);
      return s.replace(/[\t\n\r]/g, ' ');
    }).join('\t'));
  });
  return lines.join('\n');
}

// ---- quick chart: a bar chart of the current page only, never implying a full-result view ----
var CHART_MAX_BARS = 50;

function numericColumns(rows) {
  return columnsOf(rows).filter(function (c) {
    var any = false;
    var allNumericOrNull = rows.every(function (r) {
      var v = r[c];
      if (v === null || v === undefined) return true;
      if (typeof v === 'number' && isFinite(v)) { any = true; return true; }
      return false;
    });
    return any && allNumericOrNull;
  });
}

function buildChartPanel(tableData) {
  var cols = columnsOf(tableData);
  var numCols = numericColumns(tableData);
  var labelCol = cols.filter(function (c) { return numCols.indexOf(c) === -1; })[0] || cols[0];
  var valueCol = numCols[0];
  var shown = tableData.slice(0, CHART_MAX_BARS);
  var labelSel = h('select', { 'aria-label': 'Label column' },
    cols.map(function (c) { return h('option', { value: c, text: c, selected: c === labelCol ? true : null }); }));
  var valueSel = h('select', { 'aria-label': 'Value column' },
    numCols.map(function (c) { return h('option', { value: c, text: c, selected: c === valueCol ? true : null }); }));
  var svgSlot = h('div', { className: 'chart-svg-slot' });
  function repaint() { clear(svgSlot).appendChild(barChartSvg(shown, labelSel.value, valueSel.value)); }
  labelSel.onchange = repaint;
  valueSel.onchange = repaint;
  repaint();
  return h('div', { className: 'panel chart-panel' },
    h('div', { className: 'chart-toolbar' },
      h('span', { className: 'hint', text: 'Chart of this page only (' + shown.length +
        (shown.length < tableData.length ? ' of ' + tableData.length : '') +
        (shown.length === 1 ? ' row' : ' rows') + ') — not the full result.' }),
      h('span', { className: 'spacer' }),
      h('label', { className: 'switch', style: 'font-weight:400' }, 'Label', labelSel),
      h('label', { className: 'switch', style: 'font-weight:400' }, 'Value', valueSel)),
    svgSlot);
}

function barChartSvg(rows, labelCol, valueCol) {
  var NS = 'http://www.w3.org/2000/svg';
  var data = rows.map(function (r) {
    var v = r[valueCol];
    return { label: r[labelCol] === null || r[labelCol] === undefined ? '' : String(r[labelCol]),
            value: typeof v === 'number' && isFinite(v) ? v : 0 };
  });
  var width = 680, height = 220, pad = { top: 10, right: 10, bottom: 30, left: 46 };
  var innerW = width - pad.left - pad.right, innerH = height - pad.top - pad.bottom;
  var maxVal = Math.max.apply(null, data.map(function (d) { return d.value; }).concat([0]));
  var minVal = Math.min.apply(null, data.map(function (d) { return d.value; }).concat([0]));
  var range = (maxVal - minVal) || 1;
  var zeroY = pad.top + innerH * (maxVal / range);
  var gap = 4;
  var barW = data.length ? Math.max(2, (innerW - gap * (data.length - 1)) / data.length) : 0;

  var svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
  svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');

  var axis = document.createElementNS(NS, 'line');
  axis.setAttribute('x1', pad.left); axis.setAttribute('x2', width - pad.right);
  axis.setAttribute('y1', zeroY); axis.setAttribute('y2', zeroY);
  axis.setAttribute('class', 'chart-axis');
  svg.appendChild(axis);

  data.forEach(function (d, i) {
    var barH = innerH * (Math.abs(d.value) / range);
    var x = pad.left + i * (barW + gap);
    var y = d.value >= 0 ? zeroY - barH : zeroY;
    var rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', x); rect.setAttribute('y', y);
    rect.setAttribute('width', barW); rect.setAttribute('height', Math.max(0, barH));
    rect.setAttribute('class', 'chart-bar');
    var title = document.createElementNS(NS, 'title');
    title.textContent = d.label + ': ' + d.value;
    rect.appendChild(title);
    svg.appendChild(rect);
    if (barW > 16) {
      var label = document.createElementNS(NS, 'text');
      label.setAttribute('x', x + barW / 2);
      label.setAttribute('y', height - pad.bottom + 13);
      label.setAttribute('class', 'chart-label chart-label-x');
      label.textContent = d.label.length > 9 ? d.label.slice(0, 8) + '…' : d.label;
      svg.appendChild(label);
    }
  });

  [[maxVal, pad.top + 8], [minVal, height - pad.bottom + 3]].forEach(function (pair) {
    var label = document.createElementNS(NS, 'text');
    label.setAttribute('x', 2); label.setAttribute('y', pair[1]);
    label.setAttribute('class', 'chart-label chart-label-y');
    label.textContent = String(pair[0]);
    svg.appendChild(label);
  });

  return svg;
}

function shQuote(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }
/** o.sql/o.connection/o.params come from runSql()'s call to execute() - ad-hoc runs only, not saved-query
 * ones. The API key, if any, is a placeholder rather than the real value: this text is meant to be copied
 * out of the browser (to a terminal, a ticket, a chat), and the key typed into this page shouldn't ride
 * along by default. */
function asCurl(o) {
  var qs = 'format=' + enc(o.format) + '&page=' + o.page + '&page_size=' + o.pageSize + (o.timeout ? '&timeout=' + enc(o.timeout) : '');
  var url = new URL('execute_sql?' + qs, location.href).href;
  var body = JSON.stringify({ sql: o.sql, connection_name: o.connection, params: o.params || {} });
  var lines = ['curl -X POST ' + shQuote(url), "  -H 'Content-Type: application/json'"];
  if (getKey()) lines.push("  -H 'X-API-Key: YOUR_KEY_HERE'  # replace with your own key");
  lines.push('  -d ' + shQuote(body));
  return lines.join(' \\\n');
}
/** A saved query's own GET /q/<name> endpoint as a curl command - readable as a reference, not necessarily
 * runnable as-is: a parameter with no declared default becomes a <name> placeholder to fill in rather than
 * a real value, since none is on hand outside the Run tab's own form. Same API-key placeholder policy as
 * asCurl() above. */
function asSavedQueryCurl(name, params, version) {
  // Built as a plain string, not new URL(...).href, since a <placeholder> value would otherwise come back
  // percent-encoded (%3Cid%3E) - unreadable for a command that's meant to be read and edited, not run as-is.
  var query = params.map(function (p) {
    var sch = p.schema || {};
    return sch.default !== undefined ? enc(p.name) + '=' + enc(String(sch.default)) : enc(p.name) + '=<' + p.name + '>';
  });
  query.push('format=json');
  if (version) query.push('version=' + version);
  var base = new URL('q/' + enc(name), location.href).href;
  var url = query.length ? base + '?' + query.join('&') : base;
  var lines = ['curl ' + shQuote(url)];
  if (getKey()) lines.push("  -H 'X-API-Key: YOUR_KEY_HERE'  # replace with your own key");
  return lines.join(' \\\n');
}

/** A collapsible tree for a JSON value that isn't a row array - the same idea browser devtools or `jq`
 * give for free, instead of a flat stringified dump. */
function jsonNode(entries, bracketOpen, bracketClose) {
  var open = true;
  var toggle = h('button', { type: 'button', className: 'jt-toggle', text: '▾', 'aria-label': 'Collapse' });
  var items = h('div', { className: 'jt-children' }, entries.map(function (pair) {
    return h('div', { className: 'jt-item' }, h('span', { className: 'jt-key', text: pair[0] + ': ' }), jsonTree(pair[1]));
  }));
  toggle.onclick = function () {
    open = !open;
    items.hidden = !open;
    toggle.textContent = open ? '▾' : '▸';
    toggle.setAttribute('aria-label', open ? 'Collapse' : 'Expand');
  };
  return h('div', { className: 'jt-node' },
    h('div', { className: 'jt-head' }, toggle, h('span', { className: 'jt-punct', text: bracketOpen + entries.length + bracketClose })),
    items);
}
function jsonTree(value) {
  if (value === null || value === undefined) return h('span', { className: 'jt-null', text: 'null' });
  if (Array.isArray(value)) {
    if (!value.length) return h('span', { className: 'jt-punct', text: '[]' });
    return jsonNode(value.map(function (v, i) { return [i, v]; }), '[', ']');
  }
  if (typeof value === 'object') {
    var keys = Object.keys(value);
    if (!keys.length) return h('span', { className: 'jt-punct', text: '{}' });
    return jsonNode(keys.map(function (k) { return [k, value[k]]; }), '{', '}');
  }
  if (typeof value === 'string') return h('span', { className: 'jt-str', text: JSON.stringify(value) });
  return h('span', { className: 'jt-num', text: String(value) });
}

function pager(page, size, hasMore, o) {
  var pageInput = h('input', { type: 'number', min: '1', value: String(page), 'aria-label': 'Page', onchange: function () {
    var n = Math.max(1, Number(pageInput.value) || 1); o.onPage(n); } });
  var presets = [10, 25, 50, 100, 500];
  if (presets.indexOf(size) === -1) presets.push(size);
  presets.sort(function (a, b) { return a - b; });
  var sizeSelect = h('select', { 'aria-label': 'Page size', onchange: function () { o.onPageSize(Number(sizeSelect.value)); } },
    presets.map(function (n) { return h('option', { value: String(n), text: n + ' / page' }); }));
  sizeSelect.value = String(size);
  return h('div', { className: 'pager' },
    h('button', { type: 'button', className: 'btn sm', text: '‹ Prev', disabled: page <= 1, onclick: function () { o.onPage(page - 1); } }),
    h('span', { className: 'hint', text: 'Page' }), pageInput,
    h('button', { type: 'button', className: 'btn sm', text: hasMore ? 'Next page ›' : 'Next ›', disabled: !hasMore, title: hasMore ? 'X-Has-More: true' : 'No more rows', onclick: function () { o.onPage(page + 1); } }),
    sizeSelect);
}

function renderTable(box, rows, offset) {
  if (!rows.length) { box.appendChild(h('div', { className: 'res-note', text: 'No rows returned.' })); return; }
  var cols = [], seen = {};
  rows.forEach(function (r) { Object.keys(r || {}).forEach(function (c) { if (!seen[c]) { seen[c] = true; cols.push(c); } }); });
  var numeric = {};
  cols.forEach(function (c) {
    numeric[c] = rows.every(function (r) { var v = r[c]; return v === null || v === undefined || typeof v === 'number'; })
      && rows.some(function (r) { return typeof r[c] === 'number'; });
  });
  box.appendChild(h('div', { className: 'table-wrap' }, h('table', { className: 'rs' },
    h('thead', {}, h('tr', {}, h('th', { className: 'rn', text: '#' }), cols.map(function (c) { return h('th', { className: numeric[c] ? 'num' : null, text: c }); }))),
    h('tbody', {}, rows.map(function (row, i) {
      return h('tr', {}, h('td', { className: 'rn', text: String(offset + i + 1) }), cols.map(function (c) {
        var v = row[c];
        if (v === null || v === undefined) return h('td', {}, h('span', { className: 'null', text: 'NULL' }));
        var s = typeof v === 'object' ? JSON.stringify(v) : String(v);
        return h('td', { className: numeric[c] ? 'num' : null, title: s.length > 40 ? s : null, text: s });
      }));
    })))));
}

// ---- Run SQL tab ----
var runPage = 1;
function paintRunRefs(sql) {
  var box = clear($('run-refs'));
  var names = sqlParams(sql);
  if (!names.length) return;
  box.appendChild(h('span', { className: 'hint', text: 'In SQL:' }));
  names.forEach(function (n) { box.appendChild(h('span', { className: 'tag', text: ':' + n })); });
}
bindEditor($('run-sql'), $('run-sql-hl'), paintRunRefs);
var runSchema = schemaBrowser(function (text) { insertAtCursor($('run-sql'), text); },
  function (tableName) { previewTable($('run-connection').value, tableName); });
$('run-schema-slot').appendChild(schemaField(runSchema));
$('run-connection').onchange = function () { runSchema.setConnection($('run-connection').value); };
function keyRun(e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('run-form').requestSubmit ? $('run-form').requestSubmit() : $('run-form').onsubmit(e); } }
$('run-sql').addEventListener('keydown', keyRun);
$('run-params').addEventListener('keydown', keyRun);
$('run-form').onsubmit = function (e) {
  e.preventDefault();
  runPage = Number($('run-page').value) || 1;
  recordRunHistory();
  runSql({});
};
$('run-explain-button').onclick = function () {
  if (!$('run-sql').value.trim()) { showError('Write some SQL to run.', { errors: { sql: 'This field is required' } }); $('run-sql').focus(); return; }
  runPage = 1;
  runSql({ explain: true, button: $('run-explain-button') });
};
function runSql(opts) {
  var sql = $('run-sql').value;
  if (!sql.trim()) { showError('Write some SQL to run.', { errors: { sql: 'This field is required' } }); $('run-sql').focus(); return; }
  if (!$('run-connection').value) { showError('Pick a connection first — add one on the Connections tab.'); return; }
  var paramsText = $('run-params').value.trim();
  var params = {};
  if (paramsText) {
    try { params = JSON.parse(paramsText); }
    catch (e) { showError('Bound parameters must be valid JSON: ' + e.message, { errors: { params: e.message } }); return; }
  }
  var format = $('run-format').value;
  var pageSize = Number($('run-page-size').value) || 10;
  var timeout = $('run-timeout').value;
  $('run-page').value = String(runPage);
  var qs = 'format=' + enc(format) + '&page=' + runPage + '&page_size=' + pageSize + (timeout ? '&timeout=' + enc(timeout) : '');
  var connection = $('run-connection').value;
  var sqlToRun = opts.explain ? 'EXPLAIN ' + sql : sql;
  execute(function () {
    return apiFetch('execute_sql?' + qs, { method: 'POST', json: { sql: sqlToRun, connection_name: connection, params: params } });
  }, {
    results: $('run-results'), status: $('run-status'), button: opts.button || $('run-button'), page: runPage, pageSize: pageSize,
    filename: opts.explain ? 'explain' : 'query', format: format,
    sql: sqlToRun, connection: connection, params: params, timeout: timeout,
    onPage: function (n) { runPage = n; runSql(opts); },
    onPageSize: function (n) { $('run-page-size').value = String(n); runPage = 1; runSql(opts); }
  });
}

/** Jump to the Run SQL tab pre-filled with a preview of one table - from either schema browser. */
function previewTable(connectionName, tableName) {
  showTab('run');
  if (connectionName && connectionsCache[connectionName]) {
    $('run-connection').value = connectionName;
    runSchema.setConnection(connectionName);
  }
  $('run-sql').value = 'SELECT * FROM ' + tableName;
  if ($('run-sql').repaint) $('run-sql').repaint();
  runPage = 1;
  recordRunHistory();
  runSql({});
}

// ---- client-side ad-hoc query history (this browser tab only; not the saved-query execution_history) ----
var RUN_HISTORY_KEY = 'queryapigate-run-history', RUN_HISTORY_MAX = 20;
function loadRunHistory() {
  try { return JSON.parse(sessionStorage.getItem(RUN_HISTORY_KEY) || '[]'); } catch (e) { return []; }
}
function recordRunHistory() {
  var sql = $('run-sql').value.trim();
  if (!sql) return;
  var entry = { sql: sql, connection: $('run-connection').value, format: $('run-format').value };
  var list = loadRunHistory().filter(function (e) { return !(e.sql === entry.sql && e.connection === entry.connection); });
  list.unshift(entry);
  if (list.length > RUN_HISTORY_MAX) list = list.slice(0, RUN_HISTORY_MAX);
  try { sessionStorage.setItem(RUN_HISTORY_KEY, JSON.stringify(list)); } catch (e) {}
  renderRunHistory();
}
function renderRunHistory() {
  var box = clear($('run-history-slot'));
  var list = loadRunHistory();
  if (!list.length) return;
  box.appendChild(h('div', { className: 'sub-h', text: 'Recent queries' }));
  box.appendChild(h('div', { className: 'history-list' }, list.map(function (entry) {
    return h('button', { type: 'button', className: 'history-item', title: entry.sql, onclick: function () {
      $('run-sql').value = entry.sql;
      if ($('run-sql').repaint) $('run-sql').repaint();
      if (entry.connection && connectionsCache[entry.connection]) { $('run-connection').value = entry.connection; runSchema.setConnection(entry.connection); }
      if (entry.format) $('run-format').value = entry.format;
    } }, entry.sql.length > 64 ? entry.sql.slice(0, 64) + '…' : entry.sql);
  })));
}

// ---- startup ----
function refreshAll() { loadConnections(); loadQueries(); loadApiKeys(); loadRoles(); loadAuditLog(); loadMetrics(); loadExamples(); }
apiFetch('health').then(function (res) { return res.ok ? res.json() : null; }).then(function (info) {
  $('health-dot').className = 'dot ' + (info && info.status === 'ok' ? 'ok' : 'bad');
  $('version').textContent = info ? 'v' + info.version : 'unreachable';
}, function () { $('health-dot').className = 'dot bad'; $('version').textContent = 'unreachable'; });
try { var lastTab = sessionStorage.getItem('queryapigate-ui-tab'); if (lastTab && $('tab-' + lastTab)) showTab(lastTab); } catch (e) {}
renderRunHistory();
refreshAll();
</script>
</body></html>
"""
