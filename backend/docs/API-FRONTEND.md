# TM Transportadora — Referência de API para Frontend

Documentação das rotas REST consumidas pelo frontend. Gerada a partir do código em `backend/app/`.

---

## Informações gerais

| Item | Valor |
|------|-------|
| Base URL (dev) | `http://localhost:8000` |

### Padronização automática de dados (backend)

O backend **normaliza o payload antes de salvar**. O frontend pode enviar dados “sujos”; a API corrige:

| Tipo | Exemplo entrada | Salvo como |
|------|-----------------|------------|
| Texto (nome, marca, cidade…) | `"  joão silva  "` | `"JOÃO SILVA"` |
| E-mail | `"Admin@Email.COM"` | `"admin@email.com"` |
| CPF/CNPJ/telefone/CEP | `"529.982.247-25"` | `"52998224725"` |
| Placa | `"abc-1d23"` | `"ABC1D23"` |
| UF | `"sp"` | `"SP"` |
| Número BR | `"30.000,50"` ou `"2,5"` | `30000.5` / `2.5` |
| Ano | `"2.022"` | `2022` |
| Categoria CNH | `"e"` | `"E"` (enum) |

Campos em **inglês** (`name`, `plate`, `cnh_number`…) também são aceitos nos módulos drivers/trucks.
| Prefixo da API | `/api/v1` |
| Formato | JSON |
| Autenticação | JWT Bearer (`Authorization: Bearer <access_token>`) |
| Docs interativas | `/docs`, `/redoc`, `/openapi.json` (desabilitadas em produção) |
| Rate limit | 60 req/min por IP (padrão) |

### Resposta de erro padrão

```json
{
  "detail": "mensagem ou array de erros de validação"
}
```

| Status | Significado |
|--------|-------------|
| `400` | Requisição inválida |
| `401` | Não autenticado / token inválido |
| `403` | Sem permissão (role ou regra de negócio) |
| `404` | Recurso não encontrado |
| `409` | Conflito (email, CPF, placa duplicados) |
| `422` | Erro de validação Pydantic |
| `429` | Rate limit excedido |
| `503` | Banco indisponível |

---

## Autenticação e sessão

### Fluxo recomendado para o frontend

```
1. POST /api/v1/auth/login          → guardar access_token + refresh_token + user
2. Requests autenticados            → header Authorization: Bearer <access_token>
3. Token expirado (401)             → POST /api/v1/auth/refresh
4. Logout                           → POST /api/v1/auth/logout (revoga refresh)
5. Perfil do usuário logado         → GET /api/v1/auth/me (formato frontend)
```

### LoginResponse (login, refresh, register-tenant)

```typescript
interface LoginResponse {
  tokens: {
    access_token: string;
    refresh_token: string;
    token_type: "bearer";
    expires_in: number; // segundos (padrão: 1800 = 30 min)
  };
  user: AuthUser;
}

interface AuthUser {
  id: string;           // UUID
  email: string;
  name: string;
  role: "admin" | "operacional" | "financeiro" | "motorista";
  tenant_id: string;    // hoje = user.id (single-tenant)
  branch_id: string | null;
  permissions: string[];
}
```

> **Mapeamento de role:** backend `operador` → frontend `operacional`.

### Permissões por role (campo `permissions`)

| Role frontend | Permissões |
|---------------|------------|
| `admin` | `dashboard:read`, `fleet:read`, `fleet:write`, `drivers:read`, `drivers:write`, `freight:read`, `freight:write`, `freight:status`, `finance:read`, `tenant:admin` |
| `operacional` | `dashboard:read`, `fleet:read`, `fleet:write`, `drivers:read`, `drivers:write`, `freight:read`, `freight:write`, `freight:status` |
| `financeiro` | `dashboard:read`, `finance:read`, `freight:read` |
| `motorista` | `freight:read`, `freight:status` |

---

## Paginação

Endpoints de listagem aceitam:

| Query | Tipo | Padrão | Limites |
|-------|------|--------|---------|
| `page` | int | `1` | min `1` |
| `size` | int | `20` | min `1`, max `100` |

Resposta paginada:

```typescript
interface PagedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  page_size: number;  // alias de size (compatibilidade)
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}
```

---

## Enums

```typescript
type UserRole = "admin" | "operador" | "financeiro" | "motorista";

type TruckStatus = "disponivel" | "em_viagem" | "em_manutencao" | "inativo";

type DriverStatus = "ativo" | "inativo" | "suspenso" | "ferias";

type FreightStatus =
  | "orcamento"
  | "confirmado"
  | "em_coleta"
  | "em_transporte"
  | "entregue"
  | "cancelado";

type MaintenanceType = "preventiva" | "corretiva";
type MaintenanceStatus = "agendada" | "em_andamento" | "concluida" | "cancelada";

type FinanceEntryType = "receita" | "despesa";
type FinanceEntryStatus = "pendente" | "pago" | "cancelado" | "vencido";

type TrackingStatus =
  | "coletado"
  | "em_transito"
  | "saiu_para_entrega"
  | "tentativa_entrega"
  | "entregue"
  | "devolvido";

type CNHCategory = "A" | "B" | "C" | "D" | "E" | "AB" | "AC" | "AD" | "AE";
```

---

## Health

### `GET /health`

Público. Sem autenticação.

**Resposta 200:**
```json
{ "status": "ok", "version": "0.1.0" }
```

---

## Auth — `/api/v1/auth`

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/login` | Público | Login |
| POST | `/register-tenant` | Público | Cadastro inicial (admin) |
| GET | `/me` | JWT | Perfil no formato frontend |
| POST | `/refresh` | Público | Renovar tokens |
| POST | `/logout` | Público | Revogar refresh token |
| POST | `/logout-all` | JWT | Encerrar todas as sessões |
| POST | `/forgot-password` | Público | Solicitar reset |
| POST | `/reset-password` | Público | Redefinir senha |
| POST | `/change-password` | JWT | Alterar senha logado |

### POST `/auth/login`

**Body:**
```json
{ "email": "admin@tmtransportadora.com.br", "password": "Admin@123!" }
```

**Resposta 200:** `LoginResponse`

**Erros:** `401` credenciais inválidas ou conta desativada

---

### POST `/auth/register-tenant`

**Body:**
```json
{
  "tenant_name": "Minha Transportadora",
  "admin_name": "João Silva",
  "email": "joao@empresa.com.br",
  "password": "Senha@123",
  "document": "12345678000199"
}
```

| Campo | Regras |
|-------|--------|
| `tenant_name` | 2–150 chars |
| `admin_name` | 2–150 chars |
| `email` | Email válido |
| `password` | min 8 chars |
| `document` | opcional |

**Resposta 201:** `LoginResponse`  
**Erros:** `409` email já cadastrado

---

### GET `/auth/me`

**Resposta 200:** `AuthUser` (mesmo shape de `user` no login)

> Preferir este endpoint no frontend (inclui `permissions` e `role` mapeada).

---

### POST `/auth/refresh`

**Body:**
```json
{ "refresh_token": "<refresh_token>" }
```

**Resposta 200:** `LoginResponse` (novo par de tokens — rotação automática)

---

### POST `/auth/logout`

**Body:**
```json
{ "refresh_token": "<refresh_token>" }
```

**Resposta 200:**
```json
{ "message": "Logout realizado com sucesso" }
```

---

### POST `/auth/logout-all`

**Resposta 200:**
```json
{ "message": "Todas as sessões encerradas" }
```

---

### POST `/auth/forgot-password`

**Body:** `{ "email": "user@email.com" }`

**Resposta 200:** mensagem genérica (não revela se email existe)

---

### POST `/auth/reset-password`

**Body:**
```json
{ "token": "<reset_token>", "new_password": "NovaSenha@123" }
```

---

### POST `/auth/change-password`

**Body:**
```json
{ "current_password": "...", "new_password": "..." }
```

---

## Users — `/api/v1/users`

| Método | Rota | Auth | Role |
|--------|------|------|------|
| GET | `/me` | JWT | qualquer |
| GET | `/` | JWT | admin |
| POST | `/` | JWT | admin |
| GET | `/{user_id}` | JWT | admin |
| PATCH | `/{user_id}` | JWT | self ou admin |
| DELETE | `/{user_id}` | JWT | admin |

### GET `/users/me`

Retorna perfil no formato **backend** (campo `nome`, role `operador` etc.).

> Para o frontend, usar **`GET /auth/me`**.

**Resposta 200:**
```typescript
interface UserRead {
  id: string;
  nome: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
```

---

### GET `/users`

**Query:** `page`, `size`, `role?`, `is_active?`, `search?`

**Resposta 200:** `PagedResponse<UserListResponse>`

---

### POST `/users`

**Body:**
```json
{
  "nome": "Maria Operadora",
  "email": "maria@empresa.com.br",
  "password": "Senha@123",
  "role": "operador",
  "is_active": true
}
```

Senha: min 8 chars, 1 maiúscula, 1 número.

**Resposta 201:** `UserRead`  
**Erros:** `409` email duplicado

---

### PATCH `/users/{user_id}`

**Body (todos opcionais):**
```json
{ "nome": "...", "email": "...", "role": "...", "is_active": true }
```

- Usuário comum: só edita o próprio perfil (`nome`, `email`)
- Admin: pode alterar `role` e `is_active` de qualquer usuário

---

### DELETE `/users/{user_id}`

**Resposta 204** (sem body)  
**Erros:** `400` não pode excluir a si mesmo

---

## Drivers — `/api/v1/drivers`

Leitura: qualquer usuário autenticado.  
Escrita (POST/PATCH/DELETE): **admin** ou **operador**.

Respostas usam **nomes em inglês** (compatível com frontend).

### GET `/drivers`

**Query:** `page`, `size`, `status?`, `search?`

**Resposta 200:** `PagedResponse<DriverListItem>`

```typescript
interface DriverListItem {
  id: string;
  tenant_id: string;       // "default"
  name: string;
  cpf: string | null;
  cnh_number: string;
  cnh_category: string;
  cnh_expires_at: string;  // ISO date
  status: DriverStatus;
  created_at: string;
}
```

---

### POST `/drivers`

**Body (português — request):**
```json
{
  "nome": "Carlos Motorista",
  "cpf": "12345678909",
  "telefone": "11999998888",
  "email": "carlos@email.com",
  "cnh": "12345678901",
  "cnh_category": "E",
  "cnh_expiry": "2027-12-31",
  "status": "ativo",
  "observacoes": null,
  "user_id": null
}
```

**Resposta 201:** `DriverRead` (campos em inglês)

```typescript
interface DriverRead {
  id: string;
  tenant_id: string;
  name: string;
  cpf: string | null;
  cnh_number: string;
  cnh_category: string;
  cnh_expires_at: string;
  status: DriverStatus;
  phone: string | null;
  photo_url: string | null;
  commission_pct: number | null;
  created_at: string;
}
```

**Erros:** `409` CPF ou CNH duplicado, `422` CPF/CNH inválido

---

### GET `/drivers/{driver_id}`

**Resposta 200:** `DriverRead`

---

### PATCH `/drivers/{driver_id}`

**Body (opcionais):** `nome`, `telefone`, `email`, `cnh_category`, `cnh_expiry`, `status`, `observacoes`

**Resposta 200:** `DriverRead`

---

### DELETE `/drivers/{driver_id}`

**Resposta 204**

---

## Trucks — `/api/v1/trucks`

Leitura: JWT. Escrita: **admin** ou **operador**.

### GET `/trucks`

**Query:** `page`, `size`, `status?`, `search?`

**Resposta 200:** `PagedResponse<TruckListItem>`

```typescript
interface TruckListItem {
  id: string;
  tenant_id: string;
  plate: string;
  brand: string;
  model: string;
  year: number;
  type: "cavalo";
  capacity_kg: number | null;
  status: TruckStatus;
  mileage_km: number;
  created_at: string;
}
```

---

### POST `/trucks`

**Body (português — request):**
```json
{
  "placa": "ABC1D23",
  "modelo": "FH 540",
  "marca": "Volvo",
  "ano": 2022,
  "capacidade_kg": 30000,
  "consumo_km_l": 2.5,
  "km_atual": 150000,
  "status": "disponivel",
  "renavam": null,
  "chassi": null,
  "cor": "Branco",
  "observacoes": null
}
```

**Resposta 201:** `TruckRead` (inglês)

```typescript
interface TruckRead {
  id: string;
  tenant_id: string;
  branch_id: string | null;
  plate: string;
  renavam: string | null;
  brand: string;
  model: string;
  year: number;
  type: "cavalo";
  capacity_kg: number | null;
  avg_consumption_km_l: number | null;
  status: TruckStatus;
  mileage_km: number;
  insurance_expires_at: string | null;
  license_expires_at: string | null;
  created_at: string;
}
```

**Erros:** `409` placa duplicada

---

### PATCH `/trucks/{truck_id}`

**Body (opcionais):** `modelo`, `marca`, `capacidade_kg`, `consumo_km_l`, `km_atual`, `status`, `cor`, `observacoes`

---

### DELETE `/trucks/{truck_id}`

**Resposta 204**  
**Erros:** `403` caminhão com status `em_viagem`

---

## Clients — `/api/v1/clients`

Leitura: JWT. Escrita: **admin** ou **operador**.  
Request/response em **português**.

### Endereço (`AddressSchema`)

```typescript
interface Address {
  logradouro?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  cidade?: string;
  estado?: string;  // 2 chars (UF)
  cep?: string;
}
```

---

### GET `/clients`

**Query:** `page`, `size`, `is_active?`, `search?`

**Resposta 200:** `PagedResponse<ClientListItem>`

---

### POST `/clients`

**Body:**
```json
{
  "nome": "Cliente ABC Ltda",
  "cpf_cnpj": "12345678000199",
  "email": "contato@abc.com.br",
  "telefone": "1133334444",
  "endereco": { "cidade": "São Paulo", "estado": "SP" },
  "observacoes": null
}
```

**Erros:** `409` CPF/CNPJ duplicado, `422` documento inválido

---

### GET `/clients/{client_id}`

**Resposta 200:** `ClientRead` (com `endereco` como objeto JSON)

---

### PATCH `/clients/{client_id}`

**Body (opcionais):** `nome`, `email`, `telefone`, `endereco`, `observacoes`, `is_active`

---

### DELETE `/clients/{client_id}`

**Resposta 204** (soft delete)

---

## Freights — `/api/v1/freights`

Leitura: JWT. Escrita: **admin** ou **operador**.  
Respostas em **inglês** (`FreightOrder` shape).

### Transições de status válidas

```
orcamento     → confirmado | cancelado
confirmado    → em_coleta  | cancelado
em_coleta     → em_transporte | cancelado
em_transporte → entregue   | cancelado
entregue      → (final)
cancelado     → (final)
```

Fluxo de avanço automático (`advance-status`):
```
orcamento → confirmado → em_coleta → em_transporte → entregue
```

---

### GET `/freights`

**Query:** `page`, `size`, `status?`, `client_id?`, `driver_id?`, `truck_id?`

**Resposta 200:** `PagedResponse<FreightListItem>`

```typescript
interface FreightListItem {
  id: string;
  tenant_id: string;
  code: string;              // "OF-" + primeiros 8 chars do UUID
  customer_id: string;
  origin_city: string;
  origin_state: string;
  destination_city: string;
  destination_state: string;
  value_brl: number;
  status: FreightStatus;
  truck_id: string | null;
  driver_id: string | null;
  created_at: string;
  updated_at: string;
}
```

---

### POST `/freights`

**Body (português — request):**
```json
{
  "client_id": "uuid",
  "driver_id": null,
  "truck_id": null,
  "origem": {
    "logradouro": "Rua A",
    "cidade": "São Paulo",
    "estado": "SP"
  },
  "destino": {
    "logradouro": "Av B",
    "cidade": "Curitiba",
    "estado": "PR"
  },
  "valor_frete": 5500.00,
  "status": "orcamento",
  "data_coleta": "2026-06-01T08:00:00Z",
  "data_entrega_prevista": "2026-06-03T18:00:00Z",
  "distancia_km": 410,
  "observacoes": "Carga frágil",
  "costs": [
    { "tipo": "pedagio", "valor": 120.50, "descricao": "Rodovias" }
  ]
}
```

**Resposta 201:** `FreightRead`

```typescript
interface FreightRead {
  id: string;
  tenant_id: string;
  branch_id: string | null;
  code: string;
  customer_id: string;
  customer_name: string | null;
  origin_city: string;
  origin_state: string;
  destination_city: string;
  destination_state: string;
  cargo_description: string;
  weight_kg: number;
  value_brl: number;
  freight_type: "carga_geral";
  status: FreightStatus;
  deadline_at: string | null;
  responsible_id: string | null;
  truck_id: string | null;
  driver_id: string | null;
  created_at: string;
  updated_at: string;
}
```

---

### PATCH `/freights/{freight_id}`

**Body (opcionais):** `driver_id`, `truck_id`, `valor_frete`, `status`, `data_coleta`, `data_entrega_prevista`, `data_entrega_real`, `distancia_km`, `observacoes`

**Erros:** `403` transição de status inválida

---

### POST `/freights/{freight_id}/advance-status`

Avança um passo no fluxo linear. Sem body.

**Erros:** `403` se `cancelado` ou já `entregue`

---

### PATCH `/freights/{freight_id}/status`

**Body:** `{ "status": "confirmado" }`

Atualiza status com validação de transição.

---

### DELETE `/freights/{freight_id}`

**Resposta 204**  
**Erros:** `403` só permite excluir `orcamento` ou `cancelado`

---

### POST `/freights/{freight_id}/costs`

**Body:**
```json
{ "tipo": "combustivel", "valor": 800.00, "descricao": "Abastecimento" }
```

**Resposta 201:**
```typescript
interface FreightCost {
  id: string;
  tipo: string;
  valor: number;
  descricao: string | null;
  created_at: string;
}
```

---

## Maintenance — `/api/v1/maintenance`

Leitura: JWT. Escrita: **admin** ou **operador**.

> Rota `/alerts` registrada **antes** de `/{maintenance_id}` — não conflita.

### GET `/maintenance`

**Query:** `page`, `size`, `truck_id?`, `status?`, `tipo?`

---

### GET `/maintenance/alerts`

**Query:** `days_ahead` (padrão `30`, max `365`)

**Resposta 200:** array de `MaintenanceRead`

---

### POST `/maintenance`

**Body:**
```json
{
  "truck_id": "uuid",
  "tipo": "preventiva",
  "descricao": "Troca de óleo e filtros",
  "km_atual": 150000,
  "km_proxima": 160000,
  "custo": 850.00,
  "fornecedor": "Oficina XYZ",
  "data_prevista": "2026-06-15T09:00:00Z",
  "status": "agendada"
}
```

---

### GET `/maintenance/{maintenance_id}`

### PATCH `/maintenance/{maintenance_id}`

### DELETE `/maintenance/{maintenance_id}`

**Resposta 204**

---

## Finance — `/api/v1/finance`

**Todos os endpoints:** JWT + role **admin** ou **financeiro**.

### GET `/finance/cash-flow`

**Resposta 200:**
```typescript
interface CashFlow {
  total_receitas: number;
  total_despesas: number;
  saldo: number;
  receitas_pendentes: number;
  despesas_pendentes: number;
  receitas_pagas: number;
  despesas_pagas: number;
}
```

---

### GET `/finance`

**Query:** `page`, `size`, `tipo?`, `status?`, `categoria?`, `freight_id?`, `vencimento_from?`, `vencimento_to?`

---

### POST `/finance`

**Body:**
```json
{
  "tipo": "receita",
  "categoria": "frete",
  "descricao": "Pagamento frete #123",
  "valor": 5500.00,
  "freight_id": "uuid",
  "data_vencimento": "2026-06-10",
  "data_pagamento": null,
  "status": "pendente",
  "observacoes": null
}
```

---

### GET `/finance/{entry_id}`

### PATCH `/finance/{entry_id}`

### DELETE `/finance/{entry_id}`

**Resposta 204**

---

## Abastecimento — `/api/v1/fuel`

Registros de abastecimento **vinculados ao frete e motorista** em viagem. Valores aceitam formato BR (`1.200,75`, `150,5`). Ao salvar, o backend:

- Cria custo do frete (`tipo: COMBUSTIVEL`) em `tm_freight_costs`
- Gera notificação para admin/operador/financeiro
- Mantém `freight_id`, `driver_id` e `truck_id` (do frete) em `tm_fuel_refills`

Escrita: **admin**, **operador** ou **motorista** (motorista só no próprio frete; `driver_id` deve ser o motorista vinculado ao frete).

### GET `/fuel/eligible-freights` — Fretes para seleção no abastecimento

Lista fretes **em viagem** (`confirmado`, `em_coleta`, `em_transporte`). **Não inclui** entregues, cancelados nem orçamento.

- **Motorista:** apenas fretes em que está vinculado como `driver_id`
- **Admin/operador:** todos os fretes elegíveis com motorista atribuído

**Resposta 200:** array de `ActiveFreightContext` (mesmos campos do frete ativo).

---

### GET `/fuel/active-freight` — Frete em andamento (motorista)

Pré-preenche a tela de abastecimento com o frete ativo (`confirmado`, `em_coleta`, `em_transporte`).

**Resposta 200:**
```typescript
interface ActiveFreightContext {
  freight_id: string;
  freight_code: string;  // ex: OF-A1B2C3D4
  status: string;
  driver_id: string;
  driver_name: string;
  truck_id: string | null;
  truck_plate: string | null;
  origin_city: string;
  origin_state: string;
  destination_city: string;
  destination_state: string;
}
```

**Erros:** `404` se não houver frete em andamento; `403` se não for motorista.

---

### POST `/fuel` — Registrar abastecimento

**Body (campos PT ou aliases EN):**
```json
{
  "freight_id": "uuid",
  "driver_id": "uuid",
  "litros": "150,5",
  "valor_total": "1.200,75",
  "valor_litro": "7,98",
  "km_atual": 185420,
  "posto": "Posto Shell",
  "cidade": "Joinville",
  "estado": "SC",
  "observacoes": "Tanque cheio",
  "data_abastecimento": "2026-05-22T18:00:00Z"
}
```

Aliases aceitos: `freightId`, `driverId`, `liters` → `litros`, `value`/`valor`/`amount` → `valor_total`, `gasStation` → `posto`, `currentKm` → `km_atual`.

`driver_id` é opcional: usa o motorista do frete. Motorista logado não precisa enviar `driver_id`.

**Resposta 201:**
```typescript
interface FuelRefillCreated {
  id: string;
  freight_id: string;
  driver_id: string;
  truck_id: string | null;
  litros: number;
  valor_total: number;
  valor_litro: number | null;  // calculado se omitido
  km_atual: number | null;
  posto: string | null;
  cidade: string | null;
  estado: string | null;
  freight_cost_id: string;
  freight_code: string;
  notification_id: string;
  created_at: string;
}
```

---

### GET `/fuel/freight/{freight_id}` — Lista por frete

**Query:** `page`, `size`

---

### GET `/fuel/freight/{freight_id}/summary` — Totais do frete

```typescript
interface FuelFreightSummary {
  freight_id: string;
  freight_code: string;
  total_litros: number;
  total_valor: number;
  refills_count: number;
  driver_id: string | null;
  driver_name: string | null;
  truck_plate: string | null;
}
```

---

### GET `/fuel/{refill_id}`

---

## Tracking — `/api/v1/tracking`

### POST `/tracking` — Registrar ocorrência (motorista/operador)

Escrita: **admin**, **operador** ou **motorista**.

Ao criar uma ocorrência, o backend **gera automaticamente uma notificação** para o centro de alertas (admin/operador/financeiro).

**Body:**
```json
{
  "freight_id": "uuid",
  "status": "em_transito",
  "descricao": "Parada para abastecimento",
  "latitude": -24.487,
  "longitude": -47.844,
  "cidade": "registro",
  "estado": "sp",
  "evento_at": "2026-06-02T14:30:00Z"
}
```

**Resposta 201:**
```typescript
interface TrackingUpdateCreated {
  id: string;
  freight_id: string;
  status: TrackingStatus;
  descricao: string | null;
  cidade: string | null;
  estado: string | null;
  evento_at: string;
  created_at: string;
  status_label: string;
  notification_id: string;  // ID da notificação criada
}
```

---

### GET `/tracking/{freight_id}/detail` — Tela de rastreamento de carga

Payload completo para a tela de rastreamento: resumo do frete + linha do tempo + última ocorrência.

**Resposta 200:**
```typescript
interface TrackingFreightDetail {
  freight: {
    id: string;
    code: string;              // OF-XXXXXXXX
    status: FreightStatus;
    customer_id: string;
    customer_name: string | null;
    driver_id: string | null;
    driver_name: string | null;
    truck_id: string | null;
    truck_plate: string | null;
    origin_city: string;
    origin_state: string;
    destination_city: string;
    destination_state: string;
    value_brl: number;
  };
  current_status: TrackingStatus | null;
  latest_occurrence: TrackingUpdate | null;
  timeline: TrackingUpdate[];   // ordem cronológica (mais antiga → mais recente)
  total_occurrences: number;
  unread_notifications: number; // badge global (admin/operador/financeiro)
  fuel_refills: FuelRefillCreated[];
  fuel_total_litros: number;
  fuel_total_valor: number;
}
```

**Uso no front:** rota `/rastreamento/[freightId]` deve consumir este endpoint.

---

### GET `/tracking/{freight_id}/timeline`

Versão simplificada (só linha do tempo).

**Resposta 200:**
```typescript
interface TrackingTimeline {
  freight_id: string;
  updates: TrackingUpdate[];
  current_status: TrackingStatus | null;
  total_occurrences: number;
}
```

---

## Notificações — `/api/v1/notifications`

Ocorrências de rastreamento aparecem como notificações para **admin**, **operador** e **financeiro** (badge + lista).

### GET `/notifications`

**Query:** `page`, `size`, `unread_only` (boolean)

**Resposta 200:**
```typescript
interface NotificationList {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

interface NotificationItem {
  id: string;
  freight_id: string;
  tracking_update_id: string;
  tipo: "tracking_occurrence";
  titulo: string;           // ex: "NOVA OCORRÊNCIA NO FRETE OF-A1B2C3D4"
  mensagem: string;
  autor_nome: string;
  freight_code: string;
  is_read: boolean;
  created_at: string;
  freight_status: string | null;
  tracking_status: TrackingStatus | null;
  cidade: string | null;
  estado: string | null;
}
```

**Uso no front:** ícone de sino / drawer de notificações; ao clicar, navegar para `/rastreamento/{freight_id}`.

---

### GET `/notifications/unread-count`

**Resposta 200:** `{ "unread_count": 3 }` — para badge no header.

---

### PATCH `/notifications/{notification_id}/read`

Marca uma notificação como lida para o usuário logado.

---

### POST `/notifications/read-all`

Marca todas como lidas.

**Resposta 200:** `{ "message": "...", "marked_count": 5 }`

---

## Dashboard — `/api/v1/dashboard`

**Todos:** JWT + role **admin**, **operador** ou **financeiro**.

### GET `/dashboard/kpis`

**Resposta 200:**
```typescript
interface DashboardKpis {
  freights_in_progress: number;
  active_trucks: number;
  available_drivers: number;
  monthly_revenue_brl: number;
  operational_costs_brl: number;
  maintenance_alerts: number;
  financial_pending: number;
}
```

---

### GET `/dashboard/freights-by-status`

**Resposta 200:**
```typescript
interface FreightStatusCount {
  status: string;
  count: number;
}[]
```

---

### GET `/dashboard/revenue-series`

**Query:** `days` (padrão `30`, max `365`)

**Resposta 200:**
```typescript
interface RevenuePoint {
  date: string;
  revenue: number;
}[]
```

---

## Matriz de permissões por módulo

| Módulo | GET (leitura) | POST/PATCH/DELETE (escrita) |
|--------|---------------|----------------------------|
| Auth (público) | — | login, refresh, logout, forgot/reset |
| Auth (JWT) | `/me` | change-password, logout-all |
| Users | `/me` (todos), list/detail (admin) | create/delete (admin), patch (self/admin) |
| Drivers | todos autenticados | admin, operador |
| Trucks | todos autenticados | admin, operador |
| Clients | todos autenticados | admin, operador |
| Freights | todos autenticados | admin, operador |
| Maintenance | todos autenticados | admin, operador |
| Finance | admin, financeiro | admin, financeiro |
| Tracking | timeline (todos) | add update: admin, operador, motorista |
| Dashboard | admin, operador, financeiro | — |

---

## Convenções request vs response

| Módulo | Request body | Response body |
|--------|--------------|---------------|
| Auth | português/inglês misto | inglês (`AuthUser`) |
| Users | português (`nome`) | português |
| Drivers | **português ou inglês** (`nome`/`name`, `cnh`/`cnh_number`, etc.) | **inglês** |
| Trucks | **português ou inglês** (`placa`/`plate`, `marca`/`brand`, etc.) | **inglês** |
| Clients | português | português |
| Freights | português | **inglês** |
| Maintenance | português | português |
| Finance | português | português |
| Tracking | português | português |
| Dashboard | — | **inglês** (KPIs flat) |

---

## Exemplo de cliente HTTP (TypeScript)

```typescript
const API_BASE = "http://localhost:8000/api/v1";

async function api<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(JSON.stringify(err.detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Login
const session = await api<LoginResponse>("/auth/login", {
  method: "POST",
  body: JSON.stringify({ email, password }),
});

// Listar fretes
const freights = await api<PagedResponse<FreightListItem>>(
  "/freights?page=1&size=20",
  {},
  session.tokens.access_token
);
```

---

## Credenciais de desenvolvimento (seed)

| Campo | Valor |
|-------|-------|
| Email | `admin@tmtransportadora.com.br` |
| Senha | `Admin@123!` |
| Role | `admin` |

---

## Changelog desta documentação

- **2026-05-22:** Documento inicial com 56 endpoints REST + health.
- Endpoints frontend-ready: drivers, trucks, freights, dashboard, auth/me.
- `GET /users/me` mantido para compatibilidade interna; frontend deve usar `GET /auth/me`.
