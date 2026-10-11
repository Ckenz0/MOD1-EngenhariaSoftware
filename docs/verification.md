# Verificação do candidato 0.1.0 — 11/10/2026

O recorte permite criar conta, entrar, consultar a identidade e consumir o JWT
RS256 nos demais serviços. Contas ficam no Neon e a chave privada permanece no
host da API. Frontend e serviço de projetos executam separadamente.

Antes de publicar a branch `feat/auth-mvp`:

- Suíte completa: **108 passaram, 5 ignorados**, em 97,55 segundos.
- Os cinco ignorados exigem PostgreSQL local descartável e `TEST_DATABASE_URL`;
  nunca configurar essa variável com o Neon. Host remoto e parâmetros que
  sobrescrevam o endereço são recusados antes de inicializar o banco.
- Ruff, formatação, mypy estrito e `uv lock --check` passaram.
- Wheel/sdist foram construídos com Hatchling no ambiente local autorizado;
  arquivos privados, `.env`, chaves e `.local/` ficaram fora dos pacotes.
- Frontend: **48 testes passaram**, incluindo identidade e projetos com APIs reais
  e bancos/chaves sintéticos. Backend de projetos: **73 passaram, 1 opt-in ignorado**.
- A demonstração anterior no Neon comprovou cadastro, login, consulta, isolamento
  de contas e persistência após reinício. Evidências em `database-neon.md` e no
  repositório MOD1-Frontend, `docs/verification.md`.

Não foram executados Docker/deploy Azure nesta conferência. Cadastro permite login
imediato sem confirmar posse do e-mail. Logout não revoga JWT já emitido; equipes,
papéis por projeto e backlog pertencem aos próximos recortes.

Versão SemVer candidata definida em `pyproject.toml`. Esta publicação de branch/PR
não cria tag/release nem integra alterações na main. Brian Freire é coautor dos
novos commits; a revisão será solicitada a `briankfreire`.
