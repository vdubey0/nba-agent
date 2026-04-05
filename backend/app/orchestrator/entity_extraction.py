from openai import OpenAI
import json
import pprint
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from app.query.resolvers import resolve_player, resolve_team
from app.db import SessionLocal
from app.utils.retry import retry_with_context, format_retry_context_for_prompt
from app.models.conversation import Conversation, ResolvedEntity

load_dotenv()

@retry_with_context(max_attempts=3)
def extract_entity_mentions(
    client,
    question: str,
    conversation: Optional[Conversation] = None,
    retry_context: Optional[Dict[str, Any]] = None
) -> list[dict]:
    """
    Extract entity mentions from a question with retry logic and conversation context.
    
    Args:
        client: OpenAI client
        question: User's question
        conversation: Optional conversation for context
        retry_context: Injected by retry decorator on retry attempts
    
    Returns:
        List of entity mentions or error dict
    """
    with open('app/orchestrator/prompts/entity-extraction-prompt.txt') as f:
        prompt = f.read()
    
    # Add retry context if this is a retry attempt
    if retry_context:
        prompt += format_retry_context_for_prompt(retry_context)
    
    # Add conversation context for better entity resolution
    if conversation and conversation.messages:
        context_messages = conversation.get_context_for_llm(max_messages=3)
        
        # Add context about previously resolved entities
        if conversation.resolved_entities:
            prompt += "\n\nPREVIOUSLY RESOLVED ENTITIES IN THIS CONVERSATION:\n"
            for surface_text, entity in conversation.resolved_entities.items():
                prompt += f"- '{surface_text}' → {entity.resolved_name} (ID: {entity.resolved_id})\n"
            prompt += "\nIf the current question mentions any of these entities by a shortened name "
            prompt += "(e.g., 'Curry' after 'Steph Curry'), they likely refer to the same entity.\n"

    # Build input messages
    input_messages = [
        {
            "role": "system",
            "content": prompt
        }
    ]
    
    # Add conversation history if available
    if conversation and conversation.messages:
        recent_messages = conversation.get_context_for_llm(max_messages=3)
        input_messages.extend(recent_messages)
    
    # Add current question
    input_messages.append({
        "role": "user",
        "content": question
    })

    response = client.responses.create(
        model="gpt-5.4",
        input=input_messages,
        temperature=0.0
    )

    output_text = response.output[0].content[0].text
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as e:
        return {
            'status': 'failed',
            'error': f'JSON parsing failed:\nError: {e.msg}\nLine {e.lineno}, Column: {e.colno}',
            'raw_text': output_text
        }

def resolve_entity_mentions(
    session,
    mentions: list[dict],
    conversation: Optional[Conversation] = None
) -> list[dict]:
    """
    Resolve entity mentions to actual entities, using conversation cache when available.
    
    Args:
        session: Database session
        mentions: List of entity mentions from extraction
        conversation: Optional conversation for caching
    
    Returns:
        List of resolved entities
    """
    entities = []

    for mention in mentions:
        surface_text = mention['text']
        entity_type = mention['entity_type']
        
        # Check conversation cache first
        if conversation:
            cached_entity = conversation.get_cached_entity(surface_text)
            if cached_entity and cached_entity.entity_type == entity_type:
                # Use cached entity
                entity_resolved = {
                    'status': 'resolved',
                    'id': cached_entity.resolved_id,
                    'full_name': cached_entity.resolved_name,
                    'surface_text': surface_text,
                    'entity_type': entity_type,
                    'from_cache': True
                }
                entities.append(entity_resolved)
                continue
        
        # Resolve from database
        if entity_type == 'player':
            entity_resolved = resolve_player(session, name=surface_text)
            entity_resolved['surface_text'] = surface_text
            entity_resolved['entity_type'] = entity_type
            
            # Cache if resolved successfully
            if conversation and entity_resolved.get('status') == 'resolved':
                resolved_entity = ResolvedEntity(
                    entity_type='player',
                    surface_text=surface_text,
                    resolved_id=entity_resolved['id'],
                    resolved_name=entity_resolved['full_name']
                )
                conversation.cache_resolved_entity(surface_text, resolved_entity)

            entities.append(entity_resolved)
            
        elif entity_type == 'team':
            entity_resolved = resolve_team(session, name=surface_text)
            entity_resolved['surface_text'] = surface_text
            entity_resolved['entity_type'] = entity_type
            
            # Cache if resolved successfully
            if conversation and entity_resolved.get('status') == 'resolved':
                resolved_entity = ResolvedEntity(
                    entity_type='team',
                    surface_text=surface_text,
                    resolved_id=entity_resolved['id'],
                    resolved_name=entity_resolved['team']
                )
                conversation.cache_resolved_entity(surface_text, resolved_entity)

            entities.append(entity_resolved)
            
        else:
            entities.append(
                {
                    'status': 'failed',
                    'error': f"Invalid entity_type: {entity_type}. entity_type must be 'player' or 'team'",
                    'surface_text': surface_text,
                    'entity_type': entity_type
                }
            )

    return entities


    
if __name__ == '__main__':
    client = OpenAI()
    session = SessionLocal()

    question = "How many threes did Lebron make against the Cavs and Dubs?"

    mentions = extract_entity_mentions(client=client, question=question)
    pprint.pprint(resolve_entity_mentions(session=session, mentions=mentions))

    

    