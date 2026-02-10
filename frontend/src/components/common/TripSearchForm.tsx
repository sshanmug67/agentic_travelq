/**
 * Enhanced Trip Search Form with Comprehensive Preferences
 * Location: frontend/src/components/common/TripSearchForm.tsx
 */
import React, { useState } from 'react';
import { Search, ChevronDown, ChevronUp } from 'lucide-react';
import type { 
  TripRequest, 
  TripPreset, 
  FlightPreferences, 
  HotelPreferences,
  ActivityPreferences,
  BudgetConstraints 
} from '@/types/trip';
import { 
  TRIP_PRESETS, 
  getDefaultFlightPrefs, 
  getDefaultHotelPrefs,
  getDefaultActivityPrefs,
  getDefaultBudget 
} from '@/types/trip';

interface TripSearchFormProps {
  onSubmit: (request: TripRequest) => void | Promise<void>;  // ✅ Changed from onSearch
  loading?: boolean;
}

export const TripSearchForm: React.FC<TripSearchFormProps> = ({ 
  onSubmit,  // ✅ Changed from onSearch
  loading = false 
}) => {
  const [preset, setPreset] = useState<TripPreset>('default');
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const [formData, setFormData] = useState<TripRequest>({
    origin: '',
    destination: '',
    departure_date: '',
    return_date: '',
    num_travelers: 1,
    trip_purpose: 'leisure',
    flight_prefs: getDefaultFlightPrefs('default'),
    hotel_prefs: getDefaultHotelPrefs('default'),
    activity_prefs: getDefaultActivityPrefs('default'),
    transport_prefs: {
      preferred_modes: ['metro', 'walk', 'cab'],
      max_walk_distance: 1.0,
      comfort_level: 'moderate',
    },
    budget: getDefaultBudget('default'),
  });

  const handlePresetChange = (newPreset: TripPreset) => {
    setPreset(newPreset);
    
    // Calculate days for budget
    const days = formData.departure_date && formData.return_date
      ? Math.ceil((new Date(formData.return_date).getTime() - new Date(formData.departure_date).getTime()) / (1000 * 60 * 60 * 24))
      : 7;
    
    setFormData({
      ...formData,
      flight_prefs: getDefaultFlightPrefs(newPreset),
      hotel_prefs: getDefaultHotelPrefs(newPreset),
      activity_prefs: getDefaultActivityPrefs(newPreset),
      budget: getDefaultBudget(newPreset, days),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {  // ✅ Made async
    e.preventDefault();
    await onSubmit(formData);  // ✅ Changed from onSearch, added await
  };

  const handleBasicChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: name === 'num_travelers' ? parseInt(value) : value,
    });
  };

  const handleFlightChange = (field: keyof FlightPreferences, value: any) => {
    setFormData({
      ...formData,
      flight_prefs: {
        ...formData.flight_prefs,
        [field]: value,
      },
    });
  };

  const handleHotelChange = (field: keyof HotelPreferences, value: any) => {
    setFormData({
      ...formData,
      hotel_prefs: {
        ...formData.hotel_prefs,
        [field]: value,
      },
    });
  };

  const handleBudgetChange = (field: keyof BudgetConstraints, value: number) => {
    setFormData({
      ...formData,
      budget: {
        ...formData.budget,
        [field]: value,
      },
    });
  };

  const handleInterestsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const interests = e.target.value.split(',').map(i => i.trim()).filter(Boolean);
    setFormData({
      ...formData,
      activity_prefs: {
        ...formData.activity_prefs,
        interests,
      },
    });
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">Plan Your Trip</h2>
      
      {/* Preset Selection */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Trip Style
        </label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {TRIP_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => handlePresetChange(p.id)}
              className={`p-3 rounded-lg border-2 text-sm transition-colors ${
                preset === p.id
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="font-semibold">{p.name}</div>
              <div className="text-xs text-gray-600 mt-1">{p.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Basic Trip Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Origin City *
          </label>
          <input
            type="text"
            name="origin"
            value={formData.origin}
            onChange={handleBasicChange}
            placeholder="e.g., New York, NY"
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Destination *
          </label>
          <input
            type="text"
            name="destination"
            value={formData.destination}
            onChange={handleBasicChange}
            placeholder="e.g., Tokyo, Japan"
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Departure Date *
          </label>
          <input
            type="date"
            name="departure_date"
            value={formData.departure_date}
            onChange={handleBasicChange}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Return Date *
          </label>
          <input
            type="date"
            name="return_date"
            value={formData.return_date}
            onChange={handleBasicChange}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Number of Travelers *
          </label>
          <input
            type="number"
            name="num_travelers"
            value={formData.num_travelers}
            onChange={handleBasicChange}
            min="1"
            max="10"
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Trip Purpose
          </label>
          <select
            name="trip_purpose"
            value={formData.trip_purpose}
            onChange={handleBasicChange}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="leisure">Leisure</option>
            <option value="business">Business</option>
            <option value="adventure">Adventure</option>
            <option value="relaxation">Relaxation</option>
          </select>
        </div>
      </div>

      {/* Budget */}
      <div className="mb-6 p-4 bg-green-50 rounded-lg">
        <h3 className="font-semibold text-gray-800 mb-3">Budget</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-700 mb-1">Total Budget ($)</label>
            <input
              type="number"
              value={formData.budget.total_budget}
              onChange={(e) => handleBudgetChange('total_budget', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Flights ($)</label>
            <input
              type="number"
              value={formData.budget.flight_budget}
              onChange={(e) => handleBudgetChange('flight_budget', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Hotel/Night ($)</label>
            <input
              type="number"
              value={formData.budget.hotel_budget_per_night}
              onChange={(e) => handleBudgetChange('hotel_budget_per_night', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
        </div>
      </div>

      {/* Interests */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Interests (comma-separated)
        </label>
        <input
          type="text"
          value={formData.activity_prefs.interests.join(', ')}
          onChange={handleInterestsChange}
          placeholder="e.g., food, museums, nightlife, shopping"
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Advanced Options Toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-4"
      >
        {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        <span className="font-medium">Advanced Options</span>
      </button>

      {/* Advanced Options */}
      {showAdvanced && (
        <div className="space-y-6 mb-6 p-4 bg-gray-50 rounded-lg">
          {/* Flight Preferences */}
          <div>
            <h3 className="font-semibold text-gray-800 mb-3">Flight Preferences</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">Max Stops</label>
                <select
                  value={formData.flight_prefs.max_stops}
                  onChange={(e) => handleFlightChange('max_stops', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="0">Direct only</option>
                  <option value="1">Up to 1 stop</option>
                  <option value="2">Up to 2 stops</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">Cabin Class</label>
                <select
                  value={formData.flight_prefs.cabin_class}
                  onChange={(e) => handleFlightChange('cabin_class', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="economy">Economy</option>
                  <option value="premium_economy">Premium Economy</option>
                  <option value="business">Business</option>
                  <option value="first">First Class</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">Time Preference</label>
                <select
                  value={formData.flight_prefs.time_preference}
                  onChange={(e) => handleFlightChange('time_preference', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="flexible">Flexible</option>
                  <option value="morning">Morning</option>
                  <option value="afternoon">Afternoon</option>
                  <option value="evening">Evening</option>
                  <option value="night">Red-eye</option>
                </select>
              </div>
            </div>
          </div>

          {/* Hotel Preferences */}
          <div>
            <h3 className="font-semibold text-gray-800 mb-3">Hotel Preferences</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">Minimum Rating</label>
                <select
                  value={formData.hotel_prefs.min_rating}
                  onChange={(e) => handleHotelChange('min_rating', parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="3">3+ stars</option>
                  <option value="3.5">3.5+ stars</option>
                  <option value="4">4+ stars</option>
                  <option value="4.5">4.5+ stars</option>
                  <option value="5">5 stars</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">Location</label>
                <select
                  value={formData.hotel_prefs.preferred_location}
                  onChange={(e) => handleHotelChange('preferred_location', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="city_center">City Center</option>
                  <option value="near_attractions">Near Attractions</option>
                  <option value="quiet_area">Quiet Area</option>
                </select>
              </div>
            </div>
          </div>

          {/* Activity Preferences */}
          <div>
            <h3 className="font-semibold text-gray-800 mb-3">Activity Preferences</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">Pace</label>
                <select
                  value={formData.activity_prefs.pace}
                  onChange={(e) => setFormData({
                    ...formData,
                    activity_prefs: { ...formData.activity_prefs, pace: e.target.value as any }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="relaxed">Relaxed</option>
                  <option value="moderate">Moderate</option>
                  <option value="fast-paced">Fast-paced</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">Daily Activity Hours</label>
                <input
                  type="number"
                  value={formData.activity_prefs.entertainment_hours_per_day}
                  onChange={(e) => setFormData({
                    ...formData,
                    activity_prefs: { ...formData.activity_prefs, entertainment_hours_per_day: parseInt(e.target.value) }
                  })}
                  min="2"
                  max="12"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <Search className="w-5 h-5" />
        {loading ? 'Planning Your Trip...' : 'Plan My Trip'}
      </button>

      <p className="text-xs text-gray-500 mt-3 text-center">
        AI will coordinate flights, hotels, activities, and weather to create your perfect itinerary
      </p>
    </form>
  );
};