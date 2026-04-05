from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import uuid


@dataclass
class ResolvedEntity:
    """Represents a resolved entity (player or team) in the conversation."""
    entity_type: str  # "player" or "team"
    surface_text: str  # Original text from user (e.g., "Curry", "Anthony")
    resolved_id: str  # Database ID
    resolved_name: str  # Full canonical name
    resolved_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_type': self.entity_type,
            'surface_text': self.surface_text,
            'resolved_id': self.resolved_id,
            'resolved_name': self.resolved_name,
            'resolved_at': self.resolved_at.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class Clarification:
    """Represents a pending clarification request."""
    clarification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "entity_disambiguation"  # Type of clarification needed
    prompt: str = ""  # Prompt to show user
    options: List[Dict[str, Any]] = field(default_factory=list)  # List of options
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'clarification_id': self.clarification_id,
            'type': self.type,
            'prompt': self.prompt,
            'options': self.options,
            'context': self.context,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class Message:
    """Represents a single message in the conversation."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    role: str = "user"  # "user", "assistant", or "system"
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    intermediate_steps: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'message_id': self.message_id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'intermediate_steps': self.intermediate_steps,
            'metadata': self.metadata
        }


@dataclass
class Conversation:
    """Represents a conversation with message history and context."""
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    messages: List[Message] = field(default_factory=list)
    resolved_entities: Dict[str, ResolvedEntity] = field(default_factory=dict)
    pending_clarification: Optional[Clarification] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, 
                   intermediate_steps: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a message to the conversation."""
        message = Message(
            conversation_id=self.conversation_id,
            role=role,
            content=content,
            intermediate_steps=intermediate_steps,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get the most recent messages."""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages
    
    def get_context_for_llm(self, max_messages: int = 5) -> List[Dict[str, str]]:
        """
        Get conversation context formatted for LLM input.
        Returns list of {role, content} dicts.
        """
        recent = self.get_recent_messages(max_messages)
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in recent
        ]
    
    def cache_resolved_entity(self, surface_text: str, entity: ResolvedEntity):
        """Cache a resolved entity for future reference."""
        # Normalize the surface text for lookup
        normalized_key = surface_text.lower().strip()
        self.resolved_entities[normalized_key] = entity
        self.updated_at = datetime.utcnow()
    
    def get_cached_entity(self, surface_text: str) -> Optional[ResolvedEntity]:
        """Get a cached resolved entity."""
        normalized_key = surface_text.lower().strip()
        return self.resolved_entities.get(normalized_key)
    
    def set_pending_clarification(self, clarification: Clarification):
        """Set a pending clarification request."""
        self.pending_clarification = clarification
        self.updated_at = datetime.utcnow()
    
    def clear_pending_clarification(self):
        """Clear the pending clarification."""
        self.pending_clarification = None
        self.updated_at = datetime.utcnow()
    
    def is_expired(self, ttl_hours: int = 24) -> bool:
        """Check if conversation has expired based on TTL."""
        expiry_time = self.updated_at + timedelta(hours=ttl_hours)
        return datetime.utcnow() > expiry_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary."""
        return {
            'conversation_id': self.conversation_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'messages': [msg.to_dict() for msg in self.messages],
            'resolved_entities': {
                key: entity.to_dict() 
                for key, entity in self.resolved_entities.items()
            },
            'pending_clarification': (
                self.pending_clarification.to_dict() 
                if self.pending_clarification else None
            ),
            'metadata': self.metadata
        }


class ConversationStore:
    """In-memory store for conversations with TTL-based cleanup."""
    
    def __init__(self, ttl_hours: int = 24):
        self.conversations: Dict[str, Conversation] = {}
        self.ttl_hours = ttl_hours
    
    def create_conversation(self) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation()
        self.conversations[conversation.conversation_id] = conversation
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        conversation = self.conversations.get(conversation_id)
        
        # Check if expired
        if conversation and conversation.is_expired(self.ttl_hours):
            self.delete_conversation(conversation_id)
            return None
        
        return conversation
    
    def get_or_create_conversation(self, conversation_id: Optional[str] = None) -> Conversation:
        """Get existing conversation or create new one."""
        if conversation_id:
            conversation = self.get_conversation(conversation_id)
            if conversation:
                return conversation
        
        return self.create_conversation()
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            return True
        return False
    
    def cleanup_expired(self):
        """Remove expired conversations."""
        expired_ids = [
            conv_id for conv_id, conv in self.conversations.items()
            if conv.is_expired(self.ttl_hours)
        ]
        
        for conv_id in expired_ids:
            del self.conversations[conv_id]
        
        return len(expired_ids)
    
    def get_all_conversation_ids(self) -> List[str]:
        """Get all active conversation IDs."""
        return list(self.conversations.keys())
    
    def count(self) -> int:
        """Get count of active conversations."""
        return len(self.conversations)


# Global conversation store instance
conversation_store = ConversationStore(ttl_hours=24)

# Made with Bob
