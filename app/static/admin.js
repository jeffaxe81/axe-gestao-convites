(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  if (!$('login-form')) return;
  let csrfToken = null;
  let csrfPending = null;
  let dashboardData = null;
  let sessionGeneration = 0;
  let refreshPending = false;
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

  async function downloadFamilyTemplate() {
    const generation = sessionGeneration;
    const status = $('family-preview-status');
    status.textContent = '';
    try {
      const response = await fetch('/api/admin/guest-list-template.csv', {
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
        link.download = 'modelo-familias.csv';
        document.body.append(link);
        link.click();
        link.remove();
      } finally {
        URL.revokeObjectURL(href);
      }
      status.textContent = 'Modelo baixado com dados fictícios. Preencha em Excel ou CSV.';
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
        SETTINGS_CHANGED: 'Configuração da festa alterada'
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
  $('family-template-btn').addEventListener('click', downloadFamilyTemplate);
  $('family-preview-btn').addEventListener('click', validateFamilyFile);
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
