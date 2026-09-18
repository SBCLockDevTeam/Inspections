(() => {
  const form = document.querySelector('#inspection-form');
  const previewButton = document.querySelector('#preview-list');
  const modal = document.querySelector('#preview-modal');
  const body = document.querySelector('#preview-body');
  const summary = document.querySelector('#preview-summary');
  const message = document.querySelector('#message');
  const decisionField = document.querySelector('#point-decisions');
  const saveButton = document.querySelector('#save-review');
  const deleteButton = document.querySelector('#delete-review');
  const lists = document.querySelector('#point-lists');
  if (!form || !previewButton || !modal || !body) return;

  function renderRows(rows) {
    body.replaceChildren();
    for (const item of rows) {
      const row = document.createElement('tr');
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
      const status = document.createElement('select');
      status.className = 'review-status';
      for (const [value, label] of [['accept', 'Accept'], ['review', 'Review']]) {
        const option = new Option(label, value);
        option.selected = (value === 'accept') === Boolean(item.accepted);
        status.add(option);
      }
      statusCell.append(status);
      const reason = document.createElement('td');
      reason.textContent = item.reason ?? '';
      row.append(point, descriptionCell, statusCell, reason);
      body.append(row);
    }
  }

  function decisions() {
    return [...body.querySelectorAll('tr')].map((row) => ({
      address: row.dataset.address ? Number(row.dataset.address) : null,
      text: row.querySelector('.review-description').value,
      accepted: row.querySelector('.review-status').value === 'accept',
      deleted: false,
      reason: row.dataset.reason || 'technician review',
    }));
  }

  previewButton.addEventListener('click', async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    const file = lists?.querySelector('input[type=file]')?.files?.[0];
    if (!file) { message.textContent = 'Choose an XLSX file first.'; return; }
    message.textContent = 'Analyzing...';
    const data = new FormData();
    data.append('points_file', file);
    const response = await fetch('/api/point-lists/preview', { method: 'POST', body: data });
    const result = await response.json();
    if (result.error) { message.textContent = result.error; return; }
    summary.textContent = `Accepted: ${result.accepted} | Needs review: ${result.rejected} | File: ${result.filename}`;
    renderRows(result.rows);
    modal.classList.add('open');
    message.textContent = '';
  }, true);

  deleteButton?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    for (const row of [...body.querySelectorAll('tr')]) {
      if (row.querySelector('.review-status').value === 'review') row.remove();
    }
  }, true);

  saveButton?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    decisionField.value = JSON.stringify(decisions());
    modal.classList.remove('open');
    message.textContent = 'Review decisions saved. Creating the inspection will commit them.';
  }, true);
})();
