# TM Transportadora — Backend API

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?logo=supabase&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0-red" />
  <img src="https://img.shields.io/badge/coverage-80%25%2B-brightgreen" />
  <img src="https://img.shields.io/badge/tests-74%20passed-brightgreen" />
  <img src="https://img.shields.io/badge/code%20style-ruff-black" />
</p>

> Backend SaaS production-ready para gestão operacional de transportadora de pequeno porte.

---

## Índice

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Início Rápido](#início-rápido)
- [Configuração de Ambiente](#configuração-de-ambiente)
- [Endpoints da API](#endpoints-da-api)
- [Documentação para Frontend](./docs/API-FRONTEND.md)
- [Autenticação e RBAC](#autenticação-e-rbac)
- [Banco de Dados](#banco-de-dados)
- [Testes](#testes)
- [Qualidade de Código](#qualidade-de-código)
- [Docker](#docker)
- [Workers e Tasks](#workers-e-tasks)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Visão Geral

API RESTful assíncrona para gerenciamento completo de transportadora: frota, motoristas, clientes, fretes, financeiro, manutenção, rastreamento e dashboard de KPIs.

### Funcionalidades

| Módulo | Funcionalidades |
|---|---|
| **Autenticação** | Login/Logout, JWT access + refresh token rotation, recuperação de senha, RBAC |
| **Usuários** | CRUD completo, perfis de acesso, soft delete, auditoria |
| **Motoristas** | Cadastro, CNH, validade, status operacional |
| **Frota** | Caminhões, placa, km, capacidade, status em tempo real |
| **Clientes** | Cadastro com CPF/CNPJ validado, endereço estruturado |
| **Fretes** | Controle de estados, custos extras, comprovantes, transições validadas |
| **Manutenção** | Preventiva/corretiva, alertas por prazo, histórico por caminhão |
| **Financeiro** | Receitas e despesas, fluxo de caixa, contas a pagar/receber |
| **Rastreamento** | Linha do tempo de entregas, geolocalização |
| **Dashboard** | KPIs consolidados: frota, fretes, financeiro, alertas |

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12+ |
| Framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 (async) |
| Banco de Dados | PostgreSQL via Supabase |
| Migrations | Alembic (async mode) |
| Validação | Pydantic v2 |
| Autenticação | JWT (python-jose) + Argon2 (passlib) |
| Cache/Fila | Redis + Celery |
| Logs | Structlog (JSON estruturado) |
| Rate Limiting | SlowAPI |
| Testes | Pytest + pytest-asyncio |
| Lint/Format | Ruff |
| Containerização | Docker + Docker Compose |

---

## Arquitetura

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── dependencies/       # auth.py (JWT + RBAC), database.py, pagination.py
│   │   └── middleware/         # LoggingMiddleware, AuditMiddleware
│   ├── core/
│   │   ├── config/             # settings.py — Pydantic BaseSettings + @lru_cache
│   │   ├── database/           # engine.py (@lru_cache), session.py, redis.py (@lru_cache)
│   │   ├── security/           # jwt.py, password.py (Argon2)
│   │   └── logging/            # structlog com contextvars (request_id por request)
│   ├── modules/                # Um módulo por domínio (auth, users, drivers...)
│   │   └── <módulo>/
│   │       ├── models.py       # SQLAlchemy ORM (Mapped[T] + mapped_column)
│   │       ├── schemas.py      # Pydantic v2 (Create, Update, Read, ListResponse)
│   │       ├── repository.py   # Queries async, soft delete, paginação
│   │       ├── service.py      # Regras de negócio, RBAC, logs
│   │       └── router.py       # FastAPI com Annotated[T, Depends()]
│   ├── shared/
│   │   ├── base_model.py       # BaseModel (UUID PK, timestamps, soft delete)
│   │   ├── enums/              # UserRole, FreightStatus, TruckStatus...
│   │   ├── exceptions/         # Exceções customizadas + global handlers
│   │   ├── pagination/         # PageParams, PagedResponse[T] genérico
│   │   └── utils/              # Validação CPF/CNPJ
│   ├── workers/
│   │   ├── celery_app.py       # Configuração + beat schedule
│   │   └── tasks.py            # Alertas, vencimentos, limpeza de tokens
│   └── main.py                 # App factory, lifespan, middlewares
├── tests/                      # 74 testes, 80%+ cobertura
├── alembic/                    # Migrations async
├── docker/                     # Dockerfile + Dockerfile.worker + nginx.conf
├── scripts/                    # seed.py, dev.ps1, start.sh
├── .env.example
├── docker-compose.yml
└── pyproject.toml
```

### Padrões Adotados

- **Clean Architecture** com separação clara de camadas
- **Repository Pattern** — abstração de queries desacoplada dos serviços
- **Service Layer** — regras de negócio isoladas, testáveis
- **Dependency Injection** via `Annotated[T, Depends()]` do FastAPI
- **Async-first** — todas as operações de I/O são assíncronas
- **LRU Cache** nas conexões: `Settings`, `AsyncEngine` e `Redis ConnectionPool`

---

## Início Rápido

### Pré-requisitos

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Redis (local ou via Docker)
- Conta no [Supabase](https://supabase.com) (ou PostgreSQL local)

### Setup Local (sem Docker)

```bash
# 1. Entrar no diretório
cd backend

# 2. Instalar dependências
poetry install

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais (DATABASE_URL, SECRET_KEY, etc.)

# 4. Rodar migrations
poetry run alembic upgrade head

# 5. Criar usuário admin inicial
poetry run python scripts/seed.py

# 6. Iniciar o servidor de desenvolvimento
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse: **http://localhost:8000/docs**

### Setup Rápido (PowerShell / Windows)

```powershell
# Executa migrations + seed + servidor automaticamente
.\scripts\dev.ps1
```

---

## Configuração de Ambiente

Copie `.env.example` para `.env` e preencha:

| Variável | Descrição | Padrão |
|---|---|---|
| `APP_ENV` | Ambiente (`development`, `staging`, `production`) | `development` |
| `SECRET_KEY` | Chave JWT — mínimo 32 caracteres | *(obrigatório)* |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Validade do refresh token | `7` |
| `DATABASE_URL` | URL PostgreSQL async (`postgresql+asyncpg://...`) | *(obrigatório)* |
| `SUPABASE_URL` | URL do projeto Supabase | *(opcional)* |
| `SUPABASE_SERVICE_KEY` | Service role key (bypass RLS) | *(obrigatório em prod)* |
| `REDIS_URL` | URL do Redis | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Broker Celery (mesmo Redis) | `redis://localhost:6379/0` |
| `CORS_ORIGINS` | Origens permitidas (separadas por vírgula) | `http://localhost:3000` |
| `RATE_LIMIT_PER_MINUTE` | Requisições/min por IP | `60` |
| `LOG_LEVEL` | Nível de log (`DEBUG`, `INFO`, `WARNING`) | `INFO` |
| `LOG_FORMAT` | Formato dos logs (`json`, `console`) | `json` |

---

## Endpoints da API

Base URL: `http://localhost:8000/api/v1`

### Autenticação

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `POST` | `/auth/login` | Login com email e senha | Público |
| `POST` | `/auth/refresh` | Renovar access token | Público |
| `POST` | `/auth/logout` | Revogar refresh token | Público |
| `POST` | `/auth/logout-all` | Encerrar todas as sessões | JWT |
| `POST` | `/auth/forgot-password` | Solicitar redefinição de senha | Público |
| `POST` | `/auth/reset-password` | Redefinir senha com token | Público |
| `POST` | `/auth/change-password` | Alterar senha do usuário logado | JWT |

### Usuários

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/users/me` | Dados do usuário logado | Qualquer |
| `GET` | `/users` | Listar usuários | Admin |
| `POST` | `/users` | Criar usuário | Admin |
| `GET` | `/users/{id}` | Detalhes do usuário | Admin |
| `PATCH` | `/users/{id}` | Atualizar usuário | Admin / Próprio |
| `DELETE` | `/users/{id}` | Remover usuário (soft delete) | Admin |

### Motoristas

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/drivers` | Listar motoristas | Qualquer |
| `POST` | `/drivers` | Cadastrar motorista | Admin / Operador |
| `GET` | `/drivers/{id}` | Detalhes do motorista | Qualquer |
| `PATCH` | `/drivers/{id}` | Atualizar motorista | Admin / Operador |
| `DELETE` | `/drivers/{id}` | Remover (soft delete) | Admin / Operador |

### Frota (Caminhões)

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/trucks` | Listar caminhões | Qualquer |
| `POST` | `/trucks` | Cadastrar caminhão | Admin / Operador |
| `GET` | `/trucks/{id}` | Detalhes do caminhão | Qualquer |
| `PATCH` | `/trucks/{id}` | Atualizar caminhão | Admin / Operador |
| `DELETE` | `/trucks/{id}` | Remover (soft delete) | Admin / Operador |

### Clientes

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/clients` | Listar clientes | Qualquer |
| `POST` | `/clients` | Cadastrar cliente | Admin / Operador |
| `GET` | `/clients/{id}` | Detalhes do cliente | Qualquer |
| `PATCH` | `/clients/{id}` | Atualizar cliente | Admin / Operador |
| `DELETE` | `/clients/{id}` | Remover (soft delete) | Admin / Operador |

### Fretes

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/freights` | Listar fretes (filtros: status, client, driver, truck) | Qualquer |
| `POST` | `/freights` | Criar frete | Admin / Operador |
| `GET` | `/freights/{id}` | Detalhes do frete | Qualquer |
| `PATCH` | `/freights/{id}` | Atualizar frete / mudar status | Admin / Operador |
| `DELETE` | `/freights/{id}` | Remover (soft delete) | Admin / Operador |
| `POST` | `/freights/{id}/costs` | Adicionar custo ao frete | Admin / Operador |

**Transições de status válidas:**

```
orcamento → confirmado | cancelado
confirmado → em_coleta | cancelado
em_coleta → em_transporte | cancelado
em_transporte → entregue | cancelado
```

### Manutenção

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/maintenance` | Listar manutenções (filtros: truck, status, tipo) | Qualquer |
| `GET` | `/maintenance/alerts` | Alertas de manutenção próximos (`?days_ahead=30`) | Qualquer |
| `POST` | `/maintenance` | Criar registro de manutenção | Admin / Operador |
| `GET` | `/maintenance/{id}` | Detalhes | Qualquer |
| `PATCH` | `/maintenance/{id}` | Atualizar | Admin / Operador |
| `DELETE` | `/maintenance/{id}` | Remover | Admin / Operador |

### Financeiro

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/finance/cash-flow` | Fluxo de caixa consolidado | Admin / Financeiro |
| `GET` | `/finance` | Listar lançamentos (filtros: tipo, status, categoria) | Admin / Financeiro |
| `POST` | `/finance` | Criar lançamento financeiro | Admin / Financeiro |
| `GET` | `/finance/{id}` | Detalhes do lançamento | Admin / Financeiro |
| `PATCH` | `/finance/{id}` | Atualizar lançamento | Admin / Financeiro |
| `DELETE` | `/finance/{id}` | Remover (soft delete) | Admin / Financeiro |

### Rastreamento

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `POST` | `/tracking` | Adicionar atualização de rastreamento | Admin / Operador / Motorista |
| `GET` | `/tracking/{freight_id}/timeline` | Linha do tempo do frete | Qualquer |

### Dashboard

| Método | Endpoint | Descrição | Role |
|---|---|---|---|
| `GET` | `/dashboard/kpis` | KPIs consolidados | Admin / Operador / Financeiro |

### Health Check

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Status da aplicação |

---

## Autenticação e RBAC

### Fluxo de Autenticação

```
1. POST /api/v1/auth/login
   → Retorna: access_token (JWT, 30min) + refresh_token (opaque, 7 dias)

2. Requests autenticados:
   Authorization: Bearer <access_token>

3. Renovar token:
   POST /api/v1/auth/refresh  { "refresh_token": "..." }
   → Novo access_token + novo refresh_token (rotação automática)

4. Logout:
   POST /api/v1/auth/logout  { "refresh_token": "..." }
```

### Perfis de Acesso (RBAC)

| Role | Descrição | Endpoints |
|---|---|---|
| `admin` | Acesso total ao sistema | Todos |
| `operador` | Gestão operacional | Fretes, motoristas, frota, clientes, rastreamento |
| `financeiro` | Módulo financeiro | Financeiro, dashboard, relatórios |
| `motorista` | Acesso restrito | Rastreamento (próprios fretes), leitura básica |

---

## Banco de Dados

### Tabelas (`tm_*`)

| Tabela | Descrição |
|---|---|
| `tm_users` | Usuários do sistema |
| `tm_refresh_tokens` | Tokens de refresh (rotação) |
| `tm_clients` | Clientes |
| `tm_drivers` | Motoristas |
| `tm_trucks` | Frota de caminhões |
| `tm_freights` | Fretes |
| `tm_freight_costs` | Custos adicionais por frete |
| `tm_freight_attachments` | Comprovantes e arquivos |
| `tm_maintenance` | Registros de manutenção |
| `tm_finance_entries` | Lançamentos financeiros |
| `tm_tracking_updates` | Atualizações de rastreamento |

Todas as tabelas possuem:
- UUID como chave primária (`gen_random_uuid()`)
- `created_at` / `updated_at` com trigger automático
- `deleted_at` para soft delete (onde aplicável)
- RLS (Row Level Security) habilitado no Supabase

### Migrations

```bash
# Criar nova migration
poetry run alembic revision --autogenerate -m "descricao"

# Aplicar migrations pendentes
poetry run alembic upgrade head

# Rollback (uma migration)
poetry run alembic downgrade -1
```

---

## Testes

```bash
# Todos os testes com relatório de cobertura
poetry run pytest

# Modo verbose
poetry run pytest -v

# Módulo específico
poetry run pytest tests/auth/ -v
poetry run pytest tests/freights/ -v

# Com relatório HTML de cobertura
poetry run pytest --cov-report=html
# Abrir: htmlcov/index.html

# Somente testes rápidos (sem cobertura)
poetry run pytest --no-cov
```

**Resultado atual:** 74 testes passando — cobertura de **80.77%**

---

## Qualidade de Código

```bash
# Lint com autofix
poetry run ruff check . --fix

# Formatar código
poetry run ruff format .

# Type checking
poetry run mypy app/

# Tudo de uma vez (pre-commit)
poetry run pre-commit run --all-files
```

### Instalar hooks de pre-commit

```bash
poetry run pre-commit install
```

---

## Docker

### Desenvolvimento

```bash
# Subir todos os serviços (API + Worker + Redis + Nginx)
docker-compose up -d

# Ver logs da API
docker-compose logs -f api

# Reiniciar apenas a API
docker-compose restart api

# Parar tudo
docker-compose down

# Parar e remover volumes
docker-compose down -v
```

### Serviços no Docker Compose

| Serviço | Porta | Descrição |
|---|---|---|
| `api` | `8000` | FastAPI + Uvicorn (hot reload) |
| `worker` | — | Celery worker |
| `redis` | `6379` | Cache e broker Celery |
| `nginx` | `80` | Reverse proxy |

---

## Workers e Tasks

O Celery executa tarefas em background, agendadas automaticamente:

| Task | Frequência | Descrição |
|---|---|---|
| `check_maintenance_alerts` | A cada 1 hora | Verifica manutenções com vencimento em ≤7 dias |
| `mark_overdue_payments` | A cada 24 horas | Marca lançamentos vencidos como `vencido` |
| `cleanup_expired_tokens` | A cada 1 hora | Remove refresh tokens expirados do banco |

### Iniciar worker manualmente

```bash
# Worker
poetry run celery -A app.workers.celery_app:celery_app worker --loglevel=info

# Worker + Beat (scheduler)
poetry run celery -A app.workers.celery_app:celery_app worker --beat --loglevel=info
```

---

## Credenciais Padrão (seed)

| Campo | Valor |
|---|---|
| Email | `admin@tmtransportadora.com.br` |
| Senha | `Admin@123!` |
| Role | `admin` |

> **Atenção:** Troque imediatamente em produção!

---

## Segurança

- Senhas hasheadas com **Argon2id** (memória: 64MB, iterações: 3)
- JWT com expiração curta (30 min) + refresh token rotation (7 dias)
- Hash SHA-256 dos refresh tokens no banco (nunca o token em plain text)
- Rate limiting por IP via SlowAPI
- CORS configurável por variável de ambiente
- RLS habilitado em todas as tabelas `tm_*` no Supabase
- Soft delete — dados nunca são apagados fisicamente
- Request ID por requisição para correlação de logs

---

## Contribuindo

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/minha-funcionalidade`
3. Instale as dependências e os hooks: `poetry install && pre-commit install`
4. Faça as alterações com testes
5. Verifique qualidade: `ruff check . && pytest`
6. Commit seguindo [Conventional Commits](https://www.conventionalcommits.org/)
7. Abra um Pull Request

---

## Licença

MIT License — veja [LICENSE](../LICENSE) para detalhes.
