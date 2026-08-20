import json
from collections import defaultdict
from typing import Any, Dict, List


def deserialize_dynamodb(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DynamoDB format to plain JSON."""
    if isinstance(item, dict):
        if len(item) == 1:
            type_key = list(item.keys())[0]
            value = item[type_key]
            
            if type_key == 'S':
                return value
            elif type_key == 'N':
                return float(value) if '.' in value else int(value) # type: ignore
            elif type_key == 'M':
                return {k: deserialize_dynamodb(v) for k, v in value.items()}
            elif type_key == 'L':
                return [deserialize_dynamodb(i) for i in value] # type: ignore
            elif type_key == 'BOOL':
                return value
            elif type_key == 'NULL':
                return None # type: ignore
        
        return {k: deserialize_dynamodb(v) for k, v in item.items()}
    
    return item


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


def aggregate_all_messages(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group records by contact, metadata, context and concatenate consecutive text messages."""
    grouped = defaultdict(lambda: {'messaging_product': None, 'metadata': None, 'context': None, 'contacts': {}, 'messages': []})
    
    for record in records:
        metadata = record.get('metadata', {})
        context = record.get('context', {})
        sender = record.get('from')
        
        key = (json.dumps(metadata, sort_keys=True), json.dumps(context, sort_keys=True), sender)
        
        grouped[key]['messaging_product'] = record.get('messaging_product')
        grouped[key]['metadata'] = metadata
        grouped[key]['context'] = context
        grouped[key]['messages'].append(record) # type: ignore
        
        contact = record.get('contact')
        if contact:
            grouped[key]['contacts'][sender] = contact # type: ignore
    
    result = []
    for data in grouped.values():
        sorted_msgs = sorted(data['messages'], key=lambda m: int(m.get('timestamp', 0))) # type: ignore
        
        aggregated = []
        text_buffer = []
        
        for msg in sorted_msgs:
            if msg.get('type') == 'text' and msg.get('from') == sorted_msgs[0].get('from'):
                text_buffer.append(msg)
            else:
                if text_buffer:
                    last = text_buffer[-1].copy()
                    last['text'] = {'body': '\n'.join(m['text']['body'] for m in text_buffer)}
                    aggregated.append(last)
                    text_buffer = []
                aggregated.append(msg)
        
        if text_buffer:
            last = text_buffer[-1].copy()
            last['text'] = {'body': '\n'.join(m['text']['body'] for m in text_buffer)}
            aggregated.append(last)
        
        result.append({
            'messaging_product': data['messaging_product'],
            'metadata': data['metadata'],
            'context': data['context'],
            'field': 'messages',
            'contacts': [build_contact(c) for c in data['contacts'].values()],
            'messages': [build_message(m) for m in aggregated]
        })
    
    return result

