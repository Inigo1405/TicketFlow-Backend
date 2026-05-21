#!/bin/bash
# Levantar microservicios en segundo plano en puertos locales (localhost)
cd auth-service && uvicorn app.main:app --host 127.0.0.1 --port 8001 &
cd ../ticket-service && uvicorn app.main:app --host 127.0.0.1 --port 8002 &
cd ../notification-service && uvicorn app.main:app --host 127.0.0.1 --port 8003 &
cd ../agent-service && uvicorn app.main:app --host 127.0.0.1 --port 8004 &

# Levantar el API Gateway exponiéndolo a internet
cd ../api-gateway && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3000}