# Buffering de Mensajes de WhatsApp para Amazon Connect


   _Aprende a optimizar las integraciones de WhatsApp con Amazon Connect mediante el buffering de mensajes rápidos consecutivos en un solo mensaje coherente. Esta guía paso a paso cubre la arquitectura completa usando AWS CDK, DynamoDB Streams, AWS Lambda, AWS End User Messaging Social y Amazon Connect. Reduce costos y ofrece una experiencia de conversación natural para tus agentes. Ideal para equipos que manejan un alto volumen de interacciones con clientes por WhatsApp._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/demo_buffer.gif)


Cuando los clientes se comunican por WhatsApp, rara vez envían un solo mensaje. Escriben rápido: "Hola", "Necesito ayuda", "con mi pedido", "P12345". Cada uno de esos mensajes genera un evento de webhook separado y, sin ninguna optimización, cada uno crea un mensaje de chat independiente en Amazon Connect. ¿El resultado? Una conversación fragmentada, un agente confundido y costos innecesarios.

En los chats con IA, normalmente evitamos que los usuarios envíen mensajes adicionales mientras el agente aún está procesando. Lamentablemente, con mensajes asincrónicos y programáticos, no podemos controlar eso. Pero sí podemos controlar cuánto tiempo esperamos antes de empezar a responder. Este blog no solo aplica para escenarios de WhatsApp a Connect, sino para cualquier canal de chat que enfrente el mismo desafío: SMS, mensajes directos en redes sociales y más.

En este blog, aprenderás a resolver esto con una capa de buffering de mensajes que agrega mensajes rápidos consecutivos de WhatsApp en un solo mensaje coherente antes de reenviarlos a Amazon Connect.

Consulta el código en [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## Lo que vas a construir

Una capa de buffering entre AWS End User Messaging Social y Amazon Connect que:

1. Captura los mensajes entrantes de WhatsApp en una tabla de DynamoDB
2. Usa DynamoDB Streams con una ventana de agregación (tumbling window) para almacenar mensajes en buffer
3. Agrega mensajes de texto consecutivos del mismo remitente en uno solo
4. Reenvía el mensaje combinado a Amazon Connect como un único mensaje de chat

El resultado final: los agentes ven una conversación limpia y natural en lugar de una avalancha de mensajes fragmentados.

## Arquitectura

![Diagrama de Arquitectura](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/whatsapp-optimization-connect-DynamoDB.drawio.svg)

Así funciona el flujo:

1. Un mensaje de WhatsApp llega a través de AWS End User Messaging Social y se publica en un tema de SNS
2. Una función Lambda (`on_raw_messages`) almacena cada mensaje en una tabla de DynamoDB (`raw_messages`)
3. DynamoDB Streams activa una función Lambda (`message_aggregator`) usando una ventana de agregación como buffer
4. El agregador agrupa, ordena y concatena los mensajes de texto del mismo remitente
5. El mensaje agregado se reenvía al manejador de eventos de WhatsApp, que crea o actualiza la sesión de chat en Amazon Connect

## El Problema

Cuando los usuarios envían múltiples mensajes en rápida sucesión:

```
Mensaje 1: Hola
Mensaje 2: Necesito ayuda
Mensaje 3: con mi pedido
Mensaje 4: P12345
```

Sin buffering, cada mensaje crea un mensaje de chat separado en Amazon Connect. Esto genera:
- Una conversación fragmentada difícil de seguir para los agentes
- Costos más altos (cada mensaje se factura individualmente)
- Múltiples invocaciones de Lambda aguas abajo

## La Solución: Cómo Funciona el Buffering

### 1. Almacenamiento de Mensajes en Crudo

Los mensajes entrantes de WhatsApp se almacenan en una tabla de DynamoDB (`raw_messages`) con:

- Clave de partición: `from` (número de teléfono del remitente)
- Clave de ordenamiento: `id` (ID del mensaje)
- TTL habilitado para limpieza automática
- DynamoDB Streams habilitado con ventana de agregación

Usar `from` como clave de partición e `id` como clave de ordenamiento garantiza que los mensajes del mismo usuario se almacenen juntos y caigan en el mismo shard, por lo que se procesan secuencialmente por el stream.

La Lambda que maneja esto es sencilla:

```python
def lambda_handler(event, context):
    records = event.get("Records", [])

    for record in records:
        sns = record.get("Sns", {})
        sns_message = json.loads(sns.get("Message", "{}"), parse_float=decimal.Decimal)
        webhook_entry = json.loads(sns_message.get("whatsAppWebhookEntry", {}))

        for change in webhook_entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            contacts = value.get("contacts", [])

            for message in value.get("messages", []):
                item = message.copy()
                item["metadata"] = metadata
                item["messaging_product"] = value.get("messaging_product")

                # Almacenar en DynamoDB
                table.put_item(Item=item)

    return {'statusCode': 200}
```

### 2. Procesamiento del Stream con Ventana de Agregación

La ventana de agregación (tumbling window) es la clave de la estrategia de buffering. DynamoDB Streams activa la Lambda `message_aggregator`, pero en lugar de invocarla por cada registro individual, la ventana de agregación espera un número configurable de segundos (por defecto: 20) antes de invocar la función con todos los registros acumulados en esa ventana.

Cada shard invoca una sola Lambda, por lo que los mensajes del mismo usuario dentro de esa ventana se procesan todos juntos.

### 3. Lógica de Agregación

El agregador agrupa los mensajes por remitente, los ordena por marca de tiempo y concatena los mensajes de texto consecutivos con saltos de línea. Los mensajes que no son de texto (imágenes, audio, documentos, etc.) se preservan como elementos separados.

```
Entrada:
  Mensaje 1: Hola
  Mensaje 2: Necesito ayuda
  Mensaje 3: con mi pedido
  Mensaje 4: P12345

Salida (mensaje agregado único):
  Hola
  Necesito ayuda
  con mi pedido
  P12345
```

La lógica principal de agregación:

```python
def lambda_handler(event, context):
    raw_records = event.get("Records", [])

    records = []
    for record in raw_records:
        if record.get("eventName") == "INSERT":
            new_image = record.get("dynamodb", {}).get("NewImage", {})
            deserialized = deserialize_dynamodb(new_image)
            records.append(deserialized)

    if len(records) == 0:
        return {"state": event.get('state', {})}

    aggregated = aggregate_all_messages(records)

    # Reenviar cada mensaje agregado al manejador de eventos de WhatsApp
    for agg in aggregated:
        lambda_client.invoke(
            FunctionName=os.environ['WHATSAPP_EVENT_HANDLER'],
            InvocationType='Event',
            Payload=json.dumps(agg)
        )

    return {"state": event.get('state', {})}
```

### 4. Reenvío a Amazon Connect

Una vez agregados, la Lambda invoca asincrónicamente al manejador de eventos de WhatsApp, que crea o actualiza la sesión de chat en Amazon Connect con el mensaje combinado. El agente ve un mensaje limpio en lugar de cuatro mensajes separados.

### Beneficios

- **Flujo de conversación natural**: Múltiples mensajes rápidos aparecen como un solo mensaje coherente
- **Optimización de costos**: Menos mensajes aguas abajo significa menores costos de chat en Amazon Connect
- **Limpieza automática**: El TTL elimina los mensajes en crudo automáticamente
- **Escalable**: DynamoDB Streams maneja alto rendimiento (hasta 10,000 registros por stream)
- **Confiable**: El procesamiento del stream asegura que no se pierdan mensajes (entrega al menos una vez)

## Estimación de Costos

Escenario de ejemplo: 1,000 mensajes en crudo agregados en 250 mensajes (suponiendo una proporción de 4:1). Los mensajes son respondidos por un agente humano.

| Componente | Sin Buffering | Con Buffering | Ahorro |
|---|---|---|---|
| DynamoDB + Streams | — | ~$0.0013 | — |
| Lambda (todas las funciones) | — | ~$0.00078 | — |
| Infraestructura de Buffering | $0.00 | ~$0.002 | — |
| Llamadas API entrantes | 1,000 llamadas | 250 llamadas | 75% menos llamadas |
| Costo Chat Connect (entrada) | $4.00 | $1.00 | $3.00 |
| **Total** | **$4.00** | **~$1.00** | **~$3.00 (75%)** |


Ten en cuenta que el costo total considera Connect entrada y salida, así como EUM entrada y salida. Aquí solo estamos reduciendo los mensajes de entrada de Amazon Connect Chat.

- *Costo de Connect Chat: $0.004 × msg (entrada) + $0.004 × msg (salida). [Ver precios](https://aws.amazon.com/connect/pricing/)*
- *Costo de EUM: $0.005 × msg (entrada) + $0.005 × msg (salida). [Ver precios](https://aws.amazon.com/end-user-messaging/pricing/)*

## Prerrequisitos

Antes de comenzar necesitarás:

### Cuenta de WhatsApp Business

Para empezar, necesitas crear una nueva cuenta de WhatsApp Business (WABA) o migrar una existente a AWS. Los pasos principales se describen [aquí](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). En resumen:

1. Tener o crear una cuenta de Meta Business
2. Acceder a la consola de AWS End User Messaging Social y vincular tu cuenta de negocio a través del portal integrado de Facebook
3. Asegurarte de tener un número de teléfono que pueda recibir verificación por SMS/voz y agregarlo a WhatsApp

⚠️ Importante: No uses tu número personal de WhatsApp para esto.

### Una Instancia de Amazon Connect

Necesitas una instancia de Amazon Connect. Si aún no tienes una, puedes [seguir esta guía](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html) para crear una.

Necesitarás el **INSTANCE_ID** de tu instancia. Puedes encontrarlo en la consola de Amazon Connect o en el ARN de la instancia:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

### Un Flujo de Chat para Manejar Mensajes

Crea o ten listo el flujo de contacto que define la experiencia del usuario. [Sigue esta guía](https://docs.aws.amazon.com/connect/latest/adminguide/create-contact-flow.html) para crear un flujo de contacto de entrada (Inbound Contact Flow). El más sencillo funcionará.

Recuerda publicar el flujo.

![Flujo Simple](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/flow_simple.png)

Toma nota del **INSTANCE_ID** y **CONTACT_FLOW_ID** desde la pestaña de Detalles. Los valores están en el ARN del flujo:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID/contact-flow/CONTACT_FLOW_ID`

## Despliegue con AWS CDK

⚠️ Despliega en la misma región donde están configurados tus números de WhatsApp en AWS End User Messaging.

### 1. Clona el repositorio y navega al proyecto

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/whatsapp-eum-connect-chat
```

### 2. Despliega con CDK

Sigue las instrucciones en la [Guía de Despliegue con CDK](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_cdk_deploy.md).

## Configuración Post-despliegue

### Paso 1: Actualizar el Parámetro SSM

Después del despliegue, actualiza el parámetro SSM `/whatsapp_eum_connect_chat/config` con los detalles de tu Amazon Connect:

```json
{
  "instance_id": "<tu-connect-instance-id>",
  "contact_flow_id": "<tu-contact-flow-id>",
  "chat_duration_minutes": 60,
  "ignore_reactions": "yes",
  "ignore_stickers": "yes"
}
```

| Parámetro | Descripción |
|---|---|
| `instance_id` | El ID de tu instancia de Amazon Connect |
| `contact_flow_id` | El ID del flujo de contacto de entrada para chat |
| `chat_duration_minutes` | Cuánto tiempo permanece activa la sesión de chat (por defecto: 60) |
| `ignore_reactions` | Si se ignoran las reacciones de WhatsApp (por defecto: yes) |
| `ignore_stickers` | Si se ignoran los stickers de WhatsApp (por defecto: yes) |

### Paso 2: Agregar el Destino de Eventos

Después de desplegar el stack, usa el tema SNS creado como destino de eventos en la consola de AWS End User Messaging Social.

1. Ve a AWS Systems Manager Parameter Store y copia el valor de `/whatsapp_eum_connect_chat/topic/in` (comienza con `arn:aws:sns`)

![Parámetro del Tema](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/topic_parameter.png)

2. En la consola de AWS End User Messaging Social, selecciona el destino **Amazon SNS** y pega el **Topic ARN** del paso anterior

![Configuración SNS EUM](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/SNS_EUM.png)

### Paso 3: Ajustar el Tiempo de Buffer (Opcional)

La ventana de buffer por defecto es de 20 segundos. Si deseas cambiarla, edita `BUFFER_IN_SECONDS` en [`config.py`](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/whatsapp-eum-connect-chat/config.py) y vuelve a desplegar:

```python
BUFFER_IN_SECONDS = 20  # Cambia este valor (en segundos)
```

## Pruebas

Ve a tu instancia de Amazon Connect y [abre el Panel de Control de Contactos (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html). Envía un mensaje de WhatsApp al número de End User Messaging Social.

Intenta enviar una secuencia rápida de mensajes y observa cómo llegan como un solo mensaje agregado en Amazon Connect.

<div align="center">
<video src="https://github.com/user-attachments/assets/652683f2-5a5c-4a35-ad82-c80f0f3fe275" width="540" controls></video>
</div>

## Próximos Pasos

Aunque este blog se enfoca en WhatsApp y Amazon Connect, el patrón de buffering aplica de forma amplia. Cualquier canal de chat donde los usuarios envíen mensajes rápidos y asincrónicos — SMS, mensajes directos en redes sociales o integraciones personalizadas — puede beneficiarse del mismo enfoque. Si no puedes evitar que los usuarios envíen múltiples mensajes mientras se procesa una respuesta, al menos puedes controlar cuánto tiempo esperas antes de actuar.

Algunas ideas para extender esta solución:

- Ajustar la ventana de buffer según tu caso de uso (más corta para tiempo real, más larga para ahorro de costos)
- Agregar una Cola de Mensajes Fallidos (Dead Letter Queue) para el procesamiento fallido del stream
- Implementar lógica de agregación personalizada para tipos de mensajes específicos (por ejemplo, agrupar imágenes)
- Combinar con la solución de [WhatsApp Iniciado por el Agente](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) para comunicación bidireccional completa

## Recursos

- [Repositorio del Proyecto](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [Guía del Administrador de Amazon Connect](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [Referencia de API de Amazon Connect](https://docs.aws.amazon.com/connect/latest/APIReference/Welcome.html)
- [Guía del Usuario de AWS End User Messaging Social](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [Guía del Desarrollador de DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)
- [DynamoDB Streams y Ventanas de Agregación con Lambda](https://docs.aws.amazon.com/lambda/latest/dg/with-ddb.html)
