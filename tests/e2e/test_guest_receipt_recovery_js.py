"""Exercise guest.js receipt recovery without browser executables.

This small DOM double checks the real startup code's visible error/success state;
it is not a substitute for the mobile Playwright tests in this directory.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("missing", ["id", "revision", "edit_token"])
def test_saved_receipt_missing_required_field_never_claims_success(missing):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable for guest.js runtime regression")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.hidden = false; this.children = []; this.dataset = {}; this.value = ''; }
  append(...children) { this.children.push(...children); }
  addEventListener() {}
  scrollIntoView() {}
  querySelectorAll(selector) {
    return selector === '.person-row' ? this.children : [];
  }
  querySelector() { return {value: 'yes'}; }
}
async function recover(receipt) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  get('success').hidden = true;
  get('error').hidden = true;
  const document = {
    getElementById: get,
    createElement: () => new Element(),
    addEventListener() {},
  };
  const own = {
    contact_name: 'Pessoa Rede Teste', adults: 1, children_0_5: 0,
    children_6_12: 0, responded: true, receipt,
  };
  const window = {
    location: {pathname: '/convite', hash: '#' + 'a'.repeat(36) + '.' + 'b'.repeat(64), origin: 'http://local.test'},
    setTimeout, clearTimeout, addEventListener() {},
  };
  vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
    document, window, AbortController,
    navigator: {onLine: true},
    sessionStorage: {getItem() { return null; }},
    fetch: async url => ({ok: true, json: async () =>
      url === '/api/event' ? {venue: 'Local a confirmar'} : own}),
  });
  await new Promise(resolve => setImmediate(resolve));
  return get;
}
(async () => {
  const receipt = {id: '12345678-1234-1234-1234-123456789abc', revision: 1,
    edit_token: 'c'.repeat(64), attending: true};
  const broken = {...receipt};
  delete broken[process.argv[2]];
  const failed = await recover(broken);
  assert.equal(failed('success').hidden, true, 'damaged receipt displayed success');
  assert.equal(failed('error').hidden, false, 'damaged receipt did not report error');
  assert.match(failed('error').textContent, /Não foi possível verificar/);
  assert.equal(failed('edit-link').value, '', 'damaged receipt generated an edit link');
  const recovered = await recover(receipt);
  assert.equal(recovered('success').hidden, false, 'valid receipt did not recover');
  assert.equal(recovered('error').hidden, true);
  assert.equal(recovered('edit-link').value,
    'http://local.test/editar#' + receipt.id + '.' + receipt.edit_token);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        [node, "-e", script, str(Path("app/static/guest.js").resolve()), missing],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
