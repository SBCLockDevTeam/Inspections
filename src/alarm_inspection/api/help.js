(() => {
  const panel = document.getElementById('admin-panel-help');
  let enabled = {};
  const el = (tag, text) => { const n = document.createElement(tag); if (text) n.textContent = text; return n; };
  async function api(url, options) {
    const r = await fetch(url, options); const data = await r.json();
    if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.error || 'Unable to save help.');
    return data;
  }
  function dialog(title) {
    const d = el('dialog'); d.className = 'field-help-dialog';
    const close = el('button', 'Close'); close.type = 'button'; close.className = 'secondary';
    const heading = el('h2', title); const content = el('div');
    d.append(close, heading, content); document.body.append(d);
    close.onclick = () => d.close();
    d.addEventListener('close', () => { d.querySelectorAll('video').forEach(v => v.pause()); d.remove(); });
    d.showModal(); return {d, content};
  }
  function mediaNode(item) {
    const node = el(item.type.startsWith('video/') ? 'video' : 'img');
    node.src = `/api/help/media/${encodeURIComponent(item.id)}`;
    if (node.tagName === 'VIDEO') { node.controls = true; node.playsInline = true; node.preload = 'metadata'; }
    else { node.alt = item.name; node.loading = 'lazy'; }
    return node;
  }
  function show(id, label) {
    const h = enabled[id]; if (!h) return;
    const {content} = dialog(label);
    const text = el('p', h.body); text.style.whiteSpace = 'pre-wrap'; content.append(text);
    for (const item of h.media) content.append(mediaNode(item));
  }
  function attach(root, id, label) {
    if (!root || !enabled[id] || root.querySelector(`button[data-help-id="${CSS.escape(id)}"]`)) return;
    const b = el('button', '?'); b.type = 'button'; b.className = 'field-help-button'; b.dataset.helpId = id;
    b.setAttribute('aria-label', `Help: ${label}`); b.title = `Help: ${label}`;
    b.onclick = e => { e.preventDefault(); e.stopPropagation(); show(id, label); };
    root.append(b);
  }
  function decorate() {
    document.querySelectorAll('[data-help-id]').forEach(b => { if (!enabled[b.dataset.helpId]) b.remove(); });
    document.querySelectorAll('[data-custom-field]').forEach(row => attach(row.querySelector('label,.inspection-task-description'), row.dataset.customField, row.querySelector('label,.inspection-task-description')?.childNodes[0]?.textContent || 'Field help'));
    document.querySelectorAll('[data-inspection-field]').forEach(row => attach(row.querySelector('label'), `builtin:${row.dataset.inspectionField}`, row.querySelector('label')?.childNodes[0]?.textContent || 'Field help'));
    document.querySelectorAll('#new-inspection-form [name]').forEach(control => attach(control.closest('.form-field')?.querySelector('label'), `builtin:${control.name}`, control.name.replaceAll('_',' ')));
    document.querySelectorAll('[data-help-field]').forEach(row => attach(row, row.dataset.helpField, row.childNodes[0]?.textContent || 'Field help'));
  }
  async function refresh() { try { enabled = await api('/api/help'); decorate(); } catch { enabled = {}; decorate(); } }
  async function save(field, h) {
    field.help = await api(`/api/admin/help/${encodeURIComponent(field.id)}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...h, media:h.media.map(m=>m.id)})});
    await refresh();
  }
  function edit(field) {
    const {d, content} = dialog(`Configure help: ${field.text}`);
    let h = structuredClone(field.help);
    const label = el('label', 'Instructions'); const body = el('textarea'); body.value = h.body; body.maxLength = 20000; body.rows = 8; label.append(body);
    const activeLabel = el('label', 'Activate help button '); const active = el('input'); active.type='checkbox'; active.checked=h.enabled; activeLabel.prepend(active);
    const media = el('div');
    function render() { media.replaceChildren(); h.media.forEach((item, index) => { const row = el('div'); const remove = el('button', `Remove ${item.name}`); remove.type='button'; remove.onclick=()=>{h.media.splice(index,1);render();}; row.append(mediaNode(item), remove); media.append(row); }); }
    render();
    const uploadLabel = el('label','Add pictures or one video (up to 50 MB each)'); const upload=el('input'); upload.type='file'; upload.multiple=true; upload.accept='image/png,image/jpeg,image/webp,video/mp4,video/webm'; uploadLabel.append(upload);
    const message=el('p'); message.setAttribute('role','status');
    const submit=el('button','Save help'); submit.type='button';
    upload.onchange=async()=>{submit.disabled=true;upload.disabled=true;try { for (const file of upload.files) { const form=new FormData();form.append('file',file);h.media.push(await api(`/api/admin/help/${encodeURIComponent(field.id)}/media`,{method:'POST',body:form})); } render();message.textContent='Media uploaded. Save help to publish changes.'; } catch(e){message.textContent=e.message;} finally {submit.disabled=false;upload.disabled=false;upload.value='';}};
    submit.onclick=async()=>{submit.disabled=true;try{await save(field,{...h,body:body.value,enabled:active.checked});d.close();await loadAdmin();}catch(e){message.textContent=e.message;}finally{submit.disabled=false;}};
    content.append(activeLabel,label,uploadLabel,media,message,submit);
  }
  async function loadAdmin() {
    panel.replaceChildren(el('p','Loading help settings…'));
    try {
      const data=await api('/api/admin/help');panel.replaceChildren(el('h2','Help Administration'));
      panel.append(el('p','Activate a question-mark button beside any field. Configure instructions, pictures, and a video.'));
      for(const [section,title] of [['store_data','Store Data'],['nfpa72','NFPA 72'],['compliance','Compliance'],['points','Points Lists & Events']]) {
        const group=el('details');group.open=true;group.append(el('summary',title));
        for(const field of data.fields.filter(f=>f.section===section)) {
          const row=el('div');row.className='help-admin-row';const label=el('label',field.text+(field.active===false?' (inactive)':''));const check=el('input');check.type='checkbox';check.checked=field.help.enabled;check.setAttribute('aria-label',`Activate help: ${field.text}`);label.prepend(check);
          const configure=el('button','Configure help');configure.type='button';configure.onclick=()=>edit(field);const message=el('span');message.setAttribute('role','status');
          check.onchange=async()=>{check.disabled=true;try{await save(field,{...field.help,enabled:check.checked});message.textContent='Saved';}catch(e){check.checked=field.help.enabled;message.textContent=e.message;}finally{check.disabled=false;}};
          row.append(label,configure,message);group.append(row);
        }panel.append(group);
      }
    } catch(e) {panel.replaceChildren(el('p',e.message));}
  }
  document.getElementById('admin-tab-help').addEventListener('click',loadAdmin);
  let scheduled=false;
  new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;decorate();});}}).observe(document.getElementById('inspection-screen'),{childList:true,subtree:true});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden)refresh();},10000);refresh();
})();
