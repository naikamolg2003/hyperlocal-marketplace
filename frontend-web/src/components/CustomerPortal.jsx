import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { CustomerRequirementQuotesView } from './CustomerRequirementQuotesView';
import {
  Sparkles,
  MapPin,
  Send,
  Navigation,
  CheckCircle2,
  Clock,
  Store,
  Phone,
  AlertCircle,
  Package,
  Layers,
  ArrowRight,
  ShieldCheck,
  ChevronDown,
  CreditCard,
  Check,
  Receipt,
  Lock,
  RefreshCw,
  Zap,
  ShoppingBag,
  IndianRupee,
  X,
  CheckCircle,
  Truck,
} from 'lucide-react';

const LOCATION_PRESETS = [
  {
    name: 'Wakad, Pune',
    badge: 'Preset',
    lat: 18.5987,
    lon: 73.7660,
    desc: 'Wakad Bridge, Pimpri-Chinchwad, Pune',
  },
  {
    name: 'Indiranagar, Bangalore',
    badge: 'Live Demo',
    lat: 12.9745,
    lon: 77.6350,
    desc: 'Defence Colony, 100ft Road (Active Stores)',
  },
];

const SUGGESTED_PROMPTS = [
  'Need 2 packets of milk and some fresh cilantro delivered quickly',
  '1 loaf of artisanal sourdough bread and 6 farm fresh brown eggs',
  'Need 1kg whole wheat atta and cold pressed cooking oil',
  '2 packets of organic dahi and greek yogurt before evening',
];

export function CustomerPortal() {
  const [prompt, setPrompt] = useState('Need 2 packets of milk and some fresh cilantro delivered quickly');
  const [selectedPreset, setSelectedPreset] = useState(LOCATION_PRESETS[1]); // Default Indiranagar with live stores
  const [customLat, setCustomLat] = useState(LOCATION_PRESETS[1].lat);
  const [customLon, setCustomLon] = useState(LOCATION_PRESETS[1].lon);
  const [customerName, setCustomerName] = useState('Priya Sharma');
  const [radiusKm, setRadiusKm] = useState(3.0);
  const [showLocationSettings, setShowLocationSettings] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // Quotes and Payment Loop State
  const [quotes, setQuotes] = useState([]);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [activePaymentQuote, setActivePaymentQuote] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('upi');
  const [submittingPayment, setSubmittingPayment] = useState(false);
  const [paymentReceipt, setPaymentReceipt] = useState(null);
  const [simulatingQuote, setSimulatingQuote] = useState(false);

  const handlePresetSelect = (preset) => {
    setSelectedPreset(preset);
    setCustomLat(preset.lat);
    setCustomLon(preset.lon);
  };

  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(4));
        const lon = parseFloat(pos.coords.longitude.toFixed(4));
        setCustomLat(lat);
        setCustomLon(lon);
        setSelectedPreset({
          name: 'My Current Location',
          badge: 'GPS',
          lat,
          lon,
          desc: 'Obtained via Device GPS',
        });
      },
      (err) => {
        alert(`Location permission denied or unavailable: ${err.message}`);
      }
    );
  };

  // Fetch Quotes for requirement
  const fetchQuotes = async (requirementId) => {
    if (!requirementId) return;
    setLoadingQuotes(true);
    try {
      const data = await api.getRequirementQuotes(requirementId);
      setQuotes(data.quotes || []);
    } catch (err) {
      console.warn('Could not fetch quotes yet:', err.message);
    } finally {
      setLoadingQuotes(false);
    }
  };

  // Poll for quotes while requirement is open
  useEffect(() => {
    if (!result?.requirement_id) return;

    fetchQuotes(result.requirement_id);
    const interval = setInterval(() => {
      fetchQuotes(result.requirement_id);
    }, 4000);

    return () => clearInterval(interval);
  }, [result?.requirement_id]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setQuotes([]);
    setPaymentReceipt(null);

    try {
      const payload = {
        raw_text: prompt.trim(),
        latitude: parseFloat(customLat),
        longitude: parseFloat(customLon),
        customer_name: customerName || 'Guest Customer',
        radius_km: parseFloat(radiusKm),
      };

      const response = await api.submitRequirement(payload);
      setResult(response);
    } catch (err) {
      setError(err.message || 'Failed to submit requirement. Please check backend connection.');
    } finally {
      setLoading(false);
    }
  };

  // Quick Action: Simulate Instant Merchant Quote (for frictionless testing)
  const handleSimulateQuote = async () => {
    if (!result?.requirement_id) return;
    setSimulatingQuote(true);

    try {
      const seller = result.matching_summary?.sellers?.[0] || {
        seller_id: 'e3b0c442-98fc-1c14-9afb-4c7ac2206123',
        name: 'Neighborhood Fresh Mart',
      };

      const items = result.parsed_requirement?.items || [];
      const itemizedItems = items.map((it, idx) => ({
        item_name: it.product_name,
        quantity: it.quantity || '1',
        price: 35.0 + idx * 15.0,
        total: 35.0 + idx * 15.0,
      }));

      const total = itemizedItems.reduce((acc, curr) => acc + curr.total, 0) || 120.0;

      await api.submitOrderQuote({
        requirement_id: result.requirement_id,
        seller_id: seller.seller_id,
        quote_amount: total,
        delivery_estimate_minutes: 15,
        itemized_items: itemizedItems,
        notes: 'Simulated merchant response: All items verified in stock and packed fresh.',
      });

      await fetchQuotes(result.requirement_id);
    } catch (err) {
      alert(`Simulation failed: ${err.message}`);
    } finally {
      setSimulatingQuote(false);
    }
  };

  // Open Checkout Modal
  const handleOpenPayment = (quote) => {
    setActivePaymentQuote(quote);
    setPaymentMethod('upi');
  };

  // Settle Order with Escrow
  const handleConfirmPayment = async () => {
    if (!activePaymentQuote) return;
    setSubmittingPayment(true);

    try {
      const txnRef = `TXN_ESCROW_${Date.now().toString(36).toUpperCase()}_${Math.floor(1000 + Math.random() * 9000)}`;
      const settlement = await api.payAndSettleOrder(activePaymentQuote.id, {
        payment_method: paymentMethod,
        transaction_ref: txnRef,
      });

      setPaymentReceipt({
        ...settlement,
        quote: activePaymentQuote,
        method: paymentMethod,
      });

      setActivePaymentQuote(null);
      await fetchQuotes(result.requirement_id);
    } catch (err) {
      alert(`Payment failed: ${err.message}`);
    } finally {
      setSubmittingPayment(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Hero Headline */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold mb-3">
          <Sparkles className="w-3.5 h-3.5" />
          <span>AI Natural Language • 3 km PostGIS Spherical Radius</span>
        </div>
        <h1 className="text-3xl sm:text-5xl font-black text-white tracking-tight mb-3">
          What do you need today?
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base font-normal">
          Type your grocery or household request in plain English. Our AI parses items, urgency & categories,
          broadcasting your order strictly to local merchants within a 3 km perimeter.
        </p>
      </div>

      {/* Main Input Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-4 sm:p-6 shadow-2xl backdrop-blur-xl relative overflow-hidden mb-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

        <form onSubmit={handleSubmit} className="relative z-10">
          {/* Natural Language Prompt Area */}
          <div className="relative mb-4">
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Type anything... e.g., 'Need 2 packets of milk and fresh cilantro delivered quickly'"
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-2xl p-4 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 text-base sm:text-lg transition-all resize-none shadow-inner"
            />
          </div>

          {/* Prompt Suggestions */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_PROMPTS.map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setPrompt(sample)}
                  className="text-xs bg-slate-800/60 hover:bg-slate-700/80 text-slate-300 hover:text-white px-3 py-1.5 rounded-xl border border-slate-700/60 transition-colors text-left"
                >
                  {sample}
                </button>
              ))}
            </div>
          </div>

          {/* Location & Radius Control Bar */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-2xl p-3 mb-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              {/* Presets */}
              <div className="flex items-center space-x-2 flex-wrap">
                <span className="text-xs font-medium text-slate-400 flex items-center space-x-1">
                  <MapPin className="w-3.5 h-3.5 text-indigo-400" />
                  <span>GPS Pin:</span>
                </span>
                {LOCATION_PRESETS.map((loc) => {
                  const isSelected = selectedPreset.name === loc.name;
                  return (
                    <button
                      key={loc.name}
                      type="button"
                      onClick={() => handlePresetSelect(loc)}
                      className={`text-xs px-2.5 py-1 rounded-lg font-medium border transition-all ${
                        isSelected
                          ? 'bg-indigo-600/30 border-indigo-500 text-indigo-300 font-semibold shadow-sm'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {loc.name}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={handleUseCurrentLocation}
                  className="text-xs px-2 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 flex items-center space-x-1"
                >
                  <Navigation className="w-3 h-3" />
                  <span>Device GPS</span>
                </button>
              </div>

              {/* Radius & Coordinate Details Toggle */}
              <button
                type="button"
                onClick={() => setShowLocationSettings(!showLocationSettings)}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center space-x-1 self-end sm:self-auto"
              >
                <span>Lat: {customLat}, Lon: {customLon} ({radiusKm} km)</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showLocationSettings ? 'rotate-180' : ''}`} />
              </button>
            </div>

            {/* Expandable Coordinate & Radius Customization */}
            {showLocationSettings && (
              <div className="mt-3 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">Customer Name</label>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customLat}
                    onChange={(e) => setCustomLat(parseFloat(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customLon}
                    onChange={(e) => setCustomLon(parseFloat(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Radius (km)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    max="20"
                    value={radiusKm}
                    onChange={(e) => setRadiusKm(parseFloat(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="text-xs text-slate-400 flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Strict 3 km PostGIS perimeter • Privacy-preserved customer location</span>
            </div>

            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-emerald-500 hover:from-indigo-500 hover:to-emerald-400 text-white font-bold text-sm shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-all duration-200"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                  <span>AI Parsing & 3 km Matching...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Broadcast to Local Merchants</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-8 p-4 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-rose-300 flex items-start space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-rose-200">Submission Error</p>
            <p className="text-xs text-rose-300 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results View */}
      {result && (
        <div className="space-y-6 animate-fadeIn">
          {/* Notification Confirmation Banner */}
          <div className="p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-emerald-950/60 via-slate-900 to-indigo-950/60 border border-emerald-500/40 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl">
            <div className="flex items-center space-x-3 text-center sm:text-left">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 flex-shrink-0">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">
                  Broadcast Sent to {result.notified_sellers_count} Local Merchants!
                </h3>
                <p className="text-xs text-emerald-300/90 font-medium">
                  Active within {result.matching_summary?.search_radius_km || 3.0} km perimeter of {selectedPreset.name}.
                  Requirement ID: <span className="font-mono text-slate-300">{result.requirement_id.slice(0, 8)}...</span>
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold uppercase tracking-wider">
                Status: {result.status}
              </span>
            </div>
          </div>

          {/* Payment Receipt Banner if settled */}
          {paymentReceipt && (
            <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/80 to-slate-900 border-2 border-emerald-400 shadow-2xl animate-fadeIn">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500 text-slate-950 flex items-center justify-center font-bold">
                    <CheckCircle className="w-7 h-7" />
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-white flex items-center space-x-2">
                      <span>Order Paid & Escrow Settled!</span>
                      <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">
                        {paymentReceipt.status}
                      </span>
                    </h3>
                    <p className="text-xs text-slate-300 mt-0.5">
                      Transaction Ref:{' '}
                      <span className="font-mono text-emerald-400 font-semibold">
                        {paymentReceipt.transaction_ref}
                      </span>
                    </p>
                  </div>
                </div>
                <div className="text-left sm:text-right">
                  <p className="text-2xl font-black text-emerald-400">
                    ₹{paymentReceipt.quote?.total_amount?.toFixed(2)}
                  </p>
                  <p className="text-xs text-slate-400">
                    Method: <span className="uppercase font-semibold text-slate-300">{paymentReceipt.method}</span>
                  </p>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800 text-xs text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span>
                  Merchant: <strong className="text-white">{paymentReceipt.quote?.seller_name || 'Local Merchant'}</strong> •
                  Seller Completed Orders Count: <strong className="text-emerald-400">{paymentReceipt.seller_completed_orders}</strong>
                </span>
                {paymentReceipt.freemium_triggered && (
                  <span className="px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">
                    🔔 Freemium Milestone Reached (2nd Order Limit)
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Live Incoming Quotes & Accept Quote Lifecycle View */}
          <CustomerRequirementQuotesView
            requirement={result}
            onReset={() => {
              setResult(null);
              setQuotes([]);
            }}
          />

          {/* AI Structured Shopping List Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <h3 className="font-bold text-white text-base">AI Structured Shopping List</h3>
              </div>
              <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded-full font-mono">
                Engine: {result.parsed_requirement?.parsing_engine || 'AI'}
              </span>
            </div>

            {/* Extracted Items */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mb-4">
              {result.parsed_requirement?.items?.map((item, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-start space-x-3"
                >
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 flex-shrink-0 mt-0.5">
                    <Package className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-white truncate">{item.product_name}</p>
                    </div>
                    <p className="text-xs text-indigo-300 font-medium">{item.quantity}</p>
                    {item.category && (
                      <span className="inline-block mt-1 text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                        {item.category}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Metadata Badges */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/60 text-xs">
              <span className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 font-semibold uppercase tracking-wider">
                <Clock className="w-3 h-3" />
                <span>Urgency: {result.parsed_requirement?.urgency}</span>
              </span>
              {result.parsed_requirement?.estimated_delivery_time && (
                <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300">
                  Target: {result.parsed_requirement.estimated_delivery_time}
                </span>
              )}
              {result.parsed_requirement?.additional_notes && (
                <span className="px-2.5 py-1 rounded-lg bg-slate-800/60 text-slate-400 italic">
                  "{result.parsed_requirement.additional_notes}"
                </span>
              )}
            </div>
          </div>

          {/* Matched Local Merchants (3 km Radius) */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center space-x-2">
                  <Store className="w-5 h-5 text-emerald-400" />
                  <span>Notified Neighborhood Merchants</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Found {result.matching_summary?.sellers?.length || 0} active stores within 3 km of your GPS location
                </p>
              </div>
              <span className="text-xs font-semibold text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-lg border border-indigo-500/20">
                Sorted by Proximity & In-Stock Match
              </span>
            </div>

            {/* Sellers Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.matching_summary?.sellers?.map((seller) => {
                const isExact = seller.match_status === 'full_match';
                const isPartial = seller.match_status === 'partial_match';

                return (
                  <div
                    key={seller.seller_id}
                    className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between shadow-md"
                  >
                    <div>
                      {/* Store Header */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div>
                          <h4 className="font-bold text-white text-base">{seller.name}</h4>
                          <p className="text-xs text-slate-400">{seller.address || 'Neighborhood Merchant'}</p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <span className="inline-block px-2 py-0.5 rounded-md text-xs font-bold bg-slate-800 text-emerald-400">
                            {seller.distance_meters}m away
                          </span>
                        </div>
                      </div>

                      {/* Match Status Badge & Fulfillment */}
                      <div className="flex items-center space-x-2 mb-3">
                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                            isExact
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : isPartial
                              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {seller.match_status.replace('_', ' ')}
                        </span>
                        <span className="text-xs text-slate-400">
                          Fulfillment: <strong className="text-white">{seller.fulfillment_percentage}%</strong>
                        </span>
                      </div>

                      {/* In-Stock Items Preview */}
                      {seller.matched_items && seller.matched_items.length > 0 && (
                        <div className="mb-3">
                          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                            Matching Items in Stock:
                          </p>
                          <div className="space-y-1">
                            {seller.matched_items.map((it, idx) => (
                              <div
                                key={idx}
                                className="flex items-center justify-between text-xs bg-slate-950/70 p-2 rounded-lg border border-slate-800/80"
                              >
                                <span className="text-slate-200 font-medium">{it.product_name}</span>
                                <span className="font-bold text-emerald-400">₹{it.price.toFixed(2)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Contact Action */}
                    <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-1.5 text-slate-400">
                        <Phone className="w-3.5 h-3.5 text-slate-400" />
                        <span>{seller.phone}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => alert(`Calling merchant ${seller.name} (${seller.phone})`)}
                        className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors"
                      >
                        Contact Store
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Escrow Payment Modal */}
      {activePaymentQuote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fadeIn">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-lg w-full p-6 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

            <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <Lock className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Mock Escrow Payment</h3>
                  <p className="text-xs text-slate-400">Merchant: {activePaymentQuote.seller_name}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActivePaymentQuote(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Bill Summary */}
            <div className="bg-slate-950/70 rounded-2xl p-4 border border-slate-800 mb-5">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-slate-400">Order Subtotal</span>
                <span className="text-white font-medium">₹{Number(activePaymentQuote.total_amount).toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-slate-400">Hyperlocal Delivery & Escrow Fee</span>
                <span className="text-emerald-400 font-medium">FREE (Promotional)</span>
              </div>
              <div className="border-t border-slate-800/80 pt-2 flex items-center justify-between text-base font-bold">
                <span className="text-white">Total Amount to Pay</span>
                <span className="text-emerald-400 text-xl font-black">
                  ₹{Number(activePaymentQuote.total_amount).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Payment Method Selector */}
            <div className="mb-5">
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Select Payment Channel:
              </label>
              <div className="space-y-2">
                {[
                  { id: 'upi', name: 'Instant UPI (Google Pay / PhonePe / Paytm / BHIM)', badge: 'Recommended' },
                  { id: 'card', name: 'Credit or Debit Card (Visa / Mastercard / RuPay)', badge: 'Zero Surcharge' },
                  { id: 'escrow', name: 'Direct Escrow Settlement (Hyperlocal Safe Pay)', badge: 'Protected' },
                ].map((channel) => (
                  <label
                    key={channel.id}
                    onClick={() => setPaymentMethod(channel.id)}
                    className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                      paymentMethod === channel.id
                        ? 'bg-indigo-600/20 border-indigo-500 text-white shadow-sm'
                        : 'bg-slate-950/50 border-slate-800 text-slate-300 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5">
                      <div
                        className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                          paymentMethod === channel.id
                            ? 'border-indigo-400 bg-indigo-500'
                            : 'border-slate-600'
                        }`}
                      >
                        {paymentMethod === channel.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </div>
                      <span className="text-xs font-medium">{channel.name}</span>
                    </div>
                    <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                      {channel.badge}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Escrow Guarantee Statement */}
            <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/20 text-xs text-emerald-300 flex items-start space-x-2 mb-6">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>
                <strong>Escrow Safeguard:</strong> Your money is held in platform escrow. The vendor is notified to pack and dispatch immediately. Funds are disbursed upon customer confirmation.
              </span>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={() => setActivePaymentQuote(null)}
                className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPayment}
                disabled={submittingPayment}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center space-x-2 transition-all"
              >
                {submittingPayment ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                    <span>Processing Escrow Settle...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Authorize & Pay ₹{Number(activePaymentQuote.total_amount).toFixed(2)}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
