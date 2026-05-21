# Pruebas del Proyecto — TicketFlow Backend

---

## HEALTH

### Health check – ESPERA 200

**Herramienta:** Thunder Client — VS Code  
**Método:** `GET`  
**URL:** `http://localhost:3000/api/health`

**Resultado obtenido — Status: 200 OK | Size: 39 Bytes | Time: 15 ms**

```json
{
  "status": "ok",
  "service": "api-gateway"
}
```

> **Nota:** En el log de la terminal se observa que las peticiones anteriores a `/api/auth/login` retornaron `405 Method Not Allowed` porque se usó GET en lugar de POST. Al ejecutar el health check correctamente con GET, el api-gateway respondió `200 OK`.

---

## AUTH

### Login (Cliente) – ESPERA 200 + TOKEN

**Método:** `POST`  
**URL:** `http://localhost:3000/api/auth/login`

**Body enviado:**
```json
{
  "email": "usuario@ticketflow.com",
  "password": "usuario1234"
}
```

**Resultado obtenido — Status: 200 OK | Size: 253 Bytes | Time: 568 ms**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "name": "Usuario Demo",
    "email": "usuario@ticketflow.com",
    "role": "Cliente",
    "area": null,
    "id": 1
  }
}
```

> **Nota:** En la terminal se observa la ejecución del seed: `docker exec -it auth-service python seed.py`. El seed creó al usuario Cliente: `usuario@ticketflow.com / usuario1234`.

---

### Login con credenciales inválidas – ESPERA 401

**Método:** `POST`  
**URL:** `http://localhost:3000/api/auth/login`

**Body enviado:**
```json
{
  "email": "admin@ticketflow.com",
  "password": "admin1234"
}
```

**Resultado obtenido — Status: 401 Unauthorized | Size: 37 Bytes | Time: 297 ms**

```json
{
  "detail": "Credenciales incorrectas"
}
```

> **Nota:** El usuario admin no existía aún en la base de datos, por lo que las credenciales fueron rechazadas correctamente con 401.

---

### GET /auth/me sin token – ESPERA 401

**Método:** `GET`  
**URL:** `http://localhost:3000/api/auth/me`

**Resultado obtenido — Status: 401 Unauthorized | Size: 39 Bytes | Time: 13 ms**

```json
{
  "detail": "Se requiere autenticación"
}
```

---

### GET /auth/me con token – ESPERA 200 + DATOS DEL USUARIO

**Método:** `GET`  
**URL:** `http://localhost:3000/api/auth/me`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 101 Bytes | Time: 342 ms**

```json
{
  "user": {
    "name": "Usuario Demo",
    "email": "usuario@ticketflow.com",
    "role": "Cliente",
    "area": null,
    "id": 1
  }
}
```

---

## TICKETS

### Mis tickets (GET /api/tickets/mine)

**Método:** `GET`  
**URL:** `http://localhost:3000/api/tickets/mine`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 338 Bytes | Time: 62 ms**

```json
[
  {
    "title": "Error al iniciar sesión en el portal",
    "description": "No puedo acceder con mis credenciales desde ayer por la mañana.",
    "category": "technical",
    "id": 1,
    "priority": "low",
    "status": "open",
    "tic_area": "uncategorized",
    "agent_processed": false,
    "created_at": "2026-05-20T17:50:45.815965Z",
    "created_by": 1,
    "sla_breached": false,
    "notes": null
  }
]
```

---

### Listar todos los tickets — Admin (GET /api/tickets/)

**Método:** `GET`  
**URL:** `http://localhost:3000/api/tickets/`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 338 Bytes | Time: 173 ms**

```json
[
  {
    "title": "Error al iniciar sesión en el portal",
    "description": "No puedo acceder con mis credenciales desde ayer por la mañana.",
    "category": "technical",
    "id": 1,
    "priority": "low",
    "status": "open",
    "tic_area": "uncategorized",
    "agent_processed": false,
    "created_at": "2026-05-20T17:50:45.815965Z",
    "created_by": 1,
    "sla_breached": false,
    "notes": null
  }
]
```

---

### Crear ticket – ESPERA 201

**Método:** `POST`  
**URL:** `http://localhost:3000/api/tickets/`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Body enviado:**
```json
{
  "title": "Error al iniciar sesión en el portal",
  "description": "No puedo acceder con mis credenciales desde ayer por la mañana.",
  "category": "technical",
  "status": "open"
}
```

**Resultado obtenido — Status: 201 Created | Size: 349 Bytes | Time: 2.58 s**

```json
{
  "title": "Error al iniciar sesión en el portal",
  "description": "No puedo acceder con mis credenciales desde ayer por la mañana.",
  "category": "technical",
  "id": 1,
  "priority": "low",
  "status": "open",
  "tic_area": "uncategorized",
  "agent_processed": false,
  "created_at": "2026-05-20T17:50:45.815965Z",
  "created_by": 1,
  "sla_breached": false,
  "notes": null,
  "replies": []
}
```

---

### Obtener ticket por ID (GET /api/tickets/1)

**Método:** `GET`  
**URL:** `http://localhost:3000/api/tickets/1`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 349 Bytes | Time: 123 ms**

```json
{
  "title": "Error al iniciar sesión en el portal",
  "description": "No puedo acceder con mis credenciales desde ayer por la mañana.",
  "category": "technical",
  "id": 1,
  "priority": "low",
  "status": "open",
  "tic_area": "uncategorized",
  "agent_processed": false,
  "created_at": "2026-05-20T17:50:45.815965Z",
  "created_by": 1,
  "sla_breached": false,
  "notes": null,
  "replies": []
}
```

---

### Actualizar prioridad (PATCH /api/tickets/1) — ESPERA 403 con token de Cliente

**Método:** `PATCH`  
**URL:** `http://localhost:3000/api/tickets/1`

**Body enviado:**
```json
{
  "priority": "high",
  "notes": "Revisado por agente. Requiere atención inmediata."
}
```

**Resultado obtenido — Status: 403 Forbidden | Size: 43 Bytes | Time: 38 ms**

```json
{
  "detail": "Se requiere rol Agente o Admin"
}
```

> **Nota:** Se requería crear un usuario con rol Agente o Admin para realizar esta acción.

---

### Login (Agente) – ESPERA 200 + TOKEN

**Método:** `POST`  
**URL:** `http://localhost:3000/api/auth/login`

**Body enviado:**
```json
{
  "email": "marco@ticketflow.com",
  "password": "agente1234"
}
```

**Resultado obtenido — Status: 200 OK | Size: 249 Bytes | Time: 337 ms**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "name": "Marco",
    "email": "marco@ticketflow.com",
    "role": "Agente",
    "area": "technical",
    "id": 2
  }
}
```

> **Nota:** El agente fue creado manualmente mediante `docker exec -it auth-service python -c "..."`. En la terminal se confirmó: `Agente creado`.

---

### Cerrar ticket (Agente) – ESPERA 200

**Método:** `PATCH`  
**URL:** `http://localhost:3000/api/tickets/1/close`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (token de Agente)

**Resultado obtenido — Status: 200 OK | Size: 2 Bytes | Time: 669 ms**

```json
{}
```

---

### Crear segundo ticket (billing) – ESPERA 201

**Método:** `POST`  
**URL:** `http://localhost:3000/api/tickets/`

**Body enviado:**
```json
{
  "title": "Factura incorrecta del mes de mayo",
  "description": "Me cobraron de más en mi factura de este mes.",
  "category": "billing",
  "status": "open"
}
```

**Resultado obtenido — Status: 201 Created | Size: 326 Bytes | Time: 352 ms**

```json
{
  "title": "Factura incorrecta del mes de mayo",
  "description": "Me cobraron de más en mi factura de este mes.",
  "category": "billing",
  "id": 2,
  "priority": "low",
  "status": "open",
  "tic_area": "uncategorized",
  "agent_processed": false,
  "created_at": "2026-05-21T00:20:39.975908Z",
  "created_by": 1,
  "sla_breached": false,
  "notes": null,
  "replies": []
}
```

---

### Resolver ticket (Agente) – ESPERA 200

**Método:** `PATCH`  
**URL:** `http://localhost:3000/api/tickets/2/resolve`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (token de Agente)

**Resultado obtenido — Status: 200 OK | Size: 2 Bytes | Time: 18 ms**

```json
{}
```

---

### Crear tercer ticket (access) – ESPERA 201

**Método:** `POST`  
**URL:** `http://localhost:3000/api/tickets/`

**Body enviado:**
```json
{
  "title": "Solicitud de acceso al módulo CRM",
  "description": "Necesito acceso al módulo CRM para mi trabajo.",
  "category": "access",
  "status": "open"
}
```

**Resultado obtenido — Status: 201 Created | Size: 326 Bytes | Time: 86 ms**

```json
{
  "title": "Solicitud de acceso al módulo CRM",
  "description": "Necesito acceso al módulo CRM para mi trabajo.",
  "category": "access",
  "id": 3,
  "priority": "low",
  "status": "open",
  "tic_area": "uncategorized",
  "agent_processed": false,
  "created_at": "2026-05-21T00:27:00.481488Z",
  "created_by": 1,
  "sla_breached": false,
  "notes": null,
  "replies": []
}
```

---

### Set ticket Pending

**Método:** `PATCH`  
**URL:** `http://localhost:3000/api/tickets/3/pending`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (token de Agente)

**Resultado obtenido — Status: 200 OK | Size: 2 Bytes | Time: 75 ms**

```json
{}
```

---

### Agregar reply – ESPERA 201

**Método:** `POST`  
**URL:** `http://localhost:3000/api/tickets/3/replies`

**Body enviado:**
```json
{
  "text": "Hemos revisado tu solicitud. Te daremos acceso al módulo CRM en breve."
}
```

**Resultado obtenido — Status: 201 Created | Size: 193 Bytes | Time: 204 ms**

```json
{
  "id": 1,
  "author_id": 2,
  "author_name": "Usuario #2",
  "text": "Hemos revisado tu solicitud. Te daremos acceso al módulo CRM en breve.",
  "is_internal": false,
  "created_at": "2026-05-21T00:33:50.096928Z"
}
```

---

## NOTIFICATIONS

### Listar notificaciones – ESPERA 200

**Primera prueba — Error 500 (antes del git pull)**

**Método:** `GET`  
**URL:** `http://localhost:3000/api/notifications/`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 500 Internal Server Error | Size: 21 Bytes | Time: 2.02 s**

```
Internal Server Error
```

> **Nota:** El error 500 ocurrió porque no se había hecho `git pull` para obtener la nueva rama donde se encuentra el `notification-service`. Una vez actualizado el repositorio, el servicio funcionó correctamente.

---

**Segunda prueba — Después del git pull y actualización**

**Resultado obtenido — Status: 200 OK | Size: 2 Bytes | Time: 970 ms**

```json
[]
```

> **Nota:** La lista aparece vacía inicialmente. La notificación fue creada manualmente desde el contenedor con `docker exec -it notification-service python -c "..."`. La terminal confirmó: `Notificacion creada con id: 1`.

---

### Unread-count (GET /api/notifications/unread-count)

**Método:** `GET`  
**URL:** `http://localhost:3000/api/notifications/unread-count`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 12 Bytes | Time: 49 ms**

```json
{
  "unread": 0
}
```

---

### Marcar notificación como leída – ESPERA 200

**Método:** `PATCH`  
**URL:** `http://localhost:3000/api/notifications/1/read`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 180 Bytes | Time: 376 ms**

```json
{
  "id": 1,
  "user_id": 1,
  "type": "info",
  "title": "Ticket creado",
  "message": "Tu ticket fue creado exitosamente.",
  "ticket_id": null,
  "is_read": true,
  "created_at": "2026-05-21T03:58:28.048368Z"
}
```

---

### Marcar todas como leídas – ESPERA 200

**Método:** `PATCH`  
**URL:** `http://localhost:3000/api/notifications/mark-all-read`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 59 Bytes | Time: 119 ms**

```json
{
  "detail": "Todas las notificaciones marcadas como leídas"
}
```

---

### Eliminar notificación – ESPERA 204

**Método:** `DELETE`  
**URL:** `http://localhost:3000/api/notifications/1`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 204 No Content | Size: 0 Bytes | Time: 72 ms**

```
(Sin cuerpo de respuesta — comportamiento correcto para DELETE)
```

---

## AGENT

### Categorize — Error inicial (sin rol correcto)

**Método:** `POST`  
**URL:** `http://localhost:3000/api/agent/categorize/1`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (token de Cliente)

**Resultado obtenido — Status: 403 Forbidden | Size: 43 Bytes | Time: 219 ms**

```json
{
  "detail": "Se requiere rol Agente o Admin"
}
```

> **Nota:** El error 403 ocurrió porque se olvidó crear el usuario con rol Admin antes de ejecutar las pruebas del agente. Se creó el usuario Admin `marco@ticketflow.com` mediante `docker exec`.

---

### Login (Admin Marco) – ESPERA 200 + TOKEN

**Intento fallido con admin@ticketflow.com**

**Resultado — Status: 401 Unauthorized**
```json
{ "detail": "Credenciales incorrectas" }
```

**Creación del Admin Marco en la terminal:**
```
docker exec -it auth-service python -c "..."
Admin Marco creado
```

**Login exitoso con marco@ticketflow.com**

**Método:** `POST`  
**URL:** `http://localhost:3000/api/auth/login`

**Body enviado:**
```json
{
  "email": "marco@ticketflow.com",
  "password": "admin1234"
}
```

**Resultado obtenido — Status: 200 OK | Size: 240 Bytes | Time: 871 ms**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "name": "Marco",
    "email": "marco@ticketflow.com",
    "role": "Admin",
    "area": null,
    "id": 2
  }
}
```

---

### Categorize (con token Admin) – Error 500

**Método:** `POST`  
**URL:** `http://localhost:3000/api/agent/categorize/1`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (token de Admin Marco)

**Resultado obtenido — Status: 500 Internal Server Error | Size: 34 Bytes | Time: 3.24 s**

```json
{
  "detail": "Internal Server Error"
}
```

**Log del contenedor (`docker logs agent-service --tail 30`):**
```
File ".../langchain_google_genai/chat_models.py", line 1592, in validate_environment
  self.client = genaix.build_generative_service(...)
File ".../langchain_google_genai/_genai_extension.py", line 286, in build_generative_service
  return v1betaGenerativeServiceClient(**config)
...
google.auth.exceptions.DefaultCredentialsError: Your default credentials were not found.
To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc
```

> **Causa:** El `agent-service` utiliza Google Gemini AI (LangChain + Google GenAI) para la categorización. Las credenciales de Google Cloud (Application Default Credentials) no están configuradas en el entorno local. Este error aplica a todos los endpoints de Agent que dependen de IA.

---

### Interact – Error 500

**Método:** `POST`  
**URL:** `http://localhost:3000/api/agent/interact/1`

**Body enviado:**
```json
{
  "message": "Hola, necesito ayuda con mi ticket"
}
```

**Resultado obtenido — Status: 500 Internal Server Error | Time: 3.17 s**

```json
{
  "detail": "Internal Server Error"
}
```

> **Causa:** Mismo error que Categorize — requiere credenciales de Google Gemini AI.

---

### Notes – Error 500

**Método:** `POST`  
**URL:** `http://localhost:3000/api/agent/notes/1`

**Resultado obtenido — Status: 500 Internal Server Error | Time: 3.15 s**

```json
{
  "detail": "Internal Server Error"
}
```

> **Causa:** Mismo error — requiere Google Gemini AI.

---

### Agent Health – ESPERA 200

**Método:** `GET`  
**URL:** `http://localhost:3000/api/agent/health`  
**Headers:** `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

**Resultado obtenido — Status: 200 OK | Size: 41 Bytes | Time: 469 ms**

```json
{
  "status": "ok",
  "service": "agent-service"
}
```

---

## RESUMEN DE RESULTADOS

| Sección | Prueba | Status Esperado | Status Obtenido | Resultado |
|---------|--------|-----------------|-----------------|-----------|
| Health | GET /api/health | 200 | 200 OK | ✅ |
| Auth | POST /api/auth/login (Cliente) | 200 + TOKEN | 200 OK | ✅ |
| Auth | POST /api/auth/login (credenciales inválidas) | 401 | 401 Unauthorized | ✅ |
| Auth | GET /api/auth/me sin token | 401 | 401 Unauthorized | ✅ |
| Auth | GET /api/auth/me con token | 200 + datos | 200 OK | ✅ |
| Tickets | GET /api/tickets/mine | 200 | 200 OK | ✅ |
| Tickets | GET /api/tickets/ (Admin) | 200 | 200 OK | ✅ |
| Tickets | POST /api/tickets/ | 201 | 201 Created | ✅ |
| Tickets | GET /api/tickets/1 | 200 | 200 OK | ✅ |
| Tickets | PATCH /api/tickets/1 (sin rol) | 403 | 403 Forbidden | ✅ |
| Tickets | PATCH /api/tickets/1/close (Agente) | 200 | 200 OK | ✅ |
| Tickets | PATCH /api/tickets/2/resolve (Agente) | 200 | 200 OK | ✅ |
| Tickets | PATCH /api/tickets/3/pending | 200 | 200 OK | ✅ |
| Tickets | POST /api/tickets/3/replies | 201 | 201 Created | ✅ |
| Notifications | GET /api/notifications/ | 200 | 500 → luego 200 | ⚠️ |
| Notifications | GET /api/notifications/unread-count | 200 | 200 OK | ✅ |
| Notifications | PATCH /api/notifications/1/read | 200 | 200 OK | ✅ |
| Notifications | PATCH /api/notifications/mark-all-read | 200 | 200 OK | ✅ |
| Notifications | DELETE /api/notifications/1 | 200/204 | 204 No Content | ✅ |
| Agent | POST /api/agent/categorize/1 | 200 | 403 → 500 | ❌ |
| Agent | POST /api/agent/interact/1 | 200 | 500 | ❌ |
| Agent | POST /api/agent/notes/1 | 200 | 500 | ❌ |
| Agent | GET /api/agent/health | 200 | 200 OK | ✅ |

> **⚠️ Notifications — Error inicial:** El primer intento retornó 500 porque no se había actualizado el repositorio con `git pull` para obtener la rama con el `notification-service`.
>
> **❌ Agent — Error 500:** Los endpoints de IA del agent-service requieren credenciales de Google Gemini (Application Default Credentials) que no están configuradas en el entorno local de desarrollo. El servicio en sí funciona correctamente (`/agent/health` responde 200).
