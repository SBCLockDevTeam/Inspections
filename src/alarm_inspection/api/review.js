(() => {
  const loginScreen = document.querySelector('#login-screen');
  const homeScreen = document.querySelector('#home-screen');
  const createScreen = document.querySelector('#create-screen');
  const inspectionScreen = document.querySelector('#inspection-screen');
  const adminScreen = document.querySelector('#admin-screen');

  const userBar = document.querySelector('#user-bar');
  const activeUserLabel = document.querySelector('#active-user-label');
  const avatarWrap = document.querySelector('#avatar-wrap');
  const avatarButton = document.querySelector('#avatar-button');
  const avatarMenu = document.querySelector('#avatar-menu');
  const adminMenuOption = document.querySelector('#avatar-menu-option-admin');
  const logoutMenuOption = document.querySelector('#avatar-menu-option-logout');
  const loginForm = document.querySelector('#login-form');
  const loginEmail = document.querySelector('#login-email');
  const loginPassword = document.querySelector('#login-password');
  const loginMessage = document.querySelector('#login-message');
  const passwordResetForm = document.querySelector('#password-reset-form');
  const resetCurrentPassword = document.querySelector('#reset-current-password');
  const resetNewPassword = document.querySelector('#reset-new-password');

  const backHomeFromAdmin = document.querySelector('#back-home-from-admin');
  const openAdminAddUserButton = document.querySelector('#open-admin-add-user');
  const saveAdminSettingsButton = document.querySelector('#save-admin-settings');
  const adminDefaultPassword = document.querySelector('#admin-default-password');
  const adminForceResetDefault = document.querySelector('#admin-force-reset-default');
  const adminUsersBody = document.querySelector('#admin-users-body');
  const adminMessage = document.querySelector('#admin-message');
  const adminAddUserModal = document.querySelector('#admin-add-user-modal');
  const adminAddUserForm = document.querySelector('#admin-add-user-form');
  const adminAddUserEmail = document.querySelector('#admin-add-user-email');
  const closeAdminAddUserButton = document.querySelector('#close-admin-add-user');
  const cancelAdminAddUserButton = document.querySelector('#cancel-admin-add-user');

  const startCreateButton = document.querySelector('#start-create');
  const backHomeFromCreate = document.querySelector('#back-home-from-create');
  const backHomeFromInspection = document.querySelector('#back-home-from-inspection');
  const refreshInspectionsButton = document.querySelector('#refresh-inspections');
  const inspectionPicker = document.querySelector('#inspection-picker');
  const openInspectionButton = document.querySelector('#open-inspection');
  const deleteInspectionButton = document.querySelector('#delete-inspection');
  const homeMessage = document.querySelector('#home-message');

  const inspectionStoreNumber = document.querySelector('#inspection-store-number');
  const inspectionStoreType = document.querySelector('#inspection-store-type');
  const inspectionAddress = document.querySelector('#inspection-address');
  const inspectionInspector = document.querySelector('#inspection-inspector');
  const inspectionStartDate = document.querySelector('#inspection-start-date');
  const inspectionEndDate = document.querySelector('#inspection-end-date');
  const acceptedPointsBody = document.querySelector('#accepted-points-body');
  const inspectionPointListSelector = document.querySelector('#inspection-point-list-selector');
  const inspectionMessage = document.querySelector('#inspection-message');
  const refreshInspectionButton = document.querySelector('#refresh-inspection');
  const eventHistoryForm = document.querySelector('#event-history-form');
  const chooseEventFileButton = document.querySelector('#choose-event-file');
  const eventFile = document.querySelector('#event-file');
  const eventFileName = document.querySelector('#event-file-name');
  const editTableButton = document.querySelector('#edit-table');
  const saveTableButton = document.querySelector('#save-table');
  const saveEventDatesButton = document.querySelector('#save-event-dates');
  const exportPdfButton = document.querySelector('#export-pdf');
  const clearEventDatesButton = document.querySelector('#clear-event-dates');
  const toggleMissingPointsButton = document.querySelector('#toggle-missing-points');

  const form = document.querySelector('#inspection-form');
  const previewButton = document.querySelector('#preview-list');
  const modal = document.querySelector('#preview-modal');
  const body = document.querySelector('#preview-body');
  const summary = document.querySelector('#preview-summary');
  const message = document.querySelector('#message');
  const decisionField = document.querySelector('#point-decisions');
  const saveButtons = [...document.querySelectorAll('.save-review-action')];
  const deleteButtons = [...document.querySelectorAll('.delete-review-action')];
  const finishReviewButtons = [...document.querySelectorAll('.finish-review-action')];
  const lists = document.querySelector('#point-lists');
  const listSelector = document.querySelector('#preview-list-selector');
  const closePreviewButton = document.querySelector('#close-preview');
  const deleteInspectionModal = document.querySelector('#delete-inspection-modal');
  const deleteInspectionSelector = document.querySelector('#delete-inspection-selector');
  const closeDeleteInspectionButton = document.querySelector('#close-delete-inspection');
  const cancelDeleteInspectionButton = document.querySelector('#cancel-delete-inspection');
  const confirmDeleteInspectionButton = document.querySelector('#confirm-delete-inspection');
  const reviewConfirmModal = document.querySelector('#review-confirm-modal');
  const reviewConfirmSummary = document.querySelector('#review-confirm-summary');
  const closeReviewConfirmButton = document.querySelector('#close-review-confirm');
  const cancelFinishReviewButton = document.querySelector('#cancel-finish-review');
  const confirmFinishReviewButton = document.querySelector('#confirm-finish-review');

  if (!form || !previewButton || !modal || !body || !homeScreen || !createScreen || !inspectionScreen) {
    return;
  }

  let previewLists = [];
  let selectedListIndex = 0;
  let renderedListIndex = null;
  let previewInputSignature = null;
  let currentInspectionId = null;
  let inspectionPoints = [];
  let pendingEventDates = new Map();
  let showMissingOnly = false;
  let currentPointListId = null;
  let inspectionOptions = [];
  let suppressInspectionDetailsSave = false;
  let currentUser = null;
  let tableEditable = false;

  function showScreen(name) {
    loginScreen?.classList.toggle('hidden', name !== 'login');
    homeScreen.classList.toggle('hidden', name !== 'home');
    createScreen.classList.toggle('hidden', name !== 'create');
    inspectionScreen.classList.toggle('hidden', name !== 'inspection');
    adminScreen?.classList.toggle('hidden', name !== 'admin');
  }

  function clearPreviewState() {
    previewLists = [];
    selectedListIndex = 0;
    renderedListIndex = null;
    previewInputSignature = null;
    decisionField.value = '[]';
  }

  function resetCreateForm() {
    form.reset();
    const rows = [...lists.querySelectorAll('.point-list')];
    for (const row of rows.slice(1)) {
      row.remove();
    }
    syncPointListRemoveButtons();
    clearPreviewState();
    message.textContent = '';
  }

  function syncPointListRemoveButtons() {
    const rows = [...lists.querySelectorAll('.point-list')];
    const disableRemove = rows.length <= 1;
    for (const row of rows) {
      const removeButton = row.querySelector('.remove-point-list');
      if (!removeButton) {
        continue;
      }
      removeButton.disabled = disableRemove;
      removeButton.title = disableRemove ? 'At least one Points List is required.' : '';
    }
  }

  function formatInspectionLabel(inspection) {
    return `${inspection.store_number} | ${inspection.address} | ${inspection.status}`;
  }

  function updateUserChrome() {
    if (!currentUser) {
      userBar?.classList.add('hidden');
      if (activeUserLabel) {
        activeUserLabel.textContent = '';
      }
      adminMenuOption?.classList.add('hidden');
      return;
    }
    userBar?.classList.remove('hidden');
    if (activeUserLabel) {
      activeUserLabel.textContent = `${currentUser.email}${currentUser.is_admin ? ' (Admin)' : ''}`;
    }
    if (avatarButton) {
      const id = (currentUser.email || '').slice(0, 2).replace(/[^a-zA-Z]/g, '').toUpperCase();
      avatarButton.textContent = id || 'U';
    }
    adminMenuOption?.classList.toggle('hidden', !currentUser.is_admin);
  }

  async function openAdminScreen() {
    adminMessage.textContent = '';
    closeAdminAddUserModal();
    await loadAdminSettings();
    await loadAdminUsers();
    showScreen('admin');
  }

  async function ensureSession() {
    const response = await fetch('/api/auth/me');
    const payload = await response.json();
    if (!payload.authenticated) {
      currentUser = null;
      updateUserChrome();
      showScreen('login');
      return false;
    }
    currentUser = payload.user;
    updateUserChrome();
    if (currentUser.force_password_reset) {
      loginMessage.textContent = 'Password reset is required before continuing.';
      passwordResetForm?.classList.remove('hidden');
      loginForm?.classList.add('hidden');
      showScreen('login');
      return false;
    }
    passwordResetForm?.classList.add('hidden');
    loginForm?.classList.remove('hidden');
    return true;
  }

  function renderAdminUsers(users) {
    if (!adminUsersBody) {
      return;
    }
    adminUsersBody.replaceChildren();
    for (const user of users) {
      const row = document.createElement('tr');
      const email = document.createElement('td');
      email.textContent = user.email;
      const admin = document.createElement('td');
      const adminCheckbox = document.createElement('input');
      adminCheckbox.type = 'checkbox';
      adminCheckbox.checked = Boolean(user.is_admin);
      adminCheckbox.addEventListener('change', async () => {
        const response = await fetch(`/api/admin/users/${user.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_admin: adminCheckbox.checked }),
        });
        const result = await response.json();
        if (!response.ok || result.error) {
          adminMessage.textContent = result.error || result.detail || 'Updating user failed.';
          adminCheckbox.checked = !adminCheckbox.checked;
          return;
        }
        adminMessage.textContent = `Updated ${user.email}.`;
        await loadAdminUsers();
      });
      admin.append(adminCheckbox);
      const actions = document.createElement('td');
      const wrapper = document.createElement('div');
      wrapper.className = 'user-actions';

      const removeUser = document.createElement('button');
      removeUser.type = 'button';
      removeUser.textContent = 'Remove User';
      removeUser.addEventListener('click', async () => {
        if (!window.confirm(`Remove user ${user.email}?`)) {
          return;
        }
        const response = await fetch(`/api/admin/users/${user.id}`, { method: 'DELETE' });
        const result = await response.json();
        if (!response.ok || result.error) {
          adminMessage.textContent = result.error || result.detail || 'Removing user failed.';
          return;
        }
        adminMessage.textContent = `Removed ${user.email}.`;
        await loadAdminUsers();
      });

      wrapper.append(removeUser);
      actions.append(wrapper);
      row.append(email, admin, actions);
      adminUsersBody.append(row);
    }
  }

  async function loadAdminUsers() {
    const response = await fetch('/api/admin/users');
    const payload = await response.json();
    if (!response.ok || payload.error) {
      adminMessage.textContent = payload.error || payload.detail || 'Unable to load users.';
      return;
    }
    renderAdminUsers(payload.users || []);
  }

  async function loadAdminSettings() {
    const response = await fetch('/api/admin/settings');
    const payload = await response.json();
    if (!response.ok || payload.error) {
      adminMessage.textContent = payload.error || payload.detail || 'Unable to load admin settings.';
      return;
    }
    if (adminDefaultPassword) {
      adminDefaultPassword.value = payload.default_password || '';
    }
    if (adminForceResetDefault) {
      adminForceResetDefault.checked = Boolean(payload.force_password_reset_default);
    }
  }

  async function saveAdminSettings() {
    if (!adminDefaultPassword || !adminForceResetDefault) {
      return;
    }
    const candidate = adminDefaultPassword.value || '';
    const response = await fetch('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        default_password: candidate,
        force_password_reset_default: adminForceResetDefault.checked,
      }),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      adminMessage.textContent = payload.error || payload.detail || 'Saving admin settings failed.';
      return;
    }
    adminDefaultPassword.value = payload.default_password || candidate;
    adminForceResetDefault.checked = Boolean(payload.force_password_reset_default);
    adminMessage.textContent = 'Global admin settings updated.';
  }

  function openAdminAddUserModal() {
    if (!adminAddUserModal || !adminAddUserEmail) {
      return;
    }
    adminAddUserEmail.value = '';
    adminAddUserModal.classList.add('open');
    adminAddUserEmail.focus();
  }

  function closeAdminAddUserModal() {
    adminAddUserModal?.classList.remove('open');
  }

  async function loadInspections() {
    const response = await fetch('/api/inspections');
    const items = await response.json();
    inspectionOptions = items;
    inspectionPicker.replaceChildren();
    if (!items.length) {
      inspectionPicker.add(new Option('No inspections yet', ''));
      return;
    }
    for (const item of items) {
      inspectionPicker.add(new Option(formatInspectionLabel(item), item.id));
    }
  }

  function openDeleteInspectionModal() {
    if (!deleteInspectionModal || !deleteInspectionSelector) {
      return;
    }
    deleteInspectionSelector.replaceChildren();
    if (!inspectionOptions.length) {
      deleteInspectionSelector.add(new Option('No inspections available', ''));
      deleteInspectionSelector.disabled = true;
      confirmDeleteInspectionButton.disabled = true;
    } else {
      for (const item of inspectionOptions) {
        deleteInspectionSelector.add(new Option(formatInspectionLabel(item), item.id));
      }
      deleteInspectionSelector.disabled = false;
      confirmDeleteInspectionButton.disabled = false;
      deleteInspectionSelector.value = inspectionPicker.value || inspectionOptions[0].id;
    }
    deleteInspectionModal.classList.add('open');
  }

  function closeDeleteInspectionModal() {
    deleteInspectionModal?.classList.remove('open');
  }

  async function createInspection(openAfterCreate = false) {
    message.textContent = 'Creating inspection...';
    const data = new FormData();
    for (const id of ['store_number', 'address']) {
      data.append(id, document.querySelector(`#${id}`).value);
    }
    for (const row of document.querySelectorAll('.point-list')) {
      const category = row.querySelector('select')?.value || '';
      const file = row.querySelector('input[type=file]')?.files?.[0];
      if (!file) {
        message.textContent = 'Choose an XLSX file for each Points List first.';
        return false;
      }
      data.append('point_list_categories', category);
      data.append('points_files', file);
    }
    data.append('point_decisions', decisionField.value || '[]');
    const response = await fetch('/api/inspections', { method: 'POST', body: data });
    const result = await response.json();
    if (!response.ok || result.error) {
      message.textContent = result.error || result.detail || 'Inspection creation failed.';
      return false;
    }

    if (openAfterCreate) {
      modal.classList.remove('open');
      await loadInspections();
      await openInspection(result.id);
      message.textContent = '';
      resetCreateForm();
      return true;
    }

    await loadInspections();
    showScreen('home');
    inspectionPicker.value = result.id;
    homeMessage.textContent = `Inspection created and saved. Select it and click Open Inspection.`;
    resetCreateForm();
    return true;
  }

  function renderVisibleAcceptedPoints() {
    acceptedPointsBody.replaceChildren();
    const pointsToRender = showMissingOnly
      ? inspectionPoints.filter((point) => {
          const pointKey = Number(point.address);
          const pending = Number.isFinite(pointKey) ? pendingEventDates.get(pointKey) : undefined;
          return !(point.event_date || pending);
        })
      : inspectionPoints;

    if (!pointsToRender.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 4;
      cell.textContent = showMissingOnly
        ? 'All accepted points currently have dates. Click Show All Points to view every point.'
        : 'No accepted points recorded yet.';
      row.append(cell);
      acceptedPointsBody.append(row);
      return;
    }
    for (const point of pointsToRender) {
      const row = document.createElement('tr');
      const text = document.createElement('td');
      const textValue = point.editableText ?? point.text ?? '';
      if (tableEditable) {
        const textInput = document.createElement('input');
        textInput.type = 'text';
        textInput.className = 'location-input';
        textInput.value = textValue;
        textInput.addEventListener('input', () => {
          point.editableText = textInput.value;
        });
        text.append(textInput);
      } else {
        text.textContent = textValue;
      }

      const address = document.createElement('td');
      const addressValue = point.editableAddress ?? point.address ?? '';
      if (tableEditable) {
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.className = 'location-input';
        addressInput.value = addressValue;
        addressInput.addEventListener('input', () => {
          point.editableAddress = addressInput.value;
        });
        address.append(addressInput);
      } else {
        address.textContent = addressValue;
      }

      const locationCell = document.createElement('td');
      const locationValue = point.location ?? '';
      if (tableEditable) {
        const locationInput = document.createElement('input');
        locationInput.type = 'text';
        locationInput.className = 'location-input';
        locationInput.value = locationValue;
        locationInput.placeholder = 'Enter location';
        locationInput.addEventListener('input', () => {
          point.location = locationInput.value;
        });
        locationCell.append(locationInput);
      } else {
        locationCell.textContent = locationValue;
      }

      const eventDate = document.createElement('td');
      const pointKey = Number(point.address);
      const pending = Number.isFinite(pointKey) ? pendingEventDates.get(pointKey) : undefined;
      const savedEventValue = String(point.editableEventDate ?? point.event_date ?? '').trim();
      const eventValue = savedEventValue || (pending ? `${pending} (pending)` : '');
      if (tableEditable) {
        const eventDateInput = document.createElement('input');
        eventDateInput.type = 'text';
        eventDateInput.className = 'location-input';
        eventDateInput.value = eventValue;
        eventDateInput.addEventListener('input', () => {
          point.editableEventDate = eventDateInput.value;
        });
        eventDate.append(eventDateInput);
      } else {
        eventDate.textContent = eventValue;
      }

      row.append(text, address, locationCell, eventDate);
      acceptedPointsBody.append(row);
    }
  }

  function renderAcceptedPoints(points) {
    inspectionPoints = (points || []).map((point) => ({
      ...point,
      id: point.id ?? '',
      editableText: point.editableText ?? point.text ?? '',
      editableAddress: point.editableAddress ?? (point.address ?? ''),
      location: point.location ?? '',
      editableEventDate: point.editableEventDate ?? point.event_date ?? '',
    }));
    renderVisibleAcceptedPoints();
  }

  function syncTableEditButtons() {
    if (editTableButton) {
      editTableButton.disabled = tableEditable;
    }
    if (saveTableButton) {
      saveTableButton.disabled = !tableEditable;
    }
  }

  function setEventFileName() {
    if (!eventFileName) {
      return;
    }
    const file = eventFile?.files?.[0];
    eventFileName.textContent = file ? file.name : 'No file selected';
  }

  function syncMissingToggleLabel() {
    if (!toggleMissingPointsButton) {
      return;
    }
    toggleMissingPointsButton.textContent = showMissingOnly ? 'Show All Points' : 'Show Missing Points Only';
  }

  function validateRowsForExport(rows) {
    if (!rows.length) {
      return 'No accepted points available for export.';
    }
    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      const line = index + 1;
      if (!row.text) {
        return `Row ${line} is missing Device Type.`;
      }
      if (!row.address) {
        return `Row ${line} is missing Address.`;
      }
      if (!row.location) {
        return `Row ${line} is missing Location.`;
      }
      if (!row.event_date) {
        return `Row ${line} is missing Test Result.`;
      }
      if (row.event_date.toLowerCase().includes('(pending)')) {
        return `Row ${line} still has a pending Test Result. Accept results before exporting.`;
      }
    }
    return '';
  }

  async function blobLooksLikePdf(blob) {
    const headerBytes = new Uint8Array(await blob.slice(0, 5).arrayBuffer());
    const header = String.fromCharCode(...headerBytes);
    return header === '%PDF-';
  }

  async function savePdfWithDialog(blob, filename, pickedHandle = null) {
    if (!blob || blob.size <= 0) {
      throw new Error('PDF payload was empty.');
    }

    if (pickedHandle) {
      const writable = await pickedHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      const savedFile = await pickedHandle.getFile();
      if (!savedFile || savedFile.size <= 0) {
        throw new Error('Save As created an empty file.');
      }
      return 'saved';
    }

    if (typeof window.showSaveFilePicker === 'function') {
      const lateHandle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [
          {
            description: 'PDF Document',
            accept: { 'application/pdf': ['.pdf'] },
          },
        ],
      });
      const writable = await lateHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      const savedFile = await lateHandle.getFile();
      if (!savedFile || savedFile.size <= 0) {
        throw new Error('Save As created an empty file.');
      }
      return 'saved';
    }

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    return 'downloaded';
  }

  function renderInspectionPointListSelector(pointLists, selectedPointListId) {
    if (!inspectionPointListSelector) {
      return;
    }
    inspectionPointListSelector.replaceChildren();
    for (const item of pointLists || []) {
      const label = `${item.category || 'Panel'} · ${item.filename || ''}`;
      inspectionPointListSelector.add(new Option(label, item.id));
    }
    if (selectedPointListId) {
      inspectionPointListSelector.value = selectedPointListId;
    }
    inspectionPointListSelector.disabled = (pointLists || []).length < 2;
  }

  function asDateInputValue(rawValue) {
    if (!rawValue) {
      return '';
    }
    const text = String(rawValue);
    return text.includes('T') ? text.split('T')[0] : text;
  }

  async function saveInspectionDetails() {
    if (suppressInspectionDetailsSave || !currentInspectionId) {
      return;
    }
    const payload = {
      store_number: inspectionStoreNumber?.value || '',
      store_type: inspectionStoreType?.value || '',
      address: inspectionAddress?.value || '',
      inspector_name: inspectionInspector?.value || '',
      start_date: inspectionStartDate?.value || '',
      completion_date: inspectionEndDate?.value || '',
    };
    const response = await fetch(`/api/inspections/${currentInspectionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      inspectionMessage.textContent = result.error || result.detail || 'Saving inspection details failed.';
      return;
    }
    inspectionMessage.textContent = 'Inspection details saved.';
    await loadInspections();
  }

  async function persistAcceptedPoints(rows) {
    if (!currentInspectionId || !currentPointListId) {
      return { error: 'No inspection or Points List selected.' };
    }
    const response = await fetch(`/api/inspections/${currentInspectionId}/accepted-points/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        point_list_id: currentPointListId,
        rows,
      }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      return { error: result.error || result.detail || 'Saving accepted points failed.' };
    }
    return { result };
  }

  async function openInspection(inspectionId, pointListId = null) {
    if (!inspectionId) {
      return;
    }
    const query = pointListId ? `?point_list_id=${encodeURIComponent(pointListId)}` : '';
    const response = await fetch(`/api/inspections/${inspectionId}${query}`);
    const inspection = await response.json();
    if (inspection.error) {
      inspectionMessage.textContent = inspection.error;
      return;
    }
    pendingEventDates = new Map();
    showMissingOnly = false;
    tableEditable = false;
    syncTableEditButtons();
    currentInspectionId = inspection.id;
    currentPointListId = inspection.selected_point_list_id || null;
    suppressInspectionDetailsSave = true;
    if (inspectionStoreNumber) {
      inspectionStoreNumber.value = inspection.store_number || '';
    }
    if (inspectionStoreType) {
      inspectionStoreType.value = inspection.store_type || 'Walmart - Supercenter';
    }
    if (inspectionAddress) {
      inspectionAddress.value = inspection.address || '';
    }
    if (inspectionInspector) {
      inspectionInspector.value = inspection.inspector_name || '';
    }
    if (inspectionStartDate) {
      inspectionStartDate.value = asDateInputValue(inspection.start_date);
    }
    if (inspectionEndDate) {
      inspectionEndDate.value = asDateInputValue(inspection.completion_date);
    }
    suppressInspectionDetailsSave = false;
    renderInspectionPointListSelector(inspection.point_lists || [], inspection.selected_point_list_id || null);
    renderAcceptedPoints(inspection.accepted_points || []);
    syncMissingToggleLabel();
    const uploaded = (inspection.event_history_files || []).join(', ');
    inspectionMessage.textContent = uploaded ? `Event History uploads: ${uploaded}` : '';
    showScreen('inspection');
  }

  function buildUploadSignature(uploads) {
    return uploads.map((upload) => {
      const file = upload.file;
      return [
        upload.category || '',
        file?.name || '',
        file?.size || 0,
        file?.lastModified || 0,
      ].join('::');
    }).join('||');
  }

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
      row.append(point, descriptionCell, statusCell);
      body.append(row);
    }
  }

  function rowDecisions(rows, sourceFilename) {
    return rows.map((item) => ({
      address: item.address ?? null,
      text: item.text ?? '',
      accepted: item.accepted === true,
      deleted: false,
      reason: item.reason || 'technician review',
      source_filename: sourceFilename || '',
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

  function hasUnresolvedReviewRows() {
    return previewLists.some((list) => (list.rows || []).some((row) => row.accepted === false));
  }

  function openReviewConfirmation() {
    if (!previewLists.length) {
      message.textContent = 'Preview at least one Points List before finishing review.';
      return;
    }
    if (hasUnresolvedReviewRows()) {
      message.textContent = 'Delete all Review rows or mark them Accepted before finishing the inspection review.';
      return;
    }
    const totalRows = previewLists.reduce((count, list) => count + (list.rows || []).length, 0);
    const acceptedRows = previewLists.reduce((count, list) => count + (list.rows || []).filter((row) => row.accepted).length, 0);
    reviewConfirmSummary.textContent = `You are about to commit ${acceptedRows} accepted points across ${totalRows} rows from ${previewLists.length} Points List(s). This is the final review approval step.`;
    reviewConfirmModal?.classList.add('open');
  }

  function closeReviewConfirmation() {
    reviewConfirmModal?.classList.remove('open');
  }

  closePreviewButton?.addEventListener('click', () => modal.classList.remove('open'));
  closeReviewConfirmButton?.addEventListener('click', closeReviewConfirmation);
  cancelFinishReviewButton?.addEventListener('click', closeReviewConfirmation);

  loginForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    loginMessage.textContent = 'Signing in...';
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: loginEmail?.value || '',
        password: loginPassword?.value || '',
      }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      loginMessage.textContent = result.error || result.detail || 'Login failed.';
      return;
    }
    currentUser = result.user;
    updateUserChrome();
    if (currentUser.force_password_reset) {
      loginMessage.textContent = 'Password reset is required before continuing.';
      passwordResetForm?.classList.remove('hidden');
      loginForm?.classList.add('hidden');
      return;
    }
    await loadInspections();
    showScreen('home');
    loginMessage.textContent = '';
    loginForm.reset();
  });

  passwordResetForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    loginMessage.textContent = 'Resetting password...';
    const response = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: resetCurrentPassword?.value || '',
        new_password: resetNewPassword?.value || '',
      }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      loginMessage.textContent = result.error || result.detail || 'Password reset failed.';
      return;
    }
    currentUser = result.user;
    updateUserChrome();
    passwordResetForm.classList.add('hidden');
    loginForm?.classList.remove('hidden');
    passwordResetForm.reset();
    loginForm.reset();
    await loadInspections();
    showScreen('home');
    loginMessage.textContent = 'Password reset complete. Signed in.';
  });

  logoutMenuOption?.addEventListener('click', async () => {
    avatarMenu?.classList.add('hidden');
    await fetch('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    updateUserChrome();
    homeMessage.textContent = '';
    inspectionMessage.textContent = '';
    adminMessage.textContent = '';
    passwordResetForm?.classList.add('hidden');
    loginForm?.classList.remove('hidden');
    showScreen('login');
  });

  adminMenuOption?.addEventListener('click', async () => {
    if (!currentUser?.is_admin) {
      return;
    }
    avatarMenu?.classList.add('hidden');
    await openAdminScreen();
  });

  backHomeFromAdmin?.addEventListener('click', async () => {
    await loadInspections();
    showScreen('home');
  });

  openAdminAddUserButton?.addEventListener('click', () => {
    openAdminAddUserModal();
  });

  closeAdminAddUserButton?.addEventListener('click', () => {
    closeAdminAddUserModal();
  });

  cancelAdminAddUserButton?.addEventListener('click', () => {
    closeAdminAddUserModal();
  });

  adminAddUserForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    adminMessage.textContent = 'Creating user...';
    const response = await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: adminAddUserEmail?.value || '',
      }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      adminMessage.textContent = result.error || result.detail || 'User creation failed.';
      return;
    }
    adminAddUserForm.reset();
    closeAdminAddUserModal();
    adminMessage.textContent = `Created ${result.user?.email || 'user'} using current global admin settings.`;
    await loadAdminUsers();
  });

  adminAddUserModal?.addEventListener('click', (event) => {
    if (event.target === adminAddUserModal) {
      closeAdminAddUserModal();
    }
  });

  saveAdminSettingsButton?.addEventListener('click', async () => {
    await saveAdminSettings();
  });

  avatarButton?.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    avatarMenu?.classList.toggle('hidden');
  });

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Node)) {
      return;
    }
    if (avatarWrap && !avatarWrap.contains(event.target)) {
      avatarMenu?.classList.add('hidden');
    }
  });

  startCreateButton?.addEventListener('click', () => {
    resetCreateForm();
    homeMessage.textContent = '';
    showScreen('create');
  });

  deleteInspectionButton?.addEventListener('click', () => {
    openDeleteInspectionModal();
  });

  closeDeleteInspectionButton?.addEventListener('click', closeDeleteInspectionModal);
  cancelDeleteInspectionButton?.addEventListener('click', closeDeleteInspectionModal);

  confirmDeleteInspectionButton?.addEventListener('click', async () => {
    const selectedId = deleteInspectionSelector?.value || '';
    if (!selectedId) {
      homeMessage.textContent = 'Choose an inspection to delete.';
      return;
    }
    const selected = inspectionOptions.find((item) => item.id === selectedId);
    const label = selected ? formatInspectionLabel(selected) : selectedId;
    const confirmed = window.confirm(`Delete this inspection?\n\n${label}\n\nClick OK to confirm or Cancel to keep it.`);
    if (!confirmed) {
      return;
    }

    const response = await fetch(`/api/inspections/${selectedId}`, { method: 'DELETE' });
    const result = await response.json();
    if (!response.ok || result.error) {
      homeMessage.textContent = result.error || result.detail || 'Inspection delete failed.';
      return;
    }

    if (currentInspectionId === selectedId) {
      currentInspectionId = null;
      currentPointListId = null;
      pendingEventDates = new Map();
      showScreen('home');
    }

    closeDeleteInspectionModal();
    await loadInspections();
    homeMessage.textContent = 'Inspection deleted.';
  });

  backHomeFromCreate?.addEventListener('click', async () => {
    await loadInspections();
    showScreen('home');
  });

  backHomeFromInspection?.addEventListener('click', async () => {
    await loadInspections();
    showScreen('home');
  });

  refreshInspectionsButton?.addEventListener('click', async () => {
    await loadInspections();
  });

  openInspectionButton?.addEventListener('click', async () => {
    homeMessage.textContent = '';
    await openInspection(inspectionPicker.value);
  });

  refreshInspectionButton?.addEventListener('click', async () => {
    if (!currentInspectionId) {
      return;
    }
    await openInspection(currentInspectionId, currentPointListId);
  });

  inspectionPointListSelector?.addEventListener('change', async () => {
    if (!currentInspectionId) {
      return;
    }
    pendingEventDates = new Map();
    currentPointListId = inspectionPointListSelector.value || null;
    await openInspection(currentInspectionId, currentPointListId);
  });

  previewButton.addEventListener('click', async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!form.reportValidity()) {
      message.textContent = 'Enter store number, address, and panel details before previewing.';
      return;
    }
    const pointListRows = [...(lists?.querySelectorAll('.point-list') || [])];
    const uploads = pointListRows.map((row) => ({
      category: row.querySelector('select')?.value || '',
      file: row.querySelector('input[type=file]')?.files?.[0],
    }));
    if (!uploads.length || uploads.some((item) => !item.file || !item.category)) {
      message.textContent = 'Choose an XLSX file and panel for each Points List first.';
      return;
    }
    const signature = buildUploadSignature(uploads);
    if (previewLists.length && previewInputSignature === signature) {
      if (renderedListIndex !== null && previewLists[renderedListIndex]) {
        selectedListIndex = renderedListIndex;
        persistSelectedList();
      }
      listSelector.replaceChildren();
      for (const [index, item] of previewLists.entries()) {
        const option = new Option(`${item.category ? `${item.category} · ` : ''}${item.filename}`, String(index));
        listSelector.add(option);
      }
      listSelector.hidden = previewLists.length < 2;
      renderList(Math.min(selectedListIndex, previewLists.length - 1));
      listSelector.value = String(selectedListIndex);
      modal.classList.add('open');
      message.textContent = 'Loaded saved preview decisions.';
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
    previewInputSignature = signature;
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

  function deleteReviewRows(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    for (const row of [...body.querySelectorAll('tr')]) {
      if (row.querySelector('.review-status').dataset.accepted !== 'true') row.remove();
    }
  }

  async function saveReviewDecisions(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    persistSelectedList();
    const selected = previewLists[selectedListIndex];
    if (!selected) {
      message.textContent = 'No Points List is selected to save.';
      return;
    }
    const selectedDecisions = rowDecisions(selected.rows, selected.filename);
    decisionField.value = JSON.stringify(selectedDecisions);
    message.textContent = `Saved review decisions for ${selected.filename}.`;
  }

  async function finishReview(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!previewLists.length) {
      message.textContent = 'Preview at least one Points List before finishing review.';
      return;
    }
    persistSelectedList();
    if (hasUnresolvedReviewRows()) {
      message.textContent = 'Delete all Review rows or mark them Accepted before finishing the inspection review.';
      return;
    }
    decisionField.value = JSON.stringify(
      previewLists.flatMap((item) => rowDecisions(item.rows, item.filename))
    );
    if (!form.reportValidity()) {
      message.textContent = 'Complete required inspection fields before finishing review.';
      return;
    }
    openReviewConfirmation();
  }

  confirmFinishReviewButton?.addEventListener('click', async () => {
    closeReviewConfirmation();
    await createInspection(true);
  });

  for (const button of deleteButtons) {
    button.addEventListener('click', deleteReviewRows, true);
  }
  for (const button of saveButtons) {
    button.addEventListener('click', saveReviewDecisions, true);
  }
  for (const button of finishReviewButtons) {
    button.addEventListener('click', finishReview, true);
  }

  document.querySelector('#add-list')?.addEventListener('click', () => {
    const row = lists.firstElementChild?.cloneNode(true);
    if (!row) {
      return;
    }
    const panelSelect = row.querySelector('select');
    const fileInput = row.querySelector('input[type=file]');
    if (panelSelect) {
      panelSelect.value = 'Combo';
      panelSelect.required = true;
    }
    if (fileInput) {
      fileInput.value = '';
      fileInput.required = true;
    }
    const removeButton = row.querySelector('.remove-point-list');
    if (removeButton) {
      removeButton.disabled = false;
      removeButton.title = '';
    }
    lists.append(row);
    syncPointListRemoveButtons();
  });

  lists?.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.classList.contains('remove-point-list')) {
      return;
    }
    event.preventDefault();
    const rows = [...lists.querySelectorAll('.point-list')];
    if (rows.length <= 1) {
      message.textContent = 'At least one Points List is required.';
      syncPointListRemoveButtons();
      return;
    }
    const row = target.closest('.point-list');
    if (row) {
      row.remove();
      clearPreviewState();
      message.textContent = 'Points List removed. Preview decisions were reset.';
    }
    syncPointListRemoveButtons();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    message.textContent = 'Use Preview Points Lists, then click Finish Review to create the inspection.';
  });

  async function uploadSelectedEventHistory() {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'Select a Points List first.';
      return;
    }
    const file = eventFile?.files?.[0];
    if (!file) {
      inspectionMessage.textContent = 'Choose an Event History file first.';
      return;
    }
    inspectionMessage.textContent = 'Uploading Event History...';
    const data = new FormData();
    data.append('point_list_id', currentPointListId);
    data.append('event_file', file);
    const response = await fetch(`/api/inspections/${currentInspectionId}/event-history`, {
      method: 'POST',
      body: data,
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      inspectionMessage.textContent = result.error || result.detail || 'Event History upload failed.';
      return;
    }

    const persistedPoints = new Set(
      (inspectionPoints || [])
        .filter((point) => point.event_date && point.address !== null && point.address !== undefined)
        .map((point) => Number(point.address))
        .filter((value) => Number.isFinite(value))
    );
    for (const match of result.pending_matches || []) {
      const point = Number(match.point);
      const timestamp = match.timestamp;
      if (!Number.isFinite(point) || !timestamp || persistedPoints.has(point)) {
        continue;
      }
      const existingPending = pendingEventDates.get(point);
      if (!existingPending || timestamp < existingPending) {
        pendingEventDates.set(point, timestamp);
      }
    }

    eventHistoryForm.reset();
    setEventFileName();
    renderVisibleAcceptedPoints();
    inspectionMessage.textContent = `Event History uploaded: ${result.filename}. Pending matches: ${pendingEventDates.size}. Click Accept Results to persist.`;
  }

  eventHistoryForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await uploadSelectedEventHistory();
  });

  chooseEventFileButton?.addEventListener('click', () => {
    eventFile?.click();
  });

  eventFile?.addEventListener('change', async () => {
    setEventFileName();
    if (!eventFile?.files?.length) {
      return;
    }
    await uploadSelectedEventHistory();
  });

  toggleMissingPointsButton?.addEventListener('click', () => {
    showMissingOnly = !showMissingOnly;
    syncMissingToggleLabel();
    renderVisibleAcceptedPoints();
  });

  editTableButton?.addEventListener('click', () => {
    tableEditable = true;
    syncTableEditButtons();
    renderVisibleAcceptedPoints();
  });

  saveTableButton?.addEventListener('click', async () => {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'Select a Points List first.';
      return;
    }

    const rows = (inspectionPoints || []).map((point) => ({
      id: String(point.id ?? ''),
      text: String(point.editableText ?? point.text ?? '').trim(),
      address: String(point.editableAddress ?? point.address ?? '').trim(),
      location: String(point.location ?? '').trim(),
      event_date: String(point.editableEventDate ?? point.event_date ?? '').trim(),
    }));

    inspectionMessage.textContent = 'Saving accepted points...';
    const persisted = await persistAcceptedPoints(rows);
    if (persisted.error) {
      inspectionMessage.textContent = persisted.error;
      return;
    }

    tableEditable = false;
    syncTableEditButtons();
    await openInspection(currentInspectionId, currentPointListId);
    inspectionMessage.textContent = `Accepted Points saved (${persisted.result.updated_rows} rows).`;
  });

  saveEventDatesButton?.addEventListener('click', async () => {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'Select a Points List first.';
      return;
    }
    const matches = [...pendingEventDates.entries()].map(([point, timestamp]) => ({
      point,
      timestamp,
    }));
    if (!matches.length) {
      inspectionMessage.textContent = 'No pending dates to accept.';
      return;
    }
    inspectionMessage.textContent = 'Accepting matched results...';
    const response = await fetch(`/api/inspections/${currentInspectionId}/event-dates/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ point_list_id: currentPointListId, matches }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      inspectionMessage.textContent = result.error || result.detail || 'Saving dates failed.';
      return;
    }
    pendingEventDates = new Map();
    await openInspection(currentInspectionId, currentPointListId);
    inspectionMessage.textContent = `Saved ${result.saved} new dates. Ignored existing: ${result.ignored_existing}.`;
  });

  clearEventDatesButton?.addEventListener('click', async () => {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'Select a Points List first.';
      return;
    }
    inspectionMessage.textContent = 'Clearing saved dates...';
    const response = await fetch(`/api/inspections/${currentInspectionId}/event-dates/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ point_list_id: currentPointListId }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      inspectionMessage.textContent = result.error || result.detail || 'Clearing dates failed.';
      return;
    }
    pendingEventDates = new Map();
    await openInspection(currentInspectionId, currentPointListId);
    inspectionMessage.textContent = `Cleared ${result.cleared} saved dates.`;
  });

  exportPdfButton?.addEventListener('click', async () => {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'Select a Points List first.';
      return;
    }
    const rows = (inspectionPoints || []).map((point) => ({
      id: String(point.id ?? ''),
      text: String(point.editableText ?? point.text ?? '').trim(),
      address: String(point.editableAddress ?? point.address ?? '').trim(),
      location: String(point.location ?? '').trim(),
      event_date: String(point.editableEventDate ?? point.event_date ?? '').trim(),
    }));

    const rowValidationError = validateRowsForExport(rows);
    if (rowValidationError) {
      inspectionMessage.textContent = rowValidationError;
      return;
    }

    const persisted = await persistAcceptedPoints(rows);
    if (persisted.error) {
      inspectionMessage.textContent = persisted.error;
      return;
    }

    inspectionMessage.textContent = 'Generating PDF...';

    const response = await fetch(`/api/inspections/${currentInspectionId}/export-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        point_list_id: currentPointListId,
        rows,
      }),
    });

    const contentType = (response.headers.get('Content-Type') || '').toLowerCase();

    if (!response.ok || !contentType.includes('application/pdf')) {
      let details = 'PDF export failed.';
      try {
        const errorResult = await response.json();
        details = errorResult.error || errorResult.detail || details;
      } catch {
        if (!response.ok) {
          details = `PDF export failed (${response.status}).`;
        } else {
          details = 'Export did not return a valid PDF file.';
        }
      }
      inspectionMessage.textContent = details;
      return;
    }

    const blob = await response.blob();
    if (!blob || blob.size <= 0) {
      inspectionMessage.textContent = 'Export returned an empty PDF payload.';
      return;
    }
    const isPdf = await blobLooksLikePdf(blob);
    if (!isPdf) {
      inspectionMessage.textContent = 'Export returned an invalid PDF payload.';
      return;
    }
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^\"]+)"?/i);
    const filename = match ? match[1] : 'initiating-devices.pdf';

    try {
      const outcome = await savePdfWithDialog(blob, filename);
      if (outcome === 'saved') {
        inspectionMessage.textContent = `PDF saved: ${filename} (${blob.size} bytes)`;
      } else {
        inspectionMessage.textContent = `PDF downloaded: ${filename} (${blob.size} bytes). Enable browser "Ask where to save" to always show Save As.`;
      }
    } catch (error) {
      if (error && error.name === 'AbortError') {
        inspectionMessage.textContent = 'Export canceled.';
        return;
      }
      const fallbackUrl = URL.createObjectURL(blob);
      const fallbackAnchor = document.createElement('a');
      fallbackAnchor.href = fallbackUrl;
      fallbackAnchor.download = filename;
      document.body.append(fallbackAnchor);
      fallbackAnchor.click();
      fallbackAnchor.remove();
      URL.revokeObjectURL(fallbackUrl);
      inspectionMessage.textContent = `Save As failed (${error?.message || 'unknown error'}). Downloaded ${filename} instead (${blob.size} bytes).`;
    }
  });

  [inspectionStoreNumber, inspectionStoreType, inspectionAddress, inspectionInspector].forEach((element) => {
    element?.addEventListener('change', async () => {
      await saveInspectionDetails();
    });
    element?.addEventListener('blur', async () => {
      await saveInspectionDetails();
    });
  });

  [inspectionStartDate, inspectionEndDate].forEach((element) => {
    element?.addEventListener('change', async () => {
      await saveInspectionDetails();
    });
  });

  async function bootstrap() {
    syncPointListRemoveButtons();
    syncMissingToggleLabel();
    syncTableEditButtons();
    setEventFileName();
    const isAuthenticated = await ensureSession();
    if (!isAuthenticated) {
      return;
    }
    await loadInspections();
    showScreen('home');
  }

  bootstrap();
})();
