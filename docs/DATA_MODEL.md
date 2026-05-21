# TicketFlow — Modelo de Datos

Cada servicio tiene su propia base de datos PostgreSQL. No existe un esquema compartido entre servicios; la comunicación se hace vía APIs REST y eventos RabbitMQ.

---

## auth-service — Base de datos: `users_db`

### Tabla `users`

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | PK, autoincremental | Identificador único del usuario |
| `name` | `VARCHAR(120)` | NOT NULL | Nombre completo |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE, INDEX | Correo electrónico (login) |
| `hashed_password` | `VARCHAR(255)` | NOT NULL | Contraseña bcrypt |
| `role` | `VARCHAR(20)` | NOT NULL, default `'Cliente'` | `Admin` \| `Agente` \| `Cliente` |
| `area` | `VARCHAR(100)` | NULL | Área de especialización (solo Agentes) |
| `created_at` | `TIMESTAMPTZ` | server default `now()` | Fecha de registro |
| `updated_at` | `TIMESTAMPTZ` | onupdate `now()` | Última modificación |

**Índices:** `email` (unique), `id` (PK)

---

## ticket-service — Base de datos: `tickets_db`

### Tabla `tickets`

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | PK, autoincremental | Identificador único |
| `title` | `VARCHAR(255)` | NOT NULL | Título del ticket |
| `description` | `TEXT` | NOT NULL | Descripción detallada |
| `category` | `VARCHAR(30)` | NOT NULL, default `'general'` | `general` \| `technical` \| `billing` \| `access` \| `other` |
| `priority` | `VARCHAR(20)` | NOT NULL, default `'low'` | `low` \| `medium` \| `high` \| `critical` |
| `status` | `VARCHAR(20)` | NOT NULL, default `'open'` | `open` \| `pending` \| `resolved` \| `closed` |
| `notes` | `TEXT` | NULL | Notas internas del agente / TICBot |
| `sla_breached` | `BOOLEAN` | NOT NULL, default `false` | Indica si se superó el SLA |
| `tic_area` | `VARCHAR(50)` | NOT NULL, default `'uncategorized'` | Área técnica asignada por el agente IA |
| `agent_processed` | `BOOLEAN` | NOT NULL, default `false` | Indica si TICBot ya procesó el ticket |
| `created_by` | `INTEGER` | NOT NULL, INDEX | ID del usuario en `auth-service` |
| `created_at` | `TIMESTAMPTZ` | server default `now()` | Fecha de creación |
| `updated_at` | `TIMESTAMPTZ` | onupdate `now()` | Última modificación |

**Índices:** `id` (PK), `created_by`  
**Relaciones:** `replies` (1:N con cascade delete)

---

### Tabla `replies`

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | PK, autoincremental | Identificador único |
| `ticket_id` | `INTEGER` | FK → `tickets.id` ON DELETE CASCADE | Ticket al que pertenece |
| `author_id` | `INTEGER` | NOT NULL | ID del autor (referencia a `auth-service`) |
| `author_name` | `VARCHAR(120)` | NOT NULL | Nombre del autor (denormalizado) |
| `text` | `TEXT` | NOT NULL | Contenido del mensaje |
| `is_internal` | `BOOLEAN` | NOT NULL, default `false` | `true` = nota interna (solo visible para agentes/admin) |
| `created_at` | `TIMESTAMPTZ` | server default `now()` | Fecha del mensaje |

**Índices:** `id` (PK), `ticket_id` (FK)

---

## notification-service — Base de datos: `notifications_db`

### Tabla `notifications`

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | PK, autoincremental | Identificador único |
| `user_id` | `INTEGER` | NOT NULL, INDEX | ID del destinatario (referencia a `auth-service`) |
| `type` | `VARCHAR(40)` | NOT NULL | Tipo de evento (ver catálogo de eventos) |
| `title` | `VARCHAR(255)` | NOT NULL | Título de la notificación |
| `message` | `TEXT` | NOT NULL | Cuerpo del mensaje |
| `ticket_id` | `INTEGER` | NULL, INDEX | Referencia opcional al ticket relacionado |
| `is_read` | `BOOLEAN` | NOT NULL, default `false` | Estado de lectura |
| `created_at` | `TIMESTAMPTZ` | server default `now()` | Fecha de creación |

**Índices:** `id` (PK), `user_id`, `ticket_id`

---

## agent-service — Base de datos: `agent_db` + `vector_db` (Qdrant)

El agent-service utiliza dos almacenes:

1. **PostgreSQL (`agent_db`):** almacena historial de conversaciones y notas internas generadas por TICBot.
2. **Qdrant (vector store):** almacena embeddings de la base de conocimiento para búsqueda semántica (`text-embedding-004`).

---

## Diagrama de relaciones entre servicios

```
auth-service (users_db)
  └─ users
       ↑ referenciado por created_by / author_id (no FK real, coordinado vía API)

ticket-service (tickets_db)
  └─ tickets 1──N replies

notification-service (notifications_db)
  └─ notifications
       ↑ creadas por consumer al recibir eventos RabbitMQ

agent-service (agent_db + qdrant)
  └─ accede a ticket-service vía REST
  └─ publica eventos a notification-service vía RabbitMQ
```

---

## Redis (datos temporales — no persistentes)

| Clave | TTL | Descripción |
|---|---|---|
| `ticket:{id}` | 10 s | Caché de ticket individual |
| `blacklist:{jti}` | ~24 h | JWT revocado (logout) |
| `rate:{ip}:{minuto}` | 60 s | Contador de rate limiting por IP |
| `sla_notif:{ticket_id}:{event_type}` | sin TTL | Dedup de notificaciones SLA (se escribe una vez) |
| `email_sent:{user_id}:{ticket_id}:{event_type}` | 3600 s | Dedup de envío de emails |
