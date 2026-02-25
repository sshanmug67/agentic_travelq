// frontend/src/components/common/AirportAutocomplete.tsx
//
// Drop-in autocomplete for airport selection in TripSummaryBar.
// Searches by IATA code, city name, airport name, and country.
// Displays: "City (CODE)" — stores the IATA code as value.

import React, { useState, useRef, useEffect, useCallback } from 'react';
import airports, { Airport, CITY_ALIASES } from '../../data/airports';

interface AirportAutocompleteProps {
  value: string;                          // Current IATA code or city name
  onChange: (value: string) => void;      // Called with "City (CODE)" display string
  onCodeChange?: (code: string) => void;  // Called with just the IATA code
  onConfirm: () => void;                  // Save / ✓ button
  onCancel: () => void;                   // Cancel / ✕ button
  placeholder?: string;
  autoFocus?: boolean;
  className?: string;                     // Additional classes for the wrapper
}

// ─── Scoring function: higher = better match ────────────────────────────
function scoreMatch(airport: Airport, query: string): number {
  const q = query.toLowerCase().trim();
  const code = airport.code.toLowerCase();
  const city = airport.city.toLowerCase();
  const name = airport.name.toLowerCase();
  const country = airport.country.toLowerCase();

  // Exact IATA code match → highest priority
  if (code === q) return 1000;

  // Code starts with query
  if (code.startsWith(q)) return 800;

  // Exact city match
  if (city === q) return 700;

  // City starts with query
  if (city.startsWith(q)) return 600;

  // City word starts with query (e.g., "fort" matches "Fort Lauderdale")
  const cityWords = city.split(/[\s\-\/]+/);
  if (cityWords.some(w => w.startsWith(q))) return 500;

  // Airport name contains query
  if (name.includes(q)) return 300;

  // Country code match
  if (country === q) return 200;

  // Partial code match anywhere
  if (code.includes(q)) return 150;

  // Partial city match anywhere
  if (city.includes(q)) return 100;

  return 0;
}

// ─── Search airports ────────────────────────────────────────────────────
function searchAirports(query: string, maxResults = 8): Airport[] {
  if (!query || query.trim().length === 0) return [];

  let q = query.toLowerCase().trim();

  // Resolve aliases: "nyc" → "new york", "sf" → "san francisco"
  if (CITY_ALIASES[q]) {
    q = CITY_ALIASES[q].toLowerCase();
  }

  const scored = airports
    .map(airport => ({ airport, score: scoreMatch(airport, q) }))
    .filter(item => item.score > 0)
    .sort((a, b) => {
      // Primary: score descending
      if (b.score !== a.score) return b.score - a.score;
      // Secondary: shorter city name first (prefer "Miami" over "Miami Beach")
      return a.airport.city.length - b.airport.city.length;
    });

  return scored.slice(0, maxResults).map(item => item.airport);
}

// ─── Format display string ──────────────────────────────────────────────
function formatAirport(airport: Airport): string {
  return `${airport.city} (${airport.code})`;
}

function formatDropdownItem(airport: Airport): { primary: string; secondary: string } {
  return {
    primary: `${airport.city} (${airport.code})`,
    secondary: airport.name,
  };
}

// ─── Component ──────────────────────────────────────────────────────────
const AirportAutocomplete: React.FC<AirportAutocompleteProps> = ({
  value,
  onChange,
  onCodeChange,
  onConfirm,
  onCancel,
  placeholder = 'City or airport code',
  autoFocus = false,
  className = '',
}) => {
  const [inputValue, setInputValue] = useState(value);
  const [results, setResults] = useState<Airport[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Initialize: if value is an IATA code, resolve it to display format
  useEffect(() => {
    if (value && value.length === 3 && value === value.toUpperCase()) {
      const found = airports.find(a => a.code === value);
      if (found) {
        setInputValue(formatAirport(found));
        return;
      }
    }
    setInputValue(value);
  }, []); // Only on mount

  // Search when input changes
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);

    if (val.trim().length >= 1) {
      const found = searchAirports(val);
      setResults(found);
      setIsOpen(found.length > 0);
      setActiveIndex(-1);
    } else {
      setResults([]);
      setIsOpen(false);
    }
  }, []);

  // Select an airport from dropdown
  const selectAirport = useCallback((airport: Airport) => {
    const display = formatAirport(airport);
    setInputValue(display);
    onChange(display);
    onCodeChange?.(airport.code);
    setIsOpen(false);
    setResults([]);
    setActiveIndex(-1);
    inputRef.current?.focus();
  }, [onChange, onCodeChange]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!isOpen || results.length === 0) {
      if (e.key === 'Enter') {
        e.preventDefault();
        onConfirm();
      } else if (e.key === 'Escape') {
        onCancel();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex(prev => (prev < results.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex(prev => (prev > 0 ? prev - 1 : results.length - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < results.length) {
          selectAirport(results[activeIndex]);
        } else if (results.length > 0) {
          selectAirport(results[0]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setActiveIndex(-1);
        break;
      case 'Tab':
        if (results.length > 0) {
          e.preventDefault();
          const idx = activeIndex >= 0 ? activeIndex : 0;
          selectAirport(results[idx]);
        }
        break;
    }
  }, [isOpen, results, activeIndex, selectAirport, onConfirm, onCancel]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex >= 0 && dropdownRef.current) {
      const items = dropdownRef.current.querySelectorAll('[data-airport-item]');
      items[activeIndex]?.scrollIntoView({ block: 'nearest' });
    }
  }, [activeIndex]);

  return (
    <div ref={wrapperRef} className={`relative ${className}`}>
      {/* ─── Input row with ✓ / ✕ buttons ─── */}
      <div className="flex items-center gap-2 bg-white/20 rounded-lg px-2 py-0.5">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (inputValue.trim().length >= 1) {
              const found = searchAirports(inputValue);
              if (found.length > 0) {
                setResults(found);
                setIsOpen(true);
              }
            }
          }}
          className="bg-transparent border-none outline-none text-white placeholder-white/60 w-48 text-sm"
          placeholder={placeholder}
          autoFocus={autoFocus}
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `airport-option-${activeIndex}` : undefined}
        />
        <button
          onClick={onConfirm}
          className="text-green-300 hover:text-green-100 text-sm"
          title="Save"
        >
          ✓
        </button>
        <button
          onClick={onCancel}
          className="text-red-300 hover:text-red-100 text-sm"
          title="Cancel"
        >
          ✕
        </button>
      </div>

      {/* ─── Dropdown ─── */}
      {isOpen && results.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 top-full left-0 mt-1 w-72 max-h-60 overflow-y-auto
                     bg-gray-900 border border-gray-700 rounded-lg shadow-xl"
          role="listbox"
        >
          {results.map((airport, index) => {
            const { primary, secondary } = formatDropdownItem(airport);
            const isActive = index === activeIndex;

            return (
              <div
                key={`${airport.code}-${index}`}
                id={`airport-option-${index}`}
                data-airport-item
                role="option"
                aria-selected={isActive}
                className={`
                  px-3 py-2 cursor-pointer transition-colors duration-75
                  ${isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-200 hover:bg-gray-800'
                  }
                `}
                onClick={() => selectAirport(airport)}
                onMouseEnter={() => setActiveIndex(index)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{primary}</span>
                  <span className={`
                    text-xs font-mono px-1.5 py-0.5 rounded
                    ${isActive ? 'bg-blue-500/50 text-blue-100' : 'bg-gray-800 text-gray-400'}
                  `}>
                    {airport.code}
                  </span>
                </div>
                <div className={`text-xs mt-0.5 truncate ${isActive ? 'text-blue-200' : 'text-gray-500'}`}>
                  {secondary}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AirportAutocomplete;
