/* Additive PDF integration workspace. All authoritative rules remain in Python. */
(() => {
  'use strict';
  const randomId=()=>{
    if(typeof crypto.randomUUID==='function')return crypto.randomUUID();
    const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
    const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const host = $('#admin-panel-integrations');
  const root = host ? document.createElement('div') : null;
  if (root) { root.id='integration-debug-workspace'; root.className='hidden'; host.append(root); }
  const api = '/api/admin/integrations';
  const names = {nfpa72: 'NFPA 72', compliance: 'Compliance inspection'};
  let integrations = [], selected = null, draft = null, targetId = null, page = 1, zoom = 1;
  let editorDirty = false;
  let dirty = false, test = null, catalog = [], verified = new Set(), loading = false;
  const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag); if (text != null) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const button = (text, action, parent, attrs = {}) => {
    const node = el('button', text, {type: 'button', ...attrs});
    node.addEventListener('click', () => Promise.resolve().then(action).catch(error => message(error.message)));
    parent.append(node); return node;
  };
  function message(text) { $('#integration-message').textContent = text; }
  async function request(url, options = {}) {
    const response = await fetch(url, {cache: 'no-store', ...options});
    const result = await response.json();
    if (!response.ok) throw new Error((response.status === 409 ? 'Conflict: your edits are retained. Download them or reload the saved version. ' : '') + (result.error || result.detail || 'Request failed.'));
    return result;
  }
  const send = (url, body, method = 'POST') => request(url, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  function markDirty() { dirty = true; test = null; verified.clear(); message('Unsaved mapping changes. Save and retest before verification.'); }
  function field(parent, label, control) {
    const wrapper = el('div', null, {class: 'form-field'}); const id = control.id || `pdf-control-${randomId()}`;
    control.id = id; wrapper.append(el('label', label + ':', {for: id}), control); parent.append(wrapper); return control;
  }
  function select(options, value) {
    const control = el('select');
    for (const item of options) control.add(new Option(typeof item === 'string' ? item : item.label, typeof item === 'string' ? item : item.value));
    control.value = value ?? ''; return control;
  }
  function input(value, type = 'text') { const control = el('input', null, {type}); control.value = value ?? ''; return control; }
  function jsonField(parent, label, value, id) {
    const control = el('textarea', null, {id, rows: '5', spellcheck: 'false'}); control.value = JSON.stringify(value, null, 2); field(parent, label, control); return control;
  }
  function parse(id) { try { return JSON.parse($(id).value); } catch (_) { throw new Error(`Invalid JSON in ${$(id).previousElementSibling?.textContent || id}. Your edits are retained.`); } }
  async function refresh(force = false) {
    if (!root || root.classList.contains('hidden') || loading || (!force && (dirty || root.contains(document.activeElement)))) return;
    loading = true;
    try {
      const result = await request(api);
      integrations = result.integrations;
      renderCards();
      if (draft && !dirty && !root.contains(document.activeElement)) {
        const current = integrations.flatMap(i => i.versions).find(v => v.id === draft.id);
        if (current && current.revision !== draft.revision) await openVersion(current);
      }
    } catch (error) { message(error.message); }
    finally { loading = false; }
  }
  function renderCards() {
    const cards = $('#integration-cards'); cards.replaceChildren();
    for (const integration of integrations) {
      const card = el('section', null, {class: 'pdf-integration-card'}); card.append(el('h3', names[integration.key]));
      const active = integration.versions.find(v => v.id === integration.active_version_id);
      const latest = integration.versions[0];
      card.append(el('p', `${integration.enabled ? 'Enabled' : 'Disabled'} · ${active ? 'Published ' + active.id : latest ? 'Draft' : 'Unconfigured'} · pages ${integration.key === 'nfpa72' ? '1–4' : '1'}`));
      if (latest) card.append(el('p', `Template ${latest.template_filename || 'retained original'} · fingerprint ${latest.config.original.sha256} · ${latest.verification.fields?.length || 0}/${latest.config.inventory.targets.length} verified · editor ${latest.last_edited_by || latest.created_by} · ${latest.updated_at}`));
      const upload = el('input', null, {type: 'file', accept: '.pdf', 'aria-label': `Upload ${names[integration.key]} template`}); card.append(upload);
      button('Upload new template', async () => {
        if (dirty) throw new Error('Save or discard your mapping edits before opening another version.');
        if (!upload.files[0]) throw new Error('Select a PDF template.');
        const data = new FormData(); data.append('file', upload.files[0]);
        const version = await request(`${api}/${integration.key}/templates`, {method: 'POST', body: data});
        selected = integration.key; await refresh(true); await openVersion(version);
      }, card);
      const versions = select([{value: '', label: 'Select version…'}, ...integration.versions.map(v => ({value: v.id, label: `${v.status} · ${v.id} · r${v.revision}`}))], draft?.config.integration_key === integration.key ? draft.id : '');
      versions.setAttribute('aria-label', `${names[integration.key]} versions`); card.append(versions);
      button('Open version', async () => {
        if (dirty) throw new Error('Save or discard your mapping edits first.');
        const version = integration.versions.find(v => v.id === versions.value);
        if (!version) throw new Error('Choose a version.'); selected = integration.key; await openVersion(version);
      }, card);
      button('Activate selected published version', async () => {
        if (dirty) throw new Error('Save or discard edits first.');
        await send(`${api}/${integration.key}/state`, {version_id: versions.value, expected_revision: integration.revision}); await refresh(true); message('Published version activated. Enable separately when ready.');
      }, card);
      button(integration.enabled ? 'Disable integration' : 'Enable integration', async () => {
        await send(`${api}/${integration.key}/state`, {enabled: !integration.enabled, expected_revision: integration.revision}); await refresh(true);
      }, card);
      cards.append(card);
    }
  }
  async function openVersion(version) {
    draft = structuredClone(version); selected = version.config.integration_key; dirty = false; test = null; verified.clear();
    page = version.config.inventory.selected_pages[0]; targetId = version.config.inventory.targets[0]?.id;
    $('#integration-workspace').classList.remove('hidden');
    $('#integration-version').textContent = `${names[selected]} · ${draft.status} · ${draft.id} · revision ${draft.revision}`;
    $('#integration-diagnostics').textContent = JSON.stringify(draft.config.inventory.diagnostics, null, 2);
    const inspections = await request('/api/inspections');
    const sample = $('#integration-sample'); const old = sample.value; sample.replaceChildren(new Option('Select saved sample inspection…', ''));
    for (const inspection of inspections) sample.add(new Option(inspection.name, inspection.id)); sample.value = old;
    renderPolicies(); renderTargets(); renderPage(); renderEditor();
    if (sample.value) await loadCatalog();
  }
  function renderPolicies() {
    const controls = $('#integration-policies'); controls.replaceChildren();
    for (const [key, label, options] of [
      ['applicability', 'Applicability', ['', 'panel', 'inspection', 'no_panel']],
      ['filename_policy', 'Download naming policy', ['unresolved','completion_date_panel_id']],
      ['signature_policy', 'Signature policy', ['unresolved', 'later_signing', 'signed_required']],
      ['supplemental_policy', 'Supplemental policy', ['unresolved', 'manual_declaration', 'not_applicable']],
    ]) {
      const control = field(controls, label, select(options, draft.config[key]));
      control.disabled = draft.status !== 'draft'; control.addEventListener('change', () => { draft.config[key] = control.value || null; markDirty(); });
    }
    const timezone = field(controls, 'Default timezone (IANA name, optional)', input(draft.config.default_timezone));
    timezone.disabled=draft.status!=='draft';timezone.placeholder='Example: America/New_York';
    timezone.addEventListener('input',()=>{draft.config.default_timezone=timezone.value||null;markDirty();});
    const reason = field(controls, 'Applicability reason', input(draft.config.applicability_reason));
    reason.disabled = draft.status !== 'draft'; reason.addEventListener('input', () => { draft.config.applicability_reason = reason.value; markDirty(); });
    jsonField(controls, 'Required panel categories (JSON)', draft.config.categories, 'integration-categories');
    jsonField(controls, 'Manual input definitions (JSON: stable id, label, meaning, type, scope, required, bounds/options)', draft.config.manual_inputs, 'integration-inputs');
    jsonField(controls, 'Answer groups (JSON: id, members by Yes/No/NA, requiredness)', draft.config.answer_groups, 'integration-groups');
    jsonField(controls, 'Supplemental declaration source (JSON)', draft.config.supplemental_source ?? null, 'integration-supplemental');
    const builder = el('fieldset'); builder.append(el('legend', 'Add a typed Form Details input'));
    const id = field(builder, 'Stable input ID', input(''));
    const label = field(builder, 'Label', input(''));
    const meaning = field(builder, 'Meaning (changing this requires review)', input(''));
    const type = field(builder, 'Value type', select(['text','number','date','datetime','yes_no_na','dropdown'],'text'));
    const scope = field(builder, 'Answer scope', select(['inspection','panel'],'inspection'));
    const unit = field(builder, 'Numeric unit', input(''));
    const minimum = field(builder, 'Numeric minimum (optional)', input('','number'));
    const maximum = field(builder, 'Numeric maximum (optional)', input('','number'));
    const options = field(builder, 'Dropdown options (one per line)', el('textarea',null,{rows:'3'}));
    const required = field(builder, 'Always required', input('','checkbox'));
    button('Add input definition', () => {
      const definitions = parse('#integration-inputs');
      definitions.push({id:id.value,label:label.value,meaning:meaning.value,type:type.value,scope:scope.value,required:required.checked,
        options:type.value==='dropdown' ? options.value.split('\n').map(v=>v.trim()).filter(Boolean):[],
        unit:type.value==='number' && unit.value ? unit.value:null,
        minimum:type.value==='number' && minimum.value!=='' ? Number(minimum.value):null,
        maximum:type.value==='number' && maximum.value!=='' ? Number(maximum.value):null});
      $('#integration-inputs').value=JSON.stringify(definitions,null,2); markDirty();
    },builder);
    controls.append(builder);
    for (const control of builder.querySelectorAll('input,select,textarea,button')) control.disabled=draft.status!=='draft';
    for (const control of controls.querySelectorAll('textarea')) { control.disabled = draft.status !== 'draft'; control.addEventListener('input', markDirty); }
  }
  async function loadCatalog() {
    if (!draft || !$('#integration-sample').value) throw new Error('Select a saved sample inspection for the source catalog and diagnostic tests.');
    const result = await request(`${api}/versions/${draft.id}/catalog?inspection_id=${encodeURIComponent($('#integration-sample').value)}&panel_ids=${encodeURIComponent($('#integration-sample-panels').value)}`);
    catalog = result.entries; $('#integration-catalog-info').textContent = result.panels.map(p => `${p.id}: ${p.category}`).join(' · ');
    renderEditor(); message('Typed source catalog loaded. Sample answers are diagnostic only.');
  }
  function mapping() { return draft.config.mappings.find(m => m.target_id === targetId); }
  function captureEditor() {
    if (!editorDirty || !draft || !targetId || draft.status !== 'draft' || !$('#integration-disposition')) return;
    const disposition = $('#integration-disposition').value;
    const source = $('#integration-source').value;
    const value = {
      ...(mapping() || {}),
      target_id: targetId, label: $('#integration-label').value, section: $('#integration-section').value,
      disposition, reason: $('#integration-reason').value, required: $('#integration-required').checked,
      overflow: $('#integration-overflow').value, missing: $('#integration-missing').value,
      font_size: Number($('#integration-font').value), minimum_font_size: Number($('#integration-min-font').value),
      transforms: parse('#integration-transforms'), required_when: parse('#integration-condition'),
      source: ['source', 'computed'].includes(disposition) && source ? JSON.parse(source) : null,
      constant: disposition === 'constant' ? parse('#integration-constant') : null,
    };
    const index = draft.config.mappings.findIndex(m => m.target_id === targetId);
    if (index < 0) draft.config.mappings.push(value); else draft.config.mappings[index] = value;
    editorDirty = false;
  }
  function captureAll() {
    captureEditor();
    draft.config.categories = parse('#integration-categories'); draft.config.manual_inputs = parse('#integration-inputs');
    draft.config.answer_groups = parse('#integration-groups'); draft.config.supplemental_source = parse('#integration-supplemental');
  }
  function choose(ident, focus = true) {
    captureEditor(); targetId = ident;
    page = draft.config.inventory.targets.find(t => t.id === ident).page;
    renderTargets(); renderPage(); renderEditor();
    $(`[data-preview-target="${ident}"]`, $('#integration-sheet'))?.scrollIntoView({block:'nearest',inline:'nearest'});
    if (focus) $(`[data-target="${ident}"]`, $('#integration-targets'))?.focus({preventScroll: true});
    $(`[data-target="${ident}"]`, $('#integration-targets'))?.scrollIntoView({block: 'nearest'});
  }
  function renderTargets() {
    const list = $('#integration-targets'); list.replaceChildren();
    const search = $('#integration-search').value.toLowerCase(); const unresolved = $('#integration-unresolved').checked;
    for (const target of draft.config.inventory.targets) {
      const mapped = draft.config.mappings.find(m => m.target_id === target.id);
      if (unresolved && (test ? verified.has(target.id) : mapped)) continue;
      if (!`${mapped?.label || ''} ${target.qualified_name} ${target.id} ${target.kind}`.toLowerCase().includes(search)) continue;
      button(`p${target.page} #${target.occurrence} ${mapped?.label || target.qualified_name || '(unlabeled)'} · ${target.kind} · ${verified.has(target.id) ? 'verified' : mapped ? mapped.disposition : 'unresolved'}`, () => choose(target.id), list,
        {'data-target': target.id, 'aria-pressed': String(target.id === targetId)});
    }
    $('#integration-coverage').textContent = `${draft.config.mappings.length}/${draft.config.inventory.targets.length} dispositions · ${verified.size} verified for current test`;
  }
  function renderPage() {
    const geometry = draft.config.inventory.pages.find(p => p.number === page);
    const sheet = $('#integration-sheet'); sheet.replaceChildren();
    sheet.style.width = `${geometry.display_width * zoom}px`; sheet.style.height = `${geometry.display_height * zoom}px`;
    const image = el('img', null, {src: `${api}/versions/${draft.id}/pages/${page}`, alt: `${names[selected]} page ${page}, field values cleared`}); sheet.append(image);
    for (const target of draft.config.inventory.targets.filter(t => t.page === page)) {
      const [x0,y0,x1,y1] = target.preview_rect;
      const node = button(`${target.occurrence}`, () => choose(target.id), sheet, {class: 'pdf-target', 'data-preview-target':target.id, 'aria-label': `Page ${page} occurrence ${target.occurrence} ${target.qualified_name}`, 'aria-pressed': String(target.id === targetId)});
      Object.assign(node.style, {left: `${100*x0/geometry.display_width}%`, top: `${100*y0/geometry.display_height}%`, width: `${100*(x1-x0)/geometry.display_width}%`, height: `${100*(y1-y0)/geometry.display_height}%`});
    }
    const control = $('#integration-page'); control.replaceChildren();
    for (const number of draft.config.inventory.selected_pages) control.add(new Option(`Page ${number}`, number)); control.value = page;
  }
  function renderEditor() {
    const editor = $('#integration-editor'); editor.replaceChildren(); editorDirty = false;
    const target = draft.config.inventory.targets.find(t => t.id === targetId); if (!target) return;
    editor.append(el('h4', `Selected p${target.page} occurrence ${target.occurrence}`));
    editor.append(el('pre', JSON.stringify(target, null, 2), {class: 'pdf-target-metadata'}));
    if (target.same_name_targets.length) editor.append(el('p', `Shared field path: ${target.same_name_targets.join(', ')}. Occurrences are independent; review each before deliberate linking.`, {class: 'pdf-warning'}));
    const m = mapping() || {disposition: 'blank', reason: '', transforms: [], required_when: null};
    field(editor, 'Friendly label', Object.assign(input(m.label), {id: 'integration-label'}));
    field(editor, 'Section', Object.assign(input(m.section), {id: 'integration-section'}));
    field(editor, 'Disposition', Object.assign(select(['source','computed','constant','blank','excluded','sign_later'], m.disposition), {id: 'integration-disposition'}));
    const choices = [{value:'',label:'Choose typed source…'}, ...catalog.map(s => ({value: JSON.stringify(s.source), label: `${s.label} · ${s.type} · ${s.state} · ${s.source.id || s.source.field}`}))];
    if (m.source && !choices.some(c => c.value === JSON.stringify(m.source))) choices.push({value: JSON.stringify(m.source), label: JSON.stringify(m.source)});
    field(editor, 'Typed saved source', Object.assign(select(choices, m.source ? JSON.stringify(m.source) : ''), {id:'integration-source'}));
    field(editor, 'Reason / invariant approval', Object.assign(input(m.reason), {id:'integration-reason'}));
    const required = input('', 'checkbox'); required.checked = Boolean(m.required); required.id = 'integration-required'; field(editor, 'Required', required);
    field(editor, 'Overflow', Object.assign(select(['block','wrap','shrink'],m.overflow || 'block'), {id:'integration-overflow'}));
    field(editor, 'Missing value', Object.assign(select(['block','blank'],m.missing || 'block'), {id:'integration-missing'}));
    field(editor, 'Font size', Object.assign(input(m.font_size ?? 9,'number'), {id:'integration-font'}));
    field(editor, 'Minimum font size', Object.assign(input(m.minimum_font_size ?? 6,'number'), {id:'integration-min-font'}));
    jsonField(editor, 'Transforms (JSON: date, time, number, concat, lookup)',m.transforms || [],'integration-transforms');
    jsonField(editor, 'Required when (JSON condition or null)',m.required_when || null,'integration-condition');
    jsonField(editor, 'Constant (JSON scalar)',m.constant ?? null,'integration-constant');
    for (const control of editor.querySelectorAll('input,select,textarea')) { control.disabled = draft.status !== 'draft'; control.addEventListener('input', () => { editorDirty = true; markDirty(); }); }
    if (test) button(verified.has(targetId) ? 'Undo selected verification' : 'Verify selected target in current test', () => {
      if (dirty) throw new Error('Save and retest first.');
      if (verified.has(targetId)) verified.delete(targetId); else verified.add(targetId);
      renderTargets(); renderEditor();
    }, editor);
  }
  async function save() {
    captureAll(); const result = await send(`${api}/versions/${draft.id}`, {config:draft.config,expected_revision:draft.revision}, 'PUT');
    dirty = false; test = null; verified.clear(); draft = result;
    await refresh(true); renderTargets(); message('Draft saved. Run tests before verifying fields.');
  }
  if (root) {
    root.innerHTML = `<div id="integration-message" role="status"></div><div id="integration-cards"></div>
      <div id="integration-workspace" class="hidden"><h3 id="integration-version"></h3><p id="integration-coverage"></p>
      <label>Sample inspection: <select id="integration-sample"></select></label>
      <label>Explicit sample panel IDs (comma separated): <input id="integration-sample-panels"></label><button id="integration-load-catalog" type="button">Load source catalog</button><p id="integration-catalog-info"></p>
      <div class="pdf-toolbar"><button id="integration-save" type="button">Save draft</button><button id="integration-copy" type="button">Copy to new draft</button><button id="integration-test" type="button">Run mapping tests</button><a id="integration-test-link" target="_blank" rel="noopener" hidden>Open watermarked tests</a><button id="integration-backup" type="button">Download local configuration</button><button id="integration-reload" type="button">Discard local edits and reload</button></div>
      <label>Publication change summary: <input id="integration-summary" maxlength="1000"></label><button id="integration-publish" type="button">Review and publish</button>
      <details><summary>Inventory diagnostics</summary><pre id="integration-diagnostics"></pre></details>
      <details><summary>Applicability, inputs, groups and policies</summary><p>JSON definitions are declarative, validated on save. Input example: {"id":"remarks","label":"Remarks","meaning":"Defects and work orders","type":"text","required":true}. Do not reuse an ID for a different question.</p><div id="integration-policies"></div></details>
      <div class="pdf-toolbar"><label>Page: <select id="integration-page"></select></label><label>Zoom: <select id="integration-zoom"><option value="0.5">50%</option><option value="1" selected>100%</option><option value="1.5">150%</option><option value="2">200%</option></select></label><label>Find target: <input id="integration-search" type="search"></label><label><input id="integration-unresolved" type="checkbox">Only unresolved / unverified</label></div>
      <div class="pdf-mapping-grid"><div id="integration-targets" aria-label="Exact PDF targets"></div><div class="pdf-page-scroll"><div id="integration-sheet"></div></div><div id="integration-editor"></div></div></div>`;
    $('#integration-load-catalog').addEventListener('click', () => { try { captureEditor(); } catch (error) { message(error.message); return; } loadCatalog().catch(error => message(error.message)); });
    $('#integration-search').addEventListener('input', renderTargets); $('#integration-unresolved').addEventListener('change', renderTargets);
    $('#integration-page').addEventListener('change', event => { page = Number(event.target.value); renderPage(); });
    $('#integration-zoom').addEventListener('change', event => { zoom = Number(event.target.value); renderPage(); });
    const action = (id, fn) => $(id).addEventListener('click', () => Promise.resolve().then(fn).catch(error => message(error.message)));
    action('#integration-save', save);
    action('#integration-copy', async () => { if (dirty) throw new Error('Save or discard edits first.'); const version = await send(`${api}/versions/${draft.id}/copy`, {}); await refresh(true); await openVersion(version); });
    action('#integration-test', async () => {
      if (dirty) throw new Error('Save mapping changes before testing.');
      message('Rendering bounded diagnostic tests…');
      test = await send(`${api}/versions/${draft.id}/test`, {inspection_id:$('#integration-sample').value, panel_ids:$('#integration-sample-panels').value.split(',').map(s => s.trim()).filter(Boolean),expected_revision:draft.revision});
      verified.clear(); const link = $('#integration-test-link'); link.href = `${api}/tests/${test.test_artifact_id}`; link.hidden = false;
      renderEditor(); renderTargets(); message(`Test complete: ${test.scenario_count} scenarios. Review every included page and verify each target.`);
    });
    action('#integration-publish', async () => {
      if (dirty || !test || verified.size !== draft.config.inventory.targets.length) throw new Error('Save, test, and explicitly verify every target before publishing.');
      const summary = $('#integration-summary').value.trim(); if (!summary) throw new Error('Enter the publication change summary.');
      if (!window.confirm(`Publish ${names[selected]}?\n${verified.size} targets verified across pages ${draft.config.inventory.selected_pages.join(', ')}.\n${summary}\nSignatures: ${draft.config.signature_policy}\nThis activates the version; enablement remains a separate decision.`)) return;
      await send(`${api}/versions/${draft.id}/publish`, {inspection_id:$('#integration-sample').value,panel_ids:$('#integration-sample-panels').value.split(',').map(s => s.trim()).filter(Boolean),expected_revision:draft.revision,integration_revision:integrations.find(i => i.key===selected).revision,test_artifact_id:test.test_artifact_id,verified_target_ids:[...verified],confirmed:true,change_summary:summary});
      dirty = false; await refresh(true); message('Verified version published and activated.');
    });
    action('#integration-backup', () => { captureAll(); const blob = new Blob([JSON.stringify(draft.config,null,2)], {type:'application/json'}); const url = URL.createObjectURL(blob); const link = el('a', null, {href:url,download:`${selected}-local-configuration.json`}); link.click(); setTimeout(() => URL.revokeObjectURL(url),1000); });
    action('#integration-reload', async () => { if (dirty && !window.confirm('Discard your unsaved mapping edits? Download a local copy first if needed.')) return; dirty = false; const id = draft.id; await refresh(true); await openVersion(integrations.flatMap(i => i.versions).find(v => v.id===id)); });
    window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  }
  window.PdfIntegrations = {randomId,refreshAdmin: refresh, resetAdmin: () => {draft=null;dirty=false;editorDirty=false;test=null;verified.clear();integrations=[];root?.querySelector('#integration-cards')?.replaceChildren();root?.querySelector('#integration-workspace')?.classList.add('hidden');}};
})();

/* The normal administration workflow uses only Store Data and Check List fields. */
(() => {
  'use strict';
  const host = document.querySelector('#admin-panel-integrations');
  if (!host) return;
  const advanced = window.PdfIntegrations;
  const root = document.createElement('div');
  host.prepend(root);
  const api = '/api/admin/integrations',
    names = {
      nfpa72: 'NFPA 72',
      compliance: 'Compliance Form'
    };
  let integrations = [],
    version = null,
    sources = [],
    mappings = new Map(),
    selected = null,
    page = 1,
    zoom = 1,
    dirty = false,
    busy = false,
    openedRevision = null,
    sourceCatalogHash = null;
  const $ = id => root.querySelector('#simple-' + id);
  const node = (tag, text, attrs = {}) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = text;
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    return n;
  };
  const message = text => {
    $('message').textContent = text;
  };
  const button = (text, action, parent, attrs = {}) => {
    const n = node('button', text, {
      type: 'button',
      ...attrs
    });
    n.addEventListener('click', () => Promise.resolve().then(action).catch(e => message(e.message)));
    parent.append(n);
    return n;
  };
  async function request(path, body) {
    const response = await fetch(api + path, {
      cache: 'no-store',
      ...(body ? {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      } : {})
    });
    const result = await response.json();
    if (!response.ok) throw new Error((response.status === 409 ? 'Your edits are retained. ' : '') + (result.error || result.detail || 'Unable to load integration.'));
    return result;
  }

  function input(value = '', type = 'text') {
    const n = node('input', null, {
      type
    });
    n.value = value ?? '';
    return n;
  }

  function select(options, value) {
    const n = node('select');
    for (const o of options) n.add(new Option(o.label ?? o, o.value ?? o));
    n.value = value ?? '';
    return n;
  }
  const target = () => version?.config.inventory.targets.find(t => t.id === selected);
  const sourceKey = source => JSON.stringify({
    kind: source.kind,
    field: source.field ?? null,
    id: source.id ?? null
  });
  const sourceFor = m => m?.source ? sources.find(s => sourceKey(s.source) === sourceKey(m.source)) : null;
  const mapped = m => m && ['source', 'constant'].includes(m.disposition);

  function change(m) {
    mappings.set(selected, m);
    dirty = true;
    message('Unsaved changes. Save integration to use this mapping on inspections.');
    renderTargets();
    updateSummary();
  }

  function blank(t) {
    return {
      target_id: t.id,
      label: t.tooltip || t.qualified_name || 'PDF field',
      disposition: t.kind === 'signature' ? 'sign_later' : 'blank',
      reason: 'Left unmapped when saving the integration.'
    };
  }

  function updateSummary() {
    const count = [...mappings.values()].filter(mapped).length;
    $('coverage').textContent = `${count} mapped · ${version.config.inventory.targets.length-count} left blank. Saved mappings apply to every inspection.`;
  }
  async function refresh(force = false) {
    if (host.classList.contains('hidden') || busy || (!force && (dirty || host.contains(document.activeElement)))) return;
    const result = await request('');
    integrations = result.integrations;
    renderCards();
  }

  function renderCards() {
    const cards = $('cards');
    cards.replaceChildren();
    for (const integration of integrations) {
      const card = node('section', null, {
        class: 'pdf-integration-card'
      });
      card.append(node('h3', names[integration.key]), node('p', integration.enabled ? 'Ready to export after required mapped data is saved.' : 'Open to configure and save this integration.'));
      const active = integration.versions.find(v => v.id === integration.active_version_id) || integration.versions[0];
      button('Open ' + names[integration.key], async () => {
        if (dirty && !window.confirm('Discard unsaved mapping changes?')) return;
        if (!active) throw new Error('Upload this form template first.');
        await refreshAfterSave();
        const current = integrations.find(i => i.key === integration.key);
        await open(current.versions.find(v => v.id === current.active_version_id) || current.versions[0], current.revision);
      }, card, {
        disabled: active ? 'false' : 'true'
      }).disabled = !active;
      const upload = node('details');
      upload.append(node('summary', active ? 'Replace form template' : 'Upload form template'));
      const file = node('input', null, {
        type: 'file',
        accept: '.pdf',
        'aria-label': names[integration.key] + ' template'
      });
      upload.append(file);
      button('Upload template', async () => {
        if (dirty) throw new Error('Save or discard your edits before replacing the template.');
        if (!file.files[0]) throw new Error('Choose a PDF file.');
        const data = new FormData();
        data.append('file', file.files[0]);
        const response = await fetch(api + '/' + integration.key + '/templates', {
          method: 'POST',
          body: data
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Upload failed.');
        await refresh(true);
        await open(result);
      }, upload);
      card.append(upload);
      cards.append(card);
    }
  }
  async function open(v, integrationRevision = integrations.find(i => i.key === v.config.integration_key).revision) {
    const result = await request('/sources');
    sources = result.entries;
    sourceCatalogHash = result.schema_sha256;
    openedRevision = integrationRevision;
    version = structuredClone(v);
    mappings = new Map();
    for (const t of v.config.inventory.targets) {
      const existing = v.config.mappings.find(m => m.target_id === t.id);
      mappings.set(t.id, existing && (!existing.source || ['inspection', 'checklist'].includes(existing.source.kind)) ? structuredClone(existing) : {
        ...blank(t),
        label: existing?.label || t.tooltip || t.qualified_name
      });
    }
    dirty = false;
    selected = v.config.inventory.targets[0]?.id;
    page = v.config.inventory.selected_pages[0];
    $('workspace').hidden = false;
    $('title').textContent = names[v.key || v.config.integration_key] + ' field mapping';
    $('page').replaceChildren(...v.config.inventory.selected_pages.map(p => new Option('Page ' + p, p)));
    $('page').value = page;
    renderTargets();
    renderPage();
    renderEditor();
    updateSummary();
    message('Select a PDF field on the left, then choose its inspection field on the right. Unmapped fields remain blank.');
  }

  function choose(id) {
    selected = id;
    page = target().page;
    $('page').value = page;
    renderTargets();
    renderPage();
    renderEditor();
    root.querySelector(`[data-preview-target="${id}"]`)?.scrollIntoView({
      block: 'nearest',
      inline: 'nearest'
    });
  }

  function renderTargets() {
    const list = $('targets');
    list.replaceChildren();
    const search = $('search').value.toLowerCase();
    for (const t of version.config.inventory.targets) {
      const m = mappings.get(t.id);
      const label = m.label || t.tooltip || t.qualified_name || 'PDF field';
      if (!`${label} ${t.qualified_name} page ${t.page}`.toLowerCase().includes(search)) continue;
      button(`Page ${t.page} · ${label} — ${mapped(m)?'Mapped':'Blank'}`, () => choose(t.id), list, {
        'data-target': t.id,
        'aria-pressed': String(selected === t.id)
      });
    }
  }

  function renderPage() {
    const geometry = version.config.inventory.pages.find(p => p.number === page);
    const sheet = $('sheet');
    sheet.replaceChildren();
    sheet.style.width = geometry.display_width * zoom + 'px';
    sheet.style.height = geometry.display_height * zoom + 'px';
    sheet.append(node('img', null, {
      src: api + '/versions/' + version.id + '/pages/' + page,
      alt: names[version.config.integration_key] + ' page ' + page
    }));
    for (const t of version.config.inventory.targets.filter(t => t.page === page)) {
      const [x0, y0, x1, y1] = t.preview_rect;
      const b = button('', () => choose(t.id), sheet, {
        class: 'pdf-target',
        'data-preview-target': t.id,
        'aria-label': t.tooltip || t.qualified_name || 'PDF field',
        'aria-pressed': String(t.id === selected)
      });
      Object.assign(b.style, {
        left: 100 * x0 / geometry.display_width + '%',
        top: 100 * y0 / geometry.display_height + '%',
        width: 100 * (x1 - x0) / geometry.display_width + '%',
        height: 100 * (y1 - y0) / geometry.display_height + '%'
      });
    }
  }

  function renderEditor() {
    const editor = $('editor');
    editor.replaceChildren();
    const t = target();
    if (!t || ['signature', 'unknown', 'pushbutton'].includes(t.kind)) return;
    let m = mappings.get(selected);
    const current = sourceFor(m);
    const buttonTarget = ['checkbox', 'radio'].includes(t.kind);
    const tools = node('div', null, {class: 'pdf-mapping-tools'});
    const clear = button('×', () => {
      change({...blank(t), label: m.label || t.tooltip || t.qualified_name});
      renderEditor();
    }, tools, {'aria-label': 'Clear mapping', title: 'Clear mapping', class: 'pdf-clear-mapping'});
    clear.disabled = !mapped(m);
    if (!buttonTarget) {
      const defaultValue = m.default_value ?? (m.disposition === 'constant' ? m.constant : '') ?? '';
      const value = current?.options?.length ? select([
        {value: '', label: 'Default'}, ...current.options
      ], defaultValue) : input(defaultValue, current?.type === 'date' ? 'date' : 'text');
      value.setAttribute('aria-label', 'Default value');
      value.setAttribute('placeholder', 'Default');
      value.title = 'Used only when the mapped field is empty';
      value.addEventListener('input', () => {
        const fallback = value.value.trim() === '' ? null : value.value;
        if (m.source) m = {...m, default_value: fallback};
        else m = fallback !== null ? {
          ...m, disposition: 'constant', constant: fallback,
          reason: 'Administrator configured a fixed default value.'
        } : {...blank(t), label: m.label};
        change(m);
        clear.disabled = !mapped(m);
      });
      tools.append(value);
    } else {
      const check = select(['Yes', 'No', 'NA'], m.check_on || 'Yes');
      check.setAttribute('aria-label', 'Mark when the saved answer is');
      check.title = 'Mark when the saved answer is';
      check.addEventListener('change', () => {
        m = {...m, check_on: check.value};
        change(m);
      });
      tools.append(check);
    }
    if (!current) editor.append(tools);
    const choices = node('div', null, {class: 'pdf-source-choices', 'aria-label': 'Inspection fields'});
    editor.append(choices);
    let selectedButton = null;
    for (const group of ['Store Data', 'Check List']) {
      const section = node('section', null, {'data-source-group': group});
      section.append(node('h4', group));
      for (const source of sources.filter(s => s.section === group)) {
        const active = !!current && sourceKey(current.source) === sourceKey(source.source);
        const row = node('div', null, {class: 'pdf-source-row' + (active ? ' is-mapped' : '')});
        const b = button(source.label, () => {
          // Re-selecting the current source must retain its default, required
          // setting and date/result formatting.
          if (active) return;
          change({
            target_id: t.id, label: m.label || t.tooltip || t.qualified_name,
            disposition: 'source', source: source.source, required: !!m.required,
            missing: m.required ? 'block' : 'blank',
            reason: 'Optional fields may be left blank when no saved answer is available.',
            overflow: 'shrink', font_size: 9, minimum_font_size: 6,
            transforms: source.type === 'date' ? [{kind: 'date', format: '%m/%d/%Y'}] : [],
            check_on: buttonTarget ? (m.check_on || 'Yes') : null
          });
          renderEditor();
        }, row, {
          'data-source-section': group, 'aria-pressed': String(active)
        });
        b.disabled = buttonTarget && source.type !== 'yes_no_na';
        if (b.disabled) b.title = 'Result marks need a Yes/No/NA Check List field.';
        if (active) {
          row.append(clear, tools);
          selectedButton = b;
        }
        section.append(row);
      }
      choices.append(section);
    }
    // Keep the mapped source visible when returning to a PDF field, including
    // a Check List source below a long Store Data list. Do not scroll the page.
    if (selectedButton) choices.scrollTop = Math.max(0,
      selectedButton.offsetTop - choices.clientHeight / 2);
  }
  async function save() {
    if (!version || busy) return;
    busy = true;
    $('save').disabled = true;
    message('Validating mappings and preparing the integration…');
    try {
      const revision = openedRevision;
      const saved = await request('/versions/' + version.id + '/save-integration', {
        expected_revision: version.revision,
        integration_revision: revision,
        source_catalog_sha256: sourceCatalogHash,
        mappings: [...mappings.values()]
      });
      dirty = false;
      await refreshAfterSave();
      await open(saved);
      message('Integration saved and ready. Open an inspection, save its Store Data and Check List answers, then export ' + names[saved.key] + '.');
    } finally {
      busy = false;
      $('save').disabled = false;
    }
  }
  async function refreshAfterSave() {
    integrations = (await request('')).integrations;
    renderCards();
  }
  root.innerHTML = `<div id="simple-message" role="status"></div><div id="simple-cards"></div><section id="simple-workspace" hidden><h3 id="simple-title"></h3><p id="simple-coverage"></p><p>Map Store Data and Check List fields. Points Lists and Events are not used. Unmapped PDF fields stay blank.</p><div class="pdf-toolbar"><button id="simple-save" type="button">Save integration</button><button id="simple-discard" type="button">Discard changes</button><label>Page: <select id="simple-page"></select></label><label>Zoom: <select id="simple-zoom"><option value="0.5">50%</option><option value="1" selected>100%</option><option value="1.5">150%</option></select></label><label>Find PDF field: <input id="simple-search" type="search"></label></div><div class="pdf-mapping-grid"><div id="simple-targets" aria-label="PDF fields"></div><div class="pdf-page-scroll"><div id="simple-sheet" class="pdf-simple-sheet"></div></div><div id="simple-editor"></div></div></section>`;
  $('save').addEventListener('click', () => save().catch(e => message(e.message)));
  $('discard').addEventListener('click', async () => {
    if (dirty && !window.confirm('Discard your unsaved mapping edits and load current saved mappings?')) return;
    try {
      await refreshAfterSave();
      const current = integrations.find(i => i.key === version.config.integration_key);
      await open(current.versions.find(v => v.id === current.active_version_id) || current.versions[0], current.revision);
    } catch (e) { message(e.message); }
  });
  $('search').addEventListener('input', () => version && renderTargets());
  $('page').addEventListener('change', () => {
    page = Number($('page').value);
    renderPage();
  });
  $('zoom').addEventListener('change', () => {
    zoom = Number($('zoom').value);
    renderPage();
  });
  const debug = node('details', null, {
    id: 'integration-debug-mode'
  });
  debug.append(node('summary', 'Debug mode — technical configuration and version history'));
  const debugRoot = document.querySelector('#integration-debug-workspace');
  debug.append(debugRoot);
  host.append(debug);
  debug.addEventListener('toggle', () => {
    debugRoot.classList.toggle('hidden', !debug.open);
    if (debug.open) advanced.refreshAdmin(true);
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  window.PdfIntegrations = {
    ...advanced,
    refreshAdmin: async (force = false) => {
      try {
        await refresh(force);
        if (debug.open) await advanced.refreshAdmin(force);
      } catch (e) {
        message(e.message);
      }
    },
    resetAdmin: () => {
      advanced.resetAdmin();
      version = null;
      dirty = false;
      busy = false;
      integrations = [];
      sources = [];
      mappings.clear();
      $('cards').replaceChildren();
      $('workspace').hidden = true;
      debug.open = false;
    }
  };
})();

/* Inspection-specific decisions have their own draft/sync lifecycle. */
(() => {
  'use strict';
  const root = document.querySelector('#form-details-integrations');
  if (!root) return;
  const message = document.querySelector('#form-details-message');
  const names = {nfpa72:'NFPA 72',compliance:'Compliance inspection'};
  const records = new Map();
  let active = null, epoch = 0, reading = false, controller = null;
  const fieldKey = field => `${field.definition.id}:${field.panel_id || ''}`;
  const localKey = (key,field) => `${key}:${fieldKey(field)}`;
  const state = id => {
    if (!records.has(id)) records.set(id,{forms:[],locals:new Map(),scopes:new Map(),archive:[]});
    return records.get(id);
  };
  const node = (tag,text,attrs={}) => {
    const result=document.createElement(tag); if (text != null) result.textContent=text;
    for (const [key,value] of Object.entries(attrs)) result.setAttribute(key,value);
    return result;
  };
  async function read(url,options={}) {
    const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(10000),...options});
    const value=await response.json();
    if (!response.ok) throw new Error((response.status===409 ? 'Conflict: your answer is retained. ' : '')+(value.error || value.detail || 'Unable to save Form Details.'));
    return value;
  }
  const url=(id,key='') => `/api/inspections/${encodeURIComponent(id)}/form-integrations${key ? '/'+key : ''}`;
  const put=(path,value) => read(path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
  function act(parent,text,fn,attrs={}) {
    const button=node('button',text,{type:'button',...attrs});
    button.addEventListener('click',()=>Promise.resolve().then(fn).catch(error=>{message.textContent=error.message;})); parent.append(button); return button;
  }
  function local(record,key,field,version) {
    const id=localKey(key,field);
    if (!record.locals.has(id)) record.locals.set(id,{value:field.source.value,base:field.source.fingerprint,version,dirty:false,error:'',override:field.override,saving:null,serial:0});
    return record.locals.get(id);
  }
  function replaceForm(record,form) {
    const index=record.forms.findIndex(f=>f.key===form.key);
    if (index<0) record.forms.push(form); else record.forms[index]=form;
  }
  function setInspection(id) {
    if (active===id) return;
    previewDialog?.close();previewDialog?.remove();previewDialog=null;
    active=id;epoch++;controller?.abort();reading=false;root.replaceChildren();message.textContent='';
    if (id) { render(); refresh(); }
  }
  async function refresh() {
    const id=active,version=epoch;
    if (!id || reading || document.hidden) return;
    reading=true;controller=new AbortController(); const currentController=controller;
    const timeout=setTimeout(()=>currentController.abort(),10000);
    try {
      const result=await read(url(id),{signal:currentController.signal});
      if (active!==id || epoch!==version) return;
      if(!state(id).forms.length)root.replaceChildren();state(id).forms=result.integrations;render();
      if (message.textContent.startsWith('Form Details unavailable')) message.textContent='';
    } catch (error) {
      if (active===id && epoch===version) {
        message.textContent='Form Details unavailable: '+error.message+' Existing inspection actions remain available. Retrying automatically.';
        if(!state(id).forms.length){root.replaceChildren();for(const key of ['nfpa72','compliance']){const card=node('section',null,{class:'pdf-form-card'});card.append(node('h3',names[key]),node('p','Integration disabled or unavailable.'));card.append(node('button',key==='nfpa72'?'Export NFPA 72':'Export Compliance Form',{type:'button',disabled:'disabled'}));root.append(card);}}
      }
    } finally { clearTimeout(timeout);if (epoch===version) reading=false; }
  }
  function render() {
    if (!active) return;
    const record=state(active);
    for (const form of record.forms) renderForm(record,form);
  }
  function renderForm(record,form) {
    let card=root.querySelector(`[data-form="${form.key}"]`);
    const schema=JSON.stringify([form.version_id,form.fields.map(f=>[fieldKey(f),f.definition]),form.panels]);
    const previous=card?.dataset.schema;
    const hasDirty=[...record.locals.entries()].some(([key,value])=>key.startsWith(form.key+':')&&(value.dirty||value.saving));
    if (card && previous!==schema && hasDirty) {
      card.querySelector('.pdf-form-summary').textContent='Published definitions or panel scope changed. Your local answers are retained. Download them, then review current definitions before saving.';
      card.querySelectorAll('.pdf-export-action').forEach(b=>b.disabled=true);return;
    }
    if (!card || previous!==schema) {
      if (card) { for (const [key,value] of record.locals) if (key.startsWith(form.key+':')) { record.archive.push({key,...value,saving:null});record.locals.delete(key); } card.remove(); }
      card=node('section',null,{class:'pdf-form-card','data-form':form.key,'data-schema':schema});
      card.append(node('h3',names[form.key]),node('p','',{class:'pdf-form-summary',role:'status'}));
      const scope=node('div',null,{class:'pdf-form-scope'});card.append(scope);buildScope(record,form,scope);
      for (const field of form.fields) buildField(record,form,field,card);
      const controls=node('div',null,{class:'pdf-toolbar'});card.append(controls);
      if (form.mapping_mode!=='store_checklist') {
      act(controls,'Save '+names[form.key]+' details',()=>saveForm(form.key));
      act(controls,'Download local answers',()=>backup(record,form.key));
      act(controls,'Review current saved answers and definitions',async()=>{
        if (!window.confirm('Retain local answers in this session’s review archive and load current saved definitions? Download local answers first if you need a permanent copy.')) return;
        for (const [key,value] of record.locals) if (key.startsWith(form.key+':')) {record.archive.push({key,...value,saving:null});record.locals.delete(key);}
        record.scopes.delete(form.key);card.remove();await refresh();render();
      });
      }
      act(controls,form.key==='nfpa72'?'Export NFPA 72':'Export Compliance Form',()=>openPreview(form.key), {class:'pdf-export-action',disabled:'disabled'});
      act(controls,'Export history',()=>loadHistory(form.key));
      card.append(node('div',null,{class:'pdf-export-history'}));
      card.append(node('p',form.export_reason,{class:'pdf-export-reason'}));
      card.append(node('ul',null,{class:'pdf-readiness-blockers'}));root.append(card);
    }
    card.querySelector('.pdf-form-summary').textContent=form.mapping_mode==='store_checklist' ? (form.readiness.ready?'Saved Store Data and Check List answers are ready to export.':'Complete the required mapped Store Data or Check List fields below.') : form.version_id ? `Version ${form.version_id} · ${hasDirty ? 'Local changes unsaved · ' : ''}${form.readiness.ready ? 'Saved data ready' : 'Resolve the blockers below'} · Signatures: ${({later_signing:'reserved for later signing',signed_required:'a supported signature is required',unresolved:'policy needs review'})[form.signature_policy] || 'policy needs review'}. Supplemental sheets: ${form.supplemental_policy==='manual_declaration'?'a saved declaration is required; reports remain separate':form.supplemental_policy==='not_applicable'?'not applicable under the reviewed policy':'policy needs review'}.` : 'Integration disabled or unconfigured.';
    card.querySelector('.pdf-export-action').disabled=!form.export_available || hasDirty || Boolean(record.scopes.get(form.key)?.dirty);
    card.querySelector('.pdf-export-reason').textContent=form.export_reason;
    const scopeState=record.scopes.get(form.key);
    if (!scopeState?.dirty && !scopeState?.saving) {
      for (const control of card.querySelectorAll('[data-scope-panel]')) control.checked=form.panel_ids.includes(control.dataset.scopePanel);
      if (scopeState) { scopeState.revision=form.scope_revision; scopeState.panels=[...form.panel_ids]; }
    }
    for (const field of form.fields) {
      const row=[...card.querySelectorAll('[data-input-key]')].find(r=>r.dataset.inputKey===fieldKey(field));if (!row) continue;
      const draft=local(record,form.key,field,form.version_id);
      const control=row.querySelector('[data-answer]');
      if (!draft.dirty && !draft.saving && !row.contains(document.activeElement)) {
        draft.value=field.source.value;draft.base=field.source.fingerprint;draft.version=form.version_id;draft.override=field.override;
        if(control.tagName==='SELECT' && field.source.value && ![...control.options].some(o=>o.value===field.source.value))control.add(new Option('Needs review: '+field.source.value,field.source.value));
        control.value=field.source.value ?? '';
      }
      const originalSelector=row.querySelector('[data-override-source]');
      if(originalSelector && !row.contains(document.activeElement) && !draft.dirty && !draft.saving){
        const old=originalSelector.value; originalSelector.replaceChildren(new Option('Choose current original source…',''));
        for(const entry of form.catalog.entries.filter(e=>e.state==='ready' && !(e.source.kind==='manual'&&e.source.id===field.definition.id)))originalSelector.add(new Option(`${entry.label} · ${JSON.stringify(entry.value)}`,JSON.stringify(entry)));
        originalSelector.value=old;
      }
      row.querySelector('.pdf-field-status').textContent=draft.error || (draft.dirty?'Unsaved changes':field.source.message || field.source.state)+(field.override?' · Override: '+field.override.reason:'');
      row.querySelector('.pdf-field-status').classList.toggle('pdf-warning',Boolean(draft.error)||draft.dirty||field.source.state==='changed');
    }
    const blockers=card.querySelector('.pdf-readiness-blockers');blockers.replaceChildren();
    if (form.scope_changed) blockers.append(node('li','Scope policy changed. Review and explicitly save panel scope again.'));
    for (const blocker of form.readiness.blockers) {
      const item=node('li');const link=node('button',`${blocker.section ? blocker.section+': ' : ''}${blocker.message}`,{type:'button',class:'secondary'});
      link.addEventListener('click',()=>{
        const ids={store_data:'store-data-section',checklist:'checklist-section',points:'points-events-section',form_details:'export-form-details-section'};
        const section=document.getElementById(ids[blocker.navigation] || 'export-form-details-section');if(section){section.open=true;section.scrollIntoView({block:'start'});}
        if(blocker.navigation==='checklist'){const task=[...document.querySelectorAll('[data-task-id]')].find(control=>control.dataset.taskId===blocker.source_id);task?.focus();}
        const fieldRow=[...card.querySelectorAll('[data-input-key]')].find(row=>row.dataset.inputKey.startsWith(blocker.source_id+':'));
        fieldRow?.querySelector('[data-answer]')?.focus();
      });item.append(link);blockers.append(item);
    }
  }
  function buildScope(record,form,parent) {
    if(form.mapping_mode==='store_checklist')return;
    parent.append(node('p',form.applicability==='no_panel'?'Reviewed policy: no panel data required.':`Explicit ${form.applicability || 'unconfigured'} scope. Required categories: ${form.categories.join(', ')}`));
    if (!form.version_id || form.applicability==='no_panel') return;
    if (!record.scopes.has(form.key)) record.scopes.set(form.key,{panels:[...form.panel_ids],revision:form.scope_revision,dirty:false,saving:false});
    const scope=record.scopes.get(form.key);
    for (const panel of form.panels) {
      const label=node('label');const checkbox=node('input',null,{type:'checkbox','data-scope-panel':panel.id,'aria-label':`${names[form.key]} panel ${panel.category} ${panel.filename}`});
      checkbox.checked=scope.panels.includes(panel.id);label.append(checkbox,document.createTextNode(` ${panel.category}: ${panel.filename} (${panel.id})`));parent.append(label);
      checkbox.addEventListener('change',()=>{scope.panels=[...parent.querySelectorAll('input:checked')].map(i=>i.dataset.scopePanel);scope.dirty=true;message.textContent='Unsaved panel selection. Save scope before entering panel-specific details.';});
    }
    act(parent,'Save explicit panel scope',async()=>{
      const inspectionId=active;
      if ([...record.locals.entries()].some(([key,v])=>key.startsWith(form.key+':')&&(v.dirty||v.saving))) throw new Error('Save or archive your local answers before changing panel scope.');
      scope.saving=true;
      try {
        const result=await put(url(inspectionId,form.key)+'/scope',{version_id:form.version_id,expected_revision:scope.revision,panel_ids:scope.panels});
        scope.dirty=false;scope.revision=result.scope_revision;replaceForm(record,result);if(active===inspectionId){render();message.textContent='Panel scope saved.';}
      } finally {scope.saving=false;}
    });
  }
  function buildField(record,form,field,parent) {
    const definition=field.definition;const draft=local(record,form.key,field,form.version_id);
    const row=node('div',null,{class:'pdf-form-input','data-input-key':fieldKey(field)});parent.append(row);
    const id=`form-detail-${form.key}-${definition.id}-${field.panel_id || 'inspection'}`;
    row.append(node('label',`${definition.label}${field.panel_id?' · panel '+field.panel_id:''}${definition.unit?' ('+definition.unit+')':''} · ${definition.required?'required':definition.required_when?'conditionally required':'optional'}`,{for:id}));
    let control;
    if (['yes_no_na','dropdown'].includes(definition.type)) {
      control=node('select');control.add(new Option('Unanswered',''));
      for (const option of definition.type==='yes_no_na'?['Yes','No','NA']:definition.options) control.add(new Option(option,option));
      if (draft.value && ![...control.options].some(o=>o.value===draft.value)) control.add(new Option('Needs review: '+draft.value,draft.value));
    } else {
      control=node('input',null,{type:definition.type==='number'?'number':definition.type==='date'?'date':'text'});
      if (definition.type==='number') {control.step='any';if(definition.minimum!==null)control.min=definition.minimum;if(definition.maximum!==null)control.max=definition.maximum;}
      if (definition.type==='datetime') control.placeholder='YYYY-MM-DDTHH:MM:SS+HH:MM';
      if (definition.type==='text') control.maxLength=2000;
    }
    if(definition.required_when){
      const dependency=definition.required_when.source;
      act(row,`Required when ${dependency.kind} ${dependency.id || dependency.field} ${definition.required_when.operator}`,()=>{
        const section=document.getElementById(dependency.kind==='checklist'?'checklist-section':dependency.kind==='inspection'?'store-data-section':'export-form-details-section');
        if(section){section.open=true;section.scrollIntoView({block:'start'});}
        const control=[...document.querySelectorAll('[data-task-id]')].find(c=>c.dataset.taskId===dependency.id);control?.focus();
      });
    }
    control.id=id;control.dataset.answer='true';control.value=draft.value ?? '';row.append(control,node('p',definition.meaning),node('span','',{class:'pdf-field-status',role:'status'}));
    const update=()=>{draft.serial++;draft.invalid=!control.checkValidity();draft.value=control.value===''?null:definition.type==='number'?Number(control.value):control.value;draft.dirty=true;draft.error='';row.querySelector('.pdf-field-status').textContent='Unsaved changes';};
    control.addEventListener('input',update);
    control.addEventListener(control.tagName==='SELECT'?'change':'blur',()=>{if(draft.dirty)saveField(record,form,field).catch(()=>{});});
    control.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();if(draft.dirty)saveField(record,form,field).catch(()=>{});}});
    act(row,'Save / confirm '+definition.label,()=>saveField(record,form,field,true));
    const override=node('details');override.open=Boolean(draft.overridePending);override.append(node('summary','Override a saved source (requires a reason)'));row.append(override);
    const source=node('select',null,{'data-override-source':'true','aria-label':`Original source for ${definition.label}`});source.add(new Option('Choose current original source…',''));
    for (const entry of form.catalog.entries.filter(e=>e.state==='ready' && !(e.source.kind==='manual'&&e.source.id===definition.id))) source.add(new Option(`${entry.label} · ${JSON.stringify(entry.value)}`,JSON.stringify(entry)));
    const reason=node('input',null,{'aria-label':`Override reason for ${definition.label}`,maxlength:'1000',placeholder:'Reason for this override'});reason.value=draft.overrideReason ?? draft.override?.reason ?? '';source.value=draft.overrideSource ?? '';override.append(source,reason);
    reason.addEventListener('input',()=>{draft.serial++;draft.overrideReason=reason.value;draft.dirty=true;draft.error='Override not saved: choose its source and use Save override.';draft.overridePending=true;});
    source.addEventListener('change',()=>{draft.serial++;draft.overrideSource=source.value;draft.dirty=true;draft.overridePending=true;});
    act(override,'Save override for '+definition.label,async()=>{
      if (!reason.value.trim()||!source.value) throw new Error('Select the current source and enter an override reason.');
      const original=JSON.parse(source.value);draft.serial++;draft.override={override:true,reason:reason.value,overridden_source:original.source,source_fingerprint:original.fingerprint,original_value:original.value};draft.overridePending=false;draft.dirty=true;
      await saveField(record,form,field,true);
    });
    act(override,'Save as ordinary answer',async()=>{draft.serial++;draft.override=null;draft.overridePending=false;draft.dirty=true;await saveField(record,form,field,true);});
  }
  async function saveField(record,form,field,force=false) {
    const draft=local(record,form.key,field,form.version_id);
    if (draft.saving) {await draft.saving;if(draft.dirty)return saveField(record,form,field,force);return true;}
    if (!draft.dirty&&!force) return true;
    if(record.scopes.get(form.key)?.dirty){draft.error='Save explicit panel scope before saving this answer.';render();throw new Error(draft.error);}
    if(draft.invalid){draft.error='Enter a valid value within the configured bounds.';render();throw new Error(draft.error);}
    if(draft.overridePending){draft.error='Complete the source and reason, then use Save override.';render();throw new Error(draft.error);}
    const id=[...records].find(([,v])=>v===record)[0];const value=draft.value;const serial=draft.serial;const proof=draft.override ? {...draft.override} : {};
    delete proof.schema_version;delete proof.input_id;delete proof.value;
    draft.saving=(async()=>{
      try {
        const result=await put(url(id,form.key)+'/answers',{version_id:draft.version,panel_id:field.panel_id,expected_fingerprint:draft.base,answer:{input_id:field.definition.id,value,...proof}});
        const saved=result.fields.find(f=>fieldKey(f)===fieldKey(field));
        draft.base=saved.source.fingerprint;
        if(draft.serial===serial && !draft.overridePending && JSON.stringify(draft.value)===JSON.stringify(value))draft.dirty=false;
        draft.error='';replaceForm(record,result);
        if(active===id)message.textContent='Form Details saved.';
        return true;
      } catch(error) {draft.error=error.message;draft.dirty=true;if(active===id)message.textContent='Form Details not saved. Your local answer is retained. '+error.message;throw error;}
      finally {draft.saving=null;if(active===id)render();}
    })();
    return draft.saving;
  }
  async function saveForm(key) {
    const record=state(active);const form=record.forms.find(f=>f.key===key);
    if(record.scopes.get(key)?.dirty)throw new Error('Save explicit panel scope first.');
    for(const field of form.fields)await saveField(record,form,field);
    await refresh();return true;
  }
  async function saveDetails() {
    if(!active)return true;
    try {for(const form of state(active).forms)await saveForm(form.key);return true;}catch(error){message.textContent=error.message;return false;}
  }
  let previewDialog=null;
  const post=(path,value)=>read(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
  function hasUnsaved(record,key){return [...record.locals].some(([id,v])=>id.startsWith(key+':')&&(v.dirty||v.saving))||record.scopes.get(key)?.dirty;}
  async function openPreview(key){
    const inspectionId=active;const record=state(inspectionId);
    if(hasUnsaved(record,key))throw new Error('Save all Form Details before previewing.');
    if(window.PdfIntegrations.hasLegacyDrafts?.())throw new Error('Save pending Store Data, checklist and point edits before previewing.');
    const legacy=document.querySelector('#inspection-screen');
    if([...legacy.querySelectorAll('[data-task-id]')].some(control=>control.dataset.saving==='true'))throw new Error('Wait for inspection saves to finish.');
    const form=record.forms.find(f=>f.key===key);
    message.textContent='Preparing saved-data preview…';
    const preview=await post(url(inspectionId,key)+'/preview',{expected_version_id:form.version_id,expected_source_fingerprint:form.readiness.source_fingerprint});
    if(active!==inspectionId)return;
    previewDialog?.remove();const dialog=node('dialog',null,{class:'pdf-export-dialog','aria-label':'Review completed form preview'});previewDialog=dialog;
    dialog.append(node('h3',names[key]+' — Draft preview'),node('p',`Version ${preview.version_id}. Scope: ${preview.panel_ids.join(', ')||'reviewed no-panel policy'}. Signatures remain blank for later signing.`));
    const blanks=node('details');blanks.append(node('summary','Deliberately blank destinations'));
    for(const blank of preview.deliberately_blank)blanks.append(node('p',`${blank.label||blank.target_id}: ${blank.reason}`));dialog.append(blanks);
    const frame=node('iframe',null,{title:'Watermarked form preview',src:url(inspectionId,key)+`/exports/${preview.id}/download`});dialog.append(frame);
    const status=node('p','Review every included page before confirming.',{role:'status'});dialog.append(status);
    const requestId=window.PdfIntegrations.randomId();
    const confirmButton=act(dialog,'Confirm and download completed PDF',async()=>{
      if(active!==inspectionId || hasUnsaved(record,key) || window.PdfIntegrations.hasLegacyDrafts?.())throw new Error('Inspection changed or has unsaved edits. Close this preview and save first.');
      confirmButton.disabled=true;status.textContent='Confirming saved data and retaining the final PDF…';
      try{
        const artifact=await post(url(inspectionId,key)+'/exports',{preview_id:preview.id,confirmation_token:preview.confirmation_token,preview_sha256:preview.sha256,request_id:requestId,confirmed:true});
        if(artifact.status!=='ready'){status.textContent=`Export ${artifact.status}. Check Export history; retries use the same confirmation.`;return;}
        const link=node('a','Download completed PDF',{href:url(inspectionId,key)+`/exports/${artifact.id}/download`,download:artifact.filename});status.replaceChildren(link);link.click();
        await loadHistory(key);
      }catch(error){status.textContent=error.message+' Your inspection data is preserved.';}
      finally{confirmButton.disabled=false;}
    });
    act(dialog,'Close preview',()=>{dialog.close();dialog.remove();});document.body.append(dialog);dialog.showModal();
    dialog.addEventListener('cancel',()=>dialog.remove());message.textContent='Draft preview ready.';
  }
  async function loadHistory(key){
    const inspectionId=active;const result=await read(url(inspectionId,key)+'/exports');if(active!==inspectionId)return;
    const container=root.querySelector(`[data-form="${key}"] .pdf-export-history`);if(!container)return;container.replaceChildren(node('h4','Retained exports'));
    for(const artifact of result.exports){
      const row=node('p',`${artifact.created_at} · ${artifact.status} · ${artifact.filename} `);
      if(artifact.status==='ready')row.append(node('a','Download',{href:url(inspectionId,key)+`/exports/${artifact.id}/download`,download:artifact.filename}));
      else if(artifact.status==='pending')act(row,'Recover pending export',async()=>{await post(url(inspectionId,key)+`/exports/${artifact.id}/recover`,{});await loadHistory(key);});
      const debug=node('details');debug.append(node('summary','Debug provenance'),node('a','View technical provenance',{href:url(inspectionId,key)+`/exports/${artifact.id}/provenance`,target:'_blank',rel:'noopener'}));row.append(debug);container.append(row);
    }
    if(!result.exports.length)container.append(node('p','No completed exports have been requested.'));
  }
  function backup(record,key) {
    const blob=new Blob([JSON.stringify({answers:[...record.locals].filter(([id])=>id.startsWith(key+':')).map(([id,v])=>({id,...v,saving:null})),archived:record.archive},null,2)],{type:'application/json'});
    const link=node('a',null,{href:URL.createObjectURL(blob),download:`${key}-local-answers.json`});link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
  }
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  window.addEventListener('online',refresh);
  window.addEventListener('beforeunload',event=>{if([...records.values()].some(r=>[...r.locals.values()].some(v=>v.dirty)||[...r.scopes.values()].some(s=>s.dirty))){event.preventDefault();event.returnValue='';}});
  let owner=null;
  const setActor=id=>{if(!id){setInspection(null);return;}if(owner && owner!==id){setInspection(null);records.clear();window.PdfIntegrations.resetAdmin();}owner=id;};
  Object.assign(window.PdfIntegrations,{setInspection,refreshDetails:refresh,saveDetails,setActor});
})();
