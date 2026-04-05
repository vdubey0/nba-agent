import time
import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional

logger = logging.getLogger(__name__)


def retry_with_context(max_attempts: int = 3, backoff: float = 1.0):
    """
    Decorator that retries LLM calls with error context injection.
    
    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff: Base backoff time in seconds (default: 1.0)
    
    Usage:
        @retry_with_context(max_attempts=3)
        def my_llm_call(client, question, retry_context=None):
            # Function will be retried up to 3 times
            # On retry, retry_context will contain error information
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            last_output = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Inject error context on retry attempts
                    if attempt > 1 and last_error:
                        retry_context = {
                            'attempt': attempt,
                            'max_attempts': max_attempts,
                            'previous_error': str(last_error),
                            'previous_output': last_output
                        }
                        kwargs['retry_context'] = retry_context
                        
                        logger.warning(
                            f"{func.__name__} - Retry attempt {attempt}/{max_attempts}. "
                            f"Previous error: {last_error}"
                        )
                    
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # Check if result indicates failure (for dict responses with 'status')
                    if isinstance(result, dict) and result.get('status') == 'failed':
                        last_error = result.get('error', 'Unknown error')
                        last_output = result.get('raw_text', '')
                        
                        if attempt < max_attempts:
                            # Wait before retry with exponential backoff
                            wait_time = backoff * (2 ** (attempt - 1))
                            logger.info(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            # All attempts exhausted
                            logger.error(
                                f"{func.__name__} - All {max_attempts} attempts failed. "
                                f"Last error: {last_error}"
                            )
                            return {
                                'status': 'failed',
                                'error': f'Failed after {max_attempts} attempts: {last_error}',
                                'retry_count': max_attempts,
                                'last_output': last_output
                            }
                    
                    # Success - return result
                    if attempt > 1:
                        logger.info(f"{func.__name__} - Succeeded on attempt {attempt}")
                    return result
                    
                except Exception as e:
                    last_error = e
                    logger.error(f"{func.__name__} - Attempt {attempt} raised exception: {e}")
                    
                    if attempt < max_attempts:
                        # Wait before retry with exponential backoff
                        wait_time = backoff * (2 ** (attempt - 1))
                        logger.info(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # All attempts exhausted, re-raise the exception
                        logger.error(
                            f"{func.__name__} - All {max_attempts} attempts failed with exception"
                        )
                        raise
            
            # Should not reach here, but just in case
            return {
                'status': 'failed',
                'error': f'Unexpected error after {max_attempts} attempts',
                'retry_count': max_attempts
            }
        
        return wrapper
    return decorator


def format_retry_context_for_prompt(retry_context: Optional[Dict[str, Any]]) -> str:
    """
    Format retry context into a string that can be appended to LLM prompts.
    
    Args:
        retry_context: Dictionary containing retry information
    
    Returns:
        Formatted string to append to prompt
    """
    if not retry_context:
        return ""
    
    attempt = retry_context.get('attempt', 0)
    max_attempts = retry_context.get('max_attempts', 0)
    previous_error = retry_context.get('previous_error', 'Unknown error')
    previous_output = retry_context.get('previous_output', '')
    
    context_str = f"\n\n{'='*60}\n"
    context_str += f"RETRY ATTEMPT {attempt}/{max_attempts}\n"
    context_str += f"{'='*60}\n\n"
    context_str += f"PREVIOUS ATTEMPT FAILED:\n"
    context_str += f"Error: {previous_error}\n\n"
    
    if previous_output:
        context_str += f"Previous Output (that caused the error):\n"
        context_str += f"{previous_output}\n\n"
    
    context_str += f"Please correct the issue and provide valid output.\n"
    context_str += f"{'='*60}\n"
    
    return context_str

# Made with Bob
