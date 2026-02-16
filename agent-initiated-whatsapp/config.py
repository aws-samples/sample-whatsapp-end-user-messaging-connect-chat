import json
import os

CONFIG_PARAM_NAME = "/whatsapp_template/config"

# update this after deployment in aws parameter store /whatsapp/config
CONFIG_PARAM_INITIAL_CONTENT = {
    "message": {
        "messaging_product": "whatsapp",
        "to": "PHONE_NUMBER",
        "recipient_type": "individual",
        "type": "template",
        "template": {
            "name": "TEMPLATE_NAME",
            "language": {"code": "TEMPLATE_LANGUAGE_CODE"},
            "components": [
                {
                    "type": "body",
                    "parameters": [],
                }
            ],
        },
    },
    "META_API_VERSION": "v23.0",
    "ORIGINATION_PHONE_NUMBER_ID": "ORIGINATION_PHONE_NUMBER_ID",
}
FORM_VIEW = {
    "Name": "enviarWhatsAppForm007",
    "Content": {
        "InputSchema": '{"type":"object","properties":{"fullName":{"anyOf":[{"type":"string","pattern":"^$|^(?!\\\\$\\\\.).+"},{"type":"number"},{"anyOf":[{"type":"string","pattern":"^\\\\$\\\\.{1}#[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*(\\\\.[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*)*$"}]}]},"whatsappNumber":{"anyOf":[{"type":"string","pattern":"^$|^(?!\\\\$\\\\.).+"},{"type":"number"},{"anyOf":[{"type":"string","pattern":"^\\\\$\\\\.{1}#[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*(\\\\.[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*)*$"}]}]},"input1":{"anyOf":[{"type":"string","pattern":"^$|^(?!\\\\$\\\\.).+"},{"type":"number"},{"anyOf":[{"type":"string","pattern":"^\\\\$\\\\.{1}#[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*(\\\\.[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*)*$"}]}]},"input3":{"anyOf":[{"type":"string","pattern":"^$|^(?!\\\\$\\\\.).+"},{"type":"number"},{"anyOf":[{"type":"string","pattern":"^\\\\$\\\\.{1}#[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*(\\\\.[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*)*$"}]}]},"input2":{"anyOf":[{"type":"string","pattern":"^$|^(?!\\\\$\\\\.).+"},{"type":"number"},{"anyOf":[{"type":"string","pattern":"^\\\\$\\\\.{1}#[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*(\\\\.[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*)*$"}]}]},"input4":{"anyOf":[{"type":"string","pattern":"^$|^(?!\\\\$\\\\.).+"},{"type":"number"},{"anyOf":[{"type":"string","pattern":"^\\\\$\\\\.{1}#[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*(\\\\.[a-zA-Z0-9_]+(\\\\[[0-9]*\\\\])*)*$"}]}]}},"required":[],"$defs":{"ViewCondition":{"$id":"/view/condition","type":"object","patternProperties":{"^(MoreThan|LessThan|NotEquals|Equals|Includes)$":{"type":"object","properties":{"ElementByKey":{"type":"string"},"ElementByValue":{"anyOf":[{"type":"number"},{"type":"string"},{"type":"boolean"},{"type":"array"},{"type":"object"}]}},"additionalProperties":false},"^(AndConditions|OrConditions)$":{"type":"array","items":{"$ref":"/view/condition"}}},"additionalProperties":false}}}',
        "Template": '{"Head":{"Configuration":{"Layout":{"Columns":["6","6"]}},"Integrations":[],"Title":"enviarWhatsAppForm007"},"Body":[{"_id":"Form_1770878372512","Type":"Form","Props":{"HideBorder":true},"Content":[{"_id":"Container_1770879408362","Type":"Container","Props":{"HideBorder":false,"Visibility":true},"Content":[{"_id":"Container_1771208520198","Type":"Container","Props":{"HideBorder":true,"Visibility":true},"Content":[{"_id":"Header_1771208640269","Type":"Header","Props":{"variant":"h2","description":"Using this form to send an Agent initiated Whatsapp"},"Content":["Send Whastapp"]},{"_id":"Container_1771187801229","Type":"Container","Props":{"HideBorder":false,"Visibility":true,"header":""},"Content":[{"_id":"FormInput_1771187734165","Type":"FormInput","Props":{"Label":"Full Name","Name":"fullName","DefaultValue":"$.fullName","InputType":"text","Required":false,"HelperText":"","ValidationPattern":"","Disabled":false},"Content":[]},{"_id":"FormInput_1770862188939","Type":"FormInput","Props":{"Label":"Whatstapp","Name":"whatsapp","DefaultValue":"$.whatsappNumber","InputType":"password","Required":false,"HelperText":"","ValidationPattern":"","Disabled":false},"Content":[]}],"Configuration":{"Layout":{"Columns":["6","6"]}}},{"_id":"Container_1771187858398","Type":"Container","Props":{"HideBorder":false,"Visibility":true},"Content":[{"_id":"FormInput_1770862255225","Type":"FormInput","Props":{"Label":"{{1}}","Name":"input1","DefaultValue":"$.input1","InputType":"text","Required":false,"HelperText":"","ValidationPattern":"","Disabled":false},"Content":[]},{"_id":"FormInput_1770862273752","Type":"FormInput","Props":{"Label":"{{3}}","Name":"input3","DefaultValue":"$.input3","InputType":"text","Required":false,"HelperText":"","ValidationPattern":"","Disabled":false},"Content":[]},{"_id":"FormInput_1770862265035","Type":"FormInput","Props":{"Label":"{{2}}","Name":"input2","DefaultValue":"$.input2","InputType":"text","Required":false,"HelperText":"","ValidationPattern":"","Disabled":false},"Content":[]},{"_id":"FormInput_1770862447226","Type":"FormInput","Props":{"Label":"{{4}}","Name":"input4","DefaultValue":"$.input4","InputType":"text","Required":false,"HelperText":"","ValidationPattern":"","Disabled":false},"Content":[]}],"Configuration":{"Layout":{"Columns":["6","6"]}}},{"_id":"SubmitButton_1770862393605","Type":"SubmitButton","Props":{"Action":"enviarWhatsapp","Label":"Enviar Whatsapp"},"Content":["Submit Button"]}],"Configuration":{"Layout":{"Columns":12}}}],"Configuration":{"Style":{"--container-border-radius":"5px"},"Layout":{"Columns":"12"}}}],"Configuration":{"Style":{"--form-padding-top":"5px","--form-padding-right":"5px","--form-padding-bottom":"5px","--form-padding-left":"5px","--form-border-radius":"5px"},"Layout":{"Columns":"12","Align":"left"}}}]}',
        "Actions": ["enviarWhatsapp"],
    },
}



CONTACT_FLOW = {
    "Name": "SendWhatsAppGuideFlow007",
    "Type": "CONTACT_FLOW",
    "Description": "FLow created to show form and submit from agent workspace",
}

CONTACT_FLOW_CONTENTS_FILE = "SendWhatsAppGuideFlowContent.json"

# Edit this pre-deployment time to create de view and contact flows

INSTANCE_ID = "f5dbbb06-46e7-4435-beab-3b3303074765"
