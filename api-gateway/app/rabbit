import os
from time import sleep
import pika

def get_channel():
  url = os.getenv("RABBIT_URL")

  for intento in range(10):
    try:
      connection = pika.BlockingConnection(pika.URLParameters(url))
      channel = connection.channel()

      channel.exchange_declare(
        exchange="orders",
        exchange_type="topic",
        durable=True
      )

      return channel

    except Exception as e:
      print(f"RabbitMQ no listo, reintentando ({intento + 1}/10)... {e}")
      sleep(3)