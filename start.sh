#!/bin/bash
# Usamos paréntesis para aislar el cambio de directorio de cada microservicio

(cd auth-service && uvicorn app.main:app --host 127.0.0.1 --port 8001) &
(cd ticket-service && uvicorn app.main:app --host 127.0.0.1 --port 8002) &
(cd notification-service && uvicorn app.main:app --host 127.0.0.1 --port 8003) &
(cd agent-service && uvicorn app.main:app --host 127.0.0.1 --port 8004) &

# El gateway va sin el '&' al final para mantener el contenedor encendido
(cd api-gateway && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3000})