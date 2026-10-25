(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const form = $('rsvp-form');
  let rowNumber = 0;
  let pendingPayload = null;
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
      const lines = [pendingPayload.attending ? 'Vou comparecer (simulação)' : 'Não poderei comparecer',
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

  function submit() {
    clearError();
    form.hidden = true;
    $('review').hidden = true;
    $('success').hidden = false;
    $('success-message').textContent = pendingPayload.attending
      ? 'Assim seria o agradecimento pela sua presença. Sua resposta não foi enviada nem registrada.'
      : 'Assim seria o agradecimento por avisar que não poderá ir. Sua resposta não foi enviada nem registrada.';
    $('success').scrollIntoView({behavior: 'smooth', block: 'start'});
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
  $('preview-reset').addEventListener('click', () => window.location.reload());
  addRow(true);
  toggleAttendance();
})();
