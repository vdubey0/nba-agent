from app.db import SessionLocal
from app.models import Player, Team
from sqlalchemy import func, or_, case
import pprint
import unicodedata
import re

def normalize_name_for_matching(name: str) -> str:
    """
    Normalize a name for matching by:
    1. Removing periods, hyphens, and apostrophes
    2. Collapsing multiple spaces into one
    3. Converting to lowercase
    
    This allows "PJ Washington", "P.J. Washington", "P J Washington" to all match.
    """
    # Remove periods, hyphens, apostrophes
    normalized = re.sub(r"[.\-']", "", name)
    # Collapse multiple spaces into one
    normalized = " ".join(normalized.strip().split())
    return normalized.lower()

def find_player_candidates(session, name: str, limit: int = 5):
    cleaned = " ".join(name.strip().split())
    normalized_input = normalize_name_for_matching(cleaned)
    terms = normalized_input.split()

    query = session.query(Player)

    for term in terms:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                func.lower(func.regexp_replace(func.unaccent(Player.first_name), '[.\\-\']', '', 'g')).like(func.lower(func.unaccent(pattern))),
                func.lower(func.regexp_replace(func.unaccent(Player.last_name), '[.\\-\']', '', 'g')).like(func.lower(func.unaccent(pattern))),
                func.lower(func.regexp_replace(func.unaccent(Player.full_name), '[.\\-\']', '', 'g')).like(func.lower(func.unaccent(pattern))),
            )
        )

    query = query.order_by(
        case(
            (
                func.lower(func.regexp_replace(func.unaccent(Player.full_name), '[.\\-\']', '', 'g'))
                == normalized_input,
                4,
            ),
            (
                func.lower(func.regexp_replace(func.unaccent(Player.full_name), '[.\\-\']', '', 'g')).like(f"{normalized_input}%"),
                3,
            ),
            (
                func.lower(func.regexp_replace(func.unaccent(Player.last_name), '[.\\-\']', '', 'g')).like(f"{normalized_input}%"),
                2,
            ),
            (
                func.lower(func.regexp_replace(func.unaccent(Player.first_name), '[.\\-\']', '', 'g')).like(f"{normalized_input}%"),
                2,
            ),
            else_=1,
        ).desc(),
        Player.last_name.asc(),
        Player.first_name.asc(),
    )

    return query.limit(limit).all()


def resolve_player(session, name: str):
    cleaned = " ".join(name.strip().split())
    terms = cleaned.split()

    candidates = find_player_candidates(session, cleaned, limit=10)

    if not candidates:
        return {
            "status": "not_found",
        }

    if len(candidates) == 1:
        player = candidates[0]
        return {
            "status": "resolved",
            "full_name": player.full_name,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "id": player.player_id
        }

    # If multiple candidates, return ambiguous regardless of number of terms
    # This ensures we always ask for clarification when there's ambiguity
    return {
        "status": "ambiguous",
        "players": [
            {"id": p.player_id, "full_name": p.full_name, "first_name": p.first_name, "last_name": p.last_name}
            for p in candidates
        ]
    }


TEAM_ALIASES = {
    "atl": ["atl", "hawks", "atlanta", "atlanta hawks"],
    "bos": ["bos", "celtics", "boston", "boston celtics"],
    "bkn": ["bkn", "nets", "brooklyn", "brooklyn nets"],
    "cha": ["cha", "hornets", "charlotte", "charlotte hornets"],
    "chi": ["chi", "bulls", "chicago", "chicago bulls"],
    "cle": ["cle", "cavs", "cavaliers", "cleveland", "cleveland cavaliers"],
    "dal": ["dal", "mavs", "mavericks", "dallas", "dallas mavericks"],
    "den": ["den", "nuggets", "denver", "denver nuggets"],
    "det": ["det", "pistons", "detroit", "detroit pistons"],
    "gsw": ["gsw", "gs", "warriors", "golden state", "golden state warriors", "dubs"],
    "hou": ["hou", "rockets", "houston", "houston rockets"],
    "ind": ["ind", "pacers", "indiana", "indiana pacers"],
    "lac": ["lac", "clippers", "la clippers", "los angeles clippers", "los angeles"],
    "lal": ["lal", "lakers", "la lakers", "los angeles lakers", "los angeles"],
    "mem": ["mem", "grizzlies", "memphis", "memphis grizzlies"],
    "mia": ["mia", "heat", "miami", "miami heat"],
    "mil": ["mil", "bucks", "milwaukee", "milwaukee bucks"],
    "min": ["min", "timberwolves", "wolves", "minnesota", "minnesota timberwolves"],
    "nop": ["nop", "no", "pelicans", "new orleans", "new orleans pelicans"],
    "nyk": ["nyk", "ny", "knicks", "new york", "new york knicks"],
    "okc": ["okc", "thunder", "oklahoma city", "oklahoma city thunder"],
    "orl": ["orl", "magic", "orlando", "orlando magic"],
    "phi": ["phi", "76ers", "sixers", "philadelphia", "philadelphia 76ers"],
    "phx": ["phx", "phoenix", "suns", "phoenix suns"],
    "por": ["por", "blazers", "trail blazers", "portland", "portland trail blazers"],
    "sac": ["sac", "kings", "sacramento", "sacramento kings"],
    "sas": ["sas", "spurs", "san antonio", "san antonio spurs", "sa"],
    "tor": ["tor", "raptors", "toronto", "toronto raptors"],
    "uta": ["uta", "jazz", "utah", "utah jazz"],
    "was": ["was", "wizards", "washington", "washington wizards"],
}

def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def resolve_team(session, name: str):
    query = _normalize(name)

    teams = session.query(Team).all()

    matches = []

    for team in teams:
        city = _normalize(team.city)
        team_name = _normalize(team.full_name)
        abbr = _normalize(team.abbreviation)

        full = f"{city} {team_name}"

        tokens = set([city, team_name, abbr, full])

        tokens.update(TEAM_ALIASES.get(abbr, []))

        tokens = {_normalize(t) for t in tokens}

        if query == "la":
            if abbr in ["lal", "lac"]:
                matches.append(team)
            continue

        if query in tokens:
            matches.append(team)
            continue

        if any(query in token for token in tokens):
            matches.append(team)

    if not matches:
        return {
            "status": "not_found",
        }

    if len(matches) == 1:
        team = matches[0]
        return {
            "status": "resolved",
            "team": f"{team.city} {team.full_name}",
            "id": team.team_id,
            "city": team.city,
            "name": team.full_name,
            "abbreviation": team.abbreviation,
        }
    return {
        "status": "ambiguous",
        "candidates": [
            {
                "id": t.team_id,
                "team": f"{t.city} {t.full_name}",
                "city": t.city,
                "name": t.full_name,
                "abbreviation": t.abbreviation,
            }
            for t in matches
        ]
    }



if __name__ == '__main__':
    pprint.pprint(resolve_team(SessionLocal(), 'warriors'))
