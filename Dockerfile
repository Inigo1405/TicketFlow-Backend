FROM python:3.10-slim
WORKDIR /app

# Copiar todos los archivos de requerimientos primero
COPY api-gateway/requirements.txt api_req.txt
COPY auth-service/requirements.txt auth_req.txt
COPY ticket-service/requirements.txt ticket_req.txt
COPY notification-service/requirements.txt notif_req.txt
COPY agent-service/requirements.txt agent_req.txt

# Instalar todo junto
RUN pip install --no-cache-dir -r api_req.txt -r auth_req.txt -r ticket_req.txt -r notif_req.txt -r agent_req.txt

# Copiar el resto del código
COPY . .

# Dar permisos de ejecución al script
RUN chmod +x start.sh

CMD ["./start.sh"]