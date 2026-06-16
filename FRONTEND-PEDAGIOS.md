# Módulo de Pedágios — Guia de Integração Frontend

> **Destino:** Agente de Frontend TM Transportadora  
> **Data:** 2026-06-12  
> **Base URL:** `https://<api-host>/api/v1`  
> **Auth:** `Authorization: Bearer <jwt_token>`

---

## Visão Geral

O módulo de pedágios (`/tolls`) permite registrar e consultar pedágios pagos durante fretes ativos. Segue exatamente o mesmo padrão do módulo de abastecimento (`/fuel`) que já está integrado no front.

### Regras de acesso por papel

| Papel       | Registrar | Listar (todos) | Listar (próprios) | Ver por frete |
|-------------|-----------|----------------|-------------------|---------------|
| admin       | ✅        | ✅             | —                 | ✅            |
| operador    | ✅        | ✅             | —                 | ✅            |
| financeiro  | ❌        | ✅             | —                 | ✅            |
| motorista   | ✅ (só frete próprio) | — | ✅            | ✅ (só frete próprio) |

---

## Rotas da API

### 1. `POST /tolls` — Registrar pedágio

**Quem pode usar:** admin, operador, motorista (do frete)

**Body (aceita campos em inglês ou português):**

```json
{
  "freightId": "uuid-do-frete",
  "value": 14.80,
  "count": 1,
  "plaza": "Praça Pedro Moro",
  "highway": "BR-376",
  "city": "Ponta Grossa",
  "state": "PR",
  "notes": "Observação opcional",
  "tollDate": "2026-06-12T15:30:00.000Z"
}
```

**Aliases aceitos (todos mapeiam para o campo interno):**

| Campo frontend | Campo interno | Obrigatório |
|----------------|---------------|-------------|
| `freightId` / `freight_id` | `freight_id` | ✅ |
| `value` / `amount` / `tollValue` / `valor` | `valor` | ✅ |
| `count` / `tollCount` / `quantidade` | `quantidade` | Não (default: 1) |
| `plaza` / `tollPlaza` / `praca` | `praca` | Não |
| `highway` / `rodovia` | `rodovia` | Não |
| `city` / `cidade` | `cidade` | Não |
| `state` / `estado` | `estado` | Não |
| `notes` / `observacoes` | `observacoes` | Não |
| `tollDate` / `toll_at` / `data_pedagio` | `data_pedagio` | Não (default: agora) |
| `driverId` / `driver_id` | `driver_id` | Não (resolvido pelo frete) |

> **Nota sobre `quantidade`:** Representa o número de praças de pedágio nesta cobrança (útil quando o motorista paga múltiplas praças de uma vez, ex: 3 praças na mesma rodovia = `count: 3`).

> **Nota sobre `valor`:** É o **valor total** pago nesta cobrança (ex: 3 praças × R$ 4,90 = `value: 14.70`). Aceita formato BR com vírgula (`"14,70"`) ou ponto (`14.70`).

**Response `201 Created`:**

```json
{
  "id": "uuid-do-pedágio",
  "freightId": "...",
  "driverId": "...",
  "registradoPorUserId": "...",
  "freightCostId": "...",
  "valor": 14.80,
  "quantidade": 1,
  "praca": "PRAÇA PEDRO MORO",
  "rodovia": "BR-376",
  "cidade": "PONTA GROSSA",
  "estado": "PR",
  "observacoes": null,
  "dataPedagio": "2026-06-12T15:30:00Z",
  "createdAt": "2026-06-12T15:30:05Z",
  "freightCode": "OF-ABCD1234",
  "driverName": "JOÃO DA SILVA",
  "notificationId": "uuid-da-notificação"
}
```

> **Efeitos colaterais automáticos:**
> - Cria `FreightCost` com `tipo = "PEDAGIO"` no frete (visível na aba de custos do frete)
> - Cria entrada na `FinanceEntry` como despesa com `categoria = "Pedágio"` (visível no financeiro)
> - Gera notificação para admin/operador/financeiro (tipo `toll_charge`)

---

### 2. `GET /tolls` — Listar todos os pedágios (paginado)

**Query params:** `page` (default: 1) · `size` (default: 20, max: 100)

**Response:**

```json
{
  "items": [ /* TollChargeRead[] */ ],
  "total": 42,
  "page": 1,
  "size": 20,
  "pages": 3
}
```

> Motorista recebe apenas os pedágios dos próprios fretes.

---

### 3. `GET /tolls/{id}` — Buscar pedágio por ID

**Response:** `TollChargeRead` (mesmo formato do item em lista)

---

### 4. `GET /tolls/freight/{freightId}` — Pedágios de um frete específico

**Query params:** `page` · `size`

**Response:** `PagedResponse<TollChargeRead>` (mesmo formato de lista)

**Uso sugerido:** Aba "Pedágios" na tela de detalhes do frete.

---

### 5. `GET /tolls/freight/{freightId}/summary` — Resumo de pedágios do frete

**Response:**

```json
{
  "freightId": "...",
  "freightCode": "OF-ABCD1234",
  "status": "em_transporte",
  "driverId": "...",
  "driverName": "JOÃO DA SILVA",
  "totalValor": 89.40,
  "totalQuantidade": 6,
  "chargesCount": 3
}
```

| Campo | Descrição |
|-------|-----------|
| `totalValor` | Soma de todos os valores pagos em pedágios neste frete |
| `totalQuantidade` | Soma total de praças pagas (ex: 3 registros × 2 praças = 6) |
| `chargesCount` | Número de registros de pedágio no frete |

**Uso sugerido:** Card de resumo na tela do frete (ex: "Pedágios: R$ 89,40 — 6 praças").

---

### 6. `GET /tolls/eligible-freights` — Fretes elegíveis para registro de pedágio

Lista fretes em andamento (status: `confirmado`, `em_coleta`, `em_transporte`) que têm motorista vinculado.

**Response:** `EligibleFreightItem[]`

```json
[
  {
    "freightId": "...",
    "freightCode": "OF-ABCD1234",
    "status": "em_transporte",
    "driverId": "...",
    "driverName": "JOÃO DA SILVA",
    "truckId": "...",
    "truckPlate": "ABC1D23",
    "originCity": "CURITIBA",
    "originState": "PR",
    "destinationCity": "SÃO PAULO",
    "destinationState": "SP"
  }
]
```

> Motorista recebe apenas os próprios fretes. Admin/operador recebe todos.

**Uso sugerido:** Select/dropdown de frete na tela de registro de pedágio.

---

### 7. `GET /tolls/active-freight` — Frete ativo do motorista logado

**Disponível apenas para motoristas.** Retorna o frete em andamento para pré-preencher o formulário.

**Response:** `ActiveFreightContext` (mesmo formato de `EligibleFreightItem`)

```json
{
  "freightId": "...",
  "freightCode": "OF-ABCD1234",
  "status": "em_transporte",
  "driverId": "...",
  "driverName": "JOÃO DA SILVA",
  "truckId": "...",
  "truckPlate": "ABC1D23",
  "originCity": "CURITIBA",
  "originState": "PR",
  "destinationCity": "SÃO PAULO",
  "destinationState": "SP"
}
```

**Uso sugerido:** Ao abrir a tela de pedágio no app do motorista, chamar este endpoint primeiro para pré-preencher o `freightId` automaticamente.

**Erros possíveis:**
- `403 Forbidden` — usuário não é motorista
- `404 Not Found` — motorista não tem frete em andamento

---

## Estrutura do objeto `TollChargeRead`

```typescript
interface TollChargeRead {
  id: string;               // UUID
  freightId: string;        // UUID do frete
  driverId: string;         // UUID do motorista
  registradoPorUserId: string | null;  // UUID de quem registrou
  freightCostId: string | null;        // UUID do custo vinculado no frete
  valor: number;            // Valor total pago
  quantidade: number;       // Número de praças nesta cobrança
  praca: string | null;     // Nome da praça
  rodovia: string | null;   // Nome da rodovia
  cidade: string | null;    // Cidade
  estado: string | null;    // UF (2 chars)
  observacoes: string | null;
  dataPedagio: string;      // ISO datetime
  createdAt: string;        // ISO datetime
  freightCode: string | null; // Ex: "OF-ABCD1234"
  driverName: string | null;
}

interface TollChargeCreatedResponse extends TollChargeRead {
  notificationId: string | null;
}
```

> **Atenção:** O backend retorna os campos em `snake_case`. Se o frontend usa `camelCase`, aplique a transformação que já usa nos outros módulos (ex: `freight_id` → `freightId`).

---

## Notificações — novo tipo `toll_charge`

O centro de notificações (`GET /notifications`) agora inclui um novo tipo:

```typescript
// NotificationType atualizado
type NotificationType = 'tracking_occurrence' | 'fuel_refill' | 'toll_charge';
```

A notificação de pedágio inclui o campo adicional `toll_charge_id`:

```typescript
interface NotificationItemRead {
  // ...campos existentes...
  fuel_refill_id: string | null;
  toll_charge_id: string | null;  // NOVO
  tipo: 'tracking_occurrence' | 'fuel_refill' | 'toll_charge';
}
```

**Sugestão de ícone/cor para o frontend:**
- `tracking_occurrence` → ícone de mapa (já existente)
- `fuel_refill` → ícone de combustível (já existente)
- `toll_charge` → ícone de pedágio/portão (ex: `🛣️` ou ícone de cancela)

---

## Telas sugeridas

### Tela do Motorista — App Mobile

**Fluxo de registro de pedágio:**

1. Motorista abre "Registrar Pedágio"
2. Frontend chama `GET /tolls/active-freight` → pré-preenche o frete
3. Motorista preenche:
   - Valor total (obrigatório)
   - Quantidade de praças (default: 1)
   - Nome da praça (opcional)
   - Rodovia (opcional)
   - Cidade/Estado (opcional)
   - Observações (opcional)
   - Data/hora (default: agora)
4. Frontend chama `POST /tolls`
5. Exibe confirmação com valor e frete

### Tela Admin/Operador — Web

**Aba "Pedágios" na tela de detalhes do frete:**

1. Chamar `GET /tolls/freight/{freightId}/summary` → exibir card de resumo
2. Chamar `GET /tolls/freight/{freightId}` → listar todos os pedágios do frete
3. Botão "Registrar Pedágio" → abre modal com formulário (usa `POST /tolls`)

**Listagem geral de pedágios:**

1. Menu lateral "Pedágios" → `GET /tolls?page=1&size=20`
2. Filtros: por data, por motorista, por frete

---

## Tratamento de erros comuns

| HTTP | Situação | Mensagem |
|------|----------|----------|
| 400 | Frete sem motorista vinculado | `"Frete sem motorista vinculado. Atribua um motorista antes de registrar pedágio."` |
| 400 | Motorista errado no payload | `"O pedágio deve ser registrado pelo motorista vinculado ao frete"` |
| 400 | Frete não está ativo | `"Pedágio só pode ser registrado em frete confirmado, em coleta ou em transporte"` |
| 403 | Motorista tentando registrar no frete de outro | `"Somente o motorista do frete pode registrar pedágio"` |
| 403 | Financeiro tentando registrar | `"Acesso negado"` |
| 404 | Frete não encontrado | `"Frete não encontrado"` |
| 404 | Pedágio não encontrado | `"Pedágio não encontrado"` |
| 404 | Motorista sem frete ativo (active-freight) | `"Nenhum frete em andamento encontrado para este motorista"` |

---

## Migration — banco de dados

> **Para o time de DevOps/Backend:** A migration `20260612_030000_toll_charges.py` precisa ser aplicada antes do deploy.

```bash
cd backend
alembic upgrade head
```

Tabela criada: `tm_toll_charges`  
Coluna adicionada: `tm_freight_notifications.toll_charge_id`

---

## Exemplo de chamada completa (TypeScript/Axios)

```typescript
// Registrar pedágio como motorista
const response = await api.post('/tolls', {
  freightId: activeFreight.freightId,
  value: 14.80,
  count: 1,
  plaza: 'Praça Pedro Moro',
  highway: 'BR-376',
  city: 'Ponta Grossa',
  state: 'PR',
  tollDate: new Date().toISOString(),
});

// Buscar resumo de pedágios de um frete
const summary = await api.get(`/tolls/freight/${freightId}/summary`);
// summary.data.totalValor  → R$ total
// summary.data.totalQuantidade → total de praças
// summary.data.chargesCount → número de registros

// Listar pedágios do frete (paginado)
const list = await api.get(`/tolls/freight/${freightId}?page=1&size=20`);
// list.data.items → TollChargeRead[]
// list.data.total → total de registros
```
