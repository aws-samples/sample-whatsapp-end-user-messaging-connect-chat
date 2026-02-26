# Mensajes de WhatsApp iniciados por el agente desde Amazon Connect

¿Tu equipo de atención al cliente necesita enviar mensajes proactivos por WhatsApp? Imagina que un agente pueda, desde su escritorio de Amazon Connect, enviar un mensaje de plantilla de WhatsApp a un cliente con un solo clic. Sin salir de la consola, sin copiar y pegar números, sin errores.

En este blog te muestro cómo construir esa experiencia usando AWS CDK, AWS Lambda, AWS End User Messaging Social y Amazon Connect.

Revisa el código en [https://github.com/aws-samples](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)


<div align="center">
<video src="https://github.com/user-attachments/assets/251a757c-2fe8-4875-966f-32d2bb7c3aa7" width="600" controls></video>
</div>


## ¿Qué vamos a construir?

Una experiencia guiada dentro del Agent Workspace de Amazon Connect que permite a los agentes:

1. Ver los datos del cliente pre-cargados en un formulario
2. Revisar y editar los parámetros de la plantilla de WhatsApp
3. Enviar el mensaje con un clic

Todo orquestado por un Contact Flow, funciones Lambda y un formulario (Connect view).

## Arquitectura

![Diagrama de Arquitectura](../agent-initiated-whatsapp/agent-initiated-whatsapp.svg)

El flujo es el siguiente:

1. Un Contact Flow invoca una función AWS Lambda (`get_customer_data`) para obtener la información del cliente (nombre, teléfono, etc.). También puede utilizar el bloque  [`Customer Profile`](https://docs.aws.amazon.com/connect/latest/adminguide/customer-profiles-block.html) para buscar información de cliente en Customer Profiles de Connect.
2. El flujo presenta un formulario (View) en el Agent Workspace con los datos pre-llenados
3. El agente revisa, edita si es necesario, y envía
4. Una segunda Lambda (`send_whatsapp_message`) envía el mensaje de plantilla de WhatsApp usando la API de AWS End User Messaging Social

## Requisitos previos

Antes de comenzar necesitas:

### Cuenta de WhatsApp Business / WhatsApp Business Account

Para comenzar, necesitas crear una nueva cuenta de WhatsApp Business (WABA) o migrar una existente a AWS. Los pasos principales están descritos [aquí](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). En resumen:

1. Tener o crear una cuenta de Meta Business
2. Acceder a la consola de AWS End User Messaging Social y vincular tu cuenta de negocio a través del portal embebido de Facebook
3. Asegurarte de tener un número de teléfono que pueda recibir verificación por SMS/voz y agregarlo a WhatsApp

⚠️ Importante: No uses tu número personal de WhatsApp para esto.

### Instancia de Amazon Connect / An Amazon Connect Instance

Necesitas una instancia de Amazon Connect. Si aún no tienes una, puedes [seguir esta guía](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html) para crearla.

Necesitarás el **INSTANCE_ID** de tu instancia. Lo puedes encontrar en la consola de Amazon Connect o en el ARN de la instancia:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

(consulta la [Prerequisitos Whatsapp / Connect](../general_connect_eum.md) mara mayores detalles) 


### Creación de plantillas de mensajes de WhatsApp 

Una plantilla de mensaje de WhatsApp creada en End User Messaging (consulta la [Guía de creación de plantillas](../general_template_creation.md))


## Despliegue con AWS CDK

⚠️ Despliega en la misma región donde tienes tus números de WhatsApp en AWS End User Messaging.

### 1. Configura el Instance ID

Edita `config.py` y coloca tu Instance ID de Amazon Connect:

```python
INSTANCE_ID = "<tu-connect-instance-id>"
```

### 2. Clona el repositorio y navega al proyecto

```bash
git clone https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat.git
cd sample-whatsapp-end-user-messaging-connect-chat/agent-initiated-whatsapp
```

### 3. Despliega con CDK

Sigue las instrucciones de la [Guía de despliegue CDK](../general_cdk_deploy.md).

## Configuración post-despliegue

Una vez desplegado, hay algunos pasos manuales para conectar todas las piezas.

### Paso 1: Actualiza el parámetro en SSM

Ve a AWS Systems Manager Parameter Store y actualiza `/whatsapp_template/config` con tu configuración de plantilla:

```json
{
  "message": {
    "messaging_product": "whatsapp",
    "to": "PHONE_NUMBER",
    "recipient_type": "individual",
    "type": "template",
    "template": {
      "name": "nombre_de_tu_plantilla",
      "language": { "code": "en_US" },
      "components": [
        {
          "type": "body",
          "parameters": []
        }
      ]
    }
  },
  "META_API_VERSION": "v23.0",
  "ORIGINATION_PHONE_NUMBER_ID": "<tu-origination-phone-number-id>"
}
```

| Parámetro | Descripción |
|---|---|
| `template.name` | Nombre de tu plantilla de WhatsApp creada en End User Messaging |
| `template.language.code` | Código de idioma de la plantilla (ej: `en_US`) |
| `ORIGINATION_PHONE_NUMBER_ID` | El ID del número de teléfono en AWS End User Messaging Social |
| `META_API_VERSION` | Versión de la API de Meta (por defecto: `v23.0`) |

### Paso 2: Explora el formulario desplegado

Navega a las vistas de tu instancia de Amazon Connect:

```
https://<tu-instancia>.my.connect.aws/views
```

Busca la vista llamada `enviarWhatsAppForm007`. Este es el formulario que los agentes usarán para revisar los datos del cliente y enviar el mensaje.

![Formulario desplegado](../agent-initiated-whatsapp/form.png)

_Nota: el campo de WhatsApp es de tipo password para ocultar el número. Incluso podría no ser parte del formulario y acceder al dato usando [Attributos de Contacto](https://docs.aws.amazon.com/connect/latest/adminguide/connect-contact-attributes.html)_

### Paso 3: Configura el Contact Flow desplegado

Navega al flujo de contacto `SendWhatsAppGuideFlow007` en tu consola de Amazon Connect.

![Contact Flow](../agent-initiated-whatsapp/flow.png)

#### 3.1 Configura la primera Lambda (Obtener datos del cliente)

Edita el primer bloque **Invoke AWS Lambda function** y selecciona la función Lambda pre-desplegada. Busca la que contenga `GetCustomerData` en el nombre.

Esta es una función mock que retorna datos de ejemplo:

```python
def lambda_handler(event, context):
    return {
        "fullName": "Juan Pérez",
        "phoneNumber": "+XXXXXXXX",
        "input4": "Entregado",
        "input3": "Puzzle 1000 piezas",
        "input2": "P12345",
        "input1": "Juan",
    }
```

Reemplaza esto con tu propia fuente de datos. Por ejemplo, podrías hacer un data dip a Amazon Connect Customer Profiles usando un `profileId`, consultar una tabla de DynamoDB o llamar a una API externa.

Presiona **Confirm** para guardar.

#### 3.2 Configura el bloque Show View

Edita el bloque **Show view** y selecciona `enviarWhatsAppForm007` como recurso de vista.

Los valores por defecto del formulario se mapean desde los valores retornados por la Lambda:

- `fullName` → `$.External.fullName`
- `whatsappNumber` → `$.External.phoneNumber`
- `input1` a `input4` → `$.External.input1` a `$.External.input4`

Estos valores pre-llenan el formulario para que el agente los revise antes de enviar. Presiona **Confirm** para guardar.

#### 3.3 Configura la segunda Lambda (Enviar mensaje de WhatsApp)

Edita el segundo bloque **Invoke AWS Lambda function** y selecciona la Lambda que contenga `SendWhatsappMessage` en el ARN.

Esta Lambda lee la configuración de la plantilla desde SSM, extrae los valores del formulario de los atributos de contacto y envía el mensaje:

```python
def lambda_handler(event, context):
    # Carga la configuración de la plantilla desde SSM Parameter Store
    config = get_ssm_parameter(CONFIG_PARAM_NAME)
    message_payload = config["message"]

    # Extrae los valores del formulario desde los atributos de contacto
    attributes = event["Details"]["ContactData"]["Attributes"]
    phone_number = attributes.get("phoneNumber")

    # Construye los parámetros de la plantilla desde input1..input4
    template_params = build_template_parameters(
        attributes, ["input1", "input2", "input3", "input4"]
    )

    # Envía usando AWS End User Messaging Social
    response = social_client.send_whatsapp_message(
        originationPhoneNumberId=origination_phone_number_id,
        message=bytes(json.dumps(message_payload), "utf-8"),
        metaApiVersion=meta_api_version,
    )
    return {"result": "OK", "messageId": response.get("messageId", "")}
```

Presiona **Confirm** para guardar. Luego **Save** y **Publish** el flujo de contacto.

### Paso 4: Crea una nueva Vista (Guía)

Navega a las vistas de Amazon Connect:

```
https://<tu-instancia>.my.connect.aws/views
```

Crea una nueva vista de tipo **Guide**.

![Crear Vista](../agent-initiated-whatsapp/create_view.png)

#### 4.1 Agrega un componente Connect Application

Arrastra un componente **Connect Application** al canvas.

#### 4.2 Configura el componente

Establece el `contactFlowId` con el flujo de contacto desplegado `SendWhatsAppGuideFlow007`.

![Crear Guía](../agent-initiated-whatsapp/create_guide.png)

#### 4.3 Nombra y publica

Dale un nombre a la vista y haz clic en **Publish**.

### Paso 5: Crea un Workspace personalizado

#### 5.1 Crea el workspace

Navega a los workspaces de Amazon Connect:

```
https://<tu-instancia>.my.connect.aws/workspaces
```

Haz clic en **Add new workspace** y completa el nombre, descripción y título.

![Crear Workspace](../agent-initiated-whatsapp/create_workspace.png)

Asigna este workspace a los usuarios o perfiles de enrutamiento que necesites.

#### 5.2 Agrega una página con la guía

Agrega una nueva página usando **Set page with custom page slug** y selecciona la vista que creaste en el paso anterior (la que tiene el componente Connect Application).

Usa un slug personalizado como:

```
/page/send_whatsapp
```

![Agregar Página](../agent-initiated-whatsapp/add_page.png)

Guarda la página.

#### 5.3 Navega al workspace personalizado

Selecciona tu workspace personalizado desde la barra de navegación superior en el Agent Workspace.

![Seleccionar Workspace](../agent-initiated-whatsapp/select_workspace.png)

El agente ahora puede navegar a la página personalizada y usar la guía para enviar mensajes de plantilla de WhatsApp a los clientes.

## Demo

Cuando el agente navega a la página personalizada, se le presenta un Connect Application que ejecuta el flujo de contacto. El flujo muestra el formulario con los valores pre-cargados desde la Lambda de datos del cliente, dándole al agente la oportunidad de revisar, modificar y enviar. Una vez que el agente envía, la Lambda de envío de WhatsApp se invoca con todos los parámetros del formulario para entregar el mensaje final.

<div align="center">
<video src="https://github.com/user-attachments/assets/251a757c-2fe8-4875-966f-32d2bb7c3aa7" width="540" controls></video>
</div>


## Próximos pasos

Esta solución es un punto de partida. Algunas ideas para extenderla:

- Conectar la Lambda de datos del cliente a Amazon Connect Customer Profiles o DynamoDB
- Agregar validaciones adicionales en el formulario
- Soportar múltiples plantillas de WhatsApp seleccionables por el agente
- Incorporar dinámicamente la cantidad de inputs, dependiendo del número de variables en el template.

## Recursos

- [Repositorio del proyecto](https://github.com/aws-samples/sample-whatsapp-end-user-messaging-connect-chat)
- [Guía de creación de plantillas](../general_template_creation.md)
- [Guía de prerrequisitos](../general_connect_eum.md)
- [Guía de despliegue CDK](../general_cdk_deploy.md)

