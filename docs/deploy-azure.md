# Deploy: Azure Container Apps e Supabase PostgreSQL

Este guia descreve a opção anterior com Supabase e publicação futura no Azure. O MVP atual utiliza Neon com execução local; siga [database-neon.md](database-neon.md). Nenhum deploy Azure foi realizado.

O template prepara somente a API de autenticação. Banco hospedado no Supabase, imagem em ACR, chave RSA e configuração do banco em Key Vault. Nenhum recurso ou deploy foi criado pela implementação local. Defina subscription, região, recursos e orçamento antes de publicar.

## Banco Supabase

Obtenha a conexão em **Connect** no painel. Use conexão direta se o ambiente alcançar seu endpoint; para IPv4, use **session pooler**, porta 5432, com host e usuário exatamente como fornecidos pelo painel. Não suponha host/região nem use transaction pooling como padrão. Para usuário dedicado pelo pooler, siga a forma `ROLE.PROJECTREF` fornecida pelo provedor.

Crie um papel de preparação e outro runtime por serviço. Apenas o administrador prepara o schema/tabela. Exemplo administrativo (senha via ferramenta segura do operador, não este arquivo):

```sql
CREATE SCHEMA IF NOT EXISTS mod1_identity;
CREATE ROLE mod1_auth_runtime LOGIN;
REVOKE ALL ON SCHEMA mod1_identity FROM PUBLIC;
GRANT USAGE ON SCHEMA mod1_identity TO mod1_auth_runtime;
```

Configure `DATABASE_URL` administrativo no ambiente do processo e execute `mod1-auth init`. Depois conceda apenas os privilégios de dados e use a credencial limitada na API/CLI de contas:

```sql
GRANT SELECT, INSERT, UPDATE ON mod1_identity.users TO mod1_auth_runtime;
REVOKE ALL ON SCHEMA mod1_identity FROM anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA mod1_identity FROM anon, authenticated;
```

O papel runtime não deve ter superuser, criação de schema/tabela, associação aos papéis de outros serviços ou acesso aos respectivos schemas. Não exponha `mod1_identity` na Data API. Se houver grants globais prévios, audite-os e remova o acesso indevido. Cada novo serviço terá seu próprio schema/papel; nenhum fará joins ou FKs entre serviços. Papéis PostgreSQL são distintos dos papéis de usuário por projeto.

Use DSN SQLAlchemy `postgresql+psycopg://...`, com senha codificada para URI, TLS `sslmode=verify-full` e CA confiável obtida do painel Supabase. No Container App, o template monta a CA em `/mnt/secrets/database-ca.pem`; o segredo de DSN deve incluir `sslrootcert=/mnt/secrets/database-ca.pem`. Localmente use o caminho absoluto da CA local. `sslmode=require` sozinho não garante verificação da identidade do servidor. O pool da API tem 2 conexões, sem overflow, pre-ping e connect timeout de 5 segundos.

Fonte: [conexão PostgreSQL/TLS](https://supabase.com/docs/guides/database/connecting-to-postgres), [papéis PostgreSQL](https://supabase.com/docs/guides/database/postgres/roles).

## Azure e segredos

Prepare Resource Group, Container Apps Environment, ACR, Key Vault e identidade gerenciada atribuída pelo usuário. A identidade precisa de permissão de leitura dos segredos pertinentes (`Key Vault Secrets User`, escopo restrito) e pull da imagem (conforme o modo de permissões do ACR; em registro sem ABAC, `AcrPull`). A identidade não precisa escrever segredos ou receber credenciais administrativas do banco.

Crie explicitamente uma chave RSA de 3072 bits com `mod1-auth init` em ambiente administrativo protegido. Armazene o PEM multiline **como arquivo**, preservando quebras de linha, em Key Vault. Fixe a URI da versão desse segredo; reutilize a mesma chave entre revisões. Armazene também o DSN runtime e a CA confiável em segredos. O template monta a chave/CA e injeta o DSN por `secretRef`; não grave os conteúdos no JSON de parâmetros, imagem ou repositório.

Se usar `az keyvault secret set --file`, o argumento deve ser o caminho do arquivo protegido, nunca o conteúdo. Configure restrições de acesso conforme sua conta; parâmetros reais ficam em `parameters.local.json`, ignorado.

## Imagem e aplicação

Depois de validar Docker/PostgreSQL localmente:

```console
docker compose build api
az acr login --name YOUR_REGISTRY
docker tag mod1-auth:0.1.0 YOUR_REGISTRY.azurecr.io/mod1-auth:0.1.0
docker push YOUR_REGISTRY.azurecr.io/mod1-auth:0.1.0
```

Obtenha o digest publicado; configure `imageReference` por `@sha256:...` em vez de tag mutável. Preencha os parâmetros a partir de `deploy/azure/parameters.example.json`. Use issuer estável, preferencialmente a URL HTTPS escolhida, mantendo audience `engenharia-software-api`. Se houver frontend, configure apenas as origens exatas em `corsOrigins`.

Compile e revise antes de aplicar:

```console
az bicep build --file deploy/azure/containerapp.bicep --outfile YOUR_TEMP_DIR/containerapp.json
az deployment group what-if --resource-group YOUR_RESOURCE_GROUP --template-file deploy/azure/containerapp.bicep --parameters @deploy/azure/parameters.local.json
az deployment group create --resource-group YOUR_RESOURCE_GROUP --template-file deploy/azure/containerapp.bicep --parameters @deploy/azure/parameters.local.json
```

Compilar não comprova deploy. O template referencia recursos existentes e configura HTTPS obrigatório, porta 8000, 0.5 CPU/1GiB e uma réplica. Startup/liveness usam `/health/live`; readiness usa `/health/ready`. Nenhum banco Azure é criado. A API não executa DDL no startup; prepare o Supabase administrativamente antes de esperar readiness 200.

## Prova de disponibilidade

Após publicar, valide a partir de outra máquina: HTTPS, readiness, JWKS, login de conta individual, `/auth/me` e o exemplo consumidor. Publique nova revisão com a mesma chave e banco; confirme UUID/kid estáveis e aceitação de token anterior. Só então entregue aos grupos URL, issuer, audience, JWKS e credenciais individuais por canal apropriado. Não compartilhe chave privada, DSN ou credencial administrativa.

Fonte: [Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview), [segredos/Key Vault](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets), [probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes), [pull por identidade](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull).
