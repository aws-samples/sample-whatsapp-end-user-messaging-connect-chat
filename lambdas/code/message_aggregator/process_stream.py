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
            'contacts': [{'profile': c['profile'], 'wa_id': c['wa_id']} for c in data['contacts'].values()],
            'messages': [{
                'from': m['from'],
                'id': m['id'],
                'timestamp': m['timestamp'],
                'text': m.get('text'),
                'type': m['type'],
                'audio': m.get('audio'),
                'image': m.get('image'),
                'video': m.get('video'),
                'document': m.get('document'),
                'sticker': m.get('sticker'),
                'location': m.get('location'),
                'contacts': m.get('contacts'),
                'interactive': m.get('interactive')
            } for m in aggregated]
        })
    
    return result

