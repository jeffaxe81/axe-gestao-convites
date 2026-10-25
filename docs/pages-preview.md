# Apresentação visual no GitHub Pages

A apresentação usa o HTML, CSS e as funções de formulário da página da Isadora. É uma demonstração pública para experimentar o visual no celular, não uma instalação do Flask/MySQL.

- O aviso de demonstração permanece visível.
- É possível confirmar/recusar, adicionar acompanhantes, informar idade, revisar e simular o agradecimento.
- Nenhum dado do formulário é enviado a APIs ou persistido no navegador. Use nomes fictícios. O próprio acesso à página segue os registros normais da hospedagem GitHub Pages.
- Não há login, painel administrativo, link de edição ou confirmação real.
- A página funciona em subdiretório, com recursos relativos, sem domínio próprio.
- A apresentação não conclui a homologação da aplicação real.

## Construir e conferir

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python scripts/build_pages_preview.py
python -m pytest tests/e2e/test_pages_preview.py -q
python -m http.server --directory dist-pages 8090
```

Abra `http://localhost:8090`. A pasta `dist-pages/` é ignorada pelo Git. O exportador copia exclusivamente `index.html`, dois assets públicos, `.nojekyll` e `robots.txt`; não copia `.env`, dados ou código do servidor. Os testes exercitam a página em um subdiretório como o do GitHub Pages e verificam que não ocorrem pedidos para APIs nem armazenamento de dados.

## Publicação

Os cinco arquivos gerados são publicados na branch independente `gh-pages`. A aplicação e a PR da release continuam separadas. O endereço esperado após habilitar a hospedagem é:

https://jeffaxe81.github.io/axe-gestao-convites/

A integração desta sessão recebeu HTTP 403 `Resource not accessible by integration` ao tentar habilitar o Pages. O proprietário deve abrir:

https://github.com/jeffaxe81/axe-gestao-convites/settings/pages

Em **Build and deployment**, selecionar **Deploy from a branch**, branch **gh-pages**, pasta **/(root)**, e **Save**. Aguardar o build automático do Pages. O endereço só está ativo depois que a implantação terminar com sucesso; a presença da branch não comprova publicação.

Para atualizar a demonstração, executar novamente o exportador e publicar os arquivos gerados na mesma branch, preservando seu histórico. Nunca publicar o diretório inteiro do projeto nem credenciais. Esta apresentação utiliza somente dados que a pessoa digita em memória na própria página.
