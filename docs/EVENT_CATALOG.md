# TicketFlow — Catálogo de Eventos de Mensajería

## Infraestructura

| Componente | Valor |
|---|---|
| Broker | RabbitMQ |
| Exchange | `ticketflow` (tipo: `topic`, durable) |
| Routing key | `notification.event` |
| Cola | `notifications` (durable) |
| Publisher | `ticket-service` |
| Consumer | `notification-service` |

---

## Schema base del evento

Todos los eventos siguen el schema `NotificationEvent`:

```json
{
  "user_ids":     [1, 2],        // IDs de usuarios destinatarios directos (reciben email si send_email=true)
  "notify_roles": ["Admin"],     // Roles que reciben la notificación en-app (sin email)
  "type":         "ticket_created",
  "title":        "Nuevo ticket #42",
  "message":      "Se ha creado el ticket: Login caído",
  "ticket_id":    42,            // null si no aplica
  "send_email":   false          // true = el notification-service envía correo a user_ids
}
```

---

## Eventos

### 1. `ticket_created`
**Publicado por:** `POST /tickets`  
**Destinatarios:** `notify_roles: ["Admin", "Agente"]`  
**Email:** No  
**Descripción:** Se crea un nuevo ticket. Notifica a todos los administradores y agentes para que lo atiendan.

---

### 2. `ticket_updated`
**Publicado por:** `PATCH /tickets/{id}`  
**Destinatarios:** `user_ids: [created_by]` (cliente que abrió el ticket)  
**Email:** No  
**Descripción:** El agente cambia prioridad, categoría, estado u otro campo del ticket. El cliente recibe la notificación in-app.

---

### 3. `critical_ticket`
**Publicado por:** `PATCH /tickets/{id}` cuando `priority` cambia a `"critical"`  
**Destinatarios:** `notify_roles: ["Admin"]`  
**Email:** No  
**Descripción:** Un ticket fue escalado a prioridad crítica. Alerta inmediata a los administradores.

---

### 4. `ticket_resolved`
**Publicado por:** `POST /tickets/{id}/resolve`  
**Destinatarios (cliente):** `user_ids: [created_by]`, `send_email: true`  
**Destinatarios (admin):** `notify_roles: ["Admin"]`  
**Email:** Sí (al cliente)  
**Descripción:** El ticket fue marcado como resuelto. Se notifica al cliente vía in-app y correo, y a los admins in-app.  
**Idempotencia:** Si el ticket ya estaba en estado `resolved`, la operación no genera eventos duplicados.

---

### 5. `ticket_closed`
**Publicado por:** `POST /tickets/{id}/close`  
**Destinatarios:** `user_ids: [created_by]`, `send_email: true`  
**Email:** Sí (al cliente)  
**Descripción:** El ticket fue cerrado definitivamente. El cliente recibe notificación in-app y por correo.

---

### 6. `new_reply`
**Publicado por:** `POST /tickets/{id}/replies` (cuando el autor es un Agente o Admin)  
**Destinatarios:** `user_ids: [created_by]`, `send_email: true`  
**Email:** Sí (al cliente)  
**Descripción:** Un agente o admin respondió en el hilo del ticket. El cliente recibe notificación in-app y correo.

---

### 7. `new_client_reply`
**Publicado por:** `POST /tickets/{id}/replies` (cuando el autor es un Cliente)  
**Destinatarios:** `notify_roles: ["Admin"]`  
**Email:** No  
**Descripción:** El cliente respondió en el hilo. Los administradores reciben notificación in-app para hacer seguimiento.

---

### 8. `sla_breached`
**Publicado por:** `GET /tickets` (evaluación lazy en listado) — máximo una vez por ticket  
**Destinatarios:** `notify_roles: ["Admin"]`  
**Email:** No  
**Descripción:** El ticket lleva más de `SLA_HOURS` (default: 24 h) abierto sin resolverse. Se usa Redis `setnx` con clave `sla_notif:{ticket_id}:sla_breached` para garantizar que el evento se publique una sola vez.

---

### 9. `ticket_escalated`
**Publicado por:** `GET /tickets` (evaluación lazy en listado) — máximo una vez por ticket  
**Destinatarios:** `notify_roles: ["Admin"]`  
**Email:** No  
**Descripción:** El ticket lleva más de `SLA_ESCALATION_HOURS` (default: 48 h) abierto sin resolverse. Escalación automática. Se usa Redis `setnx` con clave `sla_notif:{ticket_id}:ticket_escalated` para evitar eventos repetidos.

---

### 10. `agent_note`
**Publicado por:** TICBot (agent-service) al publicar una nota interna  
**Destinatarios:** `notify_roles: ["Admin", "Agente"]`  
**Email:** No  
**Descripción:** El agente de IA generó una nota interna sobre el ticket. Notifica al equipo para revisión.

---

## Deduplicación de correos (Redis)

El `notification-service` utiliza Redis para evitar enviar el mismo correo más de una vez por hora:

```
Clave:  email_sent:{user_id}:{ticket_id|none}:{event_type}
TTL:    3600 segundos (1 hora)
Método: SETNX — solo escribe si la clave no existe
```

Si la clave ya existe, el email se omite y se registra un log `[NotifService] Email deduplicado`.

---

## Flujo de publicación / consumo

```
ticket-service                    RabbitMQ                   notification-service
     │                                │                               │
     │── publish_notification() ─────>│ exchange: ticketflow          │
     │   routing_key: notification.event  queue: notifications        │
     │                                │──── _on_message() ───────────>│
     │                                │                               │── resuelve notify_roles → user_ids
     │                                │                               │── persiste en DB (tabla notifications)
     │                                │                               │── si send_email: verifica Redis dedup
     │                                │                               │── envía email vía EmailJS (si pasa dedup)
```
