from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import json
from pathlib import Path
from app.config import SYNTHESIS_MODEL
from app.orchestrator.llm_usage import record_llm_response
from app.utils.retry import retry_with_context, format_retry_context_for_prompt

load_dotenv()

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "synthesis-prompt.txt"
SYNTHESIS_PROMPT = PROMPT_PATH.read_text()

@retry_with_context(max_attempts=3)
def synthesize_output(
    client,
    question: str,
    rows: list,
    step_outputs: dict = None,
    plan: dict = None,
    retry_context: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Synthesize final answer with retry logic.
    
    Args:
        client: OpenAI client
        question: User's question
        rows: Final query results
        step_outputs: Intermediate step outputs
        plan: Query plan
        retry_context: Injected by retry decorator on retry attempts
    
    Returns:
        Synthesized answer dict
    """
    prompt = SYNTHESIS_PROMPT
    
    # Add retry context if this is a retry attempt
    if retry_context:
        prompt += format_retry_context_for_prompt(retry_context)

    # For multi-step queries where all outputs matter, use step_outputs
    # Otherwise use the final rows output
    if step_outputs and len(step_outputs) > 1:
        # If we have a plan, enrich step_outputs with descriptions
        if plan and 'steps' in plan:
            execution_results = {}
            for step in plan['steps']:
                step_id = step['step_id']
                if step_id in step_outputs:
                    execution_results[step_id] = {
                        'description': step.get('description', ''),
                        'data': step_outputs[step_id]
                    }
        else:
            execution_results = step_outputs
        
        # Performance optimization: If we have two large datasets with matching keys,
        # do the comparison in code rather than sending 1000+ rows to the LLM
        if len(step_outputs) == 2:
            step_keys = list(step_outputs.keys())
            s1_data = step_outputs[step_keys[0]]
            s2_data = step_outputs[step_keys[1]]
            
            # Only optimize if both datasets are large (>10 rows) and have common structure
            if (s1_data and s2_data and len(s1_data) > 10 and len(s2_data) > 10):
                # Find common keys between the two datasets
                if s1_data and s2_data:
                    s1_keys = set(s1_data[0].keys())
                    s2_keys = set(s2_data[0].keys())
                    common_keys = s1_keys & s2_keys
                    
                    # If they share player_id and a max aggregation, it's likely a comparison query
                    if 'player_id' in common_keys:
                        # Find max aggregation fields (e.g., pts_max, reb_max)
                        max_fields = [k for k in common_keys if k.endswith('_max')]
                        
                        if max_fields:
                            # This is a comparison query - do the comparison in code
                            comparison_field = max_fields[0]  # Use first max field
                            
                            # Create lookup dictionaries
                            s1_lookup = {row['player_id']: row for row in s1_data}
                            s2_lookup = {row['player_id']: row for row in s2_data}
                            
                            # Find matches where the max values are equal
                            matches = []
                            for player_id in s2_lookup:
                                if player_id in s1_lookup:
                                    s1_value = s1_lookup[player_id][comparison_field]
                                    s2_value = s2_lookup[player_id][comparison_field]
                                    # Only include if values match AND are greater than 0
                                    if s1_value == s2_value and s1_value > 0:
                                        matches.append(s1_lookup[player_id])
                            
                            # Sort by the comparison field descending
                            if matches:
                                matches.sort(key=lambda x: x[comparison_field], reverse=True)
                                execution_results = matches
    else:
        execution_results = rows

    planner_input = {
        "question": question,
        "execution_results": execution_results
    }

    response = client.responses.create(
        model=SYNTHESIS_MODEL,
        input=[
            {
                "role": "system", 
                "content": prompt
            },
            {
                "role": "user",
                "content": json.dumps(planner_input, indent=2, default=str)
            },
        ],
        temperature=0.0
    )
    record_llm_response("synthesis", SYNTHESIS_MODEL, response)

    output_text = response.output[0].content[0].text.strip()
    return {
        'status': 'success',
        'output': output_text
    }

# Made with Bob
