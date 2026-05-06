import React from 'react';
import Chat from './components/Chat';
import AnalyticsDashboard from './components/analytics/AnalyticsDashboard';
import './index.css';

function App() {
  const isAnalytics = window.location.pathname.startsWith('/analytics');

  return (
    <div className="min-h-screen">
      {isAnalytics ? <AnalyticsDashboard /> : <Chat />}
    </div>
  );
}

export default App;

// Made with Bob
