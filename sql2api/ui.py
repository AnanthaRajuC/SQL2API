"""A small admin UI at /ui: connections, saved queries and an ad-hoc SQL runner.

Self-contained (no build step, no external script or stylesheet - unlike /docs, which needs the real
Swagger UI library, this page is simple enough to write by hand). It is a client of the existing JSON API
only; there is no server-side logic here beyond serving this one static page. Query results are always
rendered through DOM APIs (createElement/textContent), never innerHTML, so a value coming back from a
database can never execute as markup.
"""

UI_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SQL2API</title>
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
  header.top { position: sticky; top: 0; z-index: 20; display: flex; align-items: stretch; gap: 24px; height: 48px;
    padding: 0 20px; background: var(--surface); border-bottom: 1px solid var(--line); }
  .brand { display: flex; align-items: center; gap: 10px; }
  .wordmark { font: 700 13px/1 var(--mono); letter-spacing: 0.02em; }
  .wordmark b { color: var(--accent); font-weight: 700; }
  .health { display: inline-flex; align-items: center; gap: 6px; font: 11px/1 var(--mono); color: var(--ink-3);
    padding: 4px 7px; border: 1px solid var(--line); border-radius: 20px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-3); flex: none; display: inline-block; }
  .dot.ok { background: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  .dot.bad { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-soft); }
  .dot.off { background: transparent; border: 1.5px solid var(--ink-3); }
  #tabs { display: flex; align-items: stretch; gap: 2px; }
  #tabs button { position: relative; display: flex; align-items: center; gap: 7px; border: 0; background: none; padding: 0 12px;
    font: 500 13px var(--sans); color: var(--ink-2); cursor: pointer; }
  #tabs button:hover { color: var(--ink); }
  #tabs button.active { color: var(--ink); }
  #tabs button.active::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: -1px; height: 2px; background: var(--accent); border-radius: 2px 2px 0 0; }
  .count { font: 11px/1 var(--mono); color: var(--ink-3); background: var(--surface-2); padding: 3px 5px; border-radius: 4px; min-width: 18px; text-align: center; }
  .count:empty { display: none; }
  .top-end { margin-left: auto; display: flex; align-items: center; gap: 14px; }
  .top-end > a { font-size: 12.5px; }
  .chip { font: 11px/1 var(--mono); color: var(--ink-2); padding: 5px 7px; border-radius: 4px; background: var(--surface-2); white-space: nowrap; }
  .chip.low { color: var(--danger); background: var(--danger-soft); }
  #key-bar { display: flex; align-items: center; gap: 0; border: 1px solid var(--line-strong); border-radius: 6px; background: var(--bg); height: 30px; overflow: hidden; }
  #key-bar label { font-size: 11.5px; color: var(--ink-3); padding: 0 4px 0 9px; white-space: nowrap; display: flex; align-items: center; gap: 6px; }
  #key-bar input { border: 0; background: transparent; width: 180px; height: 28px; padding: 0 6px; font: 12px var(--mono); color: var(--ink); outline: none; }
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

  /* ---- results ---- */
  .results { margin-top: 14px; }
  .results:empty { display: none; }
  .resbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 7px 10px; border-bottom: 1px solid var(--line); font-size: 12px; color: var(--ink-2); }
  .resbar:empty { display: none; }
  .resbar .stat { font: 11.5px var(--mono); color: var(--ink-2); display: flex; gap: 12px; align-items: center; }
  .resbar .stat b { color: var(--ink); font-weight: 600; }
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

  @media (max-width: 980px) {
    header.top { height: auto; flex-wrap: wrap; gap: 8px 16px; padding: 8px 14px; }
    #tabs { order: 3; width: 100%; height: 36px; margin: 0 -12px; }
    .top-end { flex-wrap: wrap; }
    #error-banner { top: 0; position: relative; }
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
    <span class="wordmark">SQL<b>2</b>API</span>
    <span class="health" id="health" title="GET /health"><span class="dot" id="health-dot"></span><span id="version">…</span></span>
  </div>
  <nav id="tabs" role="tablist">
    <button type="button" role="tab" data-tab="connections" class="active">Connections <span class="count" id="count-connections"></span></button>
    <button type="button" role="tab" data-tab="queries">Saved Queries <span class="count" id="count-queries"></span></button>
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
    <div class="toolbar">
      <h2>Saved queries</h2>
      <span class="sub" id="queries-sub"></span>
      <span class="spacer"></span>
      <input id="query-filter" class="search" type="search" placeholder="Filter by name, description, tag…">
      <button id="new-query" type="button" class="btn primary">New saved query</button>
    </div>
    <div class="split">
      <div id="queries-table" class="panel"><div class="loading"><span class="spin"></span>Loading…</div></div>
      <div id="query-detail" class="panel detail"><div class="empty"><strong>No query selected</strong><span>Pick a saved query to run it, read its SQL or see its history.</span></div></div>
    </div>
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
          <button type="submit" class="btn primary" id="run-button">Run</button>
        </div>
        <div class="editor" id="run-editor">
          <pre class="hl" id="run-sql-hl" aria-hidden="true"></pre>
          <textarea id="run-sql" required spellcheck="false" wrap="off" autocomplete="off" aria-label="SQL" placeholder="SELECT * FROM t WHERE id = :id"></textarea>
        </div>
      </div>
      <div class="runner-side">
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
function getKey() { try { return sessionStorage.getItem('sql2api-key') || ''; } catch (e) { return ''; } }
function setKey(v) { try { sessionStorage.setItem('sql2api-key', v); } catch (e) {} }
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
  try { sessionStorage.setItem('sql2api-ui-tab', name); } catch (e) {}
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
  clear($('connection-form-slot')); clear($('query-form-slot'));
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
  clear($('connection-form-slot')); clear($('query-form-slot'));
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

// ---- connections ----
var DB_TYPES = ['mysql', 'postgres', 'clickhouse', 'sqlite', 'h2']; // mirrors config.SUPPORTED_DB_TYPES
var PASSWORD_MASK = '********'; // mirrors config.PASSWORD_MASK; sending it back unchanged keeps the stored password
var connectionsCache = {};

function openConnectionForm(name, existing) {
  existing = existing || {};
  var isEdit = !!name;
  var slot = openDrawer('connection-form-slot', isEdit ? 'Edit connection' : 'New connection', isEdit ? name : 'PATCH /connections');
  function inp(id, type, value, ph) {
    return h('input', { id: id, type: type || 'text', value: value === undefined || value === null ? '' : String(value), placeholder: ph || null, autocomplete: 'off', spellcheck: 'false' });
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
      field('c-password', 'Password', inp('c-password', 'password', isEdit ? (existing.password === undefined ? '' : existing.password) : '', ''),
        isEdit ? 'Leave the mask to keep the stored password.' : '${ENV_VAR} references are resolved on the server.')),
    field('c-database', 'Database / file path', inp('c-database', 'text', existing.database, 'SQLite and H2 take a file path'), null),
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
      h('td', {}, h('span', { className: 'name', text: name })),
      h('td', {}, h('span', { className: 'tag', text: c.db || '?' })),
      h('td', { className: 'mono' }, endpoint || h('span', { className: 'dim', text: '—' })),
      h('td', { className: 'mono', text: c.database || '' }),
      h('td', { className: 'mono', text: c.user || '' }),
      h('td', { className: c.active ? '' : 'dim', text: c.active ? 'Active' : 'Inactive' }),
      h('td', {}, h('div', { className: 'actions' },
        h('button', { type: 'button', className: 'btn ghost sm', text: 'Query', disabled: !c.active, title: 'Open in Run SQL', onclick: function () {
          $('run-connection').value = name; showTab('run'); $('run-sql').focus(); } }),
        h('button', { type: 'button', className: 'btn ghost sm', text: 'Edit', onclick: function () { openConnectionForm(name, c); } }),
        h('button', { type: 'button', className: 'btn ghost sm danger', text: 'Delete', onclick: function () { deleteConnection(name); } }))));
  });
  box.appendChild(h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['', 'Name', 'Type', 'Host', 'Database', 'User', 'Status', ''].map(function (t) { return h('th', { text: t }); }))),
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
}

// ---- saved queries ----
var filesCache = [];
var selected = { name: null, version: null, tab: 'run' };
var contentCache = {};

function latestOf(f) { return f.versions[f.versions.length - 1] || {}; }
function findFile(name) { return filesCache.filter(function (f) { return f.filename === name; })[0] || null; }
function lastRun(v) { var hs = v.execution_history || []; return hs[hs.length - 1] || null; }

async function loadQueries(selectName) {
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
function renderQueryList() {
  var box = clear($('queries-table'));
  if (!filesCache.length) {
    box.appendChild(h('div', { className: 'empty' }, h('strong', { text: 'No saved queries yet' }),
      h('span', { text: 'Saved queries become GET /q/<name> endpoints with typed parameters.' }),
      h('button', { type: 'button', className: 'btn primary', text: 'New saved query', onclick: function () { openQueryForm(); } })));
    return;
  }
  var q = $('query-filter').value.trim().toLowerCase();
  var list = filesCache.filter(function (f) {
    var l = latestOf(f);
    return !q || [f.filename, l.description, (l.tags || []).join(' '), l.connection_name, l.author].join(' ').toLowerCase().indexOf(q) !== -1;
  });
  if (!list.length) { box.appendChild(h('div', { className: 'empty' }, h('span', { text: 'Nothing matches “' + q + '”.' }))); return; }
  list.forEach(function (f) {
    var l = latestOf(f), run = lastRun(l);
    box.appendChild(h('button', { type: 'button', className: 'qitem' + (f.filename === selected.name ? ' sel' : ''), onclick: function () {
      selected.name = f.filename; selected.version = l.version; renderQueryList(); renderDetail(); } },
      h('div', { className: 'qi-top' },
        h('span', { className: 'name', text: f.filename }),
        h('span', { className: 'tag', text: 'v' + l.version }),
        run ? h('span', { className: 'dot ' + (run.status === 'success' ? 'ok' : 'bad'), title: 'Last run ' + run.executed_at + ' · ' + run.status }) : null,
        h('span', { className: 'qi-conn', text: l.connection_name || '' })),
      l.description ? h('div', { className: 'qi-desc', text: l.description }) : null,
      (l.tags || []).length ? h('div', { className: 'tags' }, l.tags.map(function (t) { return h('span', { className: 'tag', text: t }); })) : null));
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
      h('button', { type: 'button', className: 'btn sm danger', text: 'Delete v' + v.version, title: 'DELETE /saved_sql/' + f.filename + '?version=' + v.version,
        onclick: function () { deleteQueryVersion(f.filename, v.version, f.versions.length); } }),
      h('button', { type: 'button', className: 'btn sm danger', text: 'Delete query', onclick: function () { deleteQuery(f.filename); } })),
    v.description ? h('p', { className: 'd-desc', text: v.description }) : null,
    h('dl', { className: 'meta' },
      metaItem('connection', v.connection_name || '—'), metaItem('author', v.author || '—'),
      metaItem('modified', v.last_modified_at || v.created_at || '—'), metaItem('status', v.status || '—'),
      (v.tags || []).length ? h('div', {}, h('dt', { text: 'tags' }), h('dd', {}, h('span', { className: 'tags' }, v.tags.map(function (t) { return h('span', { className: 'tag', text: t }); })))) : null),
    h('div', { className: 'subtabs', role: 'tablist' },
      subtab('run', 'Run'), subtab('sql', 'SQL'),
      subtab('history', 'History', h('span', { className: 'count', text: history.length ? String(history.length) : '' }))));
  var body = h('div', { className: 'd-body' });
  box.appendChild(head);
  box.appendChild(body);
  if (selected.tab === 'sql') renderSqlTab(body, f, v);
  else if (selected.tab === 'history') renderHistoryTab(body, v);
  else renderRunTab(body, f, v, isLatest);
}
function metaItem(k, val) { return h('div', {}, h('dt', { text: k }), h('dd', { text: String(val) })); }
function subtab(key, label, extra) {
  return h('button', { type: 'button', role: 'tab', className: selected.tab === key ? 'on' : '', onclick: function () { selected.tab = key; renderDetail(); } }, label, extra || null);
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
  body.appendChild(h('div', { className: 'panel', style: 'overflow:auto;max-height:60vh' }, h('table', { className: 'grid' },
    h('thead', {}, h('tr', {}, ['', 'Executed at', 'Connection', 'Rows', 'Duration', 'Error'].map(function (t) { return h('th', { text: t }); }))),
    h('tbody', {}, hs.map(function (x) {
      var good = x.status === 'success';
      return h('tr', {},
        h('td', { style: 'width:28px;padding-right:0' }, h('span', { className: 'dot ' + (good ? 'ok' : 'bad'), title: String(x.status || '') })),
        h('td', { className: 'mono', text: String(x.executed_at || '') }),
        h('td', { className: 'mono', text: String(x.connection_name || '') }),
        h('td', { className: 'mono', style: 'text-align:right', text: x.rows === undefined ? '' : String(x.rows) }),
        h('td', { className: 'mono', style: 'text-align:right', text: x.duration_ms === undefined ? '' : x.duration_ms + ' ms' }),
        h('td', { style: 'color:var(--danger)', text: x.error ? String(x.error) : '' }));
    })))));
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
  var badge = document.querySelector('#query-detail .subtabs button:last-child .count');
  if (v && badge) badge.textContent = String((v.execution_history || []).length || '');
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
  var actions = formActions(baseName ? 'Save as v' + (latestOf(findFile(baseName) || { versions: [baseVersion] }).version + 1) : 'Save', closeDrawer);
  var form = h('form', { className: 'form', novalidate: true, onsubmit: function (e) { e.preventDefault(); saveQuery(actions.submit); } },
    field('q-filename', 'Filename', inp('q-filename', baseName, 'films_by_rating', true), 'Letters, digits, spaces, “.”, “_” and “-”. Saving an existing name adds a version.'),
    h('div', { className: 'field' }, h('label', { for: 'q-sql' }, 'SQL', h('span', { className: 'type', text: 'use :name for bound parameters' })), editor, detected),
    h('div', { className: 'grid2' }, field('q-author', 'Author', inp('q-author', prefill.author, '', true)), field('q-connection', 'Default connection', connSelect)),
    field('q-description', 'Description', inp('q-description', prefill.description, '', true)),
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
  btn.disabled = true;
  var res = await apiJson('save_sql_to_file', { method: 'PATCH', json: {
    filename: filename,
    sql_query: $('q-sql').value,
    author: $('q-author').value,
    description: $('q-description').value,
    tags: tags,
    connection_name: $('q-connection').value || undefined,
    query_parameters: queryParameters
  } });
  btn.disabled = false;
  if (res) {
    showError(''); closeDrawer();
    toast('Saved ' + filename + (res.version ? ' v' + res.version : ''));
    selected.version = res.version || null;
    showTab('queries');
    loadQueries(filename);
  }
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
  var payload = null, rowCount = null, format = o.format || 'json';
  if (contentType === 'application/json') {
    var data = await res.json();
    payload = JSON.stringify(data, null, 2);
    if (Array.isArray(data)) { rowCount = data.length; renderTable(box, data, (page - 1) * size); }
    else box.appendChild(h('pre', { className: 'res-pre', text: payload }));
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
    rowCount !== null ? h('span', {}, h('b', { text: String(rowCount) }), rowCount === 1 ? ' row' : ' rows') : null,
    rowCount ? h('span', { text: 'rows ' + ((page - 1) * size + 1) + '–' + ((page - 1) * size + rowCount) }) : null,
    h('span', { text: format }),
    o.elapsed !== undefined ? h('span', { text: o.elapsed + ' ms' }) : null);
  bar.appendChild(stat);
  bar.appendChild(h('span', { className: 'spacer' }));
  if (o.onPage) bar.appendChild(pager(page, size, hasMore, o));
  if (payload !== null) {
    bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Copy', onclick: function () { copyText(payload); } }));
    bar.appendChild(h('button', { type: 'button', className: 'btn sm ghost', text: 'Download', onclick: function () {
      downloadBlob(new Blob([payload], { type: contentType || 'text/plain' }), base + '.' + (EXT[format] || 'txt')); } }));
  }
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
function keyRun(e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('run-form').requestSubmit ? $('run-form').requestSubmit() : $('run-form').onsubmit(e); } }
$('run-sql').addEventListener('keydown', keyRun);
$('run-params').addEventListener('keydown', keyRun);
$('run-form').onsubmit = function (e) {
  e.preventDefault();
  runPage = Number($('run-page').value) || 1;
  runSql();
};
function runSql() {
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
  execute(function () {
    return apiFetch('execute_sql?' + qs, { method: 'POST', json: { sql: sql, connection_name: connection, params: params } });
  }, {
    results: $('run-results'), status: $('run-status'), button: $('run-button'), page: runPage, pageSize: pageSize,
    filename: 'query', format: format,
    onPage: function (n) { runPage = n; runSql(); },
    onPageSize: function (n) { $('run-page-size').value = String(n); runPage = 1; runSql(); }
  });
}

// ---- startup ----
function refreshAll() { loadConnections(); loadQueries(); }
apiFetch('health').then(function (res) { return res.ok ? res.json() : null; }).then(function (info) {
  $('health-dot').className = 'dot ' + (info && info.status === 'ok' ? 'ok' : 'bad');
  $('version').textContent = info ? 'v' + info.version : 'unreachable';
}, function () { $('health-dot').className = 'dot bad'; $('version').textContent = 'unreachable'; });
try { var lastTab = sessionStorage.getItem('sql2api-ui-tab'); if (lastTab && $('tab-' + lastTab)) showTab(lastTab); } catch (e) {}
refreshAll();
</script>
</body></html>
"""
