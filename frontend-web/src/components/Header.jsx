import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Zap, Store, ShoppingBag, Database, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';

export function Header({ activeTab, onTabChange }) {
  const [health, setHealth] = useState(null);
  const [checking, setChecking] = useState(false);

  const checkHealth = async () => {
    setChecking(true);
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth({ status: 'offline' });
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = health && health.status === 'healthy';

  return (
    <header className="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-slate-800/80 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onTabChange('customer')}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Zap className="w-5 h-5 text-white fill-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-lg text-white tracking-tight">Hyperlocal</span>
              <span className="px-1.5 py-0.5 text-[10px] uppercase font-bold tracking-wider bg-indigo-500/20 text-indigo-400 rounded-md border border-indigo-500/30">
                AI 3km
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium hidden sm:block">
              PostGIS Geospatial Quick-Commerce Engine
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 shadow-inner">
          <button
            onClick={() => onTabChange('customer')}
            className={`flex items-center space-x-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === 'customer'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <ShoppingBag className="w-4 h-4" />
            <span>Customer Portal</span>
          </button>
          <button
            onClick={() => onTabChange('seller')}
            className={`flex items-center space-x-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === 'seller'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Store className="w-4 h-4" />
            <span>Seller Dashboard</span>
          </button>
        </div>

        {/* Backend Engine Health Badge */}
        <div className="hidden lg:flex items-center space-x-2">
          <div
            onClick={checkHealth}
            title="Click to re-ping database health probe"
            className={`cursor-pointer px-3 py-1.5 rounded-full text-xs font-medium border flex items-center space-x-2 transition-all ${
              isHealthy
                ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-400 hover:bg-emerald-900/40'
                : 'bg-rose-950/40 border-rose-500/30 text-rose-400 hover:bg-rose-900/40'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
            <span>
              {isHealthy ? (
                <>PostGIS 3.6 • pgvector 0.8</>
              ) : (
                <>Backend Offline (Port 8000)</>
              )}
            </span>
            <RefreshCw className={`w-3 h-3 opacity-60 ${checking ? 'animate-spin' : ''}`} />
          </div>
        </div>
      </div>
    </header>
  );
}
