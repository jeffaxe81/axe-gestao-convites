"""Export only the guest visual demo: no backend, credentials or RSVP storage."""
import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Guest template changed; review the visual preview export.")
    return source.replace(old, new, 1)


def build(output):
    environment = Environment(
        loader=FileSystemLoader(ROOT / "app/templates"),
        autoescape=select_autoescape(["html"]),
    )
    html = environment.get_template("index.html").render(
        url_for=lambda endpoint, filename: "./assets/" + filename,
    )
    html = replace_once(html, "<title>Um dia especial para Isadora 🌼</title>",
                        '<title>Demonstração — Convite da Isadora 🌼</title>\n  <meta name="robots" content="noindex, nofollow">')
    html = replace_once(html, '<main class="shell">', '''<main class="shell">
    <aside id="preview-notice" class="notice" aria-label="Sobre esta demonstração">
      <strong>Demonstração visual — nenhuma resposta será enviada.</strong>
      Experimente com nomes fictícios. Este site não registra presenças; os campos são apagados ao recarregar.
    </aside>''')
    html = replace_once(html, "Você poderá atualizar sua resposta pelo link privado gerado após o envio, enquanto a edição estiver aberta.",
                        "Nesta demonstração, você pode revisar os campos e simular o resultado. Nenhuma confirmação será gravada.")
    html = replace_once(html, ">Enviar confirmação</button>", ">Simular confirmação</button>")
    html = replace_once(html, "<h2>Obrigado pelo carinho!</h2>", "<h2>Simulação concluída 🌼</h2>")
    start = html.index('        <label for="edit-link">')
    end = html.index('\n      </div>', start)
    html = html[:start] + '        <button type="button" id="preview-reset" class="secondary full">Experimentar novamente</button>' + html[end:]
    html = replace_once(html, "Feito com carinho para celebrar a Isadora", "Apresentação visual do Axé Convites · Isadora")

    guest = (ROOT / "app/static/guest.js").read_text(encoding="utf-8")
    # Reuse form rendering/validation only. Never include the API, token or storage code.
    helpers = guest[guest.index("  function fail("):guest.index("  function renderSuccess(")]
    helpers = helpers.replace("'Presença confirmada'", "'Vou comparecer (simulação)'")
    javascript = """(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const form = $('rsvp-form');
  let rowNumber = 0;
  let pendingPayload = null;
""" + helpers + """
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
"""
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    (output / "index.html").write_text(html, encoding="utf-8")
    (assets / "guest.js").write_text(javascript, encoding="utf-8")
    (assets / "site.css").write_text((ROOT / "app/static/site.css").read_text(encoding="utf-8"), encoding="utf-8")
    (output / ".nojekyll").touch()
    (output / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print("Visual preview exported to", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pages")
    build(parser.parse_args().output)
