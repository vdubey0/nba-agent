import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const Message = ({ message, onClarificationSelect }) => {
  const [showSteps, setShowSteps] = useState(false);
  const isUser = message.role === 'user';

  const handleClarificationClick = (option) => {
    if (onClarificationSelect) {
      onClarificationSelect(option);
    }
  };

  // Custom components for markdown rendering
  const markdownComponents = {
    table: ({ node, ...props }) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full divide-y divide-gray-300 border border-gray-300" {...props} />
      </div>
    ),
    thead: ({ node, ...props }) => (
      <thead className="bg-gray-50" {...props} />
    ),
    tbody: ({ node, ...props }) => (
      <tbody className="divide-y divide-gray-200 bg-white" {...props} />
    ),
    tr: ({ node, ...props }) => (
      <tr {...props} />
    ),
    th: ({ node, ...props }) => (
      <th className="px-3 py-2 text-left text-xs font-medium text-gray-900 uppercase tracking-wider border-r border-gray-300 last:border-r-0" {...props} />
    ),
    td: ({ node, ...props }) => (
      <td className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200 last:border-r-0" {...props} />
    ),
    p: ({ node, ...props }) => (
      <p className="mb-2 last:mb-0" {...props} />
    ),
    ul: ({ node, ...props }) => (
      <ul className="list-disc list-inside mb-2 space-y-1" {...props} />
    ),
    ol: ({ node, ...props }) => (
      <ol className="list-decimal list-inside mb-2 space-y-1" {...props} />
    ),
    li: ({ node, ...props }) => (
      <li className="text-sm" {...props} />
    ),
    strong: ({ node, ...props }) => (
      <strong className="font-semibold" {...props} />
    ),
    em: ({ node, ...props }) => (
      <em className="italic" {...props} />
    ),
    code: ({ node, inline, ...props }) =>
      inline ? (
        <code className="bg-gray-200 px-1 py-0.5 rounded text-sm font-mono" {...props} />
      ) : (
        <code className="block bg-gray-200 p-2 rounded text-sm font-mono overflow-x-auto" {...props} />
      ),
    h1: ({ node, ...props }) => (
      <h1 className="text-xl font-bold mb-2" {...props} />
    ),
    h2: ({ node, ...props }) => (
      <h2 className="text-lg font-bold mb-2" {...props} />
    ),
    h3: ({ node, ...props }) => (
      <h3 className="text-base font-bold mb-2" {...props} />
    ),
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900 border border-gray-200'
        }`}
      >
        {/* Message Content */}
        <div className="markdown-content">
          {isUser ? (
            <p className="text-white m-0">{message.content}</p>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>

        {/* Clarification Options */}
        {message.clarification && (
          <div className="mt-3 space-y-2">
            <p className="font-semibold text-sm">{message.clarification.prompt}</p>
            <div className="space-y-1">
              {message.clarification.options.map((option) => (
                <button
                  key={option.id}
                  onClick={() => handleClarificationClick(option)}
                  className="block w-full text-left px-3 py-2 text-sm bg-white hover:bg-blue-50 border border-gray-300 rounded transition-colors"
                >
                  {option.display}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error Display */}
        {message.error && (
          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            <p className="font-semibold">Error:</p>
            <p>{message.error.message}</p>
            {message.error.details && (
              <p className="text-xs mt-1 opacity-75">{message.error.details}</p>
            )}
          </div>
        )}

        {/* Intermediate Steps */}
        {message.intermediate_steps && (
          <div className="mt-3">
            <button
              onClick={() => setShowSteps(!showSteps)}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              {showSteps ? '▼' : '▶'} Show intermediate steps
            </button>
            {showSteps && (
              <div className="mt-2 p-3 bg-gray-50 rounded text-xs space-y-2">
                {/* Entities */}
                {message.intermediate_steps.entities && (
                  <div>
                    <p className="font-semibold text-gray-700">Entities:</p>
                    <ul className="list-disc list-inside text-gray-600">
                      {message.intermediate_steps.entities.map((entity, idx) => (
                        <li key={idx}>
                          {entity.surface_text} → {entity.resolved_name || entity.status}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Plan */}
                {message.intermediate_steps.plan && (
                  <div>
                    <p className="font-semibold text-gray-700">Query Plan:</p>
                    <p className="text-gray-600">
                      Type: {message.intermediate_steps.plan.plan_type}
                    </p>
                  </div>
                )}

                {/* Execution Results */}
                {message.intermediate_steps.execution_result && (
                  <div>
                    <p className="font-semibold text-gray-700">Execution:</p>
                    <pre className="text-gray-600 overflow-x-auto">
                      {JSON.stringify(message.intermediate_steps.execution_result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div className={`text-xs mt-2 ${isUser ? 'text-blue-100' : 'text-gray-500'}`}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default Message;

// Made with Bob
