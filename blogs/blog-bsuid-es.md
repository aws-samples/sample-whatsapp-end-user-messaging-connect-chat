# Soportar Business-Scoped User IDs (BSUID) de WhatsApp en tu integración con Amazon Connect

   _Aprende a hacer que una integración de WhatsApp con Amazon Connect siga funcionando cuando el número de teléfono del cliente ya no está garantizado en el webhook. Esta guía paso a paso cubre los Business-Scoped User IDs (BSUID) de Meta, cómo transportar una identidad opaca del remitente a través de AWS Lambda, Amazon DynamoDB y Amazon Connect Chat, y cómo responder usando `recipient` en lugar de `to`. Construido sobre la solución existente de WhatsApp End User Messaging + Amazon Connect con AWS CDK._


![Demo](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/demo_blurred.gif)


Toda integración de WhatsApp que se ha construido tiene el mismo supuesto grabado en alguna parte: el cliente *es* su número de teléfono. Es la clave de la base de datos, la búsqueda en el CRM, el atributo de contacto que ve el agente y el destino al que le respondes.

Ese supuesto está por vencer. WhatsApp está desplegando **usernames**, una función opcional que permite a un usuario mostrar un nombre de usuario en lugar de su número de teléfono. Cuando un usuario adopta uno, [su número deja de aparecer en los payloads de webhook](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids/). Para que puedas seguir identificando y respondiendo a esos usuarios, Meta introdujo un nuevo identificador: el **Business-Scoped User ID (BSUID)**, entregado en una propiedad `user_id` / `from_user_id`. Soportarlo es obligatorio para todos los partners y negocios integrados directamente a la WhatsApp Business Platform.

La buena noticia: si tu pipeline está bien construido, este cambio es más pequeño de lo que suena. En este blog verás los cambios exactos que se hicieron en la [solución de WhatsApp End User Messaging + Amazon Connect Chat](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat) para soportar BSUID de punta a punta: un puñado de funciones, cero cambios de infraestructura y una decisión de diseño que evita que el resto del código tenga que enterarse.

Consulta el código en [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


## Lo que vas a construir

Una integración WhatsApp ↔ Amazon Connect que ya no asume que la identidad del cliente es un número de teléfono. En concreto:

1. Detecta si un mensaje entrante trae un BSUID (`from_user_id`) o solo un número de teléfono (`from`)
2. Usa el que esté disponible como identidad de la conversación, y conserva el número de teléfono como atributo separado cuando existe
3. Transporta esa identidad por la capa de buffering, las tablas de DynamoDB y hasta los atributos de contacto de Amazon Connect Chat
4. Direcciona los mensajes salientes con `recipient` (BSUID) o `to` (número), según la identidad almacenada
5. Se mantiene retrocompatible con las conversaciones que iniciaron antes del cambio

El resultado final: los clientes que adopten un username siguen hablando con tus agentes, y nada del flujo se rompe cuando el número desaparece del payload.

## Entendiendo BSUID

Un BSUID es un identificador opaco de un usuario de WhatsApp, con alcance limitado a un solo portafolio de negocio de Meta. Dos cosas importan para la implementación:

- **Siempre está presente.** Los BSUID aparecen en los webhooks de mensajes independientemente de si el usuario adoptó un username. El número de teléfono es el campo que puede faltar.
- **No es un número de teléfono.** Los BSUID llevan como prefijo el código de país ISO 3166 alpha-2 del usuario y un punto, seguidos de hasta 128 caracteres alfanuméricos. Por ejemplo `US.XXXXXXXXXXXXXXX`. Cuando envías a un BSUID debes usar el valor completo, incluyendo el código de país y el punto.

### Qué identificador llega, y cuándo

| Campo | El usuario tiene username | El usuario no tiene username |
|---|---|---|
| `messages[].from` (número) | Solo si el número está disponible según las condiciones de Meta | Siempre incluido |
| `messages[].from_user_id` (BSUID) | Siempre incluido | Siempre incluido |
| `contacts[].wa_id` (número) | Solo si está disponible | Siempre incluido |
| `contacts[].user_id` (BSUID) | Siempre incluido | Siempre incluido |
| `contacts[].profile.username` | Siempre incluido | No incluido |

Meta todavía comparte el número en algunos casos: si le enviaste o recibiste un mensaje o llamada de ese número en los últimos 30 días, o si el usuario está en tu contact book. En la práctica esto significa que **no puedes depender de que el número esté, ni de que no esté.** Tu código tiene que manejar ambos casos, mensaje por mensaje.

Este es un webhook entrante de un usuario que tiene BSUID y cuyo número aún está disponible (es el fixture que quedó en el repo como `lambdas/code/on_raw_messages/entry.json`):

```json
{
  "changes": [
    {
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "XXXXXXXXXX",
          "phone_number_id": "XXXXXXXXXXXXXX"
        },
        "contacts": [
          {
            "profile": { "name": "Kike" },
            "wa_id": "XXXXXXXXX",
            "user_id": "US.XXXXXXXXXXXXXXX"
          }
        ],
        "messages": [
          {
            "from": "XXXXXXXXX",
            "from_user_id": "US.XXXXXXXXXXXXXXX",
            "id": "wamid.XXXXXXXXXXXXXXXXXXXXXXXXXXXXX=",
            "timestamp": "1787204895",
            "text": { "body": "Hola" },
            "type": "text"
          }
        ]
      },
      "field": "messages"
    }
  ]
}
```

Cuando ese mismo usuario adopta un username y se vence la ventana de 30 días, `from` y `wa_id` simplemente desaparecen. Todo lo demás se mantiene.

### Envío: `to` vs `recipient`

Del lado del envío, Meta agregó una propiedad `recipient` junto al `to` existente:

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "<USER_PHONE_NUMBER>",
  "recipient": "<BSUID>",
  "type": "text",
  "text": { "body": "<BODY_TEXT>" }
}
```

Puedes incluir ambos, en cuyo caso `to` tiene precedencia. Esta solución envía exactamente uno de los dos: es más limpio y deja explícito en el payload cuál modo de identidad se está usando.

Un detalle importante del lado de AWS: **AWS End User Messaging Social pasa el cuerpo del mensaje tal cual.** La API `send_whatsapp_message` recibe el payload de Meta como bytes crudos:

```python
socialmessaging.send_whatsapp_message(
    originationPhoneNumberId=phone_number_id,
    metaApiVersion=meta_api_version,
    message=bytes(json.dumps(message_object), "utf-8"),
)
```

Por lo tanto no hay ningún cambio de API del lado de AWS que adoptar. `recipient` es un campo dentro de `message`, y el soporte viene de la `metaApiVersion` que envías. Mantén `META_API_VERSION` actualizado en [`config.py`](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/whatsapp-eum-connect-chat/config.py).

## Arquitectura

![Diagrama de Arquitectura](https://raw.githubusercontent.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/main/whatsapp-eum-connect-chat/whatsapp-optimization-connect-DynamoDB.drawio.svg)

La arquitectura no cambia. Ese es justamente el punto: sin recursos nuevos, sin tablas nuevas, sin migración de esquema. El flujo sigue siendo:

1. AWS End User Messaging Social publica el webhook de WhatsApp en un tema de Amazon SNS
2. `on_raw_messages` escribe cada mensaje en la tabla `raw_messages` de DynamoDB
3. DynamoDB Streams con ventana de agregación dispara `message_aggregator`, que hace buffer y concatena mensajes consecutivos
4. `whatsapp_event_handler` inicia o continúa la sesión de Amazon Connect Chat
5. Amazon Connect envía los mensajes del agente a SNS, y `connect_event_handler` los reenvía a WhatsApp

Lo que cambió es **el valor que circula por ahí como identidad del cliente**, y los dos lugares que convierten ese valor en un destino.

## La decisión de diseño clave: una identidad, decidida una sola vez

La tentación con BSUID es agregar manejo de `user_id` en cada Lambda. No lo hagas. En cambio, elige la identidad una sola vez en la ingesta y deja que todo lo de aguas abajo la trate como un string opaco.

El pipeline ya tenía un lugar natural para esto: `item["from"]`, que es la clave de partición de la tabla `raw_messages` y el valor que termina convirtiéndose en `customerId` en Amazon Connect. En lugar de agregar un campo paralelo, el cambio **redefine qué significa `from`**: ya no es "el número de teléfono", es "lo que sea que identifique a este remitente".

Esa única decisión es la razón por la que el diff es pequeño.

### 1. Ingesta: elegir el modo de identidad

`lambdas/code/on_raw_messages/lambda_function.py` es el único lugar que ramifica según el modo de identidad:

```python
for message in value.get("messages", []):
    item = message.copy()
    item["context"] = message_context
    item["metadata"] = metadata
    item["messaging_product"] = messaging_product
    item["field"] = field

    from_phone_number = message.get("from")
    from_user_id = message.get("from_user_id")

    # Identity mode: user_id when available, phone number otherwise.
    if from_user_id:
        item["from"] = from_user_id
        contact_key, contact_value = "user_id", from_user_id
    else:
        item["from"] = from_phone_number
        contact_key, contact_value = "wa_id", from_phone_number

    item["from_phone_number"] = from_phone_number
    if from_user_id:
        item["from_user_id"] = from_user_id

    contact = next((c for c in contacts if c.get(contact_key) == contact_value), {})
    item["contact"] = contact

    table.put_item(Item=item)
```

Antes del cambio, ese bloque eran dos líneas y el contacto siempre se buscaba por `wa_id`:

```python
wa_id = message.get("from")
contact = next((c for c in contacts if c.get("wa_id") == wa_id), {})
```

Ahora pasan tres cosas:

- `item["from"]` guarda el BSUID cuando existe, y el número de teléfono en caso contrario. Esto se convierte en la clave de la conversación.
- `item["from_phone_number"]` preserva el `from` original de Meta, así el número real sigue disponible cuando lo tienes: para enriquecer el CRM, para callbacks o para analítica.
- `item["from_user_id"]` se escribe **solo cuando no está vacío**, porque el código aguas abajo ramifica según su presencia y no según su valor. Un string vacío sería indistinguible de uno real a simple vista y volvería más ruidosas las condiciones.

Nota que la clave de búsqueda del contacto se mueve junto con el modo de identidad: `user_id` para remitentes con BSUID, `wa_id` para remitentes con número. El array de contactos viene indexado de forma distinta según cuál recibiste.

### 2. Buffering: reenviar los campos nuevos de forma explícita

Este es el paso que se pasa por alto fácilmente. La Lambda `message_aggregator` reconstruye un payload sintético de webhook a partir de las imágenes del stream de DynamoDB, y lo hace con una **lista explícita de campos permitidos**. Cualquier campo que no esté ahí se descarta silenciosamente entre la tabla de buffer y el handler.

Se agregaron dos constructores en `lambdas/code/message_aggregator/process_stream.py`:

```python
def build_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild a webhook contact, keeping user_id when the sender has one."""
    payload: Dict[str, Any] = {
        'profile': contact.get('profile', {}),
        'wa_id': contact.get('wa_id', '')
    }
    if contact.get('user_id'):
        payload['user_id'] = contact['user_id']
    return payload


def build_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild a webhook message, keeping the sender identity fields."""
    payload: Dict[str, Any] = {
        'from': message.get('from'),
        'id': message.get('id'),
        'timestamp': message.get('timestamp'),
        'text': message.get('text'),
        'type': message.get('type'),
        'audio': message.get('audio'),
        'image': message.get('image'),
        'video': message.get('video'),
        'document': message.get('document'),
        'sticker': message.get('sticker'),
        'location': message.get('location'),
        'contacts': message.get('contacts'),
        'interactive': message.get('interactive')
    }

    # from_user_id only exists for senders identified by user_id, and downstream
    # code branches on its presence, so it is omitted when empty.
    if message.get('from_user_id'):
        payload['from_user_id'] = message['from_user_id']
    if message.get('from_phone_number'):
        payload['from_phone_number'] = message['from_phone_number']

    return payload
```

La lógica de agregación en sí no necesitó cambios. Agrupa por `record.get('from')`, así que ahora agrupa por BSUID de forma transparente:

```python
sender = record.get('from')
key = (json.dumps(metadata, sort_keys=True), json.dumps(context, sort_keys=True), sender)
```

Si tienes tu propia capa de transformación entre el webhook y tus handlers, revísala buscando este mismo patrón. Las listas de campos permitidos son buena práctica, y son exactamente lo que se rompe cuando aparece un identificador nuevo.

### 3. Handler entrante: responder con `recipient` o `to`

La clase `WhatsappMessage` ahora deriva tres atributos de identidad en lugar de uno, en `lambdas/code/whatsapp_event_handler/whatsapp.py`:

```python
self.phone_number = message.get("from", "")
self.from_user_id = message.get("from_user_id", "")
# Older payloads only carry "from", which is the phone number in that case.
self.from_phone_number = message.get("from_phone_number") or (
    "" if self.from_user_id else self.phone_number
)
```

Ese fallback en `from_phone_number` es la bisagra de retrocompatibilidad. Los ítems escritos por la versión anterior del stack no tienen el atributo `from_phone_number`, y su `from` *sí es* un número de teléfono. Tratar `from` como número cuando no hay `from_user_id` mantiene funcionando las respuestas de las conversaciones en vuelo.

El destino se resuelve entonces en un solo lugar:

```python
def get_recipient(self):
    """Destination field for a send_whatsapp_message payload.

    Senders identified by user_id are addressed with "recipient";
    senders identified by phone number are addressed with "to".
    """
    if self.from_user_id:
        return {"recipient": self.from_user_id}
    if self.from_phone_number:
        return {"to": f"+{self.from_phone_number}"}
    return {}
```

Y cada payload saliente construye el cuerpo del mensaje *sin* destino, y luego lo inyecta:

```python
def text_reply(self, text_message):
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "context": {"message_id": self.message_id},
        "type": "text",
        "text": {"preview_url": False, "body": text_message},
    }
    message_object.update(self.get_recipient())

    kwargs = dict(
        originationPhoneNumberId=self.phone_number_id,
        metaApiVersion=self.meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
    response = self.client.send_whatsapp_message(**kwargs)
```

Antes, estos diccionarios llevaban un `"to": f"+{self.phone_number}"` hardcodeado. El patrón con `.update()` vale la pena copiarlo: mantiene la decisión del destino en exactamente una función, así que agregar soporte para parent BSUIDs más adelante es un cambio de una línea. El mismo tratamiento se aplicó a `reaction()`. `mark_as_read()` no necesita destino y quedó intacto.

### 4. Nombre del contacto: buscar por la clave correcta

Resolver el nombre del cliente tiene el mismo problema de dos modos: el array de contactos viene indexado por `user_id` o por `wa_id` según el remitente. La firma del método cambió de `(from_number, contacts)` a `(message, contacts)` para poder inspeccionar la identidad:

```python
def get_customer_name(self, message, contacts):
    """Match the contact by user_id when present, by wa_id otherwise."""
    from_user_id = message.get("from_user_id")
    if from_user_id:
        key, value = "user_id", from_user_id
    else:
        key, value = "wa_id", message.get("from_phone_number") or message.get("from", "")

    for contact in contacts:
        if contact.get(key) == value:
            return contact.get("profile", {}).get("name", "NN")
    return ""
```

### 5. Salida desde Amazon Connect: inferir el modo desde el valor almacenado

El lado del agente es el interesante. `connect_event_handler` nunca ve el webhook original: solo tiene el `customerId` que buscó en DynamoDB a partir del `contactId`. Así que tiene que inferir si ese string es un BSUID o un número de teléfono.

En `lambdas/code/connect_event_handler/whatsapp.py`:

```python
# A phone number destination is only digits, optionally prefixed with "+".
PHONE_NUMBER_PATTERN = re.compile(r"^\+?\d+$")


def get_recipient(destination):
    """Destination field for a send_whatsapp_message payload.

    active_connections stores whatever identified the customer: a WhatsApp
    user_id (e.g. "US.XXXXXXXXXXXXXXX") or a phone number. user_id
    destinations are addressed with "recipient", phone numbers with "to".
    """
    destination = str(destination or "").strip()
    if not destination:
        return {}
    if PHONE_NUMBER_PATTERN.match(destination):
        return {"to": f"+{destination.lstrip('+')}"}
    return {"recipient": destination}
```

Ambas funciones de envío la usan igual que el handler entrante:

```python
def send_whatsapp_text(text_message, to, phone_number_id, meta_api_version=META_API_VERSION):
    message_object = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "text",
        "text": {"preview_url": False, "body": text_message},
    }
    message_object.update(get_recipient(to))

    kwargs = dict(
        originationPhoneNumberId=phone_number_id,
        metaApiVersion=meta_api_version,
        message=bytes(json.dumps(message_object), "utf-8"),
    )
    response = socialessaging.send_whatsapp_message(**kwargs)
```

Inferir por la forma del string funciona acá porque los BSUID siempre llevan prefijo de país y un punto, así que nunca pueden hacer match con `^\+?\d+$`. Es una decisión pragmática que evita agregar una columna a la tabla de conexiones. Si prefieres ser explícito, guarda un atributo `identityType` junto a `customerId` cuando se crea el contacto y ramifica según eso. Vale la pena si tu espacio de `customerId` podría llegar a incluir identificadores compuestos solo por dígitos provenientes de otro canal.

### 6. Qué ve Amazon Connect

`start_chat_contact` no se modificó, pero es donde la identidad llega al agente. Como quien lo invoca pasa `message.phone_number` (que es `from`, es decir el BSUID cuando existe), el atributo de contacto `customerId` ahora lleva el BSUID:

```python
start_chat_response = self.connect.start_chat_contact(
    InstanceId=self.instance_id,
    ContactFlowId=self.contact_flow_id,
    Attributes={
        "Channel": channel,
        "customerId": phone,
        "customerName": name,
        "systemNumber": systemNumber,
    },
    ParticipantDetails={"DisplayName": name},
    InitialMessage={"ContentType": "text/plain", "Content": message},
    ChatDurationInMinutes=self.chat_duration_minutes,
    ...
)
```

**Revisa tus contact flows.** Si un flujo, una Lambda invocada desde el flujo o una pantalla del agente usa `customerId` como número de teléfono — una búsqueda en el CRM, un callback, una llamada saliente — ahora va a recibir `US.XXXXXXXXXXXXXXX` para algunos clientes. Dos opciones: pasar el número como un segundo atributo (está disponible en `message.from_phone_number` cuando existe), o hacer que el consumidor maneje ambas formas. Este es el cambio con más probabilidad de sorprenderte en producción, y vive fuera del código de este repositorio.

## Diferencias con la versión anterior, de un vistazo

| Aspecto | Antes | Después |
|---|---|---|
| Identidad de la conversación | `messages[].from` (siempre un número) | BSUID cuando existe, número en caso contrario |
| Número de teléfono | Era la identidad | Atributo `from_phone_number` aparte, puede faltar |
| Clave de búsqueda del contacto | Siempre `wa_id` | `user_id` o `wa_id`, por mensaje |
| Destino saliente | `"to": f"+{phone}"` hardcodeado | `get_recipient()` devuelve `{"recipient": ...}` o `{"to": ...}` |
| Payload del agregador | Lista fija de campos permitidos | La misma lista más `from_user_id`, `from_phone_number` y el `user_id` del contacto |
| Clave de partición `from` de `raw_messages` | `XXXXXXXXX` | `US.XXXXXXXXXXXXXXX` o `XXXXXXXXX` |
| GSI `customerId` de `active_connections` | Número de teléfono | BSUID o número de teléfono |
| Esquema y GSIs de DynamoDB | — | **Sin cambios** |
| Stack de CDK, IAM, SNS, tablas | — | **Sin cambios** |
| Llamadas a APIs de AWS | `send_whatsapp_message` | **Sin cambios** — solo cambia el cuerpo Meta serializado |

Vale repetirlo: **sin cambios de infraestructura y sin migración de esquema.** Las dos claves afectadas ya son de tipo `STRING` y son opacas para DynamoDB. La clave de partición de `raw_messages` sigue siendo `from`, y el GSI de `active_connections` sigue siendo `customerId-index`. Lo único que se amplió es el espacio de valores.

## Detalles a tener en cuenta antes de desplegar

**Los nombres van detrás de la semántica.** `WhatsappMessage.phone_number`, la variable `phone` en `connect_event_handler.process_message` y la línea de log `"Found existing connection for Phone Number..."` ahora manejan BSUIDs. Solo `from_phone_number` tiene garantizado ser un número de teléfono. Renombrarlos es un buen siguiente paso; dejarlos así es una buena forma de confundir a la próxima persona que lea el código.

**Continuidad de la conversación durante la transición.** Una conversación que empezó antes de que aparecieran los BSUID está indexada por número. Cuando Meta empiece a enviar `from_user_id` para ese usuario, la búsqueda en el GSI `customerId` no encuentra nada y se crea un nuevo contacto en Amazon Connect. En el sample no hay código de migración para esto. Si necesitas continuidad, la solución es una segunda búsqueda: intenta con el BSUID, luego cae a `from_phone_number` cuando esté presente, y reescribe el `customerId` almacenado cuando haya coincidencia.

**Los BSUID se regeneran cuando un usuario cambia su número.** Meta reporta esto en el campo `messages` como un mensaje de sistema, con `system.type` en `user_changed_number` o `user_changed_user_id`, y con `system.previous_user_id` llevando el valor anterior. Esa es tu clave para unir la nueva identidad al registro que ya tenías. Esta solución todavía no maneja mensajes con `type: "system"`. Si la continuidad de identidad te importa, ese es el siguiente handler que hay que escribir.

**Los payloads salientes se registran en logs.** El `print(kwargs)` en `reaction()` y en ambas funciones `send_whatsapp_*` escribe el payload saliente completo en Amazon CloudWatch Logs, incluyendo el identificador del destinatario. Tanto los BSUID como los números son identificadores de cliente; revisa tu retención y tus permisos de acceso a logs antes de que esto llegue a producción.

**La salida iniciada por el agente todavía asume números de teléfono.** La solución complementaria de [WhatsApp iniciado por el agente](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) direcciona a los clientes solo por número. Está bien para su caso de uso — un agente escribiendo un número en un formulario — pero si quieres que los agentes contacten proactivamente a un cliente que solo tiene BSUID, ese camino necesita el mismo tratamiento con `get_recipient()`.

**Si de verdad necesitas el número, pídelo.** Meta agregó un botón `REQUEST_CONTACT_INFO` para plantillas de utilidad y marketing, y también como mensaje interactivo. Cuando el usuario lo toca, su número se comparte en la conversación y llega en un webhook de contactos. Si tu proceso de negocio realmente requiere un número (verificación de identidad, envíos, un callback), constrúyelo dentro de la conversación en lugar de depender del webhook.

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

(consulta los [prerrequisitos de WhatsApp / Connect](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_connect_eum.md) para más detalles)

### Opcional: Habilitar Archivos Adjuntos

Si quieres que imágenes, documentos y notas de voz circulen en ambas direcciones, sigue [estos pasos](https://docs.aws.amazon.com/connect/latest/adminguide/enable-attachments.html) para habilitar el intercambio de adjuntos en tu instancia. Los cambios de BSUID cubren también el envío de adjuntos: `send_whatsapp_attachment` usa el mismo helper `get_recipient()`.

## Despliegue con AWS CDK

⚠️ Despliega en la misma región donde están configurados tus números de WhatsApp en AWS End User Messaging.

### 1. Clona el repositorio y navega al proyecto

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/whatsapp-eum-connect-chat
```

### 2. Despliega con CDK

Sigue las instrucciones en la [Guía de Despliegue con CDK](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/general_cdk_deploy.md).

Como el soporte de BSUID está enteramente en el código de las Lambdas, un despliegue existente solo necesita volver a desplegarse: sin reemplazo de tablas ni migración de datos.

```bash
cdk deploy
```

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

### Paso 3: Revisar la versión de la API de Meta

`recipient` es un campo del payload de Meta, así que el soporte depende de la versión de API que envíes. Se define en [`config.py`](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/blob/main/whatsapp-eum-connect-chat/config.py):

```python
BUFFER_IN_SECONDS = 5
META_API_VERSION = "v23.0"
```

Confirma que la versión que estás usando soporta envíos a BSUID, y súbela si es necesario antes de depender de `recipient` en producción.

### Paso 4: Auditar tus contact flows

Busca `customerId` en tus contact flows, en las Lambdas invocadas desde flujos y en las vistas del workspace del agente. Donde sea que se trate como número de teléfono, hay que manejar la forma del BSUID o pasar el número como atributo separado. Haz esto antes de tener clientes que solo tengan BSUID, no después.

## Pruebas

No hace falta esperar a un usuario real con username. El App Dashboard de Meta tiene una herramienta de prueba de webhooks que envía payloads realistas a tu endpoint: **App Dashboard > Use cases (icono de lápiz) > Connect with customers through WhatsApp > Customize > Configuration**, y luego **Test** junto al webhook de messages. Cubre los escenarios que importan:

- El usuario no adoptó username — BSUID y número presentes
- El usuario adoptó username, número no disponible — solo BSUID
- El usuario adoptó username, número disponible — todo presente

Para un ciclo más rápido, invoca las Lambdas directamente con los fixtures del repositorio. `lambdas/code/on_raw_messages/entry.json` es un payload con BSUID, y `lambdas/code/message_aggregator/event.json` es el evento de stream de DynamoDB correspondiente.

Después ve a tu instancia de Amazon Connect, [abre el Panel de Control de Contactos (CCP)](https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html) y verifica:

- Un mensaje real de WhatsApp sigue creando el chat y el agente sigue viendo el nombre del cliente
- La respuesta del agente llega de vuelta a WhatsApp (esto comprueba que la selección `recipient`/`to` funciona en el viaje completo)
- El ítem en la tabla `raw_messages` tiene `from` = BSUID, `from_user_id` = BSUID, `from_phone_number` = el número
- El atributo `customerId` del contacto coincide con lo que hay en `raw_messages`
- Envía varios mensajes rápido: el buffering debe seguir agrupándolos, ahora indexados por BSUID

## Próximos Pasos

El soporte de BSUID es el piso, no el techo. Algunas ideas para construir sobre esto:

- Manejar los mensajes con `type: "system"` para poder seguir `user_changed_number` / `user_changed_user_id` y mantener la continuidad de identidad cuando se regenera un BSUID
- Agregar una búsqueda de respaldo por número en el GSI `customerId` para que las conversaciones sobrevivan la transición
- Pasar el número de teléfono a Amazon Connect como su propio atributo de contacto, para que los flujos puedan usarlo sin parsear `customerId`
- Agregar un botón `REQUEST_CONTACT_INFO` a tu journey para los casos en que realmente necesitas un número
- Extender la solución de [WhatsApp iniciado por el agente](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat/tree/main/agent-initiated-whatsapp) para direccionar BSUIDs
- Si operas múltiples portafolios de negocio, revisa los parent BSUIDs (`from_parent_user_id`) para que un solo identificador funcione en todos

## Recursos

- [Repositorio del Proyecto](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [WhatsApp Business Platform — Business-scoped user IDs](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids/)
- [AWS End User Messaging Social — API SendWhatsAppMessage](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_SendWhatsAppMessage.html)
- [Guía del Usuario de AWS End User Messaging Social](https://docs.aws.amazon.com/social-messaging/latest/userguide/what-is-service.html)
- [Guía del Administrador de Amazon Connect](https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html)
- [API de Amazon Connect — StartChatContact](https://docs.aws.amazon.com/connect/latest/APIReference/API_StartChatContact.html)
- [Guía del Desarrollador de DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)

_El contenido de la documentación para desarrolladores de Meta fue reformulado para cumplir con las restricciones de licenciamiento._
