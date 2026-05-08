from openai import OpenAI
import json
import pprint
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from app.query.resolvers import TEAM_ALIASES, resolve_player, resolve_team
from app.db import SessionLocal
from app.models import Player
from app.utils.retry import retry_with_context, format_retry_context_for_prompt
from app.models.conversation import Conversation, ResolvedEntity

load_dotenv()

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "entity-extraction-prompt.txt"
ENTITY_EXTRACTION_PROMPT = PROMPT_PATH.read_text()

PLAYER_ALIASES = {
    "steph": "Steph",
    "steph curry": "Steph Curry",
    "lebron": "LeBron",
    "kd": "KD",
    "jokic": "Jokic",
    "giannis": "Giannis",
    "luka": "Luka",
    "embiid": "Embiid",
    "shai": "Shai",
}

GENERIC_PLAYER_TERMS = {
    "all",
    "away",
    "bench",
    "best",
    "black",
    "blue",
    "brown",
    "close",
    "green",
    "home",
    "last",
    "may",
    "play",
    "player",
    "players",
    "regular",
    "season",
    "team",
    "teams",
    "top",
    "white",
    "win",
}


def _clean_surface_text(surface_text: str) -> str:
    return re.sub(r"(?:'s|s')$", "", surface_text.strip(), flags=re.IGNORECASE)


def _mention_key(mention: dict) -> tuple[str, str]:
    return mention["entity_type"], mention["text"].lower()


def _add_mention(mentions: list[dict], entity_type: str, surface_text: str) -> bool:
    cleaned = _clean_surface_text(surface_text)
    if not cleaned:
        return False

    mention = {"entity_type": entity_type, "text": cleaned}
    if _mention_key(mention) not in {_mention_key(item) for item in mentions}:
        mentions.append(mention)
        return True
    return False


def _entity_pattern(text: str, *, ignore_case: bool = True) -> re.Pattern:
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(rf"(?<!\w){re.escape(text)}(?:'s|s')?(?!\w)", flags)


@lru_cache(maxsize=1)
def _player_index() -> tuple[tuple[tuple[str, str], ...], frozenset[str]]:
    session = SessionLocal()
    try:
        players = session.query(Player).all()
    finally:
        session.close()

    surfaces: dict[str, str] = {}
    term_counts: dict[str, int] = {}
    terms = set()

    for player in players:
        if player.full_name:
            normalized = player.full_name.lower()
            surfaces[normalized] = player.full_name

        for term in (player.first_name, player.last_name):
            if not term:
                continue
            normalized_term = term.lower()
            if normalized_term in GENERIC_PLAYER_TERMS:
                continue
            term_counts[normalized_term] = term_counts.get(normalized_term, 0) + 1
            terms.add(normalized_term)

    for alias, surface in PLAYER_ALIASES.items():
        surfaces[alias] = surface
        if " " not in alias and alias not in GENERIC_PLAYER_TERMS:
            terms.add(alias)

    for term, count in term_counts.items():
        if count == 1:
            surfaces[term] = term

    return (
        tuple(sorted(surfaces.items(), key=lambda item: len(item[0]), reverse=True)),
        frozenset(terms),
    )


def _player_surfaces() -> tuple[tuple[str, str], ...]:
    return _player_index()[0]


def _player_terms() -> frozenset[str]:
    return _player_index()[1]


@lru_cache(maxsize=1)
def _team_surfaces() -> tuple[tuple[str, str, bool], ...]:
    surfaces: dict[str, tuple[str, bool]] = {}

    for aliases in TEAM_ALIASES.values():
        for alias in aliases:
            normalized = alias.lower()
            if len(normalized) < 2:
                continue

            requires_exact_case = len(normalized) <= 2
            surfaces[normalized] = (alias, requires_exact_case)

    return tuple(
        sorted(
            (
                (normalized, surface, requires_exact_case)
                for normalized, (surface, requires_exact_case) in surfaces.items()
            ),
            key=lambda item: len(item[0]),
            reverse=True,
        )
    )


def _covered_token_indices(question: str, mentions: list[dict]) -> set[int]:
    covered = set()
    for mention in mentions:
        pattern = _entity_pattern(mention["text"])
        for match in pattern.finditer(question):
            covered.update(range(match.start(), match.end()))
    return covered


def _has_uncovered_player_term(question: str, mentions: list[dict]) -> bool:
    covered = _covered_token_indices(question, mentions)
    player_terms = _player_terms()

    for match in re.finditer(r"\b[A-Za-z][A-Za-z.'-]*\b", question):
        if any(index in covered for index in range(match.start(), match.end())):
            continue

        token = _clean_surface_text(match.group(0)).lower().replace(".", "")
        if token in player_terms:
            return True

    return False


def _extract_entity_mentions_deterministically(question: str) -> list[dict] | None:
    mentions: list[dict] = []
    occupied_spans: list[tuple[int, int]] = []

    def overlaps_existing(match: re.Match) -> bool:
        return any(match.start() < end and match.end() > start for start, end in occupied_spans)

    for normalized, surface in _player_surfaces():
        pattern = _entity_pattern(normalized)
        for match in pattern.finditer(question):
            if overlaps_existing(match):
                continue
            if _add_mention(mentions, "player", match.group(0)):
                occupied_spans.append((match.start(), match.end()))

    for normalized, surface, requires_exact_case in _team_surfaces():
        pattern = _entity_pattern(normalized, ignore_case=not requires_exact_case)
        for match in pattern.finditer(question):
            if overlaps_existing(match):
                continue
            matched_text = match.group(0)
            cleaned = _clean_surface_text(matched_text)
            if requires_exact_case and cleaned != cleaned.upper():
                continue
            if _add_mention(mentions, "team", matched_text):
                occupied_spans.append((match.start(), match.end()))

    if _has_uncovered_player_term(question, mentions):
        return None

    return mentions


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
    if not retry_context and not (conversation and conversation.messages):
        deterministic_mentions = _extract_entity_mentions_deterministically(question)
        if deterministic_mentions is not None:
            return deterministic_mentions

    prompt = ENTITY_EXTRACTION_PROMPT
    
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

    

    
