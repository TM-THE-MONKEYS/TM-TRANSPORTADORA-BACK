# TM Transportadora — Deploy, Alterações e Guia de Integração Frontend

> Gerado em: 2026-06-17  
> Backend: **FastAPI 0.115 / Python 3.12 / PostgreSQL (Supabase)**  
> Deploy: **Railway (projeto `tm-transportadora-back`)**

---

## 1. Acesso à Aplicação

### API em produção

| Item | Valor |
|---|---|
| **URL base** | `https://api-production-a071.up.railway.app` |
| **Health check** | `https://api-production-a071.up.railway.app/health` |
| **Docs (dev)** | Desabilitadas em produção (`APP_ENV=production`) |
| **Região** | US East (iad) — Virginia, mais próxima ao Brasil disponível no Railway |

### Conta de administrador

| Campo | Valor |
|---|---|
| **Email** | `admin@tmtransportadora.com.br` |
| **Senha** | `TM@Admin2026!` |
| **Role** | `admin` |

> **Altere a senha após o primeiro login** via `PATCH /api/v1/auth/change-password`.

---

## 2. Alterações realizadas neste ciclo

### 2.1 Novo módulo: Pedágios (`/api/v1/tolls`)

Módulo completo para registro e consulta de pedágios pagos durante fretes. Ver [FRONTEND-PEDAGIOS.md](FRONTEND-PEDAGIOS.md) para o guia de integração detalhado.

**Endpoints:**

| Método | Path | Descrição |
|---|---|---|
| `POST` | `/tolls` | Registra pedágio (admin, operador, motorista do frete) |
| `GET` | `/tolls` | Lista histórico paginado de pedágios |
| `GET` | `/tolls/{charge_id}` | Busca pedágio por ID |
| `GET` | `/tolls/freight/{freight_id}` | Lista pedágios de um frete |
| `GET` | `/tolls/freight/{freight_id}/summary` | Resumo de valor/quantidade por frete |
| `GET` | `/tolls/eligible-freights` | Fretes elegíveis para pedágio |
| `GET` | `/tolls/active-freight` | Frete em andamento do motorista logado |

### 2.2 Correções de segurança

| Severidade | Arquivo | Correção |
|---|---|---|
| **Alta** | `drivers/service.py` | Senha padrão de motoristas era previsível (`Mot@{cpf}!`). Substituída por `secrets.token_urlsafe(16)`. A senha temporária agora é retornada **uma única vez** no campo `temporary_password` da resposta de criação. |
| **Média** | `shared/exceptions/handlers.py` | Campos `password`, `new_password`, `refresh_token` e similares eram ecoados nos erros 422 e nos logs de servidor. Agora são removidos do response e do log. |
| **Média** | `shared/exceptions/handlers.py` | Erros internos de banco de dados não são mais retornados ao cliente em nenhum ambiente — ficam apenas no log do servidor. |
| **Média** | `auth/router.py` | Rate limit de autenticação (`10 req/min`) agora aplicado em `/auth/login`, `/auth/driver/login`, `/auth/refresh`, `/auth/forgot-password` e `/auth/reset-password`. |
| **Média** | `auth/service.py` | `ALLOW_TENANT_REGISTRATION=false` agora bloqueia registro de novos tenants em todos os ambientes (antes só em produção). |
| **Média** | `finance/freight_sync.py` | `sync_all_from_freights` gerava entradas financeiras duplicadas para pedágios (PEDAGIO era processado pela sync genérica mesmo já tendo entrada criada pelo módulo de pedágios). Corrigido para pular `FreightCost` do tipo PEDAGIO quando há `TollCharge` vinculado. |

### 2.3 Campo `temporary_password` em criação de motorista

Ao criar um motorista **sem enviar password**, a resposta agora inclui:

```json
{
  "id": "uuid",
  "name": "JOÃO MOTORISTA",
  "cpf": "...",
  "temporary_password": "xK9mP2...",
  ...
}
```

- O campo só aparece quando a senha foi gerada automaticamente; é `null` quando o admin enviar a senha manualmente.
- **O frontend deve exibir esse valor ao admin** para que ele repasse ao motorista. Após o primeiro login, o motorista deve alterar via `POST /auth/change-password`.

### 2.4 Notificações incluem `toll_charge_id`

`NotificationItemRead` agora expõe `toll_charge_id` para navegação direta ao pedágio a partir da notificação.

---

## 3. Infraestrutura Railway

### Serviços provisionados

| Serviço | Tipo | Config | Status |
|---|---|---|---|
| `api` | FastAPI (Dockerfile production) | `railway.api.json` | ✅ Running |
| `Redis` | Redis 8.2.1 | — | ✅ Running |
| `worker` | Celery worker (Dockerfile.worker) | `railway.worker.json` | ✅ Running |

> O `railway.json` base não define healthcheck nem migrations. A API usa `railway.api.json` (com `/health` e `alembic upgrade head`). O worker usa `railway.worker.json` (sem HTTP healthcheck).

### Variáveis de ambiente configuradas

| Variável | Valor |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `ALLOW_TENANT_REGISTRATION` | `false` |
| `WEB_CONCURRENCY` | `2` |
| `LOG_LEVEL` | `INFO` |
| `LOG_FORMAT` | `json` |
| `RATE_LIMIT_PER_MINUTE` | `60` |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `10` |
| `DATABASE_URL` | Supabase pooler asyncpg (SA East) |
| `SUPABASE_URL` | https://jkdkspbcqnfrweanmhpp.supabase.co |
| `SUPABASE_ANON_KEY` | configurado |
| `SECRET_KEY` | gerado aleatoriamente (48 chars) |
| `REDIS_URL` / `CELERY_*` | referência ao serviço Redis interno |
| `CORS_ORIGINS` | Vercel origins configuradas |

### Auto-deploy (ação pendente)

O Railway ainda exige conexão manual do repositório GitHub via painel:

1. Acesse o [painel do projeto Railway](https://railway.com/project/4bb27116-1b8d-444f-ab1d-e463b7ed4520)
2. Serviço `api` → **Settings → Source → Connect Repo** → `TM-THE-MONKEYS/TM-TRANSPORTADORA-BACK`, branch `main`
3. Repita para o serviço `worker`

Após isso, todo push para `main` dispara deploy automático.

---

## 4. Guia de integração Frontend

### 4.1 URL base e autenticação

```
BASE_URL = https://api-production-a071.up.railway.app/api/v1
```

Toda requisição autenticada deve enviar:

```
Authorization: Bearer <access_token>
```

### 4.2 Fluxo de autenticação

#### Login (usuário admin/operador/financeiro)

```http
POST /auth/login
Content-Type: application/json

{ "email": "admin@tmtransportadora.com.br", "password": "TM@Admin2026!" }
```

**Resposta:**
```json
{
  "tokens": {
    "access_token": "eyJ...",
    "refresh_token": "abc...",
    "token_type": "bearer",
    "expires_in": 1800
  },
  "user": {
    "id": "uuid",
    "email": "admin@tmtransportadora.com.br",
    "name": "Administrador",
    "role": "admin",
    "tenant_id": "uuid",
    "permissions": ["dashboard:read", "fleet:read", "fleet:write", "drivers:read", "drivers:write", "freight:read", "freight:write", "freight:status", "finance:read", "tenant:admin"]
  }
}
```

#### Login de motorista (usa CPF, não e-mail)

```http
POST /auth/driver/login
Content-Type: application/json

{ "cpf": "12345678901", "password": "senha-do-motorista" }
```

#### Renovar token

```http
POST /auth/refresh
Content-Type: application/json

{ "refresh_token": "abc..." }
```

#### Perfil do usuário logado

```http
GET /auth/me
Authorization: Bearer <token>
```

### 4.3 Roles e permissões

| Role backend | Role frontend | Permissões |
|---|---|---|
| `admin` | `admin` | Tudo, incluindo `tenant:admin` |
| `operador` | `operacional` | Dashboard, frota, motoristas, fretes |
| `financeiro` | `financeiro` | Dashboard, finanças, fretes (leitura) |
| `motorista` | `motorista` | Fretes próprios (leitura + status) |

> O backend retorna `role: "operador"` mas o frontend deve tratar como `"operacional"` (o campo `user.role` retornado pelo login já faz esse mapeamento automaticamente via `role_to_frontend`).

### 4.4 Paginação

Todos os endpoints de listagem usam o mesmo padrão:

```
GET /drivers?page=1&size=20
```

**Resposta:**
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "size": 20,
  "pages": 3
}
```

### 4.5 Erros padrão

| Status | Situação |
|---|---|
| `400` | Requisição inválida / regra de negócio |
| `401` | Token ausente, inválido ou expirado |
| `403` | Role sem permissão para a operação |
| `404` | Recurso não encontrado |
| `409` | Conflito (ex.: CPF/e-mail duplicado) |
| `422` | Erro de validação de campos |
| `429` | Rate limit atingido |
| `503` | Banco de dados indisponível |

Formato dos erros:
```json
{ "detail": "mensagem de erro" }
```

Para 422, `detail` é um array de objetos com `loc`, `msg` e `type`. Campos sensíveis (`password`, etc.) têm o valor removido.

---

## 5. Endpoints por módulo

### Motoristas (`/drivers`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/drivers` | admin, operador, financeiro |
| `POST` | `/drivers` | admin, operador |
| `GET` | `/drivers/{id}` | admin, operador, financeiro |
| `PATCH` | `/drivers/{id}` | admin, operador |
| `DELETE` | `/drivers/{id}` | admin, operador |

**Campos frontend → backend (aliases aceitos):**

| Frontend | Backend |
|---|---|
| `name` | `nome` |
| `cnh_number` | `cnh` |
| `cnh_expires_at` | `cnh_expiry` |
| `phone` | `telefone` |

**Resposta de criação inclui `temporary_password`** quando a senha foi gerada automaticamente.

### Caminhões (`/trucks`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/trucks` | admin, operador, financeiro |
| `POST` | `/trucks` | admin, operador |
| `GET` | `/trucks/{id}` | admin, operador, financeiro |
| `PATCH` | `/trucks/{id}` | admin, operador |
| `DELETE` | `/trucks/{id}` | admin, operador |

**Status possíveis:** `disponivel` · `em_viagem` · `em_manutencao` · `inativo`

### Clientes (`/clients`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/clients` | admin, operador |
| `POST` | `/clients` | admin, operador |
| `GET` | `/clients/{id}` | admin, operador |
| `PATCH` | `/clients/{id}` | admin, operador |
| `DELETE` | `/clients/{id}` | admin, operador |

### Fretes (`/freights`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/freights` | todos |
| `POST` | `/freights` | admin, operador |
| `GET` | `/freights/{id}` | todos |
| `PATCH` | `/freights/{id}` | admin, operador |
| `PATCH` | `/freights/{id}/status` | admin, operador |
| `DELETE` | `/freights/{id}` | admin, operador |

**Status do frete (fluxo):**
```
orcamento → confirmado → em_coleta → em_transporte → entregue
                                                    → cancelado
```

### Pedágios (`/tolls`) — **Novo**

Ver seção 2.1 e [FRONTEND-PEDAGIOS.md](FRONTEND-PEDAGIOS.md).

### Abastecimentos (`/fuel`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/fuel` | admin, operador, financeiro |
| `POST` | `/fuel` | admin, operador, motorista (frete próprio) |
| `GET` | `/fuel/eligible-freights` | motorista |
| `GET` | `/fuel/{id}` | admin, operador, financeiro |

### Manutenções (`/maintenance`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/maintenance` | admin, operador |
| `POST` | `/maintenance` | admin, operador |
| `PATCH` | `/maintenance/{id}` | admin, operador |
| `DELETE` | `/maintenance/{id}` | admin, operador |

**Status:** `agendada` · `em_andamento` · `concluida` · `cancelada`

### Finanças (`/finance`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/finance` | admin, financeiro |
| `POST` | `/finance` | admin, financeiro |
| `GET` | `/finance/cash-flow` | admin, financeiro |
| `PATCH` | `/finance/{id}` | admin, financeiro |
| `DELETE` | `/finance/{id}` | admin, financeiro |
| `POST` | `/finance/sync` | admin, financeiro |

### Rastreamento (`/tracking`)

| Método | Path | Roles |
|---|---|---|
| `POST` | `/tracking` | admin, operador, motorista (frete próprio) |
| `GET` | `/tracking/freight/{freight_id}` | todos |

**Status de rastreamento:** `coletado` · `em_transito` · `saiu_para_entrega` · `tentativa_entrega` · `entregue` · `devolvido`

### Notificações (`/notifications`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/notifications` | admin, operador, financeiro |
| `GET` | `/notifications/unread-count` | admin, operador, financeiro |
| `PATCH` | `/notifications/{id}/read` | admin, operador, financeiro |
| `PATCH` | `/notifications/read-all` | admin, operador, financeiro |

**Tipos de notificação:** `tracking_occurrence` · `fuel_refill` · `toll_charge`

### Dashboard (`/dashboard`)

```http
GET /dashboard/kpis
Authorization: Bearer <token>
```

Retorna KPIs consolidados do tenant (fretes ativos, receita do mês, caminhões disponíveis, etc.).

### Usuários (`/users`)

| Método | Path | Roles |
|---|---|---|
| `GET` | `/users` | admin |
| `POST` | `/users` | admin |
| `GET` | `/users/{id}` | admin, próprio |
| `PATCH` | `/users/{id}` | admin, próprio |
| `DELETE` | `/users/{id}` | admin |

---

## 6. Variáveis de ambiente necessárias no frontend

```env
NEXT_PUBLIC_API_URL=https://api-production-a071.up.railway.app/api/v1
```

> Se o frontend estiver em Vercel, certifique-se de que o domínio da Vercel está na lista `CORS_ORIGINS` configurada no Railway. Os domínios já configurados são:
> - `https://tm-transportadora.vercel.app`
> - `https://tm-transportadora-julinhohgrs-projects.vercel.app`
>
> Para outros domínios, atualize a variável `CORS_ORIGINS` no painel do Railway com um array JSON:
> ```json
> ["https://seu-dominio.vercel.app","https://outro-dominio.com"]
> ```

---

## 7. Estado do banco de dados (pós-limpeza)

| Tabela | Registros |
|---|---|
| `tm_tenants` | 1 (Transportadora TM) |
| `tm_users` | 1 (admin@tmtransportadora.com.br) |
| Todos os outros | 0 (limpos) |

Todas as tabelas foram mantidas. Apenas os dados de teste foram removidos.

---

## 8. Branches e deploy (dev → main)

### Fluxo Git

| Branch | Uso |
|--------|-----|
| **`dev`** | Desenvolvimento — push diário |
| **`main`** | Produção — merge via PR após testes locais |

### Railway (`tm-transportadora-back`)

Serviços **api** e **worker** estão configurados com:

- Repositório: `TM-THE-MONKEYS/TM-TRANSPORTADORA-BACK`
- **Branch de deploy: `main`** (root: `backend`)
- Redis: imagem Docker (sem Git)

Auto-deploy via GitHub exige **Railway GitHub App** instalada no repositório (Settings → GitHub no projeto). Com a app ativa, apenas pushes em **`main`** devem disparar deploy em production.

Deploy manual (CLI/MCP) só quando solicitado, sempre a partir de **`main`** atualizada.

### Vercel (frontend)

- Produção deve refletir apenas **`main`**.
- `vercel.json` desabilita auto-deploy Git para `dev` e demais branches; **`main`** permanece habilitada.
- Repositório privado em **organização** no plano Hobby pode exigir **Vercel Pro** para integração Git completa. Sem Pro: deploy manual `vercel deploy --prod` a partir de `main` mergeada.

### Checklist antes do merge em main

1. Testes locais (front + API local)
2. PR `dev` → `main` revisada
3. Merge em `main`
4. Confirmar deploy Railway/Vercel (automático ou manual conforme plano)

