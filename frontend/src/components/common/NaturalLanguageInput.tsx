// frontend/src/components/common/NaturalLanguageInput.tsx

import React from 'react';

interface NaturalLanguageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (request: string) => Promise<void>;
  isProcessing: boolean;
}

export const NaturalLanguageInput: React.FC<NaturalLanguageInputProps> = ({
  value,
  onChange,
  onSubmit,
  isProcessing,
}) => {
  const examplePrompts = [
    "Find cheaper flights",
    "Add Italian restaurants near my hotel",
    "Show museums within walking distance",
    "I prefer direct flights only",
  ];

  const handleSubmit = async () => {
    if (!value.trim() || isProcessing) return;
    await onSubmit(value);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-lg font-bold">💬 Refine Your Search (Optional):</h3>
      </div>

      {/* Input Box */}
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder='e.g., "Find cheaper flights", "Add Italian restaurants", "Direct flights only"'
          className="w-full p-4 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200 resize-none transition-all"
          rows={4}
          disabled={isProcessing}
        />
      </div>

      {/* Example Prompts */}
      {value === '' && !isProcessing && (
        <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
          <p className="text-sm font-semibold text-purple-900 mb-2">💡 Try asking:</p>
          <div className="space-y-1">
            {examplePrompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => onChange(prompt)}
                className="block text-left w-full text-sm text-purple-700 hover:text-purple-900 hover:bg-purple-100 px-2 py-1 rounded transition-colors"
              >
                • {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 italic">
        💡 Tip: Leave empty to use only trip details and preferences, or add specific requests to refine your search.
      </p>
    </div>
  );
};