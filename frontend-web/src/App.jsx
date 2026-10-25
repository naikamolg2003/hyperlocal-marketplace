import React, { useState } from 'react';
import { Header } from './components/Header';
import { CustomerPortal } from './components/CustomerPortal';
import { SellerDashboard } from './components/SellerDashboard';
import { Database, MapPin, Zap, ExternalLink } from 'lucide-react';

function App() {
  const [activeTab, setActiveTab] = useState('customer');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
      {/* Navigation Header */}
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main View Area */}
      <main className="flex-1">
        {activeTab === 'customer' ? (
          <CustomerPortal />
        ) : (
          <SellerDashboard />
        )}
      </main>

      {/* Modern Engineering Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-300">Hyperlocal Quick-Commerce</span>
            <span>•</span>
            <span>FastAPI Backend + PostGIS 3.6 + pgvector 0.8 + React</span>
          </div>

          <div className="flex items-center space-x-4">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-indigo-400 transition-colors flex items-center space-x-1"
            >
              <span>FastAPI Swagger Docs</span>
              <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href="http://localhost:8000/health"
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-emerald-400 transition-colors flex items-center space-x-1"
            >
              <span>Database Health Probe</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
