# Quick Start Guide - NBA Agent Enhancement

This guide provides a quick reference for implementing the three major features.

## 📋 Implementation Checklist

### Phase 1: Backend Foundation (Days 1-3)

#### 1.1 Conversation Models
- [ ] Create `backend/app/models/conversation.py`
- [ ] Define `Conversation`, `Message`, `ResolvedEntity`, `Clarification` classes
- [ ] Create in-memory conversation store with TTL

#### 1.2 Retry Mechanism
- [ ] Create `backend/app/utils/retry.py`
- [ ] Implement `retry_with_context` decorator
- [ ] Add error context injection logic
- [ ] Add exponential backoff

#### 1.3 Context-Aware Entity Resolution
- [ ] Update [`extract_entity_mentions()`](backend/app/orchestrator/entity_extraction.py:10) to accept conversation history
- [ ] Modify entity extraction prompt to include context
- [ ] Update [`resolve_entity_mentions()`](backend/app/orchestrator/entity_extraction.py:39) to check conversation cache

#### 1.4 Ambiguous Entity Handling
- [ ] Create clarification request builder
- [ ] Add numbered option formatting
- [ ] Implement selection parser (handle "1" or "Anthony Davis")

#### 1.5 FastAPI Endpoints
- [ ] `POST /api/chat` - Main chat endpoint
- [ ] `GET /api/conversations/{id}` - Get conversation history
- [ ] `DELETE /api/conversations/{id}` - Delete conversation
- [ ] `GET /api/examples` - Get example questions

### Phase 2: Backend Integration (Days 4-5)

#### 2.1 Conversational Agent Flow
- [ ] Create `backend/app/chat_flow.py` (new conversational version)
- [ ] Implement conversation state loading/saving
- [ ] Add clarification handling logic
- [ ] Integrate with existing agent flow

#### 2.2 Apply Retry Logic
- [ ] Wrap [`extract_entity_mentions()`](backend/app/orchestrator/entity_extraction.py:10) with retry
- [ ] Wrap [`plan_question()`](backend/app/orchestrator/planning.py:11) with retry
- [ ] Wrap [`synthesize_output()`](backend/app/orchestrator/synthesis.py:7) with retry
- [ ] Update error responses to include retry info

#### 2.3 Testing & Logging
- [ ] Add comprehensive logging
- [ ] Test ambiguous entity flow
- [ ] Test retry mechanism
- [ ] Test context-aware resolution

### Phase 3: Frontend Development (Days 6-9)

#### 3.1 Project Setup
```bash
cd frontend
npm create vite@latest . -- --template react
npm install axios react-markdown react-syntax-highlighter
npm install -D tailwindcss postcss autoprefixer
```

#### 3.2 Core Components
- [ ] `src/App.jsx` - Main app with routing
- [ ] `src/components/ChatContainer.jsx` - Main chat container
- [ ] `src/components/MessageList.jsx` - Message list with auto-scroll
- [ ] `src/components/Message.jsx` - Individual message
- [ ] `src/components/MessageInput.jsx` - Input with send button
- [ ] `src/components/Sidebar.jsx` - Conversation list

#### 3.3 Special Components
- [ ] `src/components/IntermediateSteps.jsx` - Collapsible steps display
- [ ] `src/components/ClarificationPrompt.jsx` - Numbered options UI
- [ ] `src/components/ExampleQuestions.jsx` - Clickable examples
- [ ] `src/components/LoadingIndicator.jsx` - Typing animation

#### 3.4 Hooks & Services
- [ ] `src/hooks/useChat.js` - Chat state management
- [ ] `src/hooks/useConversation.js` - Conversation list management
- [ ] `src/services/api.js` - API client

#### 3.5 Styling
- [ ] Set up Tailwind CSS
- [ ] Create responsive layout
- [ ] Add dark mode support (optional)
- [ ] Polish UI/UX

### Phase 4: Integration & Testing (Days 10-11)

#### 4.1 Integration
- [ ] Connect frontend to backend API
- [ ] Test all API endpoints
- [ ] Handle CORS configuration
- [ ] Test error scenarios

#### 4.2 E2E Testing
- [ ] Test ambiguous entity clarification flow
- [ ] Test retry on failures
- [ ] Test conversation persistence
- [ ] Test intermediate steps display

#### 4.3 Bug Fixes & Polish
- [ ] Fix any integration issues
- [ ] Optimize performance
- [ ] Add loading states
- [ ] Improve error messages

### Phase 5: Deployment (Day 12)

#### 5.1 Backend Deployment
- [ ] Update `requirements.txt`
- [ ] Configure environment variables
- [ ] Set up CORS for production
- [ ] Deploy to server

#### 5.2 Frontend Deployment
- [ ] Build production bundle
- [ ] Configure API endpoint
- [ ] Deploy to CDN/hosting
- [ ] Test production environment

## 🔧 Key Files to Create/Modify

### New Files
```
backend/app/models/conversation.py
backend/app/utils/retry.py
backend/app/chat_flow.py
backend/app/conversation_manager.py
frontend/                           (entire directory)
```

### Files to Modify
```
backend/app/main.py                 (add API endpoints)
backend/app/orchestrator/entity_extraction.py  (add context awareness)
backend/app/orchestrator/planning.py           (add retry)
backend/app/orchestrator/synthesis.py          (add retry)
backend/requirements.txt            (add new dependencies)
```

## 📦 New Dependencies

### Backend
```txt
# Add to requirements.txt
fastapi-cors>=0.0.6
python-multipart>=0.0.6
```

### Frontend
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "react-markdown": "^9.0.0",
    "react-syntax-highlighter": "^15.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

## 🚀 Quick Commands

### Backend Development
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Testing
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🎯 Testing Scenarios

### Scenario 1: Ambiguous Entity
```
User: "How many points did Anthony score?"
Expected: System asks for clarification
User: "1" or "Anthony Davis"
Expected: System continues with query
```

### Scenario 2: Context-Aware Resolution
```
User: "What are Steph Curry's stats?"
Expected: System resolves and answers
User: "How does Curry compare to LeBron?"
Expected: System knows "Curry" = "Steph Curry" from context
```

### Scenario 3: Retry on Failure
```
Simulate: LLM returns invalid JSON
Expected: System retries with error context
Expected: Success on retry or graceful error after 3 attempts
```

### Scenario 4: Intermediate Steps
```
User: Asks complex question
Expected: Answer displayed with expandable intermediate steps
Expected: Shows entities, plan, query results
```

## 📝 Code Snippets

### Retry Decorator Usage
```python
from app.utils.retry import retry_with_context

@retry_with_context(max_attempts=3)
def extract_entity_mentions(client, question, retry_context=None):
    prompt = load_prompt()
    
    # Inject error context on retry
    if retry_context:
        prompt += f"\n\nPREVIOUS ATTEMPT FAILED:\n{retry_context['previous_error']}"
    
    response = client.responses.create(...)
    return parse_response(response)
```

### Conversation Manager Usage
```python
from app.conversation_manager import ConversationManager

conv_mgr = ConversationManager()

# Load or create conversation
conversation = conv_mgr.get_or_create(conversation_id)

# Add user message
conversation.add_message(role="user", content=question)

# Check for pending clarification
if conversation.pending_clarification:
    # Handle clarification response
    entity = conv_mgr.resolve_clarification(conversation, user_selection)
```

### Frontend API Call
```javascript
import { sendMessage } from './services/api';

const handleSend = async (message) => {
  setLoading(true);
  try {
    const response = await sendMessage({
      conversation_id: conversationId,
      message: message,
      include_steps: true
    });
    
    if (response.status === 'needs_clarification') {
      setPendingClarification(response.clarification);
    } else {
      addMessage(response);
    }
  } catch (error) {
    setError(error.message);
  } finally {
    setLoading(false);
  }
};
```

## 🐛 Common Issues & Solutions

### Issue: CORS errors in frontend
**Solution:** Add CORS middleware in `backend/app/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Conversation not persisting
**Solution:** Check conversation TTL and cleanup logic

### Issue: Retry not working
**Solution:** Ensure retry decorator is applied and error context is properly injected

### Issue: Frontend not updating
**Solution:** Check React state updates and useEffect dependencies

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)

## 🎉 Success Criteria

- ✅ Ambiguous entities trigger clarification prompt
- ✅ Context-aware resolution works (e.g., "Curry" after "Steph Curry")
- ✅ Failed LLM calls retry with error context
- ✅ Frontend displays conversation history
- ✅ Intermediate steps are viewable
- ✅ Copy, clear, and example features work
- ✅ Responsive design on mobile and desktop
- ✅ Error messages are user-friendly
- ✅ Performance is acceptable (<5s for simple queries)
