"""
Interactive chat interface for the NBA Agent with conversational support.
Demonstrates ambiguous entity resolution and context-aware conversations.

Usage:
    cd backend
    source .venv/bin/activate
    python interactive_chat.py
"""

from app.chat_service import run_tracked_chat_message
from openai import OpenAI
import sys


def print_separator():
    """Print a visual separator."""
    print("\n" + "="*70 + "\n")


def print_response(response):
    """Print the agent's response in a readable format."""
    status = response.get('status')
    
    if status == 'success':
        print("\n🤖 Agent:")
        print("-" * 70)
        print(response['response'])
        print("-" * 70)
    
    elif status == 'needs_clarification':
        clarification = response['clarification']
        print("\n🤖 Agent:")
        print("-" * 70)
        print(clarification['prompt'])
        print()
        for option in clarification['options']:
            print(f"  {option['display']}")
        print()
        print("💡 Tip: You can respond with the number (e.g., '1') or the full name.")
        print("-" * 70)
    
    elif status == 'error':
        error = response.get('error', {})
        print("\n❌ Error:")
        print("-" * 70)
        print(f"{error.get('message', 'Unknown error')}")
        if error.get('details'):
            print(f"\nDetails: {error['details']}")
        if error.get('retry_count'):
            print(f"(Failed after {error['retry_count']} retry attempts)")
        print("-" * 70)


def main():
    """Run the interactive chat interface."""
    print_separator()
    print("🏀 NBA Agent - Interactive Chat")
    print("="*70)
    print("\nFeatures:")
    print("  ✅ Conversational context (remembers previous entities)")
    print("  ✅ Ambiguous entity clarification")
    print("  ✅ Automatic retry on errors")
    print("\nCommands:")
    print("  - Type your question and press Enter")
    print("  - Type 'quit' or 'exit' to end the session")
    print("  - Type 'new' to start a new conversation")
    print_separator()
    
    client = OpenAI()
    conversation_id = None
    
    print("💬 Start asking questions! (or type 'quit' to exit)\n")
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Check for commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() in ['new', 'reset']:
                conversation_id = None
                print("\n🔄 Started new conversation\n")
                continue
            
            # Process the message
            print("\n⏳ Processing...")
            response = run_tracked_chat_message(
                client=client,
                message=user_input,
                conversation_id=conversation_id,
                include_steps=False,
                source="interactive_chat",
            )
            
            # Update conversation ID
            conversation_id = response.get('conversation_id')
            
            # Print the response
            print_response(response)
            
            # Show conversation ID for debugging
            if conversation_id:
                print(f"\n💾 Conversation ID: {conversation_id[:8]}...")
            
            print()  # Extra newline for readability
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            print("\nFull traceback:")
            traceback.print_exc()
            print("\nYou can continue asking questions or type 'quit' to exit.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
