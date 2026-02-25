// frontend/src/components/common/NaturalLanguageInput.tsx
//
// v3 — Glass card matching TravelQ v3 mockup:
//   - Glass card: rgba(255,255,255,0.85) + blur(20px), rounded-20
//   - No heavy header bar — just inline icon + title
//   - Lighter textarea: rounded-14, subtle border
//   - Suggestion chips as individual rounded pills with hover-to-purple effect
//   - Shorter example prompts matching mockup

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
    'Find cheaper flights',
    'Italian restaurants near hotel',
    'Museums within walking distance',
    'Direct flights only',
  ];

  const handleSubmit = async () => {
    if (!value.trim() || isProcessing) return;
    await onSubmit(value);
  };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      borderRadius: 20, padding: 22, height: '100%', display: 'flex', flexDirection: 'column',
      border: '1px solid rgba(139,92,246,0.08)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    }}>
      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 18 }}>💬</span>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: '#1E293B', margin: 0 }}>Refine Your Search</h3>
      </div>

      {/* Textarea */}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        placeholder='e.g. "Add Italian restaurants" or "Direct flights only"'
        disabled={isProcessing}
        style={{
          width: '100%', height: 72, padding: 12, borderRadius: 14,
          border: '2px solid #F1F5F9', fontSize: 13, resize: 'none', outline: 'none',
          color: '#475569', background: 'rgba(241,245,249,0.5)', boxSizing: 'border-box',
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => { e.currentTarget.style.borderColor = '#C4B5FD'; }}
        onBlur={(e) => { e.currentTarget.style.borderColor = '#F1F5F9'; }}
      />

      {/* Suggestion chips */}
      {value === '' && !isProcessing && (
        <div style={{ marginTop: 14, flex: 1 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: '#8B5CF6' }}>💡 Try asking:</span>
          <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 5 }}>
            {examplePrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => onChange(prompt)}
                style={{
                  padding: '7px 12px', borderRadius: 10, fontSize: 12, fontWeight: 500,
                  color: '#6D28D9', background: 'rgba(139,92,246,0.06)',
                  border: '1px solid rgba(139,92,246,0.1)',
                  cursor: 'pointer', textAlign: 'left',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#8B5CF6';
                  e.currentTarget.style.color = 'white';
                  e.currentTarget.style.transform = 'scale(1.02)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(139,92,246,0.06)';
                  e.currentTarget.style.color = '#6D28D9';
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
