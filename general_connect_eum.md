## Prerrequisitos / Prerequisites

---

### Cuenta de WhatsApp Business / WhatsApp Business Account

🇪🇸 Para comenzar, necesitas crear una nueva cuenta de WhatsApp Business (WABA) o migrar una existente a AWS. Los pasos principales están descritos [aquí](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). En resumen:

1. Tener o crear una cuenta de Meta Business
2. Acceder a la consola de AWS End User Messaging Social y vincular tu cuenta de negocio a través del portal embebido de Facebook
3. Asegurarte de tener un número de teléfono que pueda recibir verificación por SMS/voz y agregarlo a WhatsApp

⚠️ Importante: No uses tu número personal de WhatsApp para esto.

🇺🇸 To get started, businesses need to either create a new WhatsApp Business Account (WABA) or migrate an existing one to AWS. The main steps are described [here](https://docs.aws.amazon.com/social-messaging/latest/userguide/getting-started.html). In summary:

1. Have or create a Meta Business Account
2. Access AWS End User Messaging Social console and link business account through Facebook embedded portal.
3. Ensure you have a phone number that can receive SMS/voice verification and add it to WhatsApp.

⚠️ Important: Do not use your personal WhatsApp number for this.

---

### Instancia de Amazon Connect / An Amazon Connect Instance

🇪🇸 Necesitas una instancia de Amazon Connect. Si aún no tienes una, puedes [seguir esta guía](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html) para crearla.

Necesitarás el **INSTANCE_ID** de tu instancia. Lo puedes encontrar en la consola de Amazon Connect o en el ARN de la instancia:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

🇺🇸 You need an Amazon Connect Instance. If you don't have one already you can [follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-instances.html).

You will need the **INSTANCE_ID** of your instance. You can find it in the Amazon Connect console or in the instance ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID`

---

### Flujo de chat para manejar mensajes / A Chat Flow to Handle Messages

🇪🇸 Crea o ten listo el flujo de contacto que define la experiencia del usuario. [Sigue esta guía](https://docs.aws.amazon.com/connect/latest/adminguide/create-contact-flow.html) para crear un flujo de contacto entrante (Inbound Contact Flow). El más sencillo será suficiente.

(¡Recuerda publicar el flujo!)

🇺🇸 Have or create the expected experience a user will have with a contact. [Follow this guide](https://docs.aws.amazon.com/connect/latest/adminguide/create-contact-flow.html) to create an Inbound Contact flow. The simplest one will be ok:

(Remember to publish the flow!)

![](./whatsapp-eum-connect-chat/flow_simple.png)

🇪🇸 Toma nota del **INSTANCE_ID** y **CONTACT_FLOW_ID** en la pestaña de Detalles. Los valores están en el ARN del flujo:

🇺🇸 Take note of **INSTANCE_ID** and **CONTACT_FLOW_ID** in the Details tab, values are in flow ARN:

`arn:aws:connect:<region>:<account_id>:instance/INSTANCE_ID/contact-flow/CONTACT_FLOW_ID`
