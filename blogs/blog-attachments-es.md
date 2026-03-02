# Manejo de Archivos Adjuntos (y notas de voz) entre WhatsApp y Amazon Connect

   _Aprende a manejar archivos adjuntos en ambas direcciones entre WhatsApp y Amazon Connect — imágenes, documentos, audio y video. Esta guía paso a paso cubre la arquitectura completa usando AWS CDK, AWS Lambda, AWS End User Messaging Social, Amazon S3 y Amazon Connect. Desde descargar medios de WhatsApp hasta subirlos al Chat de Connect, reenviar archivos del agente de vuelta a WhatsApp, y procesar notas de voz con conversión de formato y transcripción en tiempo real usando Amazon Transcribe._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/demo_attachments.gif)


Los mensajes de texto son solo el comienzo. Los clientes envían fotos de productos dañados, PDFs de facturas, notas de voz explicando su problema, y a veces incluso videos. Si tu integración de WhatsApp con Amazon Connect solo maneja texto, te estás perdiendo una gran parte de la conversación.

En este blog, aprenderás a manejar archivos adjuntos en ambas direcciones — del cliente al agente y del agente al cliente — incluyendo un pipeline para convertir y transcribir notas de voz. Esto habilita casos de uso avanzados como reclamos de seguros con evidencia fotográfica, instrucciones de voz transcritas para el agente, e intercambio de documentos sin salir del chat.

Consulta el código en [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## Lo que vas a construir

Una capa de manejo bidireccional de archivos adjuntos entre WhatsApp y Amazon Connect que:

1. Detecta y descarga medios de los mensajes entrantes de WhatsApp (imágenes, documentos, audio, video)
2. Convierte las notas de voz de WhatsApp (OGG/Opus) a WAV para compatibilidad con Connect
3. Transcribe las notas de voz en tiempo real usando Amazon Transcribe Streaming
4. Agrega esos archivos a la sesión de Chat de Amazon Connect para que los agentes puedan verlos
5. Reenvía los archivos enviados por los agentes desde el widget de Chat de Connect de vuelta a WhatsApp


El resultado final: agentes y clientes pueden intercambiar archivos de forma natural, y las notas de voz llegan tanto como audio reproducible como texto legible.

## Arquitectura

![Diagrama de Arquitectura](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/attach_arqui.png)

Así funciona el flujo:

1. Un cliente envía un archivo o medio por WhatsApp. La Lambda del manejador de entrada lo descarga a S3 usando el AWS SDK
2. Si el archivo es una nota de voz (OGG), se convierte a WAV usando ffmpeg en una Lambda separada
3. El archivo se sube a la sesión de Chat de Amazon Connect a través de la API de Participante
4. Cuando un agente envía un archivo desde el widget de Chat de Connect, el manejador de salida detecta el evento `ATTACHMENT`
5. El manejador obtiene una URL firmada del archivo y lo envía a WhatsApp como mensaje de medios


## Tipos de Mensajes de WhatsApp

Los mensajes de WhatsApp no son solo texto. El payload del webhook de Meta incluye un campo `type` que indica qué tipo de contenido envió el cliente. Cada tipo de medio lleva su contenido en un campo dedicado dentro del objeto del mensaje:

| Tipo | Campo | Descripción |
|---|---|---|
| `text` | `text` | Mensaje de texto plano |
| `image` | `image` | Fotos, capturas de pantalla, memes |
| `document` | `document` | PDFs, hojas de cálculo, documentos de Word |
| `audio` | `audio` | Notas de voz (formato OGG/Opus) |
| `video` | `video` | Clips de video |
| `sticker` | `sticker` | Stickers de WhatsApp |
| `reaction` | `reaction` | Reacciones con emoji a mensajes |



No todos son útiles en un contexto de atención al cliente. Los stickers y las reacciones típicamente agregan ruido en lugar de valor, por lo que la solución los hace configurables — puedes ignorarlos a través del parámetro SSM:

### Tipos de Adjuntos Soportados en este proyecto

| Dirección | Imágenes | Documentos | Audio | Video | Stickers | Reacciones
|---|---|---|---|---|---|---|
| Entrada (WhatsApp → Connect) | ✅ | ✅ | ✅ (convertido + transcrito) | N/I | Configurable | N/I
| Salida (Connect → WhatsApp) | ✅ | ✅ | — | — | — | - 

N/I: No implementado aquí, pero factible.

```json
{
  "ignore_reactions": "yes",
  "ignore_stickers": "yes"
}
```

Para los tipos de medios (`image`, `document`, `audio`, `video`), el payload del mensaje incluye un `media_id` que usas para descargar el contenido real del archivo. El archivo en sí no está en el webhook — necesitas obtenerlo por separado.

## Entrada: WhatsApp → Amazon Connect

Cuando un cliente envía un archivo por WhatsApp, la Lambda del manejador de entrada (`whatsapp_event_handler`) lo procesa en tres etapas: detección, descarga y subida.

### 1. Detección y Descarga

La clase `WhatsappMessage` inspecciona cada mensaje entrante en busca de campos de medios. Verifica `audio`, `image`, `document`, `video` y `sticker` en ese orden:

```python
def get_attachment(self, download=True):
    attachment = None
    if self.message.get("audio"):
        attachment = self.message.get("audio")
    elif self.message.get("image"):
        attachment = self.message.get("image")
    elif self.message.get("document"):
        attachment = self.message.get("document")
    elif self.message.get("video"):
        attachment = self.message.get("video")
    elif self.message.get("sticker"):
        attachment = self.message.get("sticker")
    # reacciones no implementadas

    if not attachment:
        return {}

    # Descargar usando la API de Social Messaging
    media_content = self.download_media(
        media_id=attachment.get("id"),
        phone_id=self.phone_number_id,
        bucket_name=BUCKET_NAME,
        media_prefix=ATTACHMENT_PREFIX,
    )
    # Leer contenido binario desde S3
    binary = self.get_s3_file_content(media_content.get("location"))
    attachment.update({"content": binary})
```

El método `download_media()` llama a la API de End User Messaging Social (`get_whatsapp_message_media`), que descarga el archivo desde Meta a un bucket de S3. El archivo queda en `s3://<bucket>/<prefix><media_id>.<extension>` donde la extensión se deriva del tipo MIME.


### 2. Subida al Chat de Amazon Connect

Una vez que el archivo está en S3 y su contenido binario está cargado, la función `process_attachment()` lo sube a la sesión activa de Chat de Connect usando la API de Participante. Este es un proceso de tres pasos:

1. `start_attachment_upload` — crea un slot de subida, retorna una URL pre-firmada y un ID de adjunto
2. `PUT` a la URL pre-firmada — sube el contenido binario
3. `complete_attachment_upload` — finaliza la subida

```python
def attach_file(self, fileContents, fileName, fileType, ConnectionToken):
    # Paso 1: Crear slot de subida
    attachResponse = participant_client.start_attachment_upload(
        ContentType=fileType,
        AttachmentSizeInBytes=fileSize,
        AttachmentName=fileName,
        ConnectionToken=ConnectionToken
    )

    # Paso 2: Subir a la URL pre-firmada
    upload_url = attachResponse['UploadMetadata']['Url']
    requests.put(
        upload_url,
        data=fileContents,
        headers=attachResponse['UploadMetadata']['HeadersToInclude'],
        timeout=30
    )

    # Paso 3: Finalizar
    participant_client.complete_attachment_upload(
        AttachmentIds=[attachResponse['AttachmentId']],
        ConnectionToken=ConnectionToken
    )
```


## Salida: Amazon Connect → WhatsApp

Cuando un agente envía un archivo desde el widget de Chat de Connect, la Lambda del manejador de salida (`connect_event_handler`) lo captura y lo reenvía a WhatsApp.

### 1. Detección de Adjuntos

Amazon Connect publica eventos de streaming a un tema de SNS. El manejador verifica el campo `Type` en cada evento:

- `MESSAGE` — mensaje de texto
- `ATTACHMENT` — archivo adjunto
- `EVENT` — eventos de entrada/salida de participantes


### 2. Obtención de URL Firmada

Para cada adjunto con `Status: APPROVED`, el manejador busca el número de teléfono del cliente y el número del sistema en DynamoDB usando el `contactId`, luego obtiene una URL de descarga temporal:

```python
def get_signed_url(connectionToken, attachment):
    response = participant_client.get_attachment(
        AttachmentId=attachment,
        ConnectionToken=connectionToken
    )
    return response['Url']
```

### 3. Envío a WhatsApp

El manejador mapea el tipo MIME al tipo de mensaje de WhatsApp correspondiente y envía el archivo usando la URL firmada como enlace de medios — no es necesario volver a subir el archivo:

```python
def send_whatsapp_attachment(attachment_url, mime_type, name, to, phone_number_id):
    message_type = get_file_category(mime_type)  # image, video, audio, o document
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"+{to}",
        "type": message_type,
    }
    message_object[message_type] = {"link": attachment_url}
    if message_type == "document":
        message_object[message_type]["filename"] = name

    socialessaging.send_whatsapp_message(
        originationPhoneNumberId=phone_number_id,
        metaApiVersion=meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
```

| Prefijo MIME | Tipo WhatsApp |
|---|---|
| `image/*` | `image` |
| `video/*` | `video` |
| `audio/*` | `audio` |
| todo lo demás | `document` |

Para los tipos `document`, se preserva el nombre original del archivo para que el cliente vea un nombre significativo en su chat de WhatsApp.


## Caso Especial. Procesamiento de Notas de Voz

Más allá del simple reenvío de archivos, los adjuntos pueden procesarse para habilitar casos de uso avanzados. El ejemplo más interesante en esta solución es el manejo de notas de voz — conversión de formatos de audio y transcripción de voz a texto.

### El Problema con las Notas de Voz

Las notas de voz de WhatsApp llegan en formato OGG/Opus. El Chat de Amazon Connect [no soporta archivos OGG como adjuntos](https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html). Si intentas subir un archivo OGG, será rechazado. Por eso necesitas un paso de conversión.

### Conversión OGG → WAV

Una función Lambda dedicada (`convert_to_wav`) maneja la conversión de formato usando ffmpeg. Después de la conversión, el manejador de entrada lee el contenido WAV desde S3 y lo sube al Chat de Connect como `voice.wav`.

### Transcripción en Tiempo Real con Amazon Transcribe Streaming

El archivo OGG original también se envía a una Lambda `transcribe_audio` para la conversión de voz a texto. Esta usa Amazon Transcribe Streaming — no la API por lotes — para obtener resultados en tiempo casi real.

## Más Allá de las Notas de Voz: Ideas de Procesamiento Avanzado

El mismo patrón — interceptar, procesar, reenviar — puede extenderse a otros tipos de adjuntos para casos de uso avanzados:

- **Comprensión de imágenes**: Usa Amazon Bedrock o Amazon Rekognition para analizar fotos. ¿Un cliente envía una foto de un producto dañado? Extrae una descripción y adjúntala al chat junto con la imagen. Útil para reclamos de seguros o solicitudes de garantía.
- **Análisis de video**: Extrae fotogramas clave de los adjuntos de video y pásalos por modelos multimodales para su comprensión. ¿Un cliente envía un video de un dispositivo con fallas? Resume el problema para el agente.
- **Extracción de documentos**: Usa Amazon Textract o Modelos de Base multimodales para extraer texto de documentos escaneados, facturas o formularios. Pre-llena los detalles del caso antes de que el agente abra el chat.
- **Detección de idioma y traducción**: Detecta el idioma de las notas de voz o el texto en imágenes y tradúcelos antes de reenviarlos al agente.

El manejador de entrada está diseñado para ser extensible — puedes agregar pasos de procesamiento entre la descarga y la subida a Connect sin cambiar el flujo general.



## Prerrequisitos de Despliegue

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

(consulta los [Prerrequisitos de WhatsApp / Connect](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_connect_eum.md) para más detalles)

### Importante: Habilitar Adjuntos en la Instancia de Amazon Connect

Sigue [estos pasos](https://docs.aws.amazon.com/connect/latest/adminguide/enable-attachments.html) para habilitar el intercambio de adjuntos.


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

### Paso 3: Configurar el Idioma de Transcripción (Opcional)

El idioma de transcripción está configurado en `es-US` (Español) por defecto. Para cambiarlo, edita el parámetro `language_code` en `lambdas/code/transcribe_audio/transcribe.py`:

```python
stream = await self.transcribe_client.start_stream_transcription(
    language_code="en-US",  # Cambia al idioma deseado
    media_sample_rate_hz=48000,
    media_encoding="ogg-opus",
)
```

## Pruebas

Ve a tu instancia de Amazon Connect y [abre el Panel de Control de Contactos (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html). Envía un mensaje de WhatsApp al número de End User Messaging Social.

<div align="center">
<video src="https://github.com/user-attachments/assets/652683f2-5a5c-4a35-ad82-c80f0f3fe275" width="540" controls></video>
</div>

Prueba estos escenarios:

- Envía una foto — debería aparecer como un adjunto de imagen en el chat del agente
- Envía un PDF — debería aparecer como un adjunto de documento
- Envía una nota de voz — debería llegar como un archivo de audio WAV más una transcripción de texto
- Desde el lado del agente, envía una imagen o documento — debería aparecer en el chat de WhatsApp del cliente

## Próximos Pasos

Esta solución maneja el flujo principal de adjuntos. Algunas ideas para extenderla:

- Modelo de Base multimodal para análisis de imágenes en fotos entrantes (por ejemplo, evaluación de daños para reclamos)
- Implementar soporte para adjuntos de video entrantes
- Soportar múltiples idiomas de transcripción con detección automática de idioma
- Combinar con la solución de [Buffering de Mensajes](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/whatsapp-eum-connect-chat) para agregar mensajes rápidos y la solución de [WhatsApp Iniciado por el Agente](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) para comunicación proactiva completa

## Recursos

- [Repositorio del Proyecto](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [Guía del Administrador de Amazon Connect](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [Amazon Connect Chat — Tipos de Adjuntos Soportados](https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html)
- [API de Participante de Amazon Connect — StartAttachmentUpload](https://docs.aws.amazon.com/connect-participant/latest/APIReference/API_StartAttachmentUpload.html)
- [AWS End User Messaging Social — API SendWhatsAppMessage](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_SendWhatsAppMessage.html)
- [Guía del Usuario de AWS End User Messaging Social](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [SDK de Amazon Transcribe Streaming](https://github.com/awslabs/amazon-transcribe-streaming-sdk)
- [Plataforma WhatsApp Business — Mensajes de Medios](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media)
