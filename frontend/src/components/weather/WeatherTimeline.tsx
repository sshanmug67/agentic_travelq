import React from 'react';
import { Cloud, CloudRain, Sun, Wind } from 'lucide-react';
import type { Weather } from '@/types/trip';
import { Card } from '@/components/common/Card';

interface WeatherTimelineProps {
  forecast: Weather[];
}

export const WeatherTimeline: React.FC<WeatherTimelineProps> = ({ forecast }) => {
  const getWeatherIcon = (description: string) => {
    const desc = description.toLowerCase();
    if (desc.includes('rain')) return <CloudRain className="w-8 h-8 text-blue-500" />;
    if (desc.includes('cloud')) return <Cloud className="w-8 h-8 text-gray-500" />;
    if (desc.includes('sun') || desc.includes('clear')) return <Sun className="w-8 h-8 text-yellow-500" />;
    return <Wind className="w-8 h-8 text-gray-400" />;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <Card title="Weather Forecast">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {forecast.map((day, index) => (
          <div
            key={index}
            className="flex flex-col items-center p-4 border rounded-lg hover:bg-gray-50 transition-colors"
          >
            <p className="text-sm font-medium text-gray-600 mb-2">
              {formatDate(day.date)}
            </p>
            
            <div className="my-3">
              {getWeatherIcon(day.description)}
            </div>

            <div className="text-center">
              <p className="text-2xl font-bold">
                {Math.round(day.temperature)}°C
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {Math.round(day.temp_min)}° / {Math.round(day.temp_max)}°
              </p>
            </div>

            <p className="text-xs text-gray-600 mt-2 text-center capitalize">
              {day.description}
            </p>

            <div className="mt-2 flex gap-2 text-xs text-gray-500">
              <span>💧 {day.humidity}%</span>
              <span>💨 {day.wind_speed}m/s</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
