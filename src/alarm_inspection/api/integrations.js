/* Additive PDF integration workspace. All authoritative rules remain in Python. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const root = $('#admin-panel-integrations');
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
    const wrapper = el('div', null, {class: 'form-field'}); const id = control.id || `pdf-control-${crypto.randomUUID()}`;
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
      if (latest) card.append(el('p', `Fingerprint ${latest.config.original.sha256} · ${latest.verification.fields?.length || 0}/${latest.config.inventory.targets.length} verified · editor ${latest.created_by} · ${latest.updated_at}`));
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
      ['signature_policy', 'Signature policy', ['unresolved', 'later_signing', 'signed_required']],
      ['supplemental_policy', 'Supplemental policy', ['unresolved', 'manual_declaration', 'not_applicable']],
    ]) {
      const control = field(controls, label, select(options, draft.config[key]));
      control.disabled = draft.status !== 'draft'; control.addEventListener('change', () => { draft.config[key] = control.value || null; markDirty(); });
    }
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
      const node = button(`${target.occurrence}`, () => choose(target.id), sheet, {class: 'pdf-target', 'aria-label': `Page ${page} occurrence ${target.occurrence} ${target.qualified_name}`, 'aria-pressed': String(target.id === targetId)});
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
  window.PdfIntegrations = {refreshAdmin: refresh};
})();
