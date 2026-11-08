# Isadora — reforço final de uso móvel e rede instável

**Registro:** 08/11/2026. Implementação da Release 1 na branch `improve/isadora-rsvp-resilience-mobile-webkit-20261108`.

## Funcionalidades técnicas adicionadas

1. **Prazo máximo para respostas HTTP do convidado:** em rede travada, o navegador encerra a espera após 15 segundos e devolve o controle ao usuário.
2. **Retentativa segura:** o formulário mantém os dados de revisão e, na criação, a mesma chave de idempotência. Assim, caso o servidor tenha salvo antes da perda de rede, repetir não insere outra família.
3. **Mensagem de incerteza:** a interface não afirma que o registro falhou no servidor, apenas que não conseguiu confirmar a resposta. O usuário é orientado a tentar novamente sem alterar os dados.
4. **Cobertura em dois motores:** testes automatizados de confirmação, edição e reconexão no Chromium com dispositivo Pixel 5 emulado e no WebKit com iPhone 13 emulado.
5. **Regressão de travamento:** simulação de POST sem resposta, verificação de liberação do botão e novo envio sem duplicidade.
6. **CI ampliada:** instala também WebKit no GitHub Actions. A suíte integral ainda verifica MySQL, criptografia e restauração.

## Critérios de aceite do código

- [ ] Suíte de Python, integração e navegadores sem falhas
- [ ] Android emulado (Chromium) com confirmação e edição corretas
- [ ] iPhone emulado (WebKit) com confirmação e edição corretas
- [ ] Perda de rede e retorno sem confirmação falsa nem duplicidade
- [ ] Requisição travada não bloqueia definitivamente o botão de envio
- [ ] Docker Compose, idempotência, backup cifrado e restauração aprovados
- [ ] Merge na main apenas depois de CI integral verde

**Atenção:** esta documentação descreve verificações de navegador emulado, não testes de iPhone e Android físicos. A liberação operacional continua vinculada a domínio HTTPS, backup externo, dispositivos reais, revisão e aceite (veja `docs/fechamento-100.md`).

**Progresso:** funcionalidades da Release 1 em código entregues; liberação pública permanece 86% enquanto a última etapa não for comprovada.
