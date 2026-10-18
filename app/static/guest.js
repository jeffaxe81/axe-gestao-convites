(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const form = $('rsvp-form');
  if (!form) return;

  let rowNumber = 0;
  let confirmation = null;
  let pendingPayload = null;
  let familyId = null;
  let editToken = null;
  let revision = null;
  let submissionKey = sessionStorage.getItem('isadora_submission_key');
  const editing = window.location.pathname === '/editar';

  function fail(message) {
    $('error').textContent = message;
    $('error').hidden = false;
    $('error').scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
  function clearError() { $('error').hidden = true; $('error').textContent = ''; }
  function item(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }
  function field(labelText, input, className) {
    const holder = item('div', undefined, 'field' + (className ? ' ' + className : ''));
    const label = item('label', labelText);
    input.id = 'field-' + (++rowNumber);
    label.htmlFor = input.id;
    holder.append(label, input);
    return holder;
  }
  function addRow(primary, person) {
    const row = item('div', undefined, 'person-row');
    row.dataset.primary = primary ? 'yes' : 'no';
    row.append(item('strong', primary ? 'Sobre você' : 'Acompanhante'));
    const rowFields = item('div', undefined, 'row-fields');
    if (!primary) {
      const name = item('input');
      name.type = 'text';
      name.maxLength = 160;
      name.autocomplete = 'off';
      name.placeholder = 'Nome do acompanhante';
      name.className = 'person-name';
      name.value = person ? person.name : '';
      rowFields.append(field('Nome', name));
    }
    const kind = item('select');
    kind.className = 'person-kind';
    const older = item('option', 'Acima de 12 anos');
    older.value = 'OVER_12';
    const child = item('option', 'Criança de 0 a 12 anos');
    child.value = 'CHILD';
    kind.append(older, child);
    kind.value = person ? person.kind : 'OVER_12';
    rowFields.append(field('Faixa etária', kind));
    row.append(rowFields);

    const age = item('input');
    age.type = 'number';
    age.min = '0'; age.max = '12'; age.step = '1';
    age.inputMode = 'numeric';
    age.className = 'person-age';
    age.placeholder = 'Anos completos';
    age.value = person && person.age_years !== null ? String(person.age_years) : '';
    const ageField = field('Idade na data da festa', age, 'age-field');
    row.append(ageField);
    const refreshAge = () => { ageField.hidden = kind.value !== 'CHILD'; };
    kind.addEventListener('change', refreshAge);
    refreshAge();
    if (!primary) {
      const remove = item('button', 'Remover acompanhante', 'remove');
      remove.type = 'button';
      remove.addEventListener('click', () => row.remove());
      row.append(remove);
    }
    $('participants').append(row);
  }
  function attending() {
    return form.querySelector('input[name="attendance"]:checked').value === 'yes';
  }
  function toggleAttendance() { $('attendance-details').hidden = !attending(); }
  function buildPayload() {
    const name = $('contact-name').value.trim().replace(/\s+/g, ' ');
    if (!name || name.length > 160) throw new Error('Informe seu nome para continuar.');
    const people = [];
    if (attending()) {
      for (const row of $('participants').querySelectorAll('.person-row')) {
        const primary = row.dataset.primary === 'yes';
        const nameField = row.querySelector('.person-name');
        const personName = primary ? name : (nameField ? nameField.value.trim().replace(/\s+/g, ' ') : '');
        if (!personName || personName.length > 160) throw new Error('Informe o nome de cada acompanhante.');
        const kind = row.querySelector('.person-kind').value;
        let age = null;
        if (kind === 'CHILD') {
          const raw = row.querySelector('.person-age').value.trim();
          age = Number(raw);
          if (raw === '' || !Number.isInteger(age) || age < 0 || age > 12) {
            throw new Error('Informe uma idade inteira de 0 a 12 anos para cada criança.');
          }
        }
        people.push({name: personName, kind: kind, age_years: age});
      }
    }
    return {contact_name: name, attending: attending(), participants: people};
  }
  function showReview() {
    clearError();
    try {
      pendingPayload = buildPayload();
      const lines = [pendingPayload.attending ? 'Presença confirmada' : 'Não poderei comparecer',
        'Nome: ' + pendingPayload.contact_name];
      if (pendingPayload.attending) {
        lines.push('Participantes:');
        pendingPayload.participants.forEach((p) => {
          lines.push('• ' + p.name + (p.kind === 'CHILD' ? ' — ' + p.age_years + ' ano(s)' : ' — acima de 12 anos'));
        });
      }
      $('review-data').textContent = lines.join('\n');
      form.hidden = true;
      $('review').hidden = false;
      $('review').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) { fail(error.message); }
  }
  function renderSuccess(result) {
    confirmation = result;
    form.hidden = true;
    $('review').hidden = true;
    $('success').hidden = false;
    $('success-message').textContent = result.attending
      ? 'Sua presença foi registrada com carinho. Esperamos você!'
      : 'Recebemos sua resposta. Obrigado por nos avisar!';
    familyId = result.id; editToken = result.edit_token; revision = result.revision;
    $('edit-link').value = window.location.origin + '/editar#' + familyId + '.' + editToken;
    $('success').scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function requestJson(url, options) {
    const response = await fetch(url, options || {});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 409) throw new Error('Sua resposta foi atualizada em outra aba. Copie seus dados e recarregue a página.');
      if (response.status === 403) throw new Error('O prazo para editar esta resposta terminou.');
      throw new Error((data.error && data.error.message) || 'Não foi possível concluir. Tente novamente.');
    }
    return data;
  }
  async function submit() {
    clearError();
    $('submit-btn').disabled = true;
    $('submit-btn').textContent = 'Enviando...';
    try {
      let result;
      if (editing) {
        result = await requestJson('/api/rsvps/' + encodeURIComponent(familyId), {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + editToken},
          body: JSON.stringify(Object.assign({revision: revision}, pendingPayload))
        });
      } else {
        if (!submissionKey) {
          submissionKey = crypto.randomUUID();
          sessionStorage.setItem('isadora_submission_key', submissionKey);
        }
        result = await requestJson('/api/rsvps', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Idempotency-Key': submissionKey},
          body: JSON.stringify(pendingPayload)
        });
        sessionStorage.removeItem('isadora_submission_key');
      }
      renderSuccess(result);
    } catch (error) { fail(error.message); }
    finally {
      $('submit-btn').disabled = false;
      $('submit-btn').textContent = 'Enviar confirmação';
    }
  }
  function hydrateFamily(own) {
    $('contact-name').value = own.contact_name;
    form.querySelector('input[name="attendance"][value="' + (own.attending ? 'yes' : 'no') + '"]').checked = true;
    toggleAttendance();
    $('participants').replaceChildren();
    if (own.attending) own.participants.forEach((p, i) => addRow(i === 0, p));
    else addRow(true);
    revision = own.revision;
    if (!own.can_edit) {
      $('review-btn').disabled = true;
      fail('O prazo de edição desta resposta foi encerrado.');
    }
  }
  async function start() {
    addRow(true);
    toggleAttendance();
    try {
      const event = await requestJson('/api/event');
      $('event-venue').textContent = event.venue;
      if (editing) {
        const match = /^#([0-9a-f-]{36})\.([0-9a-f]{64})$/i.exec(window.location.hash);
        if (!match) throw new Error('Link de edição inválido. Abra o link completo que você recebeu.');
        familyId = match[1]; editToken = match[2];
        $('form-title').textContent = 'Atualizar minha resposta';
        const own = await requestJson('/api/rsvps/' + encodeURIComponent(familyId), {
          headers: {'Authorization': 'Bearer ' + editToken}
        });
        hydrateFamily(own);
      }
    } catch (error) { fail(error.message); if (editing) $('rsvp-form').hidden = true; }
  }
  form.querySelectorAll('input[name="attendance"]').forEach((radio) =>
    radio.addEventListener('change', toggleAttendance));
  $('add-companion').addEventListener('click', () => {
    if ($('participants').children.length >= 100) return fail('O limite é de 100 pessoas por resposta.');
    addRow(false);
  });
  $('review-btn').addEventListener('click', showReview);
  $('back-btn').addEventListener('click', () => { $('review').hidden = true; form.hidden = false; });
  $('submit-btn').addEventListener('click', submit);
  $('copy-link').addEventListener('click', async () => {
    const link = $('edit-link').value;
    try { await navigator.clipboard.writeText(link); $('copy-link').textContent = 'Link copiado!'; }
    catch (error) { $('edit-link').focus(); $('edit-link').select(); }
  });
  start();
})();
