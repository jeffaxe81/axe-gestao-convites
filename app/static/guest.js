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
  const invited = window.location.pathname === '/convite';
  let invitationId = null;
  let invitationToken = null;

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
  function setStage(step) {
    const labels = {1: 'Sua resposta', 2: 'Revisão', 3: 'Confirmação registrada'};
    $('stage-indicator').textContent = 'Etapa ' + step + ' de 3 — ' + labels[step];
  }
  function updateParticipantCount() {
    const count = $('participants').querySelectorAll('.person-row').length;
    $('participant-count').textContent = count + (count === 1 ? ' participante informado' : ' participantes informados') + ' (máximo 100).';
    $('add-companion').disabled = count >= 100;
  }
  function updateConnectionStatus() {
    const offline = !navigator.onLine;
    $('connection-status').hidden = !offline;
    $('connection-status').textContent = offline
      ? 'Você está sem conexão. Não envie a resposta até a internet voltar.'
      : '';
  }
  function setEventDisplay(event) {
    const date = new Date(event.starts_at);
    if (!Number.isFinite(date.getTime())) return;
    const localDate = new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo', weekday: 'long', day: 'numeric',
      month: 'long', year: 'numeric'
    }).format(date);
    const localTime = new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit',
      hourCycle: 'h23'
    }).format(date);
    $('event-date').textContent = localDate + ', às ' + localTime;
    const remaining = date.getTime() - Date.now();
    if (remaining <= 0) {
      $('event-countdown').textContent = 'A data da festa já chegou!';
    } else {
      const days = Math.ceil(remaining / 86400000);
      $('event-countdown').textContent = days === 1
        ? 'Falta até 1 dia para a festa! 🌼'
        : 'Faltam ' + days + ' dias para a festa! 🌼';
    }
    $('event-countdown').hidden = false;
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
      remove.addEventListener('click', () => { row.remove(); updateParticipantCount(); });
      row.append(remove);
    }
    $('participants').append(row);
    updateParticipantCount();
  }
  function attending() {
    return form.querySelector('input[name="attendance"]:checked').value === 'yes';
  }
  function toggleAttendance() {
    $('attendance-details').hidden = !attending();
    updateParticipantCount();
  }
  function buildPayload() {
    const name = $('contact-name').value.trim().replace(/\s+/g, ' ');
    if (!name || name.length > 160) {
      $('contact-name').focus();
      throw new Error('Informe seu nome para continuar.');
    }
    const people = [];
    if (attending()) {
      for (const row of $('participants').querySelectorAll('.person-row')) {
        const primary = row.dataset.primary === 'yes';
        const nameField = row.querySelector('.person-name');
        const personName = primary ? name : (nameField ? nameField.value.trim().replace(/\s+/g, ' ') : '');
        if (!personName || personName.length > 160) {
          if (nameField) nameField.focus();
          throw new Error('Informe o nome de cada acompanhante.');
        }
        const kind = row.querySelector('.person-kind').value;
        let age = null;
        if (kind === 'CHILD') {
          const raw = row.querySelector('.person-age').value.trim();
          age = Number(raw);
          if (raw === '' || !Number.isInteger(age) || age < 0 || age > 12) {
            row.querySelector('.person-age').focus();
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
      setStage(2);
      $('review').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) { fail(error.message); }
  }
  function renderSuccess(result) {
    confirmation = result;
    form.hidden = true;
    $('review').hidden = true;
    $('success').hidden = false;
    setStage(3);
    $('success-message').textContent = result.attending
      ? 'Sua presença foi registrada com carinho. Esperamos você!'
      : 'Recebemos sua resposta. Obrigado por nos avisar!';
    familyId = result.id; editToken = result.edit_token; revision = result.revision;
    $('edit-link').value = window.location.origin + '/editar#' + familyId + '.' + editToken;
    $('success').scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function requestJson(url, options) {
    // Um proxy ou celular com sinal instável pode manter uma requisição pendente
    // indefinidamente. O aborto libera o botão, sem apagar revisão ou chave
    // de idempotência. A operação pode ter sido salva pelo servidor; repetir
    // a MESMA requisição continua seguro.
    const controller = new AbortController();
    const deadline = window.setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {...(options || {}), signal: controller.signal});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 409) {
          throw new Error(invited && !editing
            ? 'Este convite já tem uma resposta diferente. Abra seu link de edição para alterá-la.'
            : 'Sua resposta foi atualizada em outra aba. Copie seus dados e recarregue a página.');
        }
        if (response.status === 403) {
          if (data.error && data.error.code === 'INVITATION_REQUIRED') {
            throw new Error('Para confirmar presença, abra o link individual enviado à sua família.');
          }
          if (data.error && data.error.code === 'EDIT_CLOSED') {
            throw new Error('O prazo para editar esta resposta terminou.');
          }
          throw new Error('A solicitação não foi autorizada. Verifique seu link de convite.');
        }
        throw new Error((data.error && data.error.message) || 'Não foi possível concluir. Tente novamente.');
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('A conexão demorou a responder. Seus dados foram mantidos. Tente enviar novamente sem alterá-los.');
      }
      throw error;
    } finally {
      window.clearTimeout(deadline);
    }
  }
  function validateReceipt(result, expected) {
    // HTTP 200 alone is not evidence of a confirmed response. A broken
    // intermediary can return HTML, an empty object or stale JSON.
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const token = /^[0-9a-f]{64}$/i;
    if (!result || typeof result !== 'object' ||
        !uuid.test(result.id || '') ||
        !Number.isSafeInteger(result.revision) || result.revision < 1 ||
        !token.test(result.edit_token || '') ||
        typeof result.attending !== 'boolean' ||
        result.attending !== expected.attending ||
        (editing && (result.id !== familyId || result.edit_token !== editToken ||
                     result.revision !== revision + 1))) {
      throw new Error('Não foi possível verificar a confirmação. Tente novamente sem alterar os dados.');
    }
    return result;
  }
  async function submit() {
    clearError();
    $('submit-btn').disabled = true;
    $('submit-btn').textContent = 'Enviando...';
    try {
      if (!navigator.onLine) throw new Error('Sem conexão com a internet. Reconecte e tente enviar novamente.');
      let result;
      if (editing) {
        result = validateReceipt(await requestJson('/api/rsvps/' + encodeURIComponent(familyId), {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + editToken},
          body: JSON.stringify(Object.assign({revision: revision}, pendingPayload))
        }), pendingPayload);
      } else if (invited) {
        result = validateReceipt(await requestJson(
          '/api/invitations/' + encodeURIComponent(invitationId) + '/response', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + invitationToken
            },
            body: JSON.stringify(pendingPayload)
          }), pendingPayload);
      } else {
        if (!submissionKey) {
          submissionKey = crypto.randomUUID();
          sessionStorage.setItem('isadora_submission_key', submissionKey);
        }
        result = validateReceipt(await requestJson('/api/rsvps', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Idempotency-Key': submissionKey},
          body: JSON.stringify(pendingPayload)
        }), pendingPayload);
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
    updateConnectionStatus();
    $('loading').hidden = !(editing || invited);
    try {
      const event = await requestJson('/api/event');
      $('event-venue').textContent = event.venue;
      setEventDisplay(event);
      if (editing) {
        const match = /^#([0-9a-f-]{36})\.([0-9a-f]{64})$/i.exec(window.location.hash);
        if (!match) throw new Error('Link de edição inválido. Abra o link completo que você recebeu.');
        familyId = match[1]; editToken = match[2];
        $('form-title').textContent = 'Atualizar minha resposta';
        const own = await requestJson('/api/rsvps/' + encodeURIComponent(familyId), {
          headers: {'Authorization': 'Bearer ' + editToken}
        });
        hydrateFamily(own);
      } else if (invited) {
        const parts = window.location.hash.slice(1).split('.');
        if (parts.length !== 2 || !/^[0-9a-f-]{36}$/i.test(parts[0]) ||
            !/^[0-9a-f]{64}$/i.test(parts[1])) {
          throw new Error('Link individual inválido. Abra o link completo recebido.');
        }
        invitationId = parts[0]; invitationToken = parts[1];
        const own = await requestJson('/api/invitations/' +
          encodeURIComponent(invitationId), {
            headers: {'Authorization': 'Bearer ' + invitationToken}
          });
        if (!own || typeof own.contact_name !== 'string' || !own.contact_name.trim() ||
            !Number.isInteger(own.adults) || !Number.isInteger(own.children_0_5) ||
            !Number.isInteger(own.children_6_12) ||
            typeof own.responded !== 'boolean') {
          throw new Error('Não foi possível verificar os dados do convite.');
        }
        $('invitation-interest').hidden = false;
        if (own.interested === true) {
          $('interest-btn').disabled = true;
          $('interest-btn').textContent = '💛 Interesse registrado';
          $('interest-status').textContent = 'Obrigado pelo carinho!';
        }
        $('form-title').textContent = 'Confirme o convite da sua família';
        $('contact-name').value = own.contact_name;
        $('invitation-plan').textContent = 'Pessoas previstas no convite: ' +
          own.adults + ' acima de 12 anos, ' + own.children_0_5 +
          ' crianças até 5 anos e ' + own.children_6_12 +
          ' crianças de 6 a 12 anos. Informe os nomes de quem realmente irá.';
        $('invitation-plan').hidden = false;
        if (own.responded) {
          if (!own.receipt || typeof own.receipt.attending !== 'boolean') {
            throw new Error('Não foi possível recuperar sua confirmação.');
          }
          renderSuccess(own.receipt);
        }
      }
    } catch (error) { fail(error.message); if (editing || invited) $('rsvp-form').hidden = true; }
    finally { $('loading').hidden = true; }
  }
  form.querySelectorAll('input[name="attendance"]').forEach((radio) =>
    radio.addEventListener('change', toggleAttendance));
  $('add-companion').addEventListener('click', () => {
    if ($('participants').children.length >= 100) return fail('O limite é de 100 pessoas por resposta.');
    addRow(false);
  });
  $('interest-btn').addEventListener('click', async () => {
    if (!invited || !invitationId || !invitationToken) return;
    const button = $('interest-btn');
    button.disabled = true;
    try {
      const result = await requestJson('/api/invitations/' +
        encodeURIComponent(invitationId) + '/interest', {
          method: 'POST',
          headers: {'Authorization': 'Bearer ' + invitationToken}
        });
      if (result.interested !== true) throw new Error('Não foi possível confirmar o registro.');
      button.textContent = '💛 Interesse registrado';
      $('interest-status').textContent = 'Obrigado! Seu interesse foi registrado, sem confirmar presença.';
    } catch (error) {
      $('interest-status').textContent = error.message;
      button.disabled = false;
    }
  });
  $('review-btn').addEventListener('click', showReview);
  function backToForm() {
    $('review').hidden = true;
    form.hidden = false;
    setStage(1);
    $('review-btn').focus();
  }
  $('back-btn').addEventListener('click', backToForm);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !$('review').hidden) backToForm();
  });
  $('submit-btn').addEventListener('click', submit);
  window.addEventListener('online', updateConnectionStatus);
  window.addEventListener('offline', updateConnectionStatus);
  $('copy-link').addEventListener('click', async () => {
    const link = $('edit-link').value;
    try {
      await navigator.clipboard.writeText(link);
      $('copy-link').textContent = 'Link copiado!';
      $('copy-status').textContent = 'Link copiado. Guarde-o em local privado.';
    } catch (error) {
      $('edit-link').focus();
      $('edit-link').select();
      $('copy-status').textContent = 'Selecione e copie o link acima. Não o publique em grupos.';
    }
  });
  start();
})();
