// frontend/src/pages/Dashboard.tsx

import React, { useState } from 'react';
import { ItinerarySidebar } from '../components/itinerary/ItinerarySidebar';
import { NaturalLanguageInput } from '../components/common/NaturalLanguageInput';
import { PreferencesPanel } from '../components/common/PreferencesPanel';
import { TripSummaryBar } from '../components/common/TripSummaryBar';
import { useTripData } from '../hooks/useTripData';
import { useItinerary } from '../hooks/useItinerary';
import { tripApi } from '../services/api';

export const Dashboard: React.FC = () => {
  const { tripData, preferences, updatePreferences, setFlights, setHotels, setRestaurants, setActivities } = useTripData();
  const { flight, hotel, restaurants, activities } = useItinerary();
  
  const [naturalLanguageRequest, setNaturalLanguageRequest] = useState('');
  const [isPlanning, setIsPlanning] = useState(false);
  const [lastSearchMessage, setLastSearchMessage] = useState('');

  const handlePlanTrip = async (userRequest: string) => {
    // Validation
    if (!tripData.destination) {
      alert('Please enter a destination');
      return;
    }
    if (!tripData.startDate || !tripData.endDate) {
      alert('Please enter travel dates');
      return;
    }

    setIsPlanning(true);
    setLastSearchMessage('');
    
    try {
      // Send ALL data in ONE request
      const response = await tripApi.planTrip({
        tripId: tripData.id,
        userRequest: userRequest, // Natural language input (highest priority)
        tripDetails: {
          origin: tripData.origin,
          destination: tripData.destination,
          startDate: tripData.startDate,
          endDate: tripData.endDate,
          travelers: tripData.travelers,
          budget: tripData.totalBudget,
        },
        preferences: preferences, // Preferences (medium priority)
        currentItinerary: {
          flight: flight,
          hotel: hotel,
          restaurants: restaurants,
          activities: activities,
        },
      });

      // Update all options with results
      setFlights(response.results.flights || []);
      setHotels(response.results.hotels || []);
      setRestaurants(response.results.restaurants || []);
      setActivities(response.results.activities || []);

      // Show success message
      setLastSearchMessage(response.message || 'Trip planning complete!');
      
      // Clear natural language input after successful search
      setNaturalLanguageRequest('');

    } catch (error: any) {
      console.error('Failed to plan trip:', error);
      alert('Failed to plan trip: ' + (error.message || 'Unknown error'));
    } finally {
      setIsPlanning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      {/* Header */}
      <div className="bg-white shadow-md sticky top-0 z-40">
        <div className="px-6 py-3 flex items-center justify-between">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
            TravelQ
          </h1>
          <div className="flex items-center gap-4">
            <button className="text-gray-600 hover:text-gray-800">🔍</button>
            <button className="text-gray-600 hover:text-gray-800">🔔</button>
            <button className="text-gray-600 hover:text-gray-800">👤 Profile</button>
            <button className="text-gray-600 hover:text-gray-800">⚙️</button>
          </div>
        </div>
      </div>

      {/* Trip Summary Bar */}
      <TripSummaryBar />

      {/* Natural Language Input & Preferences */}
      <div className="px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Left: Natural Language Input */}
          <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
            <NaturalLanguageInput 
              value={naturalLanguageRequest}
              onChange={setNaturalLanguageRequest}
              onSubmit={handlePlanTrip}
              isProcessing={isPlanning}
            />
          </div>

          {/* Right: Preferences Panel */}
          <PreferencesPanel preferences={preferences} onUpdate={updatePreferences} />
        </div>

        {/* Big "Plan My Trip" Button */}
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => handlePlanTrip(naturalLanguageRequest)}
            disabled={isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate}
            className="w-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-600 hover:from-purple-700 hover:via-pink-700 hover:to-orange-700 disabled:from-gray-400 disabled:via-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-bold text-xl py-4 px-8 rounded-xl shadow-2xl transition-all duration-300 transform hover:scale-105 disabled:hover:scale-100 flex items-center justify-center gap-3"
          >
            {isPlanning ? (
              <>
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                Planning Your Trip...
              </>
            ) : (
              <>
                🚀 Plan My Trip
              </>
            )}
          </button>
          
          {/* Last Search Message */}
          {lastSearchMessage && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg text-center">
              <p className="text-green-800 font-semibold">✓ {lastSearchMessage}</p>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="px-6 pb-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* LEFT: Options (2/3 width) */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-200">
              <div className="text-center py-20">
                <div className="text-6xl mb-4">🚀</div>
                <h2 className="text-2xl font-bold text-gray-800 mb-2">
                  Ready to Plan Your Trip?
                </h2>
                <p className="text-gray-600 mb-6">
                  Fill in your trip details above and click "Plan My Trip" to see options!
                </p>
                <div className="text-sm text-gray-500">
                  Flight, Hotel, Restaurant, and Activity options will appear here.
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: Itinerary Sidebar (1/3 width) */}
          <div className="lg:col-span-1">
            <ItinerarySidebar />
          </div>
        </div>
      </div>
    </div>
  );
};