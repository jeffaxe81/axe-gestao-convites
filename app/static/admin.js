(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  if (!$('login-form')) return;
  let csrfToken = null;

  function setError(message) {
    $('login-error').textContent = message;
    $('login-error').hidden = false;
  }
  async function api(path, options) {
    const request = Object.assign({credentials: 'same-origin', cache: 'no-store'}, options || {});
    const response = await fetch(path, request);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error((data.error && data.error.message) || 'Não foi possível concluir.');
    }
    return data;
  }
  async function ensureCsrf() {
    if (!csrfToken) csrfToken = (await api('/api/auth/csrf')).csrf_token;
    return csrfToken;
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
  function drawDashboard(data) {
    const counts = data.counts;
    document.querySelector('[data-testid=total-count]').textContent = String(counts.total);
    document.querySelector('[data-testid=buffet-count]').textContent = String(counts.buffet);
    document.querySelector('[data-testid=young-count]').textContent = String(counts.children_0_5);
    document.querySelector('[data-testid=souvenir-count]').textContent = String(counts.children_0_12);
    document.querySelector('[data-testid=over-count]').textContent = String(counts.over_12);
    $('buffet-alert').hidden = !data.buffet_limit_reached;
    if (data.buffet_limit_reached) {
      $('buffet-alert').textContent = 'Atenção: contagem do buffet alcançou o limite interno de ' + data.buffet_limit + '.';
    }
    clearList('confirmed-list'); clearList('declined-list'); clearList('souvenir-list');
    data.confirmed.forEach((family) => appendFamily('confirmed-list', family));
    data.declined.forEach((family) => appendFamily('declined-list', family));
    data.souvenir_children.forEach((child) => {
      const li = document.createElement('li');
      li.textContent = child.name + ' — ' + child.age_years + ' ano(s)';
      $('souvenir-list').append(li);
    });
    if (!data.confirmed.length) putEmpty('confirmed-list');
    if (!data.declined.length) putEmpty('declined-list');
    if (!data.souvenir_children.length) putEmpty('souvenir-list');
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
    const data = await api('/api/admin/dashboard');
    const settings = await api('/api/admin/settings');
    $('login-panel').hidden = true;
    $('dashboard-panel').hidden = false;
    drawDashboard(data);
    $('venue-input').value = settings.venue || '';
    $('deadline-input').value = eventTime(settings.edit_deadline_utc);
  }
  async function logIn(event) {
    event.preventDefault();
    $('login-error').hidden = true;
    $('login-btn').disabled = true;
    try {
      const token = await ensureCsrf();
      const result = await api('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'X-CSRF-Token':token},
        body: JSON.stringify({
          username: $('admin-username').value,
          password: $('admin-password').value
        })
      });
      csrfToken = result.csrf_token;
      $('admin-password').value = '';
      await loadDashboard();
    } catch (error) { setError(error.message); }
    finally { $('login-btn').disabled = false; }
  }
  async function saveSettings(event) {
    event.preventDefault();
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
      $('settings-status').textContent = 'Configuração salva com sucesso.';
    } catch (error) { $('settings-status').textContent = error.message; }
    finally { $('save-settings').disabled = false; }
  }
  async function exportCsv() {
    const button = $('export-csv-btn');
    button.disabled = true;
    $('export-status').textContent = '';
    try {
      const response = await fetch('/api/admin/export.csv', {
        credentials: 'same-origin', cache: 'no-store'
      });
      if (!response.ok) throw new Error('Não foi possível exportar. Entre novamente no painel.');
      const csvBlob = await response.blob();
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
      $('export-status').textContent = 'Relatório preparado para download. Mantenha o arquivo em local privado.';
    } catch (error) {
      $('export-status').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }
  async function logOut() {
    try {
      await api('/api/auth/logout', {method:'POST',headers:{'X-CSRF-Token':await ensureCsrf()}});
      csrfToken = null;
      $('dashboard-panel').hidden = true;
      $('login-panel').hidden = false;
      ['confirmed-list','declined-list','souvenir-list'].forEach(clearList);
      $('export-status').textContent = '';
      $('venue-input').value = ''; $('deadline-input').value = '';
    } catch (error) { $('settings-status').textContent = error.message; }
  }
  $('login-form').addEventListener('submit', logIn);
  $('settings-form').addEventListener('submit', saveSettings);
  $('logout-btn').addEventListener('click', logOut);
  $('export-csv-btn').addEventListener('click', exportCsv);
  ensureCsrf().then(loadDashboard).catch(() => {
    $('login-panel').hidden = false;
    $('dashboard-panel').hidden = true;
  });
})();
