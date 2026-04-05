import React, { useState, useEffect, useRef } from 'react';
import Message from './Message';
import MessageInput from './MessageInput';
import { sendMessage } from '../services/api';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showSteps, setShowSteps] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (messageText) => {
    // Add user message to UI
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);

    try {
      const response = await sendMessage(conversationId, messageText, showSteps);
      
      // Update conversation ID if new
      if (!conversationId && response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      // Add assistant response
      const assistantMessage = {
        id: response.message_id || Date.now() + 1,
        role: 'assistant',
        content: response.response || response.clarification?.prompt || 'No response',
        timestamp: new Date().toISOString(),
        clarification: response.clarification,
        intermediate_steps: response.intermediate_steps,
        error: response.error,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message || 'Failed to send message');
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: new Date().toISOString(),
        error: {
          message: err.message || 'Unknown error',
          details: err.response?.data?.detail || '',
        },
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleClarificationSelect = (option) => {
    // Send the selected option as a new message
    handleSendMessage(option.id);
  };

  const handleClearChat = () => {
    setMessages([]);
    setConversationId(null);
    setError(null);
  };

  const exampleQuestions = [
    "What are Jaylen Brown's stats when Jayson Tatum does not play?",
    "Who scored the most points in the last Lakers game?",
    "What is the Warriors record without Steph Curry this season?",
    "Compare LeBron James and Kevin Durant's scoring.",
  ];

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">NBA Stats Chatbot</h1>
          <p className="text-sm text-gray-600">Ask me anything about NBA statistics</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={showSteps}
              onChange={(e) => setShowSteps(e.target.checked)}
              className="rounded"
            />
            Show intermediate steps
          </label>
          <button
            onClick={handleClearChat}
            className="px-4 py-2 text-sm bg-gray-200 hover:bg-gray-300 rounded-lg transition-colors"
          >
            Clear Chat
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="text-center mb-8">
              <h2 className="text-xl font-semibold text-gray-700 mb-2">
                Welcome to NBA Stats Chatbot!
              </h2>
              <p className="text-gray-600">
                Ask questions about NBA players, teams, and game statistics
              </p>
            </div>
            <div className="w-full max-w-2xl">
              <p className="text-sm font-medium text-gray-700 mb-3">Try these examples:</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {exampleQuestions.map((question, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(question)}
                    className="text-left p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all"
                  >
                    <p className="text-sm text-gray-700">{question}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <Message
                key={message.id}
                message={message}
                onClarificationSelect={handleClarificationSelect}
              />
            ))}
            {loading && (
              <div className="flex justify-start mb-4">
                <div className="bg-gray-100 rounded-lg px-4 py-3 border border-gray-200">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                    <span className="text-sm text-gray-600">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="px-6 py-2 bg-red-50 border-t border-red-200">
          <p className="text-sm text-red-700">⚠️ {error}</p>
        </div>
      )}

      {/* Input Area */}
      <MessageInput
        onSend={handleSendMessage}
        disabled={loading}
        placeholder="Ask about NBA stats..."
      />
    </div>
  );
};

export default Chat;

// Made with Bob
