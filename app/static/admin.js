(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  if (!$('login-form')) return;
  let csrfToken = null;
  let csrfPending = null;
  let dashboardData = null;
  let sessionGeneration = 0;
  let refreshPending = false;
  let familyFileValidated = null;
  let invitedFamilies = [];
  let inviteLoadPending = false;
  let refreshTimer = null;

  function setError(message) {
    $('login-error').textContent = message;
    $('login-error').hidden = false;
  }
  async function api(path, options) {
    const request = Object.assign({credentials: 'same-origin', cache: 'no-store'}, options || {});
    const response = await fetch(path, request);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error((data.error && data.error.message) || 'Não foi possível concluir.');
      error.status = response.status;
      throw error;
    }
    return data;
  }
  async function ensureCsrf() {
    if (csrfToken) return csrfToken;
    // Share one initial request and reject a response from a previous session.
    if (!csrfPending) {
      const generation = sessionGeneration;
      const pending = api('/api/auth/csrf').then((data) => {
        if (generation !== sessionGeneration) {
          throw new Error('A sessão mudou. Entre novamente.');
        }
        if (typeof data.csrf_token !== 'string' || !data.csrf_token) {
          throw new Error('Não foi possível validar a sessão.');
        }
        csrfToken = data.csrf_token;
        return csrfToken;
      }).finally(() => {
        if (csrfPending === pending) csrfPending = null;
      });
      csrfPending = pending;
    }
    return csrfPending;
  }
  function clearList(id) { $(id).replaceChildren(); }
  function putEmpty(id) {
    const li = document.createElement('li');
    li.textContent = 'Nenhum registro.';
    li.className = 'empty';
    $(id).append(li);
  }
  function appendFamily(id, family) {
    const li = document.createElement('li');
    const name = document.createElement('strong');
    name.textContent = family.contact_name;
    const details = document.createElement('p');
    details.className = 'muted';
    details.textContent = family.participants.length
      ? family.participants.map((p) => p.name + (
          p.kind === 'CHILD' ? ' (' + p.age_years + ' anos)' : ''
        )).join(', ')
      : 'Não comparecerá';
    li.append(name, details);
    $(id).append(li);
  }
  // Search happens only in the organizer's authenticated browser session.
  // No private names are sent in the URL, logs or local storage.
  function fold(value) {
    return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  }
  function matchesFamily(family, term) {
    return fold(family.contact_name).includes(term) ||
      family.participants.some((person) => fold(person.name).includes(term));
  }
  function renderGuestLists(data) {
    const term = fold($('guest-search').value.trim());
    const confirmed = data.confirmed.filter((family) => matchesFamily(family, term));
    const declined = data.declined.filter((family) => matchesFamily(family, term));
    const matchingContacts = new Set(confirmed.filter(
      (family) => fold(family.contact_name).includes(term)
    ).map((family) => family.id));
    const children = data.souvenir_children.filter((child) =>
      matchingContacts.has(child.family_id) || fold(child.name).includes(term)
    );
    clearList('confirmed-list'); clearList('declined-list'); clearList('souvenir-list');
    confirmed.forEach((family) => appendFamily('confirmed-list', family));
    declined.forEach((family) => appendFamily('declined-list', family));
    children.forEach((child) => {
      const li = document.createElement('li');
      li.textContent = child.name + ' — ' + child.age_years + ' ano(s)';
      $('souvenir-list').append(li);
    });
    if (!confirmed.length) putEmpty('confirmed-list');
    if (!declined.length) putEmpty('declined-list');
    if (!children.length) putEmpty('souvenir-list');
    const found = confirmed.length + declined.length;
    const total = data.confirmed.length + data.declined.length;
    $('search-summary').textContent = 'Exibindo ' + found + ' de ' + total +
      ' respostas. Crianças na lista: ' + children.length + '.';
    $('clear-search').hidden = !$('guest-search').value;
  }
  // Reject incomplete HTTP 200 payloads before touching private counters or lists.
  function validDashboardSnapshot(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data) ||
        !data.counts || typeof data.counts !== 'object' ||
        !Array.isArray(data.confirmed) || !Array.isArray(data.declined) ||
        !Array.isArray(data.souvenir_children) ||
        !Number.isSafeInteger(data.buffet_limit) || data.buffet_limit < 1 ||
        typeof data.buffet_limit_reached !== 'boolean') return false;

    const values = {total: 0, buffet: 0, children_0_5: 0, children_0_12: 0, over_12: 0};
    const familyIds = new Set();
    const expectedChildren = [];
    for (const [attending, families] of [[true, data.confirmed], [false, data.declined]]) {
      for (const family of families) {
        if (!family || typeof family.id !== 'string' || !family.id ||
            typeof family.contact_name !== 'string' || !family.contact_name.trim() ||
            family.attending !== attending || !Array.isArray(family.participants) ||
            familyIds.has(family.id) || (attending && !family.participants.length) ||
            (!attending && family.participants.length)) return false;
        familyIds.add(family.id);
        for (const person of family.participants) {
          if (!person || typeof person.name !== 'string' || !person.name.trim()) return false;
          values.total += 1;
          if (person.kind === 'OVER_12' && person.age_years === null) {
            values.over_12 += 1;
            values.buffet += 1;
          } else if (person.kind === 'CHILD' &&
                     Number.isInteger(person.age_years) &&
                     person.age_years >= 0 && person.age_years <= 12) {
            values.children_0_12 += 1;
            if (person.age_years <= 5) values.children_0_5 += 1;
            else values.buffet += 1;
            expectedChildren.push([family.id, person.name, person.age_years]);
          } else return false;
        }
      }
    }
    if (Object.entries(values).some(([key, value]) =>
      !Number.isSafeInteger(data.counts[key]) || data.counts[key] !== value)) return false;
    if (data.buffet_limit_reached !== (values.buffet >= data.buffet_limit) ||
        data.souvenir_children.length !== expectedChildren.length) return false;

    // Match every listed child to one actual participant, preserving duplicates.
    const unmatched = [...expectedChildren];
    for (const child of data.souvenir_children) {
      if (!child) return false;
      const index = unmatched.findIndex(([familyId, name, age]) =>
        familyId === child.family_id && name === child.name && age === child.age_years);
      if (index === -1) return false;
      unmatched.splice(index, 1);
    }
    return unmatched.length === 0;
  }
  async function fetchDashboardSnapshot() {
    const snapshot = await api('/api/admin/dashboard');
    if (!validDashboardSnapshot(snapshot)) {
      throw new Error('Dados incompletos recebidos do servidor.');
    }
    return snapshot;
  }

  function drawDashboard(data) {
    dashboardData = data;
    const counts = data.counts;
    document.querySelector('[data-testid=total-count]').textContent = String(counts.total);
    document.querySelector('[data-testid=buffet-count]').textContent = String(counts.buffet);
    document.querySelector('[data-testid=young-count]').textContent = String(counts.children_0_5);
    document.querySelector('[data-testid=souvenir-count]').textContent = String(counts.children_0_12);
    document.querySelector('[data-testid=over-count]').textContent = String(counts.over_12);
    document.querySelector('[data-testid=middle-count]').textContent =
      String(counts.children_0_12 - counts.children_0_5);
    document.querySelector('[data-testid=confirmed-families]').textContent = String(data.confirmed.length);
    document.querySelector('[data-testid=declined-families]').textContent = String(data.declined.length);
    $('buffet-alert').hidden = !data.buffet_limit_reached;
    if (data.buffet_limit_reached) {
      $('buffet-alert').textContent = 'Atenção: contagem do buffet alcançou o limite interno de ' + data.buffet_limit + '.';
    }
    renderGuestLists(data);
  }
  function eventTime(utc) {
    if (!utc) return '';
    const values = new Intl.DateTimeFormat('sv-SE', {
      timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',hourCycle:'h23'
    }).format(new Date(utc));
    return values.replace(' ', 'T').slice(0, 16);
  }
  async function loadDashboard() {
    const generation = sessionGeneration;
    const data = await fetchDashboardSnapshot();
    if (generation !== sessionGeneration) return;
    const settings = await api('/api/admin/settings');
    // A delayed HTTP 200 must never reopen names after logout/expiration.
    if (generation !== sessionGeneration) return;
    $('login-panel').hidden = true;
    $('dashboard-panel').hidden = false;
    drawDashboard(data);
    void updateFamilySummary();
    void loadInvitationRoster();
    $('venue-input').value = settings.venue || '';
    $('deadline-input').value = eventTime(settings.edit_deadline_utc);
  }
  function stopRefreshTimer() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }
  function configureRefreshTimer() {
    stopRefreshTimer();
    const seconds = Number($('refresh-interval').value);
    if (!dashboardData || $('dashboard-panel').hidden || ![15, 30, 60].includes(seconds)) {
      return;
    }
    refreshTimer = setInterval(() => {
      if (!document.hidden) void refreshDashboard();
    }, seconds * 1000);
  }
  function clearPrivateDashboard() {
    sessionGeneration += 1;
    // Expired Flask sessions no longer have the previous CSRF token.
    csrfToken = null;
    csrfPending = null;
    stopRefreshTimer();
    dashboardData = null;
    refreshPending = false;
    invitedFamilies = [];
    inviteLoadPending = false;
    clearList('invite-list');
    $('invite-search').value = '';
    $('invite-status-filter').value = 'TODOS';
    $('invite-sent-filter').value = 'TODOS';
    $('invite-status').textContent = '';
    $('invite-refresh-btn').disabled = false;
    for (const name of ['total', 'pending', 'confirmed', 'declined', 'sent', 'not-sent']) {
      document.querySelector('[data-testid="invite-' + name + '"]').textContent = '0';
    }
    $('dashboard-panel').hidden = true;
    $('login-panel').hidden = false;
    ['confirmed-list', 'declined-list', 'souvenir-list'].forEach(clearList);
    $('guest-search').value = '';
    $('search-summary').textContent = '';
    $('clear-search').hidden = true;
    $('refresh-interval').value = '0';
    $('refresh-status').textContent = '';
    $('refresh-dashboard-btn').disabled = false;
    $('refresh-dashboard-btn').textContent = 'Atualizar dados';
    $('export-status').textContent = '';
    $('planning-status').textContent = '';
    $('activity-status').textContent = '';
    $('family-preview-status').textContent = '';
    $('family-preview-errors').replaceChildren();
    $('family-file').value = '';
    familyFileValidated = null;
    $('family-import-btn').disabled = true;
    $('family-import-status').textContent = '';
    $('invitation-link-status').textContent = '';
    $('family-saved-summary').textContent = '';
    clearList('activity-list');
    $('load-activity-btn').disabled = false;
    $('venue-input').value = '';
    $('deadline-input').value = '';
    $('settings-status').textContent = '';
    $('admin-password').value = '';
    $('buffet-alert').hidden = true;
    $('buffet-alert').textContent = '';
    ['total-count', 'buffet-count', 'young-count', 'souvenir-count', 'over-count', 'middle-count', 'confirmed-families', 'declined-families']
      .forEach((name) => {
        document.querySelector('[data-testid=' + name + ']').textContent = '0';
      });
  }
  function expireOrganizerSession() {
    clearPrivateDashboard();
    setError('Sua sessão expirou. Entre novamente para consultar os convidados.');
  }
  async function refreshDashboard() {
    if (refreshPending || !dashboardData || $('dashboard-panel').hidden) return;
    const generation = sessionGeneration;
    refreshPending = true;
    $('refresh-dashboard-btn').disabled = true;
    $('refresh-dashboard-btn').textContent = 'Atualizando...';
    $('refresh-status').textContent = 'Consultando confirmações...';
    try {
      const data = await fetchDashboardSnapshot();
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      // Keep the search term and any unsaved venue/deadline edits unchanged.
      drawDashboard(data);
      void loadInvitationRoster();
      $('refresh-status').textContent = 'Dados atualizados às ' +
        new Intl.DateTimeFormat('pt-BR', {hour: '2-digit', minute: '2-digit',
          second: '2-digit'}).format(new Date()) + '.';
    } catch (error) {
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (error.status === 401 || error.status === 403) {
        expireOrganizerSession();
      } else {
        $('refresh-status').textContent = 'Falha ao atualizar. Os dados exibidos são da última consulta.';
      }
    } finally {
      if (generation === sessionGeneration) {
        refreshPending = false;
        $('refresh-dashboard-btn').disabled = false;
        $('refresh-dashboard-btn').textContent = 'Atualizar dados';
      }
    }
  }
  async function logIn(event) {
    event.preventDefault();
    $('login-error').hidden = true;
    $('login-btn').disabled = true;
    // Never keep plaintext password in the form after a failed login/network request.
    const password = $('admin-password').value;
    $('admin-password').value = '';
    try {
      const token = await ensureCsrf();
      const result = await api('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'X-CSRF-Token':token},
        body: JSON.stringify({
          username: $('admin-username').value,
          password: password
        })
      });
      csrfToken = result.csrf_token;
      sessionGeneration += 1;
      $('admin-password').value = '';
      await loadDashboard();
    } catch (error) { setError(error.message); }
    finally { $('login-btn').disabled = false; }
  }
  async function saveSettings(event) {
    event.preventDefault();
    const generation = sessionGeneration;
    $('settings-status').textContent = '';
    $('save-settings').disabled = true;
    try {
      const rawDeadline = $('deadline-input').value;
      // The party uses America/Sao_Paulo (UTC-03 in 2026).
      const payload = {
        venue: $('venue-input').value.trim() || null,
        edit_deadline_utc: rawDeadline ? rawDeadline + ':00-03:00' : null
      };
      await api('/api/admin/settings', {
        method:'PUT', headers:{'Content-Type':'application/json','X-CSRF-Token':await ensureCsrf()},
        body:JSON.stringify(payload)
      });
      if (generation !== sessionGeneration) return;
      $('settings-status').textContent = 'Configuração salva com sucesso.';
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('settings-status').textContent = error.message;
    } finally { $('save-settings').disabled = false; }
  }
  async function exportCsv() {
    const generation = sessionGeneration;
    const button = $('export-csv-btn');
    button.disabled = true;
    $('export-status').textContent = '';
    try {
      const response = await fetch('/api/admin/export.csv', {
        credentials: 'same-origin', cache: 'no-store'
      });
      if (generation !== sessionGeneration) return;
      if (!response.ok) {
        const error = new Error('Não foi possível exportar. Entre novamente no painel.');
        error.status = response.status;
        throw error;
      }
      const csvBlob = await response.blob();
      // A resposta pode chegar depois de clicar em Sair; nunca baixar dados nessa condição.
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      const href = URL.createObjectURL(csvBlob);
      try {
        const download = document.createElement('a');
        download.href = href;
        download.download = 'isadora-confirmacoes.csv';
        document.body.append(download);
        download.click();
        download.remove();
      } finally {
        URL.revokeObjectURL(href);
      }
      if (generation === sessionGeneration) {
        $('export-status').textContent = 'Relatório preparado para download. Mantenha o arquivo em local privado.';
      }
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('export-status').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }
  async function exportPlanning() {
    const generation = sessionGeneration;
    const button = $('export-planning-btn');
    button.disabled = true;
    $('planning-status').textContent = '';
    try {
      const response = await fetch('/api/admin/planning.csv', {
        credentials: 'same-origin', cache: 'no-store'
      });
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!response.ok) {
        const error = new Error('Não foi possível gerar o resumo.');
        error.status = response.status;
        throw error;
      }
      const content = await response.blob();
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      const href = URL.createObjectURL(content);
      try {
        const anchor = document.createElement('a');
        anchor.href = href;
        anchor.download = 'isadora-resumo-buffet.csv';
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
      } finally {
        URL.revokeObjectURL(href);
      }
      $('planning-status').textContent = 'Resumo quantitativo criado, sem nomes de convidados.';
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('planning-status').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function downloadFamilyTemplate(format = 'csv') {
    const generation = sessionGeneration;
    const status = $('family-preview-status');
    status.textContent = '';
    try {
      const response = await fetch('/api/admin/guest-list-template.' + format, {
        credentials: 'same-origin', cache: 'no-store'
      });
      if (!response.ok) {
        const error = new Error('Não foi possível obter o modelo.');
        error.status = response.status;
        throw error;
      }
      const blob = await response.blob();
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      const href = URL.createObjectURL(blob);
      try {
        const link = document.createElement('a');
        link.href = href;
        link.download = 'modelo-familias.' + format;
        document.body.append(link);
        link.click();
        link.remove();
      } finally {
        URL.revokeObjectURL(href);
      }
      status.textContent = 'Modelo ' + format.toUpperCase() + ' baixado com dados fictícios. Substitua o exemplo antes de importar.';
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else status.textContent = error.message;
    }
  }
  async function validateFamilyFile() {
    const file = $('family-file').files[0];
    const status = $('family-preview-status');
    const errors = $('family-preview-errors');
    errors.replaceChildren();
    if (!file) { status.textContent = 'Selecione uma planilha CSV ou XLSX.'; return; }
    if (file.size > 60 * 1024) {
      status.textContent = 'Arquivo maior que 60 KB.'; return;
    }
    const isExcel = /\.xlsx$/i.test(file.name);
    const isCsv = /\.csv$/i.test(file.name);
    if (!isExcel && !isCsv) {
      status.textContent = 'Use uma planilha .xlsx ou .csv.'; return;
    }
    const generation = sessionGeneration;
    familyFileValidated = null;
    $('family-import-btn').disabled = true;
    const button = $('family-preview-btn');
    button.disabled = true;
    status.textContent = 'Validando planilha...';
    try {
      const response = await fetch('/api/admin/guest-list-preview', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {
          'Content-Type': isExcel
            ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            : 'text/csv',
          'X-CSRF-Token': await ensureCsrf()
        },
        body: file
      });
      const data = await response.json().catch(() => ({}));
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!response.ok) {
        const error = new Error((data.error && data.error.message) || 'Falha ao validar.');
        error.status = response.status;
        throw error;
      }
      if (!Array.isArray(data.errors) || typeof data.valid !== 'boolean' ||
          !Number.isInteger(data.families) || data.saved !== false) {
        throw new Error('Resposta de validação inválida.');
      }
      if (data.valid) {
        familyFileValidated = file;
        $('family-import-btn').disabled = false;
      }
      status.textContent = (data.valid ? 'Planilha válida. ' : 'Corrija os problemas. ') +
        data.families + ' famílias; ' + data.adults + ' adultos; ' +
        data.children_0_5 + ' crianças de 0 a 5 anos; ' +
        data.children_6_12 + ' crianças de 6 a 12 anos. ' +
        'Somente prévia: nenhum cadastro ou link criado.';
      for (const message of data.errors) {
        const li = document.createElement('li');
        li.textContent = message;
        errors.append(li);
      }
      if (data.truncated_errors) {
        const li = document.createElement('li');
        li.textContent = 'Existem mais erros além dos exibidos.';
        errors.append(li);
      }
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else status.textContent = error.message;
    } finally { button.disabled = false; }
  }

  async function updateFamilySummary() {
    const generation = sessionGeneration;
    try {
      const data = await api('/api/admin/guest-list-summary');
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!Number.isInteger(data.families) || !Number.isInteger(data.pending)) {
        throw new Error('Resumo inválido.');
      }
      $('family-saved-summary').textContent =
        'Cadastro prévio: ' + data.families + ' famílias, ' + data.pending +
        ' pendentes de confirmação.';
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
    }
  }
  async function importFamilyFile() {
    const file = familyFileValidated;
    if (!file || $('family-file').files[0] !== file) {
      $('family-import-status').textContent = 'Valide novamente o arquivo antes de importar.';
      $('family-import-btn').disabled = true;
      return;
    }
    const generation = sessionGeneration;
    const button = $('family-import-btn');
    button.disabled = true;
    $('family-import-status').textContent = 'Gravando cadastro prévio...';
    try {
      const response = await fetch('/api/admin/guest-list-import', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {
          'Content-Type': /\.xlsx$/i.test(file.name)
            ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            : 'text/csv',
          'X-CSRF-Token': await ensureCsrf()
        },
        body: file
      });
      const data = await response.json().catch(() => ({}));
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!response.ok) {
        const error = new Error((data.error && data.error.message) || 'Não foi possível importar.');
        error.status = response.status;
        throw error;
      }
      if (!Number.isInteger(data.imported) || !Number.isInteger(data.existing_unchanged)) {
        throw new Error('Resposta de importação inválida.');
      }
      familyFileValidated = null;
      $('family-import-status').textContent =
        data.imported + ' famílias cadastradas; ' +
        data.existing_unchanged + ' já existentes, sem alterações. Nenhum convite enviado.';
      await updateFamilySummary();
      void loadInvitationRoster();
    } catch (error) {
      if (generation !== sessionGeneration) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('family-import-status').textContent = error.message;
    } finally { button.disabled = true; }
  }

  async function downloadInvitationLinks() {
    const generation = sessionGeneration;
    const button = $('download-invitation-links-btn');
    button.disabled = true;
    $('invitation-link-status').textContent = '';
    try {
      const response = await fetch('/api/admin/invitation-links.csv', {
        credentials: 'same-origin', cache: 'no-store'
      });
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const error = new Error((data.error && data.error.message) ||
          'Não foi possível gerar os links individuais.');
        error.status = response.status;
        throw error;
      }
      const blob = await response.blob();
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      const href = URL.createObjectURL(blob);
      try {
        const link = document.createElement('a');
        link.href = href;
        link.download = 'links-individuais-familias.csv';
        document.body.append(link);
        link.click();
        link.remove();
      } finally {
        URL.revokeObjectURL(href);
      }
      $('invitation-link-status').textContent =
        'Links exportados. Arquivo confidencial: envie cada endereço somente à família correta.';
    } catch (error) {
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('invitation-link-status').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  function validInvitationRoster(data) {
    if (!data || !Array.isArray(data.families) || !data.counts ||
        data.families.length > 10000) return false;
    const allowed = ['PENDENTE', 'CONFIRMADO', 'RECUSADO'];
    const seen = new Set();
    const counts = {
      total: data.families.length, pending: 0, confirmed: 0,
      declined: 0, sent: 0, not_sent: 0
    };
    for (const family of data.families) {
      if (!family || typeof family.id !== 'string' ||
          !/^[0-9a-f-]{36}$/i.test(family.id) || seen.has(family.id) ||
          typeof family.name !== 'string' || typeof family.key !== 'string' ||
          typeof family.phone !== 'string' || !allowed.includes(family.status) ||
          typeof family.sent !== 'boolean' ||
          (family.sent
            ? typeof family.sent_at_utc !== 'string' ||
              Number.isNaN(Date.parse(family.sent_at_utc))
            : family.sent_at_utc !== null) ||
          'token' in family || 'url' in family) return false;
      seen.add(family.id);
      if (family.status === 'PENDENTE') counts.pending += 1;
      if (family.status === 'CONFIRMADO') counts.confirmed += 1;
      if (family.status === 'RECUSADO') counts.declined += 1;
      if (family.sent) counts.sent += 1;
      else counts.not_sent += 1;
    }
    return Object.entries(counts).every(([key, value]) => data.counts[key] === value);
  }

  function whatsappNumber(raw) {
    // Brazilian national numbers (10/11 digits) receive country code +55.
    // International numbers must carry an explicit '+' to avoid a wrong recipient.
    if (!raw) return null;
    if (/^\+[1-9][0-9]{9,14}$/.test(raw)) return raw.slice(1);
    if (/^[1-9][0-9]{9,10}$/.test(raw)) return '55' + raw;
    if (/^55[1-9][0-9]{9,10}$/.test(raw)) return raw;
    return null;
  }

  function invitationUrlValid(value) {
    try {
      const parsed = new URL(value);
      return (['http:', 'https:'].includes(parsed.protocol) &&
              parsed.username === '' && parsed.password === '' &&
              parsed.pathname === '/convite' && parsed.search === '' &&
              /^#[0-9a-f-]{36}\.[0-9a-f]{64}$/i.test(parsed.hash));
    } catch (error) { return false; }
  }

  function invitationAction(family, host, mode) {
    const generation = sessionGeneration;
    const button = host.querySelector('button[data-action="' + mode + '"]');
    const status = host.querySelector('.invite-action-status');
    const linkArea = host.querySelector('.invite-link-area');
    button.disabled = true;
    status.textContent = 'Preparando link privado...';
    linkArea.replaceChildren();
    void (async () => {
      try {
        const data = await api('/api/admin/invitations/' +
          encodeURIComponent(family.id) + '/link');
        if (generation !== sessionGeneration || $('dashboard-panel').hidden ||
            !host.isConnected) return;
        if (!data || typeof data.url !== 'string' ||
            !invitationUrlValid(data.url)) {
          throw new Error('O servidor retornou um link inválido.');
        }
        if (mode === 'copy') {
          try {
            await navigator.clipboard.writeText(data.url);
            if (generation !== sessionGeneration || !host.isConnected) return;
            status.textContent = 'Link individual copiado. Compartilhe somente com esta família.';
          } catch (error) {
            if (generation !== sessionGeneration || !host.isConnected) return;
            const input = document.createElement('input');
            input.readOnly = true;
            input.value = data.url;
            input.setAttribute('aria-label', 'Link privado para cópia manual');
            linkArea.append(input);
            input.focus();
            input.select();
            status.textContent = 'Copie o link selecionado manualmente. Mantenha-o privado.';
          }
        } else {
          const phone = whatsappNumber(family.phone);
          if (!phone) throw new Error('Telefone ausente ou sem formato seguro. Copie o link e confira o contato.');
          if (!data.url.startsWith('https://')) {
            throw new Error('WhatsApp exige URL pública HTTPS homologada. Use cópia local apenas para testes.');
          }
          const message = 'Olá, ' + family.name + '! 🌼 Temos um convite especial para a festa da Isadora. ' +
            'Confirme a presença da sua família neste link individual: ' + data.url;
          const anchor = document.createElement('a');
          anchor.href = 'https://wa.me/' + phone + '?text=' + encodeURIComponent(message);
          anchor.target = '_blank';
          anchor.rel = 'noopener noreferrer';
          anchor.textContent = 'Abrir conversa no WhatsApp';
          linkArea.append(anchor);
          status.textContent = 'Confira o destinatário e clique no link para abrir a conversa. Nenhuma mensagem foi enviada.';
        }
      } catch (error) {
        if (generation !== sessionGeneration || !host.isConnected) return;
        if (error.status === 401 || error.status === 403) expireOrganizerSession();
        else status.textContent = error.message;
      } finally {
        if (generation === sessionGeneration && host.isConnected) button.disabled = false;
      }
    })();
  }

  async function setManualDispatch(family, host, sent) {
    if ($('dashboard-panel').hidden || !host.isConnected) return;
    const generation = sessionGeneration;
    const button = host.querySelector('button[data-action="dispatch"]');
    const status = host.querySelector('.invite-action-status');
    if (!button) return;
    button.disabled = true;
    status.textContent = sent
      ? 'Registrando declaração manual de envio...'
      : 'Desfazendo registro manual de envio...';
    try {
      const data = await api('/api/admin/invitations/' +
        encodeURIComponent(family.id) + '/sent', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': await ensureCsrf()
          },
          body: JSON.stringify({sent})
        });
      if (generation !== sessionGeneration || $('dashboard-panel').hidden ||
          !host.isConnected) return;
      if (!data || typeof data.sent !== 'boolean' || data.sent !== sent ||
          (sent ? typeof data.sent_at_utc !== 'string' : data.sent_at_utc !== null)) {
        throw new Error('Registro de envio não confirmado pelo servidor.');
      }
      // Leave RSVP status unchanged and refresh manual sending counters.
      family.sent = data.sent;
      family.sent_at_utc = data.sent_at_utc;
      const sentCount = invitedFamilies.filter((item) => item.sent).length;
      document.querySelector('[data-testid="invite-sent"]').textContent =
        String(sentCount);
      document.querySelector('[data-testid="invite-not-sent"]').textContent =
        String(invitedFamilies.length - sentCount);
      renderInvitationRoster();
      $('invite-status').textContent = sent
        ? 'Envio registrado manualmente. Isso não comprova entrega ou leitura.'
        : 'Registro manual de envio desfeito. A confirmação de presença não foi alterada.';
    } catch (error) {
      if (generation !== sessionGeneration || $('dashboard-panel').hidden ||
          !host.isConnected) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else status.textContent = error.message;
    } finally {
      if (generation === sessionGeneration && host.isConnected) button.disabled = false;
    }
  }

  function renderInvitationRoster() {
    const list = $('invite-list');
    list.replaceChildren();
    const term = fold($('invite-search').value.trim());
    const selected = $('invite-status-filter').value;
    const sentFilter = $('invite-sent-filter').value;
    const matching = invitedFamilies.filter((f) =>
      (selected === 'TODOS' || f.status === selected) &&
      (sentFilter === 'TODOS' ||
       (sentFilter === 'ENVIADO' && f.sent) ||
       (sentFilter === 'NAO_ENVIADO' && !f.sent)) &&
      (fold(f.name).includes(term) || fold(f.key).includes(term) ||
       f.phone.includes(term)));
    const statusNames = {
      PENDENTE: 'Aguardando resposta',
      CONFIRMADO: 'Confirmado',
      RECUSADO: 'Recusado'
    };
    for (const family of matching) {
      const li = document.createElement('li');
      const title = document.createElement('strong');
      title.textContent = family.name;
      const details = document.createElement('p');
      details.className = 'muted';
      details.textContent = 'Código: ' + family.key +
        ' · ' + statusNames[family.status] +
        ' · Telefone: ' + (family.phone || 'Não informado') +
        ' · ' + (family.sent ? 'Envio registrado manualmente em ' +
          new Intl.DateTimeFormat('pt-BR', {
            timeZone: 'America/Sao_Paulo',
            dateStyle: 'short', timeStyle: 'short'
          }).format(new Date(family.sent_at_utc)) : 'Envio não registrado');
      const controls = document.createElement('div');
      controls.className = 'admin-actions';
      for (const [mode, label] of [['copy', 'Copiar link'], ['whatsapp', 'Preparar WhatsApp']]) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'secondary';
        button.dataset.action = mode;
        button.textContent = label;
        button.addEventListener('click', () => invitationAction(family, li, mode));
        controls.append(button);
      }
      const manual = document.createElement('button');
      manual.type = 'button';
      manual.className = 'secondary';
      manual.dataset.action = 'dispatch';
      manual.textContent = family.sent
        ? 'Desfazer envio registrado'
        : 'Marcar como enviado manualmente';
      manual.addEventListener('click', () =>
        setManualDispatch(family, li, !family.sent));
      controls.append(manual);
      const actionStatus = document.createElement('p');
      actionStatus.className = 'invite-action-status muted';
      actionStatus.setAttribute('role', 'status');
      const links = document.createElement('div');
      links.className = 'invite-link-area';
      li.append(title, details, controls, actionStatus, links);
      list.append(li);
    }
    if (!matching.length) putEmpty('invite-list');
    $('invite-status').textContent = 'Exibindo ' + matching.length + ' de ' +
      invitedFamilies.length + ' famílias. Somente ações individuais disponibilizam links.';
  }

  async function loadInvitationRoster() {
    if ($('dashboard-panel').hidden || inviteLoadPending) return;
    const generation = sessionGeneration;
    inviteLoadPending = true;
    $('invite-refresh-btn').disabled = true;
    try {
      const data = await api('/api/admin/invitations');
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!validInvitationRoster(data)) throw new Error('Lista de convites inválida.');
      invitedFamilies = data.families;
      for (const name of ['total', 'pending', 'confirmed', 'declined', 'sent', 'not-sent']) {
        document.querySelector('[data-testid="invite-' + name + '"]').textContent =
          String(data.counts[name === 'not-sent' ? 'not_sent' : name]);
      }
      renderInvitationRoster();
    } catch (error) {
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('invite-status').textContent = error.message;
    } finally {
      if (generation === sessionGeneration) {
        inviteLoadPending = false;
        $('invite-refresh-btn').disabled = false;
      }
    }
  }

  async function loadActivity() {
    if ($('dashboard-panel').hidden) return;
    const generation = sessionGeneration;
    const button = $('load-activity-btn');
    button.disabled = true;
    $('activity-status').textContent = 'Consultando movimentações...';
    try {
      const response = await api('/api/admin/activity');
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (!response || !Array.isArray(response.events) || response.events.length > 50 ||
          response.events.some((item) => !item || typeof item.kind !== 'string' ||
            typeof item.occurred_at_utc !== 'string')) {
        throw new Error('Histórico inválido recebido do servidor.');
      }
      const labels = {
        RSVP_CREATED: 'Confirmação recebida',
        RSVP_DECLINED: 'Recusa recebida',
        RSVP_UPDATED: 'Confirmação alterada',
        SETTINGS_CHANGED: 'Configuração da festa alterada',
        INVITATION_SENT_MARKED: 'Envio de convite registrado manualmente',
        INVITATION_SENT_UNMARKED: 'Registro manual de envio desfeito'
      };
      const entries = [];
      for (const entry of response.events) {
        const time = new Date(entry.occurred_at_utc);
        if (!Object.hasOwn(labels, entry.kind) || Number.isNaN(time.getTime())) {
          throw new Error('Histórico inválido recebido do servidor.');
        }
        const li = document.createElement('li');
        li.textContent = labels[entry.kind] + ' — ' +
          new Intl.DateTimeFormat('pt-BR', {
            timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short'
          }).format(time);
        entries.push(li);
      }
      $('activity-list').replaceChildren(...entries);
      if (!entries.length) putEmpty('activity-list');
      $('activity-status').textContent = 'Histórico atualizado. Não são exibidos dados pessoais.';
    } catch (error) {
      if (generation !== sessionGeneration || $('dashboard-panel').hidden) return;
      if (error.status === 401 || error.status === 403) expireOrganizerSession();
      else $('activity-status').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  function printGuestList() {
    if (!dashboardData || $('dashboard-panel').hidden) return;
    window.print();
  }

  async function logOut() {
    // Hide and clear names immediately, including if the network or session has failed.
    const token = csrfToken;
    clearPrivateDashboard();
    $('login-btn').disabled = true;
    try {
      if (!token) throw new Error('Token de saída indisponível.');
      await api('/api/auth/logout', {method:'POST',headers:{'X-CSRF-Token':token}});
    } catch (error) {
      setError('Não foi possível confirmar a saída no servidor. Feche esta aba e entre novamente.');
    } finally {
      $('login-btn').disabled = false;
    }
  }
  $('invite-refresh-btn').addEventListener('click', loadInvitationRoster);
  $('invite-search').addEventListener('input', renderInvitationRoster);
  $('invite-status-filter').addEventListener('change', renderInvitationRoster);
  $('invite-sent-filter').addEventListener('change', renderInvitationRoster);
  $('family-template-btn').addEventListener('click', () => downloadFamilyTemplate('csv'));
  $('family-template-xlsx-btn').addEventListener('click', () => downloadFamilyTemplate('xlsx'));
  $('family-preview-btn').addEventListener('click', validateFamilyFile);
  $('family-import-btn').addEventListener('click', importFamilyFile);
  $('download-invitation-links-btn').addEventListener('click', downloadInvitationLinks);
  $('family-file').addEventListener('change', () => {
    familyFileValidated = null;
    $('family-import-btn').disabled = true;
    $('family-preview-status').textContent = 'Arquivo alterado. Valide antes de cadastrar.';
  });
  $('login-form').addEventListener('submit', logIn);
  $('settings-form').addEventListener('submit', saveSettings);
  $('logout-btn').addEventListener('click', logOut);
  $('export-csv-btn').addEventListener('click', exportCsv);
  $('export-planning-btn').addEventListener('click', exportPlanning);
  $('load-activity-btn').addEventListener('click', loadActivity);
  $('print-list-btn').addEventListener('click', printGuestList);
  $('refresh-dashboard-btn').addEventListener('click', refreshDashboard);
  $('refresh-interval').addEventListener('change', () => {
    configureRefreshTimer();
    $('refresh-status').textContent = $('refresh-interval').value === '0'
      ? 'Atualização manual selecionada.'
      : 'Atualização automática a cada ' + $('refresh-interval').value + ' segundos.';
  });
  $('guest-search').addEventListener('input', () => {
    if (dashboardData) renderGuestLists(dashboardData);
  });
  $('clear-search').addEventListener('click', () => {
    $('guest-search').value = '';
    if (dashboardData) renderGuestLists(dashboardData);
    $('guest-search').focus();
  });
  ensureCsrf().then(loadDashboard).catch(() => {
    $('login-panel').hidden = false;
    $('dashboard-panel').hidden = true;
  });
})();
