"""
Seed inicial para agent-service: carga conocimiento TIC y pares QA de ejemplo.
Uso desde dentro del contenedor o con DATABASE_URL configurado:
    python seed.py

Es idempotente: omite la carga si ya existen registros en knowledge_base.
"""
import asyncio
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from qdrant_client.http.models import PointStruct

from app.core.config import settings
from app.db.database import Base
from app.db.vector_db import get_vector_client
from app.agent.embeddings import embed_with_retry
from app.models.agent import KnowledgeBase, QAEntry


# ── Datos de conocimiento TIC ─────────────────────────────────────────────────

KNOWLEDGE_ENTRIES = [
    {
        "title": "Procedimiento de acceso VPN corporativa",
        "category": "VPN",
        "content": (
            "Para conectarse a la red corporativa de forma remota se utiliza Cisco AnyConnect.\n\n"
            "Pasos:\n"
            "1. Abrir Cisco AnyConnect Secure Mobility Client.\n"
            "2. Ingresar la dirección del servidor VPN: vpn.empresa.com\n"
            "3. Autenticarse con usuario y contraseña de dominio (usuario@empresa.com).\n"
            "4. Si está habilitado el doble factor, aprobar la notificación en Microsoft Authenticator.\n"
            "5. Una vez conectado, acceder normalmente a recursos internos (unidades de red, intranet, sistemas).\n\n"
            "Problemas frecuentes:\n"
            "- Error 'Authentication failed': verificar que la contraseña de dominio no haya expirado.\n"
            "- Error de certificado: reinstalar el perfil VPN desde https://intranet.empresa.com/vpn.\n"
            "- Sin acceso a internet con VPN activa: la configuración de túnel completo está activa; "
            "es el comportamiento esperado en equipos corporativos.\n\n"
            "Soporte: tickets etiquetados con área 'VPN'."
        ),
    },
    {
        "title": "Política de contraseñas y autoservicio de reset",
        "category": "Seguridad",
        "content": (
            "Política vigente de contraseñas corporativas:\n\n"
            "Requisitos:\n"
            "- Mínimo 10 caracteres.\n"
            "- Al menos una mayúscula, una minúscula, un número y un símbolo.\n"
            "- No puede repetir las 5 últimas contraseñas.\n"
            "- Vigencia: 90 días. Se notifica al usuario 15 días antes de expirar.\n\n"
            "Autoservicio de reset:\n"
            "1. Ir a https://reset.empresa.com\n"
            "2. Ingresar el correo corporativo y verificar identidad por MFA.\n"
            "3. Establecer nueva contraseña cumpliendo los requisitos.\n"
            "4. La nueva contraseña aplica inmediatamente en todos los sistemas (AD, VPN, correo).\n\n"
            "Si el autoservicio no está disponible, abrir ticket en TIC con categoría 'Contraseñas'.\n"
            "Tiempo de respuesta SLA: 2 horas en horario laboral."
        ),
    },
    {
        "title": "Configuración de correo corporativo en Outlook",
        "category": "Correo",
        "content": (
            "El correo corporativo usa Microsoft Exchange Online (Office 365).\n\n"
            "Configuración automática (recomendada):\n"
            "1. Abrir Outlook → Archivo → Agregar cuenta.\n"
            "2. Ingresar el correo corporativo (usuario@empresa.com).\n"
            "3. Outlook detecta Exchange automáticamente. Autenticarse con contraseña de dominio.\n"
            "4. Si se solicita MFA, aprobar en Microsoft Authenticator.\n\n"
            "Configuración manual (solo si la automática falla):\n"
            "- Tipo de cuenta: Microsoft 365 / Exchange\n"
            "- Servidor: outlook.office365.com\n"
            "- Puerto IMAP: 993 (SSL) | SMTP: 587 (TLS)\n\n"
            "Configuración en móvil:\n"
            "Usar la app Microsoft Outlook para iOS/Android. Agregar cuenta corporativa "
            "con usuario@empresa.com; detecta Exchange automáticamente.\n\n"
            "Cuota de buzón: 50 GB. Archivar correos antiguos con Archivo en línea habilitado."
        ),
    },
    {
        "title": "Configuración e instalación de impresoras de red",
        "category": "Impresoras",
        "content": (
            "Las impresoras de red se instalan desde el servidor de impresión corporativo.\n\n"
            "Método 1 — Desde servidor de impresión (recomendado):\n"
            "1. Abrir el Explorador de archivos → ingresar \\\\print.empresa.com en la barra de direcciones.\n"
            "2. Hacer doble clic en la impresora deseada (por piso/área).\n"
            "3. Windows instala el driver automáticamente.\n\n"
            "Método 2 — Por dirección IP (si el servidor no está disponible):\n"
            "1. Panel de control → Dispositivos e impresoras → Agregar impresora.\n"
            "2. Seleccionar 'Agregar impresora local o de red con configuración manual'.\n"
            "3. Crear nuevo puerto TCP/IP e ingresar la IP de la impresora.\n"
            "4. Instalar el driver desde la web del fabricante.\n\n"
            "IPs de impresoras por piso:\n"
            "- Piso 1 (Administración): 192.168.1.50, 192.168.1.51\n"
            "- Piso 2 (TIC): 192.168.2.50\n"
            "- Piso 3 (Operaciones): 192.168.3.50, 192.168.3.51\n\n"
            "Problemas frecuentes: reiniciar el servicio 'Cola de impresión' (spooler) si la impresora "
            "aparece en línea pero no imprime."
        ),
    },
    {
        "title": "Política de instalación de software en equipos corporativos",
        "category": "Software",
        "content": (
            "Solo TIC puede instalar software en equipos corporativos con sistema Windows.\n\n"
            "Proceso de solicitud:\n"
            "1. Abrir un ticket en TicketFlow con categoría 'Software'.\n"
            "2. Indicar: nombre del software, versión, justificación de uso, área solicitante.\n"
            "3. TIC evalúa compatibilidad, licencias y seguridad (máx. 3 días hábiles).\n"
            "4. Si se aprueba, se programa la instalación en horario no crítico.\n\n"
            "Software preinstalado en todos los equipos:\n"
            "- Microsoft Office 365 (Word, Excel, PowerPoint, Outlook, Teams)\n"
            "- Cisco AnyConnect (VPN)\n"
            "- Microsoft Defender Antivirus\n"
            "- Google Chrome / Microsoft Edge\n"
            "- Adobe Acrobat Reader\n\n"
            "Software prohibido: clientes torrent, software de acceso remoto no autorizado "
            "(TeamViewer personal, AnyDesk sin licencia corporativa), aplicaciones de criptomonedas.\n\n"
            "Excepciones: los administradores locales de sistemas tienen acceso elevado "
            "previa aprobación escrita del jefe de área."
        ),
    },
    {
        "title": "Configuración de escritorio remoto (RDP) para trabajo desde casa",
        "category": "Trabajo Remoto",
        "content": (
            "Para acceder al equipo de oficina desde casa se usa Escritorio Remoto (RDP) "
            "combinado con VPN.\n\n"
            "Requisitos previos:\n"
            "- VPN activa (ver procedimiento de acceso VPN).\n"
            "- El equipo de oficina debe estar encendido y conectado a la red corporativa.\n"
            "- TIC debe habilitar RDP en el equipo (solicitar ticket si no está habilitado).\n\n"
            "Pasos:\n"
            "1. Conectar VPN.\n"
            "2. Abrir 'Conexión a Escritorio Remoto' (mstsc.exe).\n"
            "3. Ingresar el nombre o IP del equipo de oficina (visible en la etiqueta del equipo o "
            "preguntando a TIC).\n"
            "4. Autenticarse con usuario y contraseña de dominio.\n\n"
            "Resolución recomendada: 1920x1080 para mejor rendimiento.\n"
            "Si la conexión es lenta: reducir colores a 16 bits y desactivar efectos visuales "
            "en la pestaña 'Experiencia' de la configuración RDP."
        ),
    },
    {
        "title": "Procedimiento para reportar incidentes de seguridad",
        "category": "Seguridad",
        "content": (
            "Ante cualquier sospecha de incidente de seguridad informática, actuar de inmediato.\n\n"
            "¿Qué es un incidente de seguridad?\n"
            "- Correo de phishing recibido o sospechoso.\n"
            "- Acceso no autorizado detectado a sistemas o archivos.\n"
            "- Ransomware o malware detectado por el antivirus.\n"
            "- Pérdida o robo de equipo corporativo.\n"
            "- Contraseña comprometida o filtrada.\n\n"
            "Pasos a seguir:\n"
            "1. NO apagar el equipo (preserva evidencia forense).\n"
            "2. Desconectar el equipo de la red (desenchufar cable ethernet o desactivar WiFi).\n"
            "3. Abrir ticket urgente en TicketFlow con categoría 'Seguridad' y prioridad 'Crítica'.\n"
            "4. Llamar directamente a TIC: extensión 100 (horario laboral) o al guardia de seguridad "
            "fuera de horario.\n"
            "5. No intentar resolver el incidente por cuenta propia.\n\n"
            "Phishing: si recibiste un correo sospechoso, reenvíalo como adjunto a "
            "seguridad@empresa.com antes de eliminarlo."
        ),
    },
    {
        "title": "Solución de problemas de conectividad a internet y red local",
        "category": "Redes",
        "content": (
            "Diagnóstico básico de problemas de red, realizable por el usuario antes de abrir ticket.\n\n"
            "Sin conexión a internet:\n"
            "1. Verificar que el cable ethernet esté conectado o que el WiFi esté activo.\n"
            "2. Reiniciar el adaptador de red: Panel de control → Red → deshabilitar y habilitar.\n"
            "3. Ejecutar: ipconfig /release y luego ipconfig /renew en CMD (administrador).\n"
            "4. Probar ping a la puerta de enlace: ping 192.168.1.1\n"
            "5. Si el ping a la puerta de enlace falla, el problema es local (cable, switch).\n"
            "6. Si el ping a la puerta de enlace funciona pero no hay internet: problema de DNS "
            "o salida a internet.\n\n"
            "Sin acceso a recursos de red (carpetas compartidas, intranet):\n"
            "- Verificar que la VPN esté activa si se trabaja de forma remota.\n"
            "- Ejecutar: nslookup servidor.empresa.com para verificar resolución DNS.\n\n"
            "Si los pasos anteriores no resuelven, abrir ticket con:\n"
            "- Descripción exacta del error.\n"
            "- Resultado de ipconfig /all (copiar y pegar en el ticket).\n"
            "- Indicar si otros equipos de la misma área tienen el mismo problema."
        ),
    },
]

# ── Pares QA ──────────────────────────────────────────────────────────────────

QA_ENTRIES = [
    {
        "problem": "No puedo conectarme a la VPN, me dice 'Authentication failed'.",
        "solution": (
            "La contraseña de dominio expiró o es incorrecta. "
            "Pasos: (1) Acceder al portal de autoservicio https://reset.empresa.com para restablecer "
            "la contraseña. (2) Una vez restablecida, intentar conectar nuevamente con Cisco AnyConnect "
            "usando la nueva contraseña. (3) Si el error persiste, verificar que el usuario no esté "
            "bloqueado en Active Directory (contactar TIC)."
        ),
        "tic_area": "vpn",
    },
    {
        "problem": "No puedo acceder a las unidades de red compartidas (\\\\servidor\\datos).",
        "solution": (
            "Verificar que la VPN esté conectada si se trabaja de forma remota. "
            "Si la VPN está activa y el problema persiste: (1) Confirmar credenciales de dominio "
            "escribiendo net use * /delete y reconectando la unidad. "
            "(2) Verificar permisos con el jefe de área — puede ser que el usuario no tenga "
            "acceso asignado a esa carpeta. (3) Reiniciar el servicio 'Workstation' en services.msc."
        ),
        "tic_area": "redes",
    },
    {
        "problem": "La impresora aparece en línea pero los documentos no se imprimen, se quedan en cola.",
        "solution": (
            "El servicio de cola de impresión (spooler) está bloqueado. "
            "Solución: (1) Abrir services.msc. (2) Buscar 'Cola de impresión' (Print Spooler). "
            "(3) Detener el servicio. (4) Ir a C:\\Windows\\System32\\spool\\PRINTERS y borrar "
            "todos los archivos dentro (no la carpeta). (5) Iniciar el servicio nuevamente. "
            "(6) Intentar imprimir de nuevo."
        ),
        "tic_area": "impresoras",
    },
    {
        "problem": "El correo de Outlook no se sincroniza, los mensajes no cargan o están desactualizados.",
        "solution": (
            "Primero verificar conexión a internet y que la cuenta no haya expirado. "
            "Luego: (1) Cerrar Outlook. (2) Abrir el Panel de control → Correo → Mostrar perfiles. "
            "(3) Si hay un perfil corrupto, eliminarlo y crear uno nuevo con la cuenta corporativa. "
            "(4) Alternativa rápida: en Outlook ir a Enviar/Recibir → Actualizar carpeta. "
            "(5) Si usa caché de Exchange, reducir el período de sincronización a 3 meses "
            "(Configuración de cuenta → Cambiar → Más configuraciones → Avanzado)."
        ),
        "tic_area": "correo",
    },
    {
        "problem": "Mi equipo está muy lento, tarda mucho en arrancar y los programas van lentos.",
        "solution": (
            "Diagnóstico y solución rápida: "
            "(1) Limpiar archivos temporales: ejecutar %temp% en el menú Inicio, seleccionar todo y borrar. "
            "(2) Limpiar disco: Herramientas de disco → Liberar espacio. "
            "(3) Desactivar programas de inicio: Administrador de tareas → pestaña Inicio. "
            "(4) Verificar que el antivirus no esté haciendo un análisis programado. "
            "(5) Reiniciar el equipo si lleva más de 5 días encendido. "
            "Si el problema persiste tras estos pasos, abrir ticket para diagnóstico de hardware "
            "(puede ser RAM insuficiente o disco duro con sectores defectuosos)."
        ),
        "tic_area": "hardware",
    },
    {
        "problem": "Olvidé mi contraseña de dominio y no puedo iniciar sesión.",
        "solution": (
            "Para restablecer la contraseña de dominio: "
            "(1) Desde otro equipo o el móvil, acceder a https://reset.empresa.com. "
            "(2) Ingresar el correo corporativo y verificar identidad mediante Microsoft Authenticator. "
            "(3) Establecer nueva contraseña cumpliendo los requisitos (mín. 10 caracteres, "
            "mayúscula, número, símbolo). "
            "(4) Aplicar la nueva contraseña en el equipo bloqueado (Ctrl+Alt+Del → Cambiar contraseña). "
            "Si no tienes acceso al portal de autoservicio o al autenticador, abrir ticket urgente "
            "para reset manual por TIC (SLA: 2 horas)."
        ),
        "tic_area": "seguridad",
    },
    {
        "problem": "La aplicación de doble factor (Microsoft Authenticator) no genera códigos o dice que son incorrectos.",
        "solution": (
            "El problema más común es el desajuste de hora en el dispositivo móvil. "
            "Solución: (1) En el móvil, ir a Configuración → Fecha y hora → activar 'Hora automática'. "
            "(2) Si el problema persiste, en la app Authenticator ir a los tres puntos → "
            "Configuración → Corrección de hora para códigos de verificación → Sincronizar ahora. "
            "(3) Si perdiste el móvil o cambiaste de dispositivo, contactar TIC para reregistrar "
            "el autenticador vinculado a tu cuenta corporativa."
        ),
        "tic_area": "seguridad",
    },
    {
        "problem": "Recibí un correo sospechoso que me pide mis credenciales, creo que es phishing.",
        "solution": (
            "No hacer clic en ningún enlace ni descargar archivos adjuntos. "
            "Pasos inmediatos: (1) No responder al correo. "
            "(2) Reenviar el correo sospechoso COMO ADJUNTO a seguridad@empresa.com. "
            "(3) Eliminarlo de la bandeja de entrada. "
            "(4) Si ya hiciste clic en un enlace o ingresaste credenciales, cambiar la contraseña "
            "INMEDIATAMENTE en https://reset.empresa.com y abrir ticket urgente con categoría 'Seguridad'. "
            "TIC revisará si hubo acceso no autorizado a la cuenta."
        ),
        "tic_area": "seguridad",
    },
    {
        "problem": "Necesito instalar un programa para mi trabajo pero no tengo permisos de administrador.",
        "solution": (
            "Los equipos corporativos no permiten instalación de software por parte del usuario "
            "por política de seguridad. "
            "Para solicitar la instalación: (1) Abrir ticket en TicketFlow con categoría 'Software'. "
            "(2) Indicar: nombre del software, versión requerida, y justificación de uso laboral. "
            "(3) TIC evaluará la solicitud en máximo 3 días hábiles. "
            "(4) Si se aprueba, se coordinará la instalación. "
            "Si es urgente, indicarlo en el ticket con prioridad 'Alta' y notificar al jefe de área "
            "para que lo avale."
        ),
        "tic_area": "software",
    },
    {
        "problem": "El equipo mostró una pantalla azul (BSOD) y se reinició solo.",
        "solution": (
            "Un BSOD indica un error crítico del sistema. Pasos a seguir: "
            "(1) Anotar el código de error que aparece en la pantalla azul "
            "(ej: SYSTEM_THREAD_EXCEPTION_NOT_HANDLED). "
            "(2) Después del reinicio, verificar si el equipo funciona normalmente. "
            "(3) Abrir el Visor de eventos (eventvwr.msc) → Registros de Windows → Sistema, "
            "buscar errores críticos del momento del BSOD. "
            "(4) Abrir ticket con el código de error y la hora aproximada del incidente. "
            "No apagar el equipo antes de que TIC lo revise. "
            "Causas comunes: driver desactualizado, RAM defectuosa, disco con errores."
        ),
        "tic_area": "hardware",
    },
    {
        "problem": "No tengo conexión a internet en mi equipo, pero otros equipos de la oficina sí tienen.",
        "solution": (
            "El problema es específico de ese equipo. Diagnóstico: "
            "(1) Verificar que el cable ethernet esté bien conectado (o reiniciar WiFi). "
            "(2) En CMD como administrador ejecutar: ipconfig /release, luego ipconfig /renew. "
            "(3) Si no obtiene IP automática, intentar: netsh int ip reset y reiniciar. "
            "(4) Verificar configuración de red: debe ser 'Obtener dirección IP automáticamente' "
            "(DHCP activo). "
            "(5) Probar deshabilitando y habilitando el adaptador de red en Panel de control → Red. "
            "Si ningún paso funciona, abrir ticket — puede ser problema de puerto switch o "
            "driver del adaptador de red."
        ),
        "tic_area": "redes",
    },
    {
        "problem": "Quiero acceder a mi equipo de oficina desde casa pero no sé cómo configurarlo.",
        "solution": (
            "Para acceder remotamente al equipo de oficina: "
            "(1) Asegurarte de que TIC haya habilitado el Escritorio Remoto en tu equipo "
            "(abrir ticket si no está habilitado aún). "
            "(2) Conectar la VPN corporativa desde casa (Cisco AnyConnect). "
            "(3) Abrir 'Conexión a Escritorio Remoto' (Win+R → mstsc). "
            "(4) Ingresar el nombre del equipo de oficina (está en la etiqueta del equipo o "
            "puedes preguntarlo a TIC). "
            "(5) Autenticarte con usuario y contraseña de dominio. "
            "El equipo de oficina debe estar encendido para que funcione la conexión remota."
        ),
        "tic_area": "trabajo_remoto",
    },
]


# ── Función de indexado ───────────────────────────────────────────────────────

async def index_in_qdrant(
    client,
    collection: str,
    point_id: str,
    text: str,
    payload: dict,
):
    vector = await embed_with_retry(text)
    await client.upsert(
        collection_name=collection,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )


# ── Seed principal ────────────────────────────────────────────────────────────

async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    qdrant = await get_vector_client()

    async with session_maker() as session:
        # Idempotencia: no re-seedear si ya hay conocimiento cargado
        kb_count = (
            await session.execute(select(func.count()).select_from(KnowledgeBase))
        ).scalar()
        if kb_count and kb_count > 0:
            print(f"Seed omitido: ya existen {kb_count} documentos en knowledge_base.")
            await engine.dispose()
            return

        print("Iniciando seed de agent-service...\n")

        # ── KnowledgeBase ────────────────────────────────────────────────────
        print(f"Cargando {len(KNOWLEDGE_ENTRIES)} documentos de conocimiento...")
        for data in KNOWLEDGE_ENTRIES:
            entry = KnowledgeBase(
                title=data["title"],
                content=data["content"],
                category=data["category"],
            )
            session.add(entry)
            await session.flush()
            await session.refresh(entry)

            point_id = str(uuid.uuid4())
            await index_in_qdrant(
                qdrant,
                settings.COLLECTION_KNOWLEDGE,
                point_id,
                f"{entry.title}\n{entry.content}",
                {
                    "title": entry.title,
                    "content": entry.content,
                    "category": entry.category or "",
                    "db_id": entry.id,
                },
            )
            entry.vector_id = point_id
            await session.flush()
            print(f"  + [{data['category']}] {data['title']}")

        # ── QAEntry ──────────────────────────────────────────────────────────
        print(f"\nCargando {len(QA_ENTRIES)} pares QA...")
        for data in QA_ENTRIES:
            entry = QAEntry(
                problem=data["problem"],
                solution=data["solution"],
                tic_area=data["tic_area"],
            )
            session.add(entry)
            await session.flush()
            await session.refresh(entry)

            point_id = str(uuid.uuid4())
            await index_in_qdrant(
                qdrant,
                settings.COLLECTION_QA,
                point_id,
                f"Problema: {entry.problem}\nSolución: {entry.solution}",
                {
                    "problem": entry.problem,
                    "solution": entry.solution,
                    "tic_area": entry.tic_area or "",
                    "source_ticket_id": None,
                    "db_id": entry.id,
                },
            )
            entry.vector_id = point_id
            await session.flush()
            print(f"  + [{data['tic_area']}] {data['problem'][:60]}...")

        await session.commit()
        print(
            f"\nSeed completado: {len(KNOWLEDGE_ENTRIES)} documentos KB + "
            f"{len(QA_ENTRIES)} pares QA indexados en PostgreSQL y Qdrant."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
