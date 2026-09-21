(() => {
  const form = document.querySelector('#inspection-form');
  const previewButton = document.querySelector('#preview-list');
  const modal = document.querySelector('#preview-modal');
  const body = document.querySelector('#preview-body');
  const summary = document.querySelector('#preview-summary');
  const message = document.querySelector('#message');
  const decisionField = document.querySelector('#point-decisions');
  const saveButton = document.querySelector('#save-review');
  const acceptButton = document.querySelector('#accept-review');
  const deleteButton = document.querySelector('#delete-review');
  const lists = document.querySelector('#point-lists');
  const listSelector = document.querySelector('#preview-list-selector');
  if (!form || !previewButton || !modal || !body) return;

  let previewLists = [];
  let selectedListIndex = 0;
  let renderedListIndex = null;

  function renderRows(rows) {
    body.replaceChildren();
    for (const item of rows) {
      const row = document.createElement('tr');
      row.className = item.accepted ? 'accepted-row' : 'review-row';
      row.dataset.address = item.address ?? '';
      row.dataset.reason = item.reason ?? '';
      const point = document.createElement('td');
      point.textContent = item.address ?? '';
      const descriptionCell = document.createElement('td');
      const description = document.createElement('input');
      description.className = 'review-description';
      description.value = item.text ?? '';
      descriptionCell.append(description);
      const statusCell = document.createElement('td');
      const status = document.createElement('button');
      status.type = 'button';
      status.className = `review-status status-toggle ${item.accepted ? 'accepted' : 'review'}`;
      status.textContent = item.accepted ? 'Accepted' : 'Review';
      status.dataset.accepted = String(Boolean(item.accepted));
      status.addEventListener('click', () => {
        const accepted = status.dataset.accepted !== 'true';
        status.dataset.accepted = String(accepted);
        status.textContent = accepted ? 'Accepted' : 'Review';
        status.classList.toggle('accepted', accepted);
        status.classList.toggle('review', !accepted);
        row.classList.toggle('accepted-row', accepted);
        row.classList.toggle('review-row', !accepted);
      });
      statusCell.append(status);
      const reason = document.createElement('td');
      reason.textContent = item.reason ?? '';
      row.append(point, descriptionCell, statusCell, reason);
      body.append(row);
    }
  }

  function rowDecisions(rows) {
    return rows.map((item) => ({
      address: item.address ?? null,
      text: item.text ?? '',
      accepted: Boolean(item.accepted),
      deleted: false,
      reason: item.reason || 'technician review',
    }));
  }

  function renderedRows() {
    return [...body.querySelectorAll('tr')].map((row) => ({
      address: row.dataset.address ? Number(row.dataset.address) : null,
      text: row.querySelector('.review-description').value,
      accepted: row.querySelector('.review-status').dataset.accepted === 'true',
      reason: row.dataset.reason || 'technician review',
    }));
  }

  function persistSelectedList() {
    const index = selectedListIndex;
    if (!previewLists[index]) return;
    previewLists[index].rows = renderedRows();
    previewLists[index].accepted = previewLists[index].rows.filter((item) => item.accepted).length;
    previewLists[index].rejected = previewLists[index].rows.filter((item) => !item.accepted).length;
  }

  function renderList(index) {
    if (renderedListIndex !== null && previewLists[renderedListIndex]) {
      selectedListIndex = renderedListIndex;
      persistSelectedList();
    }
    const selected = previewLists[index];
    if (!selected) return;
    selectedListIndex = index;
    summary.textContent = `${selected.category ? `${selected.category} · ` : ''}${selected.filename} — Accepted: ${selected.accepted} | Needs review: ${selected.rejected}`;
    renderRows(selected.rows);
    renderedListIndex = index;
  }

  previewButton.addEventListener('click', async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    const pointListRows = [...(lists?.querySelectorAll('.point-list') || [])];
    const uploads = pointListRows.map((row) => ({
      category: row.querySelector('select')?.value || '',
      file: row.querySelector('input[type=file]')?.files?.[0],
    }));
    if (!uploads.length || uploads.some((item) => !item.file)) {
      message.textContent = 'Choose an XLSX file for each Points List first.';
      return;
    }
    message.textContent = 'Analyzing...';
    const data = new FormData();
    for (const upload of uploads) {
      data.append('points_files', upload.file);
      data.append('point_list_categories', upload.category);
    }
    const response = await fetch('/api/point-lists/preview', { method: 'POST', body: data });
    const result = await response.json();
    if (result.error) { message.textContent = result.error; return; }
    previewLists = result.lists || [{
      filename: result.filename,
      category: '',
      accepted: result.accepted,
      rejected: result.rejected,
      rows: result.rows,
    }];
    renderedListIndex = null;
    selectedListIndex = 0;
    listSelector.replaceChildren();
    for (const [index, item] of previewLists.entries()) {
      const option = new Option(`${item.category ? `${item.category} · ` : ''}${item.filename}`, String(index));
      listSelector.add(option);
    }
    listSelector.hidden = previewLists.length < 2;
    renderList(0);
    modal.classList.add('open');
    message.textContent = '';
  }, true);

  listSelector?.addEventListener('change', () => renderList(Number(listSelector.value)));

  deleteButton?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    for (const row of [...body.querySelectorAll('tr')]) {
      if (row.querySelector('.review-status').dataset.accepted !== 'true') row.remove();
    }
  }, true);

  acceptButton?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    for (const status of body.querySelectorAll('.review-status')) {
      status.dataset.accepted = 'true';
      status.textContent = 'Accepted';
      status.classList.add('accepted');
      status.classList.remove('review');
      status.closest('tr').classList.add('accepted-row');
      status.closest('tr').classList.remove('review-row');
    }
  }, true);

  saveButton?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    persistSelectedList();
    decisionField.value = JSON.stringify(previewLists.flatMap((item) => rowDecisions(item.rows)));
    modal.classList.remove('open');
    message.textContent = 'Review decisions saved. Creating the inspection will commit them.';
  }, true);
})();
