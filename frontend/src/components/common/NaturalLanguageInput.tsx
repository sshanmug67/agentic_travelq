// frontend/src/components/common/NaturalLanguageInput.tsx
//
// v2: Compact header matching Agent Feed / Preferences panel height

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
    <div className="flex flex-col h-full">
      {/* Compact header — matches Agent Feed / Preferences header height */}
      <div className="px-4 py-2.5 border-b-2 border-gray-200 flex items-center gap-2 flex-shrink-0 bg-gradient-to-r from-gray-50 to-white">
        <span className="text-base">💬</span>
        <span className="text-[15px] font-bold text-gray-800">Refine Your Search</span>
        <span className="text-[12px] text-gray-400 font-medium">(Optional)</span>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-3 overflow-y-auto">
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
            placeholder='e.g., "Add Italian restaurants", "Direct flights only"'
            className="w-full p-3 border-2 border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200 resize-none transition-all text-[14px]"
            rows={4}
            disabled={isProcessing}
          />
        </div>

        {/* Example Prompts */}
        {value === '' && !isProcessing && (
          <div className="bg-purple-50 p-3 rounded-lg border border-purple-200">
            <p className="text-[13px] font-semibold text-purple-900 mb-2">💡 Try asking:</p>
            <div className="space-y-0.5">
              {examplePrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => onChange(prompt)}
                  className="block text-left w-full text-[13px] text-purple-700 hover:text-purple-900 hover:bg-purple-100 px-2 py-1 rounded transition-colors"
                >
                  • {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        <p className="text-[11px] text-gray-500 italic">
          💡 Tip: Leave empty to use only trip details and preferences, or add specific requests to refine your search.
        </p>
      </div>
    </div>
  );
};
