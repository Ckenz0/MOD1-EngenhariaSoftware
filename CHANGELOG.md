# Changelog

Mudanças de produto seguem Keep a Changelog e SemVer. A versão candidata do pacote é `0.1.0`; nenhuma release publicada é presumida.

## Unreleased

### Added

- Infraestrutura Bicep integrada Azure + Neon: bootstrap separado das APIs, identidades por serviço, segredos com escopo individual e escala a zero.
- Workflows manuais OIDC por digest, checks de imagem e guia completo de configuração, validação e rollback.

- API Python/FastAPI em camadas, PostgreSQL/SQLAlchemy e conexão com Neon.
- Contas individuais persistentes, hashing Argon2 e administração local por CLI.
- Cadastro público com login imediato, validação de dados e resposta uniforme para e-mails já cadastrados, preservando senha e situação da conta existente.
- Login JWT RS256 com perfil estrito, chave RSA persistente e JWKS público.
- Consulta de identidade, saúde, OpenAPI e CORS explícito.
- Exemplo consumidor independente com JWKS ou PEM público.
- Testes de segurança, HTTP, CLI, persistência e integração PostgreSQL opt-in.
- Dependências travadas, Ruff, mypy estrito, Docker/Compose e template Azure Container Apps.

### Removed

- Scripts de impressão e conteúdo de teste inicial, substituídos pela aplicação.
