# Creación de plantillas de mensajes de WhatsApp en AWS End User Messaging / Creating WhatsApp Message Templates in AWS End User Messaging

---

## ¿Qué son las plantillas de WhatsApp? / What Are WhatsApp Templates?

🇪🇸 Las plantillas de mensajes de WhatsApp son mensajes estructurados que deben ser aprobados por Meta antes de poder usarse. Soportan parámetros dinámicos (ej: `{{1}}`, `{{2}}`) que se reemplazan con valores reales al momento del envío.

Las plantillas son necesarias para:
- Enviar el primer mensaje a un cliente (abrir una conversación)
- Re-contactar a un cliente después de que la ventana de conversación de 24 horas haya cerrado

🇺🇸 WhatsApp message templates are structured messages that must be approved by Meta before they can be used. They support dynamic parameters (e.g., `{{1}}`, `{{2}}`) that are replaced with actual values at send time.

Templates are required for:
- Sending the first message to a customer (opening a conversation)
- Re-engaging a customer after the 24-hour conversation window has closed

---

## Creación de una plantilla / Creating a Template

### 1. Accede a la consola de End User Messaging Social / Access the End User Messaging Social Console

🇪🇸 Navega a la [consola de AWS End User Messaging Social](https://console.aws.amazon.com/social-messaging/) y selecciona tu cuenta de WhatsApp Business.

🇺🇸 Navigate to the [AWS End User Messaging Social console](https://console.aws.amazon.com/social-messaging/) and select your WhatsApp Business Account.

### 2. Navega a Plantillas / Navigate to Templates

🇪🇸 En la navegación izquierda, selecciona **Templates** y haz clic en **Create template**.

🇺🇸 In the left navigation, select **Templates** and click **Create template**.

### 3. Configura la plantilla / Configure the Template

🇪🇸
- **Template name**: Usa solo letras minúsculas, números y guiones bajos (ej: `order_update`, `appointment_reminder`)
- **Category**: Selecciona la categoría apropiada:
  - **Marketing**: Promociones, ofertas, recomendaciones de productos
  - **Utility**: Actualizaciones de pedidos, alertas de cuenta, recordatorios de citas
  - **Authentication**: Contraseñas de un solo uso, códigos de verificación
- **Language**: Selecciona el idioma de la plantilla (ej: English, Spanish). Puedes crear la misma plantilla en múltiples idiomas

🇺🇸
- **Template name**: Use lowercase letters, numbers, and underscores only (e.g., `order_update`, `appointment_reminder`)
- **Category**: Select the appropriate category:
  - **Marketing**: Promotions, offers, product recommendations
  - **Utility**: Order updates, account alerts, appointment reminders
  - **Authentication**: One-time passwords, verification codes
- **Language**: Select the language for the template (e.g., English, Spanish). You can create the same template in multiple languages

### 4. Define el cuerpo de la plantilla / Define the Template Body

🇪🇸 Escribe el cuerpo del mensaje usando `{{1}}`, `{{2}}`, etc. como marcadores de posición para contenido dinámico.

🇺🇸 Write the message body using `{{1}}`, `{{2}}`, etc. as placeholders for dynamic content.

Ejemplo / Example:
```
Hello {{1}}, your order {{2}} for {{3}} is now {{4}}.
```

Al momento del envío, los marcadores se reemplazan con valores reales / At send time, these placeholders are replaced with actual values:
```
Hello Enrique, your order P12345 for Puzzle 1000 piezas is now Entregado.
```

### 5. Agrega contenido de ejemplo / Add Sample Content

🇪🇸 Meta requiere valores de ejemplo para cada parámetro para revisar la plantilla. Proporciona ejemplos realistas que representen cómo se usará la plantilla.

🇺🇸 Meta requires sample values for each parameter to review the template. Provide realistic examples that represent how the template will be used.

### 6. Envía para aprobación / Submit for Approval

🇪🇸 Haz clic en **Submit** para enviar la plantilla a revisión de Meta. La aprobación normalmente toma de unos minutos a unas horas, pero puede tardar hasta 24 horas.

🇺🇸 Click **Submit** to send the template for Meta's review. Approval typically takes a few minutes to a few hours, but can take up to 24 hours.

---

## Estado de la plantilla / Template Status

| Estado / Status | Descripción / Description |
|---|---|
| **Pending** | La plantilla está en revisión por Meta / Template is under review by Meta |
| **Approved** | La plantilla está lista para usar / Template is ready to use |
| **Rejected** | La plantilla no fue aprobada. Revisa los comentarios de Meta y reenvía / Template was not approved. Review Meta's feedback and resubmit |

---

## Uso de plantillas con este proyecto / Using Templates with This Project

🇪🇸 Una vez que tu plantilla esté aprobada, actualiza el parámetro SSM `/whatsapp_template/config` con:

- `template.name`: El nombre exacto de la plantilla que creaste
- `template.language.code`: El código de idioma (ej: `en_US`, `es`)
- Los parámetros de la plantilla (`input1` a `input4`) se mapean a `{{1}}` a `{{4}}` en el cuerpo de la plantilla

🇺🇸 Once your template is approved, update the SSM parameter `/whatsapp_template/config` with:

- `template.name`: The exact template name you created
- `template.language.code`: The language code (e.g., `en_US`, `es`)
- Template parameters (`input1` through `input4`) map to `{{1}}` through `{{4}}` in the template body

---

## Consejos / Tips

🇪🇸
- Mantén las plantillas concisas y claras
- Evita lenguaje promocional en plantillas de tipo Utility para prevenir rechazos
- Prueba con los valores de ejemplo antes de desplegar a producción
- Puedes gestionar plantillas tanto desde la consola de AWS como desde el Meta Business Manager
- Los nombres de plantillas no se pueden cambiar después de crearlas. Crea una nueva plantilla si necesitas un nombre diferente

🇺🇸
- Keep templates concise and clear
- Avoid promotional language in Utility templates to prevent rejection
- Test with the sample values before deploying to production
- You can manage templates both from the AWS console and the Meta Business Manager
- Template names cannot be changed after creation. Create a new template if you need a different name
