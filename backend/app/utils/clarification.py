from typing import Dict, List, Any, Optional
from app.models.conversation import Clarification


def create_entity_clarification(
    entity_type: str,
    surface_text: str,
    candidates: List[Dict[str, Any]]
) -> Clarification:
    """
    Create a clarification request for ambiguous entity resolution.
    
    Args:
        entity_type: "player" or "team"
        surface_text: The ambiguous text from user (e.g., "Anthony")
        candidates: List of candidate entities from resolver
    
    Returns:
        Clarification object
    """
    # Format options with numbers
    options = []
    for i, candidate in enumerate(candidates, 1):
        if entity_type == "player":
            display_text = f"{i}. {candidate['full_name']}"
            if 'team' in candidate:
                display_text += f" ({candidate['team']})"
            
            options.append({
                'id': str(i),
                'display': display_text,
                'entity_id': candidate['id'],
                'full_name': candidate['full_name'],
                'entity_type': 'player'
            })
        elif entity_type == "team":
            display_text = f"{i}. {candidate['team']}"
            
            options.append({
                'id': str(i),
                'display': display_text,
                'entity_id': candidate['id'],
                'team': candidate['team'],
                'abbreviation': candidate.get('abbreviation', ''),
                'entity_type': 'team'
            })
    
    # Create prompt
    entity_name = "player" if entity_type == "player" else "team"
    prompt = f"I found multiple {entity_name}s matching '{surface_text}'. Please select one:"
    
    clarification = Clarification(
        type="entity_disambiguation",
        prompt=prompt,
        options=options,
        context={
            'entity_type': entity_type,
            'surface_text': surface_text,
            'original_candidates': candidates
        }
    )
    
    return clarification


def parse_clarification_response(
    response: str,
    clarification: Clarification
) -> Optional[Dict[str, Any]]:
    """
    Parse user's clarification response.
    Handles both numeric selection (e.g., "1") and full name (e.g., "Anthony Davis").
    
    Args:
        response: User's response
        clarification: The pending clarification
    
    Returns:
        Selected option dict or None if invalid
    """
    response = response.strip()
    
    # Try numeric selection first
    if response.isdigit():
        selection_num = int(response)
        for option in clarification.options:
            if option['id'] == str(selection_num):
                return option
    
    # Try matching full name (case-insensitive)
    response_lower = response.lower()
    for option in clarification.options:
        # For players, match against full_name
        if 'full_name' in option:
            if response_lower in option['full_name'].lower():
                return option
        # For teams, match against team name or abbreviation
        elif 'team' in option:
            if (response_lower in option['team'].lower() or 
                response_lower == option.get('abbreviation', '').lower()):
                return option
    
    return None


def format_clarification_for_display(clarification: Clarification) -> str:
    """
    Format clarification as a user-friendly string.
    
    Args:
        clarification: The clarification object
    
    Returns:
        Formatted string
    """
    lines = [clarification.prompt, ""]
    
    for option in clarification.options:
        lines.append(option['display'])
    
    lines.append("")
    lines.append("Please respond with the number or full name.")
    
    return "\n".join(lines)


def is_clarification_response(message: str, clarification: Optional[Clarification]) -> bool:
    """
    Check if a message appears to be a clarification response.
    
    Args:
        message: User's message
        clarification: Pending clarification (if any)
    
    Returns:
        True if message looks like a clarification response
    """
    if not clarification:
        return False
    
    message = message.strip()
    
    # Check if it's a number matching an option
    if message.isdigit():
        selection_num = int(message)
        return any(opt['id'] == str(selection_num) for opt in clarification.options)
    
    # Check if it matches any option name
    message_lower = message.lower()
    for option in clarification.options:
        if 'full_name' in option and message_lower in option['full_name'].lower():
            return True
        if 'team' in option and message_lower in option['team'].lower():
            return True
    
    return False

# Made with Bob
