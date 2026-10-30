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

  const inspectionTasksBody = document.querySelector('#inspection-tasks-body');
  const inspectionTasksMessage = document.querySelector('#inspection-tasks-message');
  const addInspectionTaskForm = document.querySelector('#add-inspection-task-form');
  const checklistContainer = document.querySelector('#inspection-checklist');
  const checklistMessage = document.querySelector('#checklist-message');
  const checklistProgress = document.querySelector('#checklist-progress');
  const checklistSaves = new Set();
  const adminTabs = [...document.querySelectorAll('#admin-screen [role=tab]')];
  const panelTypesBody = document.querySelector('#panel-types-body');
  const addPanelTypeForm = document.querySelector('#add-panel-type-form');
  const panelTypeName = document.querySelector('#panel-type-name');
  const addPanelTypeButton = document.querySelector('#add-panel-type');
  const panelTypeMessage = document.querySelector('#panel-type-message');
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

  const newInspectionModal = document.querySelector('#new-inspection-modal');
  const newInspectionForm = document.querySelector('#new-inspection-form');
  const newInspectionMessage = document.querySelector('#new-inspection-message');
  const saveNewInspectionButton = document.querySelector('#save-new-inspection');
  const cancelNewInspectionButton = document.querySelector('#cancel-new-inspection');
  let savingNewInspection = false;
  const startCreateButton = document.querySelector('#start-create');
  const backHomeFromCreate = document.querySelector('#back-home-from-create');
  const homeLinkFromInspection = document.querySelector('#home-link-from-inspection');
  const refreshInspectionsButton = document.querySelector('#refresh-inspections');
  const inspectionPicker = document.querySelector('#inspection-picker');
  const openInspectionButton = document.querySelector('#open-inspection');
  const deleteInspectionButton = document.querySelector('#delete-inspection');
  const homeMessage = document.querySelector('#home-message');

  const inspectionStoreNumber = document.querySelector('#inspection-store-number');
  const inspectionStoreType = document.querySelector('#inspection-store-type');
  const inspectionName = document.querySelector('#inspection-name');
  const inspectionCity = document.querySelector('#inspection-city');
  const inspectionState = document.querySelector('#inspection-state');
  const inspectionAddress = document.querySelector('#inspection-address');
  const inspectionInspector = document.querySelector('#inspection-inspector');
  const inspectionStartDate = document.querySelector('#inspection-start-date');
  const inspectionEndDate = document.querySelector('#inspection-end-date');
  const acceptedPointsBody = document.querySelector('#accepted-points-body');
  const inspectionPointListSelector = document.querySelector('#inspection-point-list-selector');
  const inspectionMessage = document.querySelector('#inspection-message');
  const saveAllInspectionButton = document.querySelector('#save-all-inspection');
  const inspectionBusyOverlay = document.querySelector('#inspection-busy-overlay');
  const inspectionBusyText = document.querySelector('#inspection-busy-text');
  const inspectionMenuWrap = document.querySelector('#inspection-menu-wrap');
  const inspectionMenuButton = document.querySelector('#inspection-menu-button');
  const inspectionMenu = document.querySelector('#inspection-menu');
  const inspectionMenuAddPointListOption = document.querySelector('#inspection-menu-option-add-point-list');
  const inspectionMenuDeletePointListOption = document.querySelector('#inspection-menu-option-delete-point-list');
  const inspectionMenuEditNfpaOption = document.querySelector('#inspection-menu-option-edit-nfpa');
  const inspectionMenuToggleMissingOption = document.querySelector('#inspection-menu-option-toggle-missing');
  const inspectionMenuExportPdfOption = document.querySelector('#inspection-menu-option-export-pdf');
  const inspectionMenuClearDatesOption = document.querySelector('#inspection-menu-option-clear-dates');
  const eventHistoryForm = document.querySelector('#event-history-form');
  const chooseEventFileButton = document.querySelector('#choose-event-file');
  const eventFile = document.querySelector('#event-file');
  const eventFileName = document.querySelector('#event-file-name');
  const editTableButton = document.querySelector('#edit-table');
  const saveTableButton = document.querySelector('#save-table');
  const saveEventDatesButton = document.querySelector('#save-event-dates');
  const nfpaDraftModal = document.querySelector('#nfpa-draft-modal');
  const closeNfpaDraftButton = document.querySelector('#close-nfpa-draft');
  const cancelNfpaDraftButton = document.querySelector('#cancel-nfpa-draft');
  const pdfTemplateKeySelect = document.querySelector('#pdf-template-key');
  const refreshPdfTemplateButton = document.querySelector('#refresh-pdf-template');
  const pdfTemplatePreviewFrame = document.querySelector('#pdf-template-preview');
  const pdfTemplateFieldsContainer = document.querySelector('#pdf-template-fields');
  const saveNfpaDraftButton = document.querySelector('#save-nfpa-draft');
  const downloadNfpaDraftButton = document.querySelector('#download-nfpa-draft');
  const nfpaDraftMessage = document.querySelector('#nfpa-draft-message');

  const form = document.querySelector('#inspection-form');
  const previewButton = document.querySelector('#preview-list');
  const modal = document.querySelector('#preview-modal');
  const body = document.querySelector('#preview-body');
  const summary = document.querySelector('#preview-summary');
  const message = document.querySelector('#message');
  const decisionField = document.querySelector('#point-decisions');
  const saveButtons = [...document.querySelectorAll('.save-review-action')];
  const deleteButtons = [...document.querySelectorAll('.delete-review-action')];
  const lists = document.querySelector('#point-lists');
  const listSelector = document.querySelector('#preview-list-selector');
  const closePreviewButton = document.querySelector('#close-preview');
  const deleteInspectionModal = document.querySelector('#delete-inspection-modal');
  const deleteInspectionSelector = document.querySelector('#delete-inspection-selector');
  const closeDeleteInspectionButton = document.querySelector('#close-delete-inspection');
  const cancelDeleteInspectionButton = document.querySelector('#cancel-delete-inspection');
  const confirmDeleteInspectionButton = document.querySelector('#confirm-delete-inspection');

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
  let inspectionDetailsSaveQueue = Promise.resolve();
  let currentUser = null;
  let tableEditable = false;
  let activePdfTemplateKey = 'nfpa72';
  let activePdfTemplateFields = {};
  let activePdfTemplateFieldNames = [];

  // Poll shared server state; local drafts remain private until their existing Save action.
  let currentScreen = 'login';
  let viewVersion = 0;
  let mutationVersion = 0;
  let pendingWrites = 0;
  let loadingInspection = 0;
  let syncing = false;
  const liveSnapshots = new Map();
  const fieldBaselines = new WeakMap();
  const controlValue = (control) => control.type === 'checkbox' ? control.checked : control.value;
  const rememberControls = (root) => root?.querySelectorAll('input,select,textarea').forEach((control) => fieldBaselines.set(control, controlValue(control)));
  if (window.PdfIntegrations) window.PdfIntegrations.hasLegacyDrafts = () => checklistSaves.size > 0 || hasDraft(document.querySelector('#store-data-section')) || hasDraft(checklistContainer) || hasDraft(acceptedPointsBody);
  const hasDraft = (root) => Boolean(root?.querySelector('[data-checklist-dirty="true"]')) || [...(root?.querySelectorAll('input,select,textarea') || [])].some((control) => fieldBaselines.has(control) && fieldBaselines.get(control) !== controlValue(control));
  const rememberResponse = (url, value) => liveSnapshots.set(url, JSON.stringify(value));
  const fetch = async (url, options = {}) => {
    const write = !['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase());
    if (write) { pendingWrites++; mutationVersion++; }
    try { return await window.fetch(url, options); }
    finally { if (write) { pendingWrites--; mutationVersion++; liveSnapshots.clear(); } }
  };
  document.addEventListener('input', () => { mutationVersion++; });
  document.addEventListener('change', () => { mutationVersion++; });
  const detailFields = () => ({ store_number: inspectionStoreNumber, store_type: inspectionStoreType,
    address: inspectionAddress, city: inspectionCity, state: inspectionState,
    inspector_name: inspectionInspector, start_date: inspectionStartDate, completion_date: inspectionEndDate });

  async function refreshSharedState() {
    if (syncing || !currentUser || currentScreen === 'login' || document.hidden || pendingWrites || loadingInspection) return;
    syncing = true;
    const version = mutationVersion;
    const view = viewVersion;
    const inspectionId = currentInspectionId;
    const listId = currentPointListId;
    const valid = () => version === mutationVersion && view === viewVersion && !pendingWrites && !loadingInspection
      && inspectionId === currentInspectionId && listId === currentPointListId;
    const read = async (url) => {
      const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (response.status === 401) throw new Error('Session expired. Sign in again.');
      if (!response.ok) throw new Error('Connection interrupted. Retrying automatically.');
      const result = await response.json();
      if (!valid()) return null;
      return result;
    };
    const collection = async (url, root, reload, protectFocus = true) => {
      const result = await read(url);
      if (result && liveSnapshots.get(url) !== JSON.stringify(result) && (!protectFocus || !hasDraft(root)) && (!protectFocus || !root?.contains(document.activeElement))) await reload(result);
    };
    try {
      const session = await read('/api/auth/me');
      if (!session) return;
      if (!session.authenticated || session.user.force_password_reset) {
        currentUser = session.user || null; updateUserChrome();
        document.querySelectorAll('.modal.open').forEach((item) => item.classList.remove('open'));
        showScreen('login');
        passwordResetForm.classList.toggle('hidden', !session.authenticated);
        loginForm.classList.toggle('hidden', Boolean(session.authenticated));
        loginMessage.textContent = session.authenticated ? 'Password reset is required before continuing.' : 'Session expired. Sign in again.';
        return;
      }
      currentUser = session.user; updateUserChrome();
      if (currentScreen === 'admin' && !currentUser.is_admin) { showScreen('home'); await loadInspections(); return; }
      if (currentScreen === 'home') await collection('/api/inspections', homeScreen, loadInspections);
      if (!valid()) return;
      await collection('/api/point-lists/types', lists, loadPanelTypes);
      if (!valid()) return;
      if (currentScreen === 'admin') {
        const tab = adminTabs.find((item) => item.getAttribute('aria-selected') === 'true')?.id;
        if (tab === 'admin-tab-users') {
          await collection('/api/admin/users', adminUsersBody, loadAdminUsers);
          if (valid()) await collection('/api/admin/settings', document.querySelector('.settings-row'), loadAdminSettings);
        } else if (tab === 'admin-tab-panel-types') {
          // Shared panel types were refreshed above.
        } else if (tab === 'admin-tab-integrations') {
          await window.PdfIntegrations?.refreshAdmin();
        } else if (tab === 'admin-tab-inspection-tasks') await collection('/api/admin/inspection-tasks', inspectionTasksBody, loadAdminInspectionTasks);
      }
      if (currentScreen === 'inspection' && inspectionId && valid()) {
        const url = `/api/inspections/${inspectionId}${listId ? `?point_list_id=${encodeURIComponent(listId)}` : ''}`;
        const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
        const result = await response.json();
        if (!valid()) return;
        if (response.status === 404 && result.detail === 'Points List not found.') {
          await openInspection(inspectionId);
          inspectionMessage.textContent = 'The selected Points List was deleted on another device.';
          return;
        }
        if (response.status === 404 || result.error === 'inspection not found') {
          currentInspectionId = null; currentPointListId = null;
          showScreen('home'); await loadInspections();
          homeMessage.textContent = 'This inspection was deleted on another device.';
          return;
        }
        if (!response.ok || result.error) throw new Error('Connection interrupted. Retrying automatically.');
        inspectionName.textContent = result.name;
        for (const [key, control] of Object.entries(detailFields())) {
          const value = String(result[key] ?? '');
          if (control !== document.activeElement && (!fieldBaselines.has(control) || control.value === fieldBaselines.get(control))) {
            control.value = value; fieldBaselines.set(control, value);
          }
        }
        const pointLists = result.point_lists || [];
        if (!listId && result.selected_point_list_id) {
          await openInspection(inspectionId, result.selected_point_list_id); return;
        }
        if (listId && !pointLists.some((item) => item.id === listId)) {
          await openInspection(inspectionId);
          inspectionMessage.textContent = 'The selected Points List was deleted on another device.'; return;
        }
        const listSnapshot = JSON.stringify(pointLists);
        if (liveSnapshots.get('inspection-point-lists') !== listSnapshot && document.activeElement !== inspectionPointListSelector) {
          renderInspectionPointListSelector(pointLists, listId);
          liveSnapshots.set('inspection-point-lists', listSnapshot);
        }
        const uploads = result.event_history_files || [];
        if (uploads.length && liveSnapshots.get('event-history-files') !== JSON.stringify(uploads)) {
          inspectionMessage.textContent = `Event History uploads: ${uploads.join(', ')}`;
        }
        rememberResponse('event-history-files', uploads);
        const points = result.accepted_points || [];
        pendingEventDates = new Map(points.filter((point) => point.pending_event_date && !point.event_date).map((point) => [Number(point.address), point.pending_event_date]));
        if (tableEditable) {
          // Merge untouched fields while preserving each local table edit.
          for (const point of inspectionPoints) {
            const remote = points.find((item) => item.id === point.id);
            if (!remote || point.highlightSaving) continue;
            point.device_highlighted = remote.device_highlighted;
            point.device_event_missing = remote.device_event_missing;
            const cell = [...acceptedPointsBody.querySelectorAll('.device-type-cell')].find((item) => item.dataset.pointId === point.id);
            if (cell) updateDeviceCellStatus(cell, point);
            const fields = [['text', 'editableText'], ['address', 'editableAddress'], ['location', 'location'], ['event_date', 'editableEventDate']];
            fields.forEach(([key, localKey], index) => {
              const control = cell?.parentElement.cells[index]?.querySelector('input');
              if (control === document.activeElement) return;
              if (String(point[localKey] ?? '') !== String(point.serverValues?.[key] ?? '')) return;
              point[localKey] = remote[key] ?? '';
              if (control) control.value = key === 'event_date' && !remote[key] && remote.pending_event_date ? `${remote.pending_event_date} (pending)` : String(remote[key] ?? '');
              point.serverValues[key] = remote[key];
            });
          }
          if (JSON.stringify(inspectionPoints.map((point) => point.id)) !== JSON.stringify(points.map((point) => point.id))) {
            const active = document.activeElement;
            const activeCell = active?.closest('.device-type-cell') || active?.closest('tr')?.querySelector('.device-type-cell');
            const activeId = activeCell?.dataset.pointId;
            const column = active?.closest('td')?.cellIndex;
            const selection = active?.selectionStart;
            const previous = new Map(inspectionPoints.map((point) => [point.id, point]));
            inspectionPoints = points.map((point) => previous.get(point.id) || {
              ...point, serverValues: { ...point }, editableText: point.text ?? '',
              editableAddress: point.address ?? '', editableEventDate: point.event_date ?? '', location: point.location ?? '',
            });
            renderVisibleAcceptedPoints();
            const cell = [...acceptedPointsBody.querySelectorAll('.device-type-cell')].find((item) => item.dataset.pointId === activeId);
            const control = cell?.parentElement.cells[column]?.querySelector('input');
            if (control) { control.focus({ preventScroll: true }); if (selection !== null && selection !== undefined) control.setSelectionRange(selection, selection); }
          }
        } else if (!inspectionPoints.some((point) => point.highlightSaving) && liveSnapshots.get('accepted-points') !== JSON.stringify(points)) {
          renderAcceptedPoints(points);
        }
        if (valid()) void window.PdfIntegrations?.refreshDetails?.();
        if (valid() && !checklistSaves.size && !hasDraft(checklistContainer)) await collection(`/api/inspections/${inspectionId}/checklist`, checklistContainer, (result) => loadInspectionChecklist(inspectionId, result), false);
      }
      if (valid() && nfpaDraftModal?.classList.contains('open')) {
        const key = activePdfTemplateKey;
        const result = await read(`/api/inspections/${inspectionId}/pdf-templates/${encodeURIComponent(key)}`);
        if (result && key === activePdfTemplateKey) {
          let changed = false;
          for (const control of pdfTemplateFieldsContainer.querySelectorAll('input')) {
            if (control === document.activeElement || control.value !== fieldBaselines.get(control)) continue;
            const name = control.id.slice('pdf-field-'.length);
            const value = String(result.fields?.[name] ?? '');
            if (control.value !== value) changed = true;
            control.value = value; fieldBaselines.set(control, value); activePdfTemplateFields[name] = value;
          }
          if (changed) refreshPdfTemplatePreviewFrame();
        }
      }
      if (valid() && document.querySelector('#live-sync-status').textContent !== 'Live updates on') document.querySelector('#live-sync-status').textContent = 'Live updates on';
    } catch (error) {
      if (valid()) document.querySelector('#live-sync-status').textContent = 'Connection interrupted. Retrying automatically.';
    } finally { syncing = false; }
  }
  window.setInterval(refreshSharedState, 3000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshSharedState(); });
  window.addEventListener('online', refreshSharedState);

  function showScreen(name) {
    currentScreen = name; viewVersion++;
    window.PdfIntegrations?.setInspection?.(name === 'inspection' ? currentInspectionId : null);
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
    clearPreviewState();
    message.textContent = '';
  }

  function formatInspectionLabel(inspection) {
    return inspection.name;
  }

  function updateUserChrome() {
    window.PdfIntegrations?.setActor?.(currentUser?.id || null);
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

  function taskError(result, fallback) {
    if (Array.isArray(result.detail)) return result.detail.map((item) => item.msg).join(' ');
    return result.error || result.detail || fallback;
  }

  function makeTaskTypeSelect(value) {
    const select = document.createElement('select');
    select.className = 'admin-task-type'; select.setAttribute('aria-label', 'Task type');
    for (const [key, label] of [['checkbox', 'Checkbox (Yes / No / NA)'], ['textbox', 'Textbox'], ['dropdown', 'Dropdown']]) select.add(new Option(label, key));
    select.value = value || 'checkbox';
    return select;
  }

  function createTaskOptionsEditor(root, typeSelect, options = []) {
    root.classList.add('task-options-editor');
    const rows = document.createElement('div');
    const add = document.createElement('button');
    add.type = 'button'; add.className = 'secondary add-task-choice'; add.textContent = 'Add Choice';
    const dirty = () => { root.dataset.checklistDirty = 'true'; mutationVersion++; };
    const refreshOrder = () => {
      [...rows.children].forEach((row, index) => {
        row.querySelector('.move-task-choice-up').disabled = index === 0 || typeSelect.value !== 'dropdown';
        row.querySelector('.move-task-choice-down').disabled = index === rows.children.length - 1 || typeSelect.value !== 'dropdown';
      });
    };
    const append = (value = '') => {
      const row = document.createElement('div'); row.className = 'task-option-row';
      const input = document.createElement('input'); input.type = 'text'; input.value = value;
      input.className = 'task-option-input'; input.maxLength = 120; input.autocomplete = 'off';
      input.setAttribute('aria-label', 'Dropdown choice'); input.placeholder = 'Choice';
      input.required = true; input.disabled = typeSelect.value !== 'dropdown';
      const moveButtons = [];
      for (const [direction, symbol] of [['up', '↑'], ['down', '↓']]) {
        const move = document.createElement('button');
        move.type = 'button'; move.className = `secondary move-task-choice-${direction}`; move.textContent = symbol;
        move.setAttribute('aria-label', `Move choice ${direction}`); move.title = `Move choice ${direction}`;
        move.addEventListener('click', () => {
          const sibling = direction === 'up' ? row.previousElementSibling : row.nextElementSibling;
          if (!sibling) return;
          if (direction === 'up') rows.insertBefore(row, sibling);
          else rows.insertBefore(sibling, row);
          dirty(); refreshOrder();
          (move.disabled ? input : move).focus();
        });
        moveButtons.push(move);
      }
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'secondary remove-task-choice'; remove.textContent = 'Remove';
      remove.addEventListener('click', () => { row.remove(); dirty(); refreshOrder(); });
      row.append(input, ...moveButtons, remove); rows.append(row); refreshOrder();
      return input;
    };
    root.replaceChildren(rows, add);
    for (const option of options) append(option);
    const refresh = () => {
      const dropdown = typeSelect.value === 'dropdown'; root.classList.toggle('hidden', !dropdown);
      if (dropdown && !rows.children.length) append();
      for (const input of rows.querySelectorAll('input')) input.disabled = !dropdown;
      refreshOrder();
    };
    typeSelect.addEventListener('change', () => { refresh(); dirty(); });
    add.addEventListener('click', () => { append().focus(); dirty(); });
    refresh();
    return {
      values: () => typeSelect.value === 'dropdown' ? [...rows.querySelectorAll('input')].map((input) => input.value) : [],
      valid: () => [...rows.querySelectorAll('input')].filter((input) => !input.disabled).every((input) => input.reportValidity()),
      reset: () => { rows.replaceChildren(); delete root.dataset.checklistDirty; refresh(); },
    };
  }
  const newTaskType = document.querySelector('#inspection-task-type');
  const newTaskOptions = createTaskOptionsEditor(document.querySelector('#inspection-task-options'), newTaskType);

  async function loadAdminInspectionTasks(supplied = null) {
    if (!supplied) {
      const loading = document.createElement('tr');
      const cell = document.createElement('td'); cell.colSpan = 6; cell.textContent = 'Loading inspection tasks...';
      loading.append(cell); inspectionTasksBody.replaceChildren(loading);
    }
    const response = supplied ? { ok: true } : await fetch('/api/admin/inspection-tasks');
    const result = supplied || await response.json();
    if (!response.ok) throw new Error(taskError(result, 'Unable to load inspection tasks.'));
    rememberResponse('/api/admin/inspection-tasks', result);
    inspectionTasksBody.replaceChildren();
    for (const task of result.tasks) {
      const row = document.createElement('tr');
      row.dataset.taskId = task.id;
      const textCell = document.createElement('td');
      const text = document.createElement('input');
      text.type = 'text'; text.value = task.text; text.maxLength = 200; text.required = true;
      text.autocomplete = 'off'; text.name = `inspection_task_${task.id}`;
      text.className = 'admin-task-text'; text.setAttribute('aria-label', 'Task description');
      textCell.append(text);
      const sectionCell = document.createElement('td');
      const section = document.createElement('select'); section.setAttribute('aria-label', 'Field section');
      section.add(new Option('Store Data', 'store_data')); section.add(new Option('Compliance', 'compliance')); section.add(new Option('NFPA 72', 'nfpa72'));
      section.value = task.section || 'compliance'; sectionCell.append(section);
      const typeCell = document.createElement('td');
      const type = makeTaskTypeSelect(task.input_type);
      const optionsRoot = document.createElement('div');
      const editor = createTaskOptionsEditor(optionsRoot, type, task.options || []);
      typeCell.append(type, optionsRoot);
      const orderCell = document.createElement('td');
      const position = document.createElement('input');
      position.type = 'number'; position.required = true; position.min = '1'; position.max = '10000'; position.step = '1';
      position.value = task.position; position.className = 'admin-task-order'; position.setAttribute('aria-label', 'Task order');
      orderCell.append(position);
      const activeCell = document.createElement('td');
      const active = document.createElement('input');
      active.type = 'checkbox'; active.checked = task.active; active.className = 'admin-task-active'; active.setAttribute('aria-label', 'Task active');
      activeCell.append(active);
      const actions = document.createElement('td');
      const save = document.createElement('button');
      save.type = 'button'; save.textContent = 'Save';
      save.addEventListener('click', async () => {
        if (!text.reportValidity() || !position.reportValidity() || !editor.valid()) return;
        save.disabled = true;
        inspectionTasksMessage.textContent = 'Saving task...';
        try {
          const response = await fetch(`/api/admin/inspection-tasks/${task.id}`, {
            method: 'PATCH', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text.value, section: section.value, position: Number(position.value), active: active.checked, input_type: type.value, options: editor.values() }),
          });
          const result = await response.json();
          if (!response.ok) throw new Error(taskError(result, 'Saving task failed.'));
          await loadAdminInspectionTasks();
          inspectionTasksMessage.textContent = 'Task updated.';
        } catch (error) { inspectionTasksMessage.textContent = error.message; }
        finally { save.disabled = false; }
      });
      actions.append(save);
      row.append(textCell, sectionCell, typeCell, orderCell, activeCell, actions);
      inspectionTasksBody.append(row);
    }
    rememberControls(inspectionTasksBody);
  }

  addInspectionTaskForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = document.querySelector('#add-inspection-task');
    if (button.disabled) return;
    button.disabled = true;
    inspectionTasksMessage.textContent = 'Adding task...';
    const position = document.querySelector('#inspection-task-position').value;
    if (!newTaskOptions.valid()) { button.disabled = false; return; }
    const payload = { section: document.querySelector('#inspection-task-section').value, text: document.querySelector('#inspection-task-text').value, input_type: newTaskType.value, options: newTaskOptions.values() };
    if (position) payload.position = Number(position);
    try {
      const response = await fetch('/api/admin/inspection-tasks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(taskError(result, 'Adding task failed.'));
      addInspectionTaskForm.reset();
      newTaskOptions.reset();
      await loadAdminInspectionTasks();
      inspectionTasksMessage.textContent = 'Task added.';
    } catch (error) { inspectionTasksMessage.textContent = error.message; }
    finally { button.disabled = false; }
  });

  function updateChecklistProgress() {
    for (const [containerId, progressId] of [['store-data-fields','store-data-progress'],['compliance-fields','checklist-progress'],['nfpa72-fields','nfpa72-progress']]) {
      const controls = [...document.getElementById(containerId).querySelectorAll('[data-task-id]')];
      const complete = controls.filter(control => Boolean(control.value.trim())).length;
      document.getElementById(progressId).textContent = controls.length ? `${complete} of ${controls.length} complete` : '';
    }
  }

  async function loadInspectionChecklist(inspectionId, supplied = null) {
    await Promise.all([...checklistSaves]);
    if (currentInspectionId !== inspectionId) return;
    try {
      const response = supplied ? { ok: true } : await fetch(`/api/inspections/${inspectionId}/checklist`);
      const result = supplied || await response.json();
      if (currentInspectionId !== inspectionId) return;
      if (!response.ok) throw new Error(taskError(result, 'Unable to load Inspection fields.'));
      rememberResponse(`/api/inspections/${inspectionId}/checklist`, result);
      const focused = checklistContainer.contains(document.activeElement) ? document.activeElement : null;
      const focusedId = focused?.id;
      const selectionStart = focused?.selectionStart;
      const selectionEnd = focused?.selectionEnd;
      const fieldContainers = {store_data: document.getElementById('store-data-fields'), compliance: document.getElementById('compliance-fields'), nfpa72: document.getElementById('nfpa72-fields')};
      for (const container of Object.values(fieldContainers)) container.replaceChildren();
      for (const task of result.tasks) {
        const checkbox = task.input_type === 'checkbox';
        const row = document.createElement('div'); row.className = checkbox ? 'inspection-task-row' : 'form-field inspection-task-value';
        const control = document.createElement(task.input_type === 'dropdown' ? 'select' : 'input');
        control.id = `checklist-task-${task.id}`; control.dataset.taskId = task.id;
        const label = document.createElement(checkbox ? 'span' : 'label');
        if (!checkbox) label.htmlFor = control.id;
        label.textContent = task.text + (checkbox ? '' : ':');
        label.style.margin = '0'; label.style.fontWeight = '400';
        const choices = [];
        const syncChoices = () => {
          for (const choice of choices) {
            choice.checked = choice.value === control.value;
            choice.disabled = control.disabled;
            fieldBaselines.set(choice, choice.checked);
          }
        };
        if (checkbox) {
          control.type = 'hidden'; control.value = task.value || '';
          label.id = `${control.id}-label`; label.className = 'inspection-task-description';
          const group = document.createElement('div'); group.className = 'task-checkbox-choices';
          group.setAttribute('role', 'group'); group.setAttribute('aria-labelledby', label.id);
          for (const value of ['Yes', 'No', 'NA']) {
            const choice = document.createElement('input'); choice.type = 'checkbox'; choice.value = value;
            choice.id = `${control.id}-${value.toLowerCase()}`;
            choice.dataset.checklistChoice = value;
            const option = document.createElement('label'); option.htmlFor = choice.id;
            option.append(choice, document.createTextNode(value)); group.append(option); choices.push(choice);
            choice.addEventListener('change', () => {
              if (control.disabled) return;
              control.value = choice.checked ? value : '';
              syncChoices(); updateChecklistProgress();
              control.dispatchEvent(new Event('change', { bubbles: true }));
            });
          }
          syncChoices(); row.append(label, control, group);
        }
        else {
          if (task.input_type === 'dropdown') {
            control.add(new Option('Select...', ''));
            for (const choice of task.options) control.add(new Option(choice, choice));
            if (task.removed_choice) control.add(new Option(`${task.value} (removed choice)`, task.value));
          } else { control.type = 'text'; control.maxLength = 2000; control.autocomplete = 'off'; }
          control.value = task.value || ''; row.append(label, control);
        }
        if (task.previous_type || task.removed_choice) {
          const note = document.createElement('span'); note.className = 'task-value-note';
          note.textContent = task.removed_choice ? 'Saved choice retained. Select a current choice to change it.' : 'The previous answer is retained in history. Enter a value for the new type.';
          row.append(note);
        }
        fieldContainers[task.section || 'compliance'].append(row);
        control.addEventListener('input', updateChecklistProgress);
        if (!checkbox) control.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' && control.tagName === 'INPUT') { event.preventDefault(); control.dispatchEvent(new Event('change', { bubbles: true })); }
        });
        control.addEventListener('change', () => {
          if (control.disabled) return;
          const previous = fieldBaselines.get(control);
          const value = controlValue(control);
          if (value === previous) return;
          control.disabled = true;
          syncChoices();
          checklistMessage.textContent = 'Saving checklist value...';
          const save = (async () => {
            try {
              const response = await fetch(`/api/inspections/${inspectionId}/checklist/${task.id}`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value }),
              });
              const result = await response.json();
              if (!response.ok) throw new Error(taskError(result, 'Saving checklist value failed.'));
              fieldBaselines.set(control, value);
              if (currentInspectionId === inspectionId) checklistMessage.textContent = `${({store_data:'Store Data',nfpa72:'NFPA 72',compliance:'Compliance'})[task.section || 'compliance']} saved.`;
              return true;
            } catch (error) {
              if (checkbox) control.value = previous;
              if (currentInspectionId === inspectionId) checklistMessage.textContent = error.message;
              return false;
            } finally {
              control.disabled = false;
              syncChoices();
              if (currentInspectionId === inspectionId) updateChecklistProgress();
            }
          })();
          checklistSaves.add(save); save.finally(() => checklistSaves.delete(save));
        });
      }
      for (const container of Object.values(fieldContainers)) rememberControls(container);
      if (focusedId) {
        const replacement = document.getElementById(focusedId);
        replacement?.focus({ preventScroll: true });
        if (replacement?.type === 'text' && typeof selectionStart === 'number') replacement.setSelectionRange(selectionStart, selectionEnd);
      }
      updateChecklistProgress();
    } catch (error) {
      if (currentInspectionId === inspectionId) checklistMessage.textContent = error.message;
    }
  }

  for (const buttonId of ['refresh-checklist','refresh-nfpa72']) document.getElementById(buttonId)?.addEventListener('click', async () => {
    if (!currentInspectionId) return;
    await Promise.all([...checklistSaves]);
    if (hasDraft(checklistContainer)) { checklistMessage.textContent = 'Save the edited checklist value before refreshing.'; return; }
    await loadInspectionChecklist(currentInspectionId);
  });

  function showAdminTab(name) {
    for (const tab of adminTabs) {
      const active = tab.id === `admin-tab-${name}`;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).classList.toggle('hidden', !active);
    }
  }

  async function loadPanelTypes(supplied = null) {
    const response = supplied ? { ok: true } : await fetch('/api/point-lists/types');
    const result = supplied || await response.json();
    if (!response.ok || result.error) throw new Error(result.error || 'Unable to load panel types.');
    rememberResponse('/api/point-lists/types', result);
    const types = result.panel_types || [];
    for (const select of document.querySelectorAll('select[name=point_list_category]')) {
      const selected = select.value || 'Combo';
      select.replaceChildren();
      for (const item of types) {
        select.add(new Option(item.name, item.name, item.name === 'Combo', item.name === selected));
      }
      if (!select.value && types.length) select.value = types[0].name;
      select.disabled = !types.length;
    }
    panelTypesBody?.replaceChildren();
    for (const item of types) {
      const row = document.createElement('tr');
      const name = document.createElement('td');
      name.textContent = item.name;
      row.append(name);
      panelTypesBody?.append(row);
    }
    return types;
  }

  for (const [index, tab] of adminTabs.entries()) {
    tab.addEventListener('click', async () => {
      showAdminTab(tab.id.replace('admin-tab-', ''));
      if (tab.id === 'admin-tab-integrations') await window.PdfIntegrations?.refreshAdmin(true);
      if (tab.id === 'admin-tab-inspection-tasks') {
        inspectionTasksMessage.textContent = '';
        try { await loadAdminInspectionTasks(); }
        catch (error) { inspectionTasksMessage.textContent = error.message; }
      }
      if (tab.id === 'admin-tab-panel-types') {
        panelTypeMessage.textContent = '';
        try { await loadPanelTypes(); }
        catch (error) { panelTypeMessage.textContent = error.message; }
      }
    });
    tab.addEventListener('keydown', (event) => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % adminTabs.length;
      if (event.key === 'ArrowLeft') next = (index + adminTabs.length - 1) % adminTabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = adminTabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      adminTabs[next].focus();
      adminTabs[next].click();
    });
  }

  addPanelTypeForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (addPanelTypeButton.disabled) return;
    addPanelTypeButton.disabled = true;
    panelTypeMessage.textContent = 'Adding panel type...';
    try {
      const response = await fetch('/api/admin/panel-types', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: panelTypeName.value }),
      });
      const result = await response.json();
      if (!response.ok || result.error) throw new Error(result.error || 'Unable to add panel type.');
      addPanelTypeForm.reset();
      await loadPanelTypes();
      panelTypeMessage.textContent = `Added ${result.panel_type.name}.`;
    } catch (error) {
      panelTypeMessage.textContent = error.message;
    } finally {
      addPanelTypeButton.disabled = false;
    }
  });

  async function openAdminScreen() {
    adminMessage.textContent = '';
    showAdminTab('users');
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

  async function loadAdminUsers(supplied = null) {
    const response = supplied ? { ok: true } : await fetch('/api/admin/users');
    const payload = supplied || await response.json();
    if (!response.ok || payload.error) {
      adminMessage.textContent = payload.error || payload.detail || 'Unable to load users.';
      return;
    }
    rememberResponse('/api/admin/users', payload);
    renderAdminUsers(payload.users || []);
    rememberControls(adminUsersBody);
  }

  async function loadAdminSettings(supplied = null) {
    const response = supplied ? { ok: true } : await fetch('/api/admin/settings');
    const payload = supplied || await response.json();
    if (!response.ok || payload.error) {
      adminMessage.textContent = payload.error || payload.detail || 'Unable to load admin settings.';
      return;
    }
    rememberResponse('/api/admin/settings', payload);
    if (adminDefaultPassword) {
      adminDefaultPassword.value = payload.default_password || '';
    }
    if (adminForceResetDefault) {
      adminForceResetDefault.checked = Boolean(payload.force_password_reset_default);
    }
    rememberControls(document.querySelector('.settings-row'));
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

  async function loadInspections(supplied = null) {
    const response = supplied ? { ok: true } : await fetch('/api/inspections');
    const items = supplied || await response.json();
    if (!response.ok || !Array.isArray(items)) return;
    rememberResponse('/api/inspections', items);
    const selected = inspectionPicker.value;
    inspectionOptions = items;
    inspectionPicker.replaceChildren();
    if (!items.length) {
      inspectionPicker.add(new Option('No inspections yet', ''));
      return;
    }
    for (const item of items) {
      inspectionPicker.add(new Option(formatInspectionLabel(item), item.id));
    }
    if (items.some((item) => item.id === selected)) inspectionPicker.value = selected;
  }

  function openDeleteInspectionModal(selectedId = null) {
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
      deleteInspectionSelector.value = selectedId || inspectionPicker.value || inspectionOptions[0].id;
    }
    deleteInspectionModal.classList.add('open');
  }

  function closeDeleteInspectionModal() {
    deleteInspectionModal?.classList.remove('open');
  }

  function closeNewInspection() {
    if (savingNewInspection) return;
    newInspectionModal.classList.remove('open');
    newInspectionForm.reset();
    newInspectionMessage.textContent = '';
  }

  newInspectionForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (savingNewInspection) return;
    savingNewInspection = true;
    saveNewInspectionButton.disabled = true;
    cancelNewInspectionButton.disabled = true;
    newInspectionMessage.textContent = 'Saving inspection...';
    let savedId = null;
    try {
      const response = await fetch('/api/inspections/blank', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(new FormData(newInspectionForm))),
      });
      const result = await response.json();
      if (!response.ok || result.error) {
        throw new Error(result.error || (Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).join(' ')
          : result.detail) || 'Saving inspection failed.');
      }
      savedId = result.id;
    } catch (error) {
      newInspectionMessage.textContent = error.message || 'Saving inspection failed.';
    } finally {
      savingNewInspection = false;
      saveNewInspectionButton.disabled = false;
      cancelNewInspectionButton.disabled = false;
    }
    if (savedId) {
      closeNewInspection();
      await loadInspections();
      await openInspection(savedId);
    }
  });

  cancelNewInspectionButton?.addEventListener('click', closeNewInspection);
  newInspectionModal?.addEventListener('click', (event) => {
    if (event.target === newInspectionModal) closeNewInspection();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && newInspectionModal?.classList.contains('open')) {
      closeNewInspection();
    }
  });

  async function addPointsListToInspection() {
    if (!currentInspectionId) {
      message.textContent = 'Open an inspection before adding a Points List.';
      return false;
    }

    const firstRow = lists?.querySelector('.point-list');
    const category = firstRow?.querySelector('select')?.value || '';
    const file = firstRow?.querySelector('input[type=file]')?.files?.[0];
    if (!category || !file) {
      message.textContent = 'Choose Security Panel Type and file before finishing review.';
      return false;
    }

    message.textContent = 'Adding Points List...';
    const data = new FormData();
    data.append('point_list_category', category);
    data.append('points_file', file);
    data.append('point_decisions', decisionField.value || '[]');

    const response = await fetch(`/api/inspections/${currentInspectionId}/point-lists`, {
      method: 'POST',
      body: data,
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      message.textContent = result.error || result.detail || 'Adding Points List failed.';
      return false;
    }

    modal.classList.remove('open');
    await openInspection(currentInspectionId, result.point_list_id || null);
    resetCreateForm();
    showScreen('inspection');
    inspectionMessage.textContent = `Points List added: ${formatPointListLabel({ category, filename: result.filename || 'uploaded file' })}.`;
    return true;
  }

  function updateDeviceCellStatus(cell, point) {
    const marked = Boolean(point.device_highlighted);
    const missing = marked && Boolean(point.device_event_missing);
    cell.classList.toggle('device-highlighted', marked);
    cell.classList.toggle('device-event-missing', missing);
    cell.setAttribute('aria-pressed', String(marked));
    cell.title = `${missing ? 'No pending or accepted event time. ' : ''}Double-click to toggle the highlight. Keyboard: Enter or Space.`;
  }

  function renderVisibleAcceptedPoints() {
    const scrollRegion = document.querySelector('#points-table-scroll');
    const previousScroll = scrollRegion.scrollLeft;
    acceptedPointsBody.closest('table').classList.toggle('table-editing', tableEditable);
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
      text.className = 'device-type-cell';
      text.dataset.pointId = point.id;
      updateDeviceCellStatus(text, point);
      text.tabIndex = 0;
      text.setAttribute('role', 'button');
      text.setAttribute('aria-pressed', String(Boolean(point.device_highlighted)));

      const inspectionId = currentInspectionId;
      const pointListId = currentPointListId;
      const toggleHighlight = async () => {
        if (point.highlightSaving) return;
        point.highlightSaving = true;
        const previous = Boolean(point.device_highlighted);
        const previousMissing = Boolean(point.device_event_missing);
        const applyHighlight = (value) => {
          point.device_highlighted = value;
          point.device_event_missing = value === previous ? previousMissing : false;
          updateDeviceCellStatus(text, point);
        };
        applyHighlight(!previous);
        try {
          const response = await fetch(`/api/inspections/${inspectionId}/point-lists/${pointListId}/points/${point.id}/highlight`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ highlighted: !previous }),
          });
          if (!response.ok) throw new Error('Saving Device Type highlight failed. Please try again.');
        } catch (error) {
          applyHighlight(previous);
          if (currentInspectionId === inspectionId && currentPointListId === pointListId) inspectionMessage.textContent = error.message;
        } finally {
          point.highlightSaving = false;
        }
      };
      text.addEventListener('dblclick', toggleHighlight);
      text.addEventListener('keydown', (event) => {
        if (event.target === text && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          toggleHighlight();
        }
      });
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
    scrollRegion.scrollLeft = previousScroll;
  }

  function renderAcceptedPoints(points) {
    rememberResponse('accepted-points', points);
    pendingEventDates = new Map((points || []).filter((point) => point.pending_event_date && !point.event_date).map((point) => [Number(point.address), point.pending_event_date]));
    inspectionPoints = (points || []).map((point) => ({
      ...point,
      id: point.id ?? '',
      serverValues: { ...point },
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

  function renderPdfTemplateFields() {
    if (!pdfTemplateFieldsContainer) {
      return;
    }
    pdfTemplateFieldsContainer.replaceChildren();
    if (!activePdfTemplateFieldNames.length) {
      const empty = document.createElement('div');
      empty.className = 'nfpa-fields-empty';
      empty.textContent = 'No editable PDF fields were found for this template.';
      pdfTemplateFieldsContainer.append(empty);
      return;
    }

    for (const fieldName of activePdfTemplateFieldNames) {
      const row = document.createElement('div');
      row.className = 'nfpa-field-row form-field';
      const label = document.createElement('label');
      label.textContent = `${fieldName}:`;
      label.setAttribute('for', `pdf-field-${fieldName}`);
      const input = document.createElement('input');
      input.type = 'text';
      input.id = `pdf-field-${fieldName}`;
      input.value = String(activePdfTemplateFields[fieldName] || '');
      input.addEventListener('input', () => {
        activePdfTemplateFields[fieldName] = input.value;
      });
      row.append(label, input);
      pdfTemplateFieldsContainer.append(row);
    }
  }

  function refreshPdfTemplatePreviewFrame() {
    if (!pdfTemplatePreviewFrame || !currentInspectionId || !activePdfTemplateKey) {
      return;
    }
    const stamp = Date.now();
    pdfTemplatePreviewFrame.src = `/api/inspections/${currentInspectionId}/pdf-templates/${encodeURIComponent(activePdfTemplateKey)}/preview?ts=${stamp}`;
  }

  async function loadPdfTemplateDraft() {
    if (!currentInspectionId) {
      return { error: 'No inspection selected.' };
    }
    let response;
    try {
      response = await fetch(`/api/inspections/${currentInspectionId}/pdf-templates/${encodeURIComponent(activePdfTemplateKey)}`);
    } catch {
      return { error: 'Unable to reach server while loading PDF template.' };
    }

    let payload;
    try {
      payload = await response.json();
    } catch {
      return { error: `PDF template endpoint returned an invalid response (${response.status}).` };
    }

    if (!response.ok || payload.error) {
      const detail = payload.error || payload.detail || '';
      if (response.status === 404 || String(detail).toLowerCase() === 'not found') {
        return { error: detail || 'PDF template API is not available on this server yet. Restart local API or deploy latest updates.' };
      }
      return { error: detail || 'Unable to load PDF template.' };
    }

    activePdfTemplateFieldNames = Array.isArray(payload.field_names) ? payload.field_names : [];
    activePdfTemplateFields = payload.fields || {};
    renderPdfTemplateFields();
    rememberControls(pdfTemplateFieldsContainer);
    refreshPdfTemplatePreviewFrame();
    return { payload };
  }

  async function savePdfTemplateDraft() {
    if (!currentInspectionId) {
      nfpaDraftMessage.textContent = 'No inspection selected.';
      return false;
    }
    nfpaDraftMessage.textContent = 'Saving PDF fields...';
    const response = await fetch(`/api/inspections/${currentInspectionId}/pdf-templates/${encodeURIComponent(activePdfTemplateKey)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields: activePdfTemplateFields }),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      nfpaDraftMessage.textContent = payload.error || payload.detail || 'Saving PDF fields failed.';
      return false;
    }
    activePdfTemplateFields = payload.fields || activePdfTemplateFields;
    rememberControls(pdfTemplateFieldsContainer);
    nfpaDraftMessage.textContent = `Saved. ${payload.updated_at ? `Updated ${payload.updated_at}` : ''}`.trim();
    refreshPdfTemplatePreviewFrame();
    return true;
  }

  async function openNfpaDraftModal() {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'Open an inspection before editing NFPA PDF fields.';
      return;
    }
    nfpaDraftModal?.classList.add('open');
    activePdfTemplateKey = (pdfTemplateKeySelect?.value || 'nfpa72').trim() || 'nfpa72';
    nfpaDraftMessage.textContent = 'Loading embedded editor...';
    const loaded = await loadPdfTemplateDraft();
    if (loaded.error) {
      nfpaDraftMessage.textContent = loaded.error;
      inspectionMessage.textContent = loaded.error;
      return;
    }
    nfpaDraftMessage.textContent = loaded.payload?.updated_at
      ? `Loaded saved draft. Last update: ${loaded.payload.updated_at}`
      : 'Template loaded. Edit fields and click Save.';
    inspectionMessage.textContent = '';
  }

  function closeNfpaDraftModal() {
    nfpaDraftModal?.classList.remove('open');
  }

  function syncMissingToggleLabel() {
    if (!inspectionMenuToggleMissingOption) {
      return;
    }
    inspectionMenuToggleMissingOption.textContent = showMissingOnly ? 'Show All Points' : 'Show Missing Points Only';
  }

  function closeInspectionMenu() {
    inspectionMenu?.classList.add('hidden');
  }

  function setInspectionBusy(isBusy, text = 'Working...') {
    if (inspectionBusyText) {
      inspectionBusyText.textContent = text;
    }
    inspectionBusyOverlay?.classList.toggle('hidden', !isBusy);
  }

  function buildEditableRowsSnapshot() {
    return (inspectionPoints || []).map((point) => ({
      id: String(point.id ?? ''),
      text: String(point.editableText ?? point.text ?? '').trim(),
      address: String(point.editableAddress ?? point.address ?? '').trim(),
      location: String(point.location ?? '').trim(),
      event_date: String(point.editableEventDate ?? point.event_date ?? '').trim(),
    }));
  }

  async function savePendingEventMatches() {
    if (!currentInspectionId || !currentPointListId) {
      return { skipped: true };
    }
    const matches = [...pendingEventDates.entries()].map(([point, timestamp]) => ({
      point,
      timestamp,
    }));
    if (!matches.length) {
      return { skipped: true, saved: 0 };
    }

    const response = await fetch(`/api/inspections/${currentInspectionId}/event-dates/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ point_list_id: currentPointListId, matches }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      return { error: result.error || result.detail || 'Saving pending event matches failed.' };
    }
    pendingEventDates = new Map();
    return { saved: Number(result.saved || 0), ignoredExisting: Number(result.ignored_existing || 0) };
  }

  async function saveAllInspectionChanges() {
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    inspectionMessage.textContent = 'Saving all changes...';
    for (const control of checklistContainer.querySelectorAll('[data-task-id]')) {
      if (!control.disabled && fieldBaselines.get(control) !== controlValue(control)) control.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if ((await Promise.all([...checklistSaves])).includes(false)) {
      inspectionMessage.textContent = 'A checklist item could not be saved. Please try again.';
      return;
    }

    await saveInspectionDetails();

    if (currentPointListId) {
      const rows = buildEditableRowsSnapshot();
      const persisted = await persistAcceptedPoints(rows);
      if (persisted.error) {
        inspectionMessage.textContent = persisted.error;
        return;
      }
      tableEditable = false;
      syncTableEditButtons();
    }

    const pendingResult = await savePendingEventMatches();
    if (pendingResult.error) {
      inspectionMessage.textContent = pendingResult.error;
      return;
    }

    if (await window.PdfIntegrations?.saveDetails?.() === false) {
      inspectionMessage.textContent = 'Inspection data saved. Some Export Form Details remain unsaved; review the field messages.';
      return;
    }
    await openInspection(currentInspectionId, currentPointListId);
    inspectionMessage.textContent = pendingResult.saved
      ? `All changes saved. Accepted ${pendingResult.saved} pending event matches.`
      : 'All changes saved.';
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

  function formatPointListLabel(item) {
    const filename = (item.filename || '').replace(/^\d{14}-/, '');
    return `${item.category || 'Panel'} (${filename})`;
  }

  function renderInspectionPointListSelector(pointLists, selectedPointListId) {
    if (!inspectionPointListSelector) {
      return;
    }
    inspectionPointListSelector.replaceChildren();
    for (const item of pointLists || []) {
      const label = formatPointListLabel(item);
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

  function saveInspectionDetails() {
    const inspectionId = currentInspectionId;
    if (suppressInspectionDetailsSave || !inspectionId) return Promise.resolve();
    inspectionDetailsSaveQueue = inspectionDetailsSaveQueue.catch(() => {}).then(() => {
      if (currentInspectionId !== inspectionId) return;
      return persistInspectionDetails();
    });
    return inspectionDetailsSaveQueue;
  }

  async function persistInspectionDetails() {
    if (suppressInspectionDetailsSave || !currentInspectionId) {
      return;
    }
    const inspectionId = currentInspectionId;
    const payload = {
      store_number: inspectionStoreNumber?.value || '',
      store_type: inspectionStoreType?.value || '',
      address: inspectionAddress?.value || '',
      city: inspectionCity?.value || '',
      state: inspectionState?.value || '',
      inspector_name: inspectionInspector?.value || '',
      start_date: inspectionStartDate?.value || '',
      completion_date: inspectionEndDate?.value || '',
    };
    for (const [key, control] of Object.entries(detailFields())) {
      if (fieldBaselines.has(control) && payload[key] === fieldBaselines.get(control)) delete payload[key];
    }
    if (!Object.keys(payload).length) return;
    const response = await fetch(`/api/inspections/${inspectionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      inspectionMessage.textContent = result.error || result.detail || 'Saving inspection details failed.';
      return;
    }
    if (currentInspectionId !== inspectionId) return;
    for (const [key, value] of Object.entries(payload)) {
      const control = detailFields()[key];
      if (control.value === value) {
        control.value = String(result[key] ?? value);
        fieldBaselines.set(control, control.value);
      }
    }
    inspectionName.textContent = result.name;
    if (inspectionCity.value === payload.city) inspectionCity.value = result.city || '';
    if (inspectionState.value === payload.state) inspectionState.value = result.state || '';
    inspectionMessage.textContent = 'Inspection details saved.';
    await loadInspections();
  }

  async function persistAcceptedPoints(rows) {
    if (!currentInspectionId || !currentPointListId) {
      return { error: 'No inspection or Points List selected.' };
    }
    const changes = [];
    for (const row of rows) {
      const point = inspectionPoints.find((item) => String(item.id) === row.id);
      const baseline = point?.serverValues || {};
      const change = { id: row.id };
      for (const key of ['text', 'address', 'location', 'event_date']) {
        if (String(row[key] ?? '') === String(baseline[key] ?? '')) continue;
        if (key === 'event_date' && baseline.event_date && !row.event_date) {
          return { error: 'Use Clear Dates to explicitly clear accepted test results.' };
        }
        change[key] = row[key];
      }
      if (Object.keys(change).length > 1) changes.push(change);
    }
    const response = await fetch(`/api/inspections/${currentInspectionId}/accepted-points/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        point_list_id: currentPointListId,
        rows: changes,
      }),
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      return { error: result.error || result.detail || 'Saving accepted points failed.' };
    }
    return { result };
  }

  async function openInspection(inspectionId, pointListId = null) {
    loadingInspection++;
    viewVersion++;
    try { return await fetchAndOpenInspection(inspectionId, pointListId); }
    finally { loadingInspection--; }
  }

  async function fetchAndOpenInspection(inspectionId, pointListId = null) {
    if (!inspectionId) {
      return;
    }
    const query = pointListId ? `?point_list_id=${encodeURIComponent(pointListId)}` : '';
    const response = await fetch(`/api/inspections/${inspectionId}${query}`);
    const inspection = await response.json();
    if (!response.ok || inspection.error) {
      inspectionMessage.textContent = inspection.error || inspection.detail || 'Loading the inspection failed.';
      return;
    }
    pendingEventDates = new Map();
    showMissingOnly = false;
    tableEditable = false;
    syncTableEditButtons();
    currentInspectionId = inspection.id;
    inspectionName.textContent = inspection.name;
    inspectionCity.value = inspection.city || '';
    inspectionState.value = inspection.state || '';
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
    await loadInspectionChecklist(inspection.id);
    rememberControls(inspectionScreen);
    rememberResponse('inspection-point-lists', inspection.point_lists || []);
    rememberResponse('event-history-files', inspection.event_history_files || []);
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
    summary.textContent = `${formatPointListLabel(selected)} — Accepted: ${selected.accepted} | Needs review: ${selected.rejected}`;
    renderRows(selected.rows);
    renderedListIndex = index;
  }

  closePreviewButton?.addEventListener('click', () => modal.classList.remove('open'));

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

  inspectionMenuButton?.addEventListener('click', (event) => {
    event.preventDefault();
    inspectionMenu?.classList.toggle('hidden');
  });

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Node)) {
      return;
    }
    if (avatarWrap && !avatarWrap.contains(event.target)) {
      avatarMenu?.classList.add('hidden');
    }
    if (inspectionMenuWrap && !inspectionMenuWrap.contains(event.target)) {
      closeInspectionMenu();
    }
  });

  startCreateButton?.addEventListener('click', () => {
    newInspectionForm.reset();
    const today = new Date();
    const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    newInspectionForm.elements.start_date.value = localDate;
    newInspectionForm.elements.completion_date.value = localDate;
    newInspectionMessage.textContent = '';
    newInspectionModal.classList.add('open');
    newInspectionForm.elements.store_number.focus();
  });

  document.querySelector('#delete-open-inspection')?.addEventListener('click', async () => {
    closeInspectionMenu();
    await loadInspections();
    openDeleteInspectionModal(currentInspectionId);
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
    const confirmed = window.confirm(`Delete this inspection?\n\n${label}\n\nIt will be removed from the inspection list. Source files and review decisions are retained for audit.\n\nClick OK to confirm or Cancel to keep it.`);
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
    showScreen('home');
    homeMessage.textContent = 'Inspection deleted.';
  });

  backHomeFromCreate?.addEventListener('click', async () => {
    if (currentInspectionId) {
      await openInspection(currentInspectionId, currentPointListId);
      showScreen('inspection');
      return;
    }
    await loadInspections();
    showScreen('home');
  });

  homeLinkFromInspection?.addEventListener('click', async (event) => {
    event.preventDefault();
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

  inspectionMenuAddPointListOption?.addEventListener('click', async () => {
    closeInspectionMenu();
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'Open an inspection before adding a Points List.';
      return;
    }
    resetCreateForm();
    try { await loadPanelTypes(); }
    catch (error) { inspectionMessage.textContent = error.message; return; }
    message.textContent = '';
    showScreen('create');
  });

  inspectionMenuDeletePointListOption?.addEventListener('click', async () => {
    closeInspectionMenu();
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'No Points List selected to delete.';
      return;
    }

    const selectedLabel = inspectionPointListSelector?.selectedOptions?.[0]?.textContent || 'selected list';
    const confirmed = window.confirm(`Delete this Points List?\n\n${selectedLabel}\n\nClick OK to confirm.`);
    if (!confirmed) {
      return;
    }

    const response = await fetch(`/api/inspections/${currentInspectionId}/point-lists/${currentPointListId}`, {
      method: 'DELETE',
    });
    const result = await response.json();
    if (!response.ok || result.error) {
      inspectionMessage.textContent = result.error || result.detail || 'Deleting Points List failed.';
      return;
    }

    await openInspection(currentInspectionId);
    inspectionMessage.textContent = 'Points List deleted.';
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
      message.textContent = 'Select Security Panel Type and upload a file before previewing.';
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
        const option = new Option(formatPointListLabel(item), String(index));
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
      const option = new Option(formatPointListLabel(item), String(index));
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
    if (!previewLists.length) {
      message.textContent = 'Preview at least one Points List before saving decisions.';
      return;
    }
    persistSelectedList();
    const selected = previewLists[selectedListIndex];
    if (!selected) {
      message.textContent = 'No Points List is selected to save.';
      return;
    }
    if ((selected.rows || []).some((row) => row.accepted === false)) {
      message.textContent = 'Delete all Review rows or mark them Accepted before saving decisions.';
      return;
    }
    const selectedDecisions = rowDecisions(selected.rows, selected.filename);
    decisionField.value = JSON.stringify(selectedDecisions);
    const added = await addPointsListToInspection();
    if (!added) {
      return;
    }
    message.textContent = `Saved review decisions for ${selected.filename}.`;
  }

  for (const button of deleteButtons) {
    button.addEventListener('click', deleteReviewRows, true);
  }
  for (const button of saveButtons) {
    button.addEventListener('click', saveReviewDecisions, true);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    message.textContent = 'Use Preview Points List and Save Decisions to add the Points List to this inspection.';
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
    setInspectionBusy(true, 'Uploading and matching event history...');
    const data = new FormData();
    data.append('point_list_id', currentPointListId);
    data.append('event_file', file);
    try {
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

      for (const status of result.device_statuses || []) {
        const point = inspectionPoints.find((item) => item.id === status.id);
        if (point) Object.assign(point, status);
      }
      eventHistoryForm.reset();
      setEventFileName();
      renderVisibleAcceptedPoints();
      inspectionMessage.textContent = `Event History uploaded: ${result.filename}. Pending matches: ${pendingEventDates.size}. Click Accept Results to persist.`;
    } finally {
      setInspectionBusy(false);
    }
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

  inspectionMenuToggleMissingOption?.addEventListener('click', () => {
    closeInspectionMenu();
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
    if (!pendingEventDates.size) {
      inspectionMessage.textContent = 'No pending dates to accept.';
      return;
    }
    inspectionMessage.textContent = 'Accepting matched results...';
    const result = await savePendingEventMatches();
    if (result.error) {
      inspectionMessage.textContent = result.error;
      return;
    }
    await openInspection(currentInspectionId, currentPointListId);
    inspectionMessage.textContent = `Saved ${result.saved} new dates. Ignored existing: ${result.ignoredExisting}.`;
  });

  saveAllInspectionButton?.addEventListener('click', async () => {
    await saveAllInspectionChanges();
  });

  inspectionMenuClearDatesOption?.addEventListener('click', async () => {
    closeInspectionMenu();
    if (!currentInspectionId) {
      inspectionMessage.textContent = 'No inspection selected.';
      return;
    }
    if (!currentPointListId) {
      inspectionMessage.textContent = 'Select a Points List first.';
      return;
    }
    if (!window.confirm('Clear all accepted test results for this Points List? Previous results will remain in the audit history.')) return;
    inspectionMessage.textContent = 'Clearing saved dates...';
    const response = await fetch(`/api/inspections/${currentInspectionId}/event-dates/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ point_list_id: currentPointListId, confirmed: true }),
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

  inspectionMenuEditNfpaOption?.addEventListener('click', async () => {
    closeInspectionMenu();
    await openNfpaDraftModal();
  });

  closeNfpaDraftButton?.addEventListener('click', () => {
    closeNfpaDraftModal();
  });

  cancelNfpaDraftButton?.addEventListener('click', () => {
    closeNfpaDraftModal();
  });

  nfpaDraftModal?.addEventListener('click', (event) => {
    if (event.target === nfpaDraftModal) {
      closeNfpaDraftModal();
    }
  });

  saveNfpaDraftButton?.addEventListener('click', async () => {
    await savePdfTemplateDraft();
  });

  pdfTemplateKeySelect?.addEventListener('change', async () => {
    activePdfTemplateKey = (pdfTemplateKeySelect.value || 'nfpa72').trim() || 'nfpa72';
    if (!nfpaDraftModal?.classList.contains('open')) {
      return;
    }
    nfpaDraftMessage.textContent = 'Loading selected template...';
    const loaded = await loadPdfTemplateDraft();
    if (loaded.error) {
      nfpaDraftMessage.textContent = loaded.error;
      return;
    }
    nfpaDraftMessage.textContent = loaded.payload?.updated_at
      ? `Loaded saved draft. Last update: ${loaded.payload.updated_at}`
      : 'Template loaded. Edit fields and click Save.';
  });

  refreshPdfTemplateButton?.addEventListener('click', async () => {
    if (!nfpaDraftModal?.classList.contains('open')) {
      return;
    }
    nfpaDraftMessage.textContent = 'Reloading template...';
    const loaded = await loadPdfTemplateDraft();
    if (loaded.error) {
      nfpaDraftMessage.textContent = loaded.error;
      return;
    }
    nfpaDraftMessage.textContent = 'Template reloaded.';
  });

  downloadNfpaDraftButton?.addEventListener('click', async () => {
    if (!currentInspectionId) {
      nfpaDraftMessage.textContent = 'No inspection selected.';
      return;
    }
    const didSave = await savePdfTemplateDraft();
    if (!didSave) {
      return;
    }
    nfpaDraftMessage.textContent = 'Downloading updated template...';
    const response = await fetch(`/api/inspections/${currentInspectionId}/pdf-templates/${encodeURIComponent(activePdfTemplateKey)}/download`);
    const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
    if (!response.ok || !contentType.includes('application/pdf')) {
      let details = 'NFPA template download failed.';
      try {
        const errorResult = await response.json();
        details = errorResult.error || errorResult.detail || details;
      } catch {
        details = `NFPA template download failed (${response.status}).`;
      }
      nfpaDraftMessage.textContent = details;
      return;
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^\"]+)"?/i);
    const filename = match ? match[1] : 'NFPA72_template.pdf';
    try {
      const outcome = await savePdfWithDialog(blob, filename);
      nfpaDraftMessage.textContent = outcome === 'saved'
        ? `Template PDF saved: ${filename}`
        : `Template PDF downloaded: ${filename}`;
    } catch (error) {
      nfpaDraftMessage.textContent = `Template PDF save failed: ${error?.message || 'unknown error'}`;
    }
  });

  inspectionMenuExportPdfOption?.addEventListener('click', async () => {
    closeInspectionMenu();
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

  [inspectionStoreNumber, inspectionStoreType, inspectionAddress, inspectionCity, inspectionState, inspectionInspector].forEach((element) => {
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
