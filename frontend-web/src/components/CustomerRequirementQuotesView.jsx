import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  Sparkles,
  MapPin,
  Clock,
  Store,
  CheckCircle2,
  CheckCircle,
  Package,
  Layers,
  ArrowRight,
  ShieldCheck,
  CreditCard,
  RefreshCw,
  Zap,
  ShoppingBag,
  IndianRupee,
  X,
  Truck,
  Phone,
  Radio,
  FileCheck,
  AlertCircle,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

/**
 * CustomerRequirementQuotesView:
 * 1. Displays submitted customer requirement summary (AI parsed items, 3 km radius matching).
 * 2. Fetches and live-polls incoming price quotes submitted by local sellers within 3 km.
 * 3. Provides an "Accept Quote" button next to each vendor's price offer.
 * 4. Calls POST /orders/accept-quote and displays a comprehensive confirmation screen.
 */
export function CustomerRequirementQuotesView({
  requirement,
  onReset,
}) {
  const requirementId = requirement?.requirement_id || requirement?.id;

  const [quotes, setQuotes] = useState([]);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [acceptingQuoteId, setAcceptingQuoteId] = useState(null);
  const [acceptedOrder, setAcceptedOrder] = useState(null);
  const [acceptanceNotes, setAcceptanceNotes] = useState('');
  const [showConfirmationModal, setShowConfirmationModal] = useState(false);
  const [simulatingQuote, setSimulatingQuote] = useState(false);
  const [error, setError] = useState(null);

  // Fetch all incoming quotes from local sellers
  const fetchQuotes = async () => {
    if (!requirementId) return;
    setLoadingQuotes(true);
    try {
      // Fetch from dedicated vendor quotations endpoint
      let vendorQuotes = [];
      try {
        vendorQuotes = await api.getRequirementVendorQuotations(requirementId);
      } catch (err) {
        console.warn('Vendor quotations fetch returned:', err.message);
      }

      // Also fetch from orders requirement endpoint
      let orderQuotes = [];
      try {
        const orderData = await api.getRequirementQuotes(requirementId);
        orderQuotes = orderData?.quotes || [];
      } catch (err) {
        console.warn('Order quotes fetch returned:', err.message);
      }

      // Merge and deduplicate by quote ID
      const mergedMap = new Map();

      (vendorQuotes || []).forEach((q) => {
        mergedMap.set(q.id, {
          id: q.id,
          seller_id: q.seller_id,
          seller_name: q.seller?.name || 'Local Verified Merchant',
          seller_phone: q.seller?.phone || '+91 98765 43210',
          seller_address: q.seller?.address || 'Within 3 km Delivery Perimeter',
          total_amount: Number(q.total_amount),
          delivery_time_estimate: q.estimated_delivery_time || '15-20 mins',
          status: (q.status || 'pending').toLowerCase(),
          itemized_quote: Array.isArray(q.itemized_prices)
            ? q.itemized_prices
            : typeof q.itemized_prices === 'object' && q.itemized_prices !== null
            ? q.itemized_prices.items || [q.itemized_prices]
            : [],
          notes: q.notes || 'Packed fresh with cold-chain guarantee.',
          created_at: q.created_at,
          source: 'vendor_quotation',
        });
      });

      (orderQuotes || []).forEach((q) => {
        if (!mergedMap.has(q.id)) {
          mergedMap.set(q.id, {
            id: q.id,
            seller_id: q.seller_id,
            seller_name: q.seller_name || q.seller?.name || 'Neighborhood Store',
            seller_phone: q.seller_phone || q.seller?.phone || '+91 98765 43210',
            seller_address: q.seller_address || q.seller?.address || 'Local Merchant',
            total_amount: Number(q.total_amount || q.quote_amount),
            delivery_time_estimate: q.delivery_time_estimate || '15-20 mins',
            status: (q.status || 'pending').toLowerCase(),
            itemized_quote: Array.isArray(q.itemized_quote)
              ? q.itemized_quote
              : q.itemized_quote?.items || [],
            notes: q.notes || '',
            created_at: q.created_at,
            source: 'order_quote',
          });
        }
      });

      const mergedList = Array.from(mergedMap.values()).sort(
        (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
      );
      setQuotes(mergedList);

      // If one of the quotes is already accepted, check if order is active
      const activeAccepted = mergedList.find((q) => q.status === 'accepted' || q.status === 'out_for_delivery');
      if (activeAccepted && !acceptedOrder) {
        // Sync active status
      }
    } catch (err) {
      console.error('Error fetching incoming quotes:', err);
    } finally {
      setLoadingQuotes(false);
    }
  };

  // Poll for incoming quotes every 3.5 seconds
  useEffect(() => {
    fetchQuotes();
    const interval = setInterval(fetchQuotes, 3500);
    return () => clearInterval(interval);
  }, [requirementId]);

  // Poll accepted order status for live delivery progress
  useEffect(() => {
    if (!acceptedOrder?.id) return;

    const pollOrder = async () => {
      try {
        const latest = await api.getOrder(acceptedOrder.id);
        if (latest) {
          setAcceptedOrder(latest);
        }
      } catch (err) {
        console.warn('Could not poll order:', err);
      }
    };

    const interval = setInterval(pollOrder, 3000);
    return () => clearInterval(interval);
  }, [acceptedOrder?.id]);

  // Action: Customer Accepts Vendor Quote
  const handleAcceptQuote = async (quote) => {
    setAcceptingQuoteId(quote.id);
    setError(null);

    try {
      const payload = {
        quotation_id: quote.id,
        notes: acceptanceNotes || 'Customer accepted quote. Please proceed with packaging and dispatch.',
      };

      const orderResult = await api.acceptQuote(payload);
      setAcceptedOrder({
        ...orderResult,
        chosenQuote: quote,
      });
      setShowConfirmationModal(true);
      await fetchQuotes();
    } catch (err) {
      setError(err.message || 'Failed to accept quote. Please try again.');
    } finally {
      setAcceptingQuoteId(null);
    }
  };

  // Instant Test Simulation: Submits a realistic quote from one of the notified sellers
  const handleSimulateQuote = async () => {
    if (!requirementId) return;
    setSimulatingQuote(true);
    setError(null);

    try {
      const sellers = requirement.matching_summary?.sellers || [];
      const eligibleSeller =
        sellers.find((s) => s.can_receive_broadcasts !== false && s.subscription_status !== 'expired') ||
        sellers[0] || {
          seller_id: '29186c60-62bc-41a1-b0e8-cc37f21f968b',
          name: 'Indiranagar Fresh Mart',
        };

      const sellerId = eligibleSeller.seller_id || eligibleSeller.id || '29186c60-62bc-41a1-b0e8-cc37f21f968b';

      const parsedItems = requirement.parsed_requirement?.items || [];
      const lineItems = parsedItems.map((it, idx) => {
        const qtyNum = parseInt(String(it.quantity || '1'), 10) || 1;
        const unitPrice = 35.0 + idx * 15.0;
        return {
          item_name: it.product_name,
          quantity: it.quantity || `${qtyNum} pcs`,
          unit_price: unitPrice,
          total: Number((qtyNum * unitPrice).toFixed(2)),
        };
      });

      if (lineItems.length === 0) {
        lineItems.push({
          item_name: 'Daily Grocery Essentials Pack',
          quantity: '1 pack',
          unit_price: 130.0,
          total: 130.0,
        });
      }

      const total = Number(lineItems.reduce((acc, curr) => acc + curr.total, 0).toFixed(2));

      try {
        await api.submitVendorQuotation({
          requirement_id: requirementId,
          seller_id: sellerId,
          total_amount: total,
          estimated_delivery_time: '15-20 mins',
          itemized_prices: lineItems,
        });
      } catch (subErr) {
        console.warn('submitVendorQuotation fallback to submitOrderQuote:', subErr);
        await api.submitOrderQuote({
          requirement_id: requirementId,
          seller_id: sellerId,
          quote_amount: total,
          delivery_estimate_minutes: 15,
          itemized_items: lineItems,
          notes: 'Packed fresh with cold chain delivery.',
        });
      }

      await fetchQuotes();
    } catch (err) {
      setError(`Simulation failed: ${err.message}`);
    } finally {
      setSimulatingQuote(false);
    }
  };

  // Parsed summary data
  const parsedItems = requirement?.parsed_requirement?.items || [];
  const urgency = requirement?.parsed_requirement?.urgency || 'MEDIUM';
  const targetEta = requirement?.parsed_requirement?.estimated_delivery_time || '30 mins';
  const sellersCount = requirement?.matching_summary?.total_sellers_in_radius || requirement?.matching_summary?.sellers?.length || 0;

  return (
    <div className="space-y-6">
      {/* ===================================================================== */}
      {/* SUBMITTED REQUIREMENT OVERVIEW CARD */}
      {/* ===================================================================== */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden backdrop-blur-xl">
        <div className="absolute top-0 right-0 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4 relative z-10">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <span className="flex items-center space-x-1 px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-bold">
                <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
                <span>Active 3 km Broadcast</span>
              </span>
              <span className="text-xs font-mono text-slate-400">
                #{String(requirementId).slice(0, 8)}...
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-black text-white">
              Submitted Shopping Requirement
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Customer: <span className="text-slate-200 font-semibold">{requirement.customer_name || 'Guest'}</span> • Broadcast Radius: <span className="text-emerald-400 font-semibold">{requirement.radius_km || 3.0} km</span>
            </p>
          </div>

          <div className="flex items-center space-x-2">
            {onReset && (
              <button
                type="button"
                onClick={onReset}
                className="px-3.5 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-colors"
              >
                + Submit Another
              </button>
            )}
            <button
              type="button"
              onClick={fetchQuotes}
              disabled={loadingQuotes}
              className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center space-x-1.5 border border-slate-700 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingQuotes ? 'animate-spin text-emerald-400' : ''}`} />
              <span>Refresh Live</span>
            </button>
          </div>
        </div>

        {/* Natural Language Prompt Quote Box */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl p-4 mb-4 relative z-10">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Your Requirement Text:
          </p>
          <p className="text-base text-white font-medium italic">
            "{requirement.raw_text}"
          </p>
        </div>

        {/* AI Structured Shopping List Items */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mb-4 relative z-10">
          {parsedItems.map((item, idx) => (
            <div
              key={idx}
              className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/90 flex items-center space-x-3"
            >
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 flex-shrink-0">
                <Package className="w-4 h-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-white truncate">{item.product_name}</p>
                <div className="flex items-center space-x-2 mt-0.5">
                  <span className="text-[11px] font-semibold text-emerald-400">{item.quantity}</span>
                  {item.category && (
                    <span className="text-[10px] text-slate-400 bg-slate-800 px-1.5 py-0.2 rounded">
                      {item.category}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Meta Stats Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-slate-800/80 text-xs text-slate-300 relative z-10">
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 font-semibold">
            <Clock className="w-3.5 h-3.5" />
            <span>Urgency: {urgency}</span>
          </span>
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
            <Store className="w-3.5 h-3.5 text-emerald-400" />
            <span>{sellersCount} local stores notified within 3 km</span>
          </span>
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
            <MapPin className="w-3.5 h-3.5 text-indigo-400" />
            <span>WGS84 ({Number(requirement.location?.latitude || 0).toFixed(4)}, {Number(requirement.location?.longitude || 0).toFixed(4)})</span>
          </span>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* ===================================================================== */}
      {/* LIVE INCOMING PRICE QUOTES SECTION */}
      {/* ===================================================================== */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center space-x-2">
              <ShoppingBag className="w-5 h-5 text-emerald-400" />
              <span>Incoming Local Seller Price Quotes</span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                {quotes.length} {quotes.length === 1 ? 'Quote' : 'Quotes'}
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Live price bids submitted by local merchants in your 3 km perimeter. Review and click "Accept Quote".
            </p>
          </div>

          {quotes.length === 0 && (
            <button
              type="button"
              onClick={handleSimulateQuote}
              disabled={simulatingQuote}
              className="inline-flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/20 transition-all self-start sm:self-auto"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>{simulatingQuote ? 'Simulating Quote...' : 'Simulate Seller Quote ⚡'}</span>
            </button>
          )}
        </div>

        {/* Empty State: Radar Broadcast animation */}
        {quotes.length === 0 ? (
          <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-12 text-center relative overflow-hidden">
            {/* Animated Pulsing Rings */}
            <div className="w-20 h-20 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto mb-4 relative">
              <Radio className="w-10 h-10 animate-pulse text-emerald-400" />
              <div className="absolute inset-0 rounded-full border border-emerald-400/40 animate-ping pointer-events-none" />
            </div>

            <h4 className="text-base font-bold text-white mb-1">
              Broadcasting to Local Stores Within 3 km...
            </h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
              Neighborhood merchants are currently reviewing your requirement and compiling itemized quotes. 
              Quotes will appear here automatically in real time!
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                type="button"
                onClick={handleSimulateQuote}
                disabled={simulatingQuote}
                className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 transition-all"
              >
                <Zap className="w-4 h-4" />
                <span>Simulate Instant Local Merchant Quote</span>
              </button>
              <button
                type="button"
                onClick={fetchQuotes}
                disabled={loadingQuotes}
                className="w-full sm:w-auto inline-flex items-center justify-center space-x-1.5 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingQuotes ? 'animate-spin' : ''}`} />
                <span>Check for Updates</span>
              </button>
            </div>
          </div>
        ) : (
          /* Quotes Cards List */
          <div className="space-y-4">
            {quotes.map((quote) => {
              const isPending = quote.status === 'pending';
              const isAccepted = quote.status === 'accepted';
              const isRejected = quote.status === 'rejected';
              const isOutForDelivery = quote.status === 'out_for_delivery';
              const isCompleted = quote.status === 'completed';
              const isAccepting = acceptingQuoteId === quote.id;

              return (
                <div
                  key={quote.id}
                  className={`rounded-2xl border p-5 shadow-xl transition-all ${
                    isAccepted || isOutForDelivery || isCompleted
                      ? 'bg-slate-900/90 border-emerald-500/50 shadow-emerald-950/20 ring-1 ring-emerald-500/30'
                      : isRejected
                      ? 'bg-slate-950/50 border-slate-800 opacity-60'
                      : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4">
                    {/* Merchant Details */}
                    <div>
                      <div className="flex items-center space-x-2.5">
                        <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 flex-shrink-0">
                          <Store className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <h4 className="text-base font-bold text-white">{quote.seller_name}</h4>
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider border ${
                                isAccepted || isCompleted
                                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                  : isOutForDelivery
                                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40 animate-pulse'
                                  : isRejected
                                  ? 'bg-slate-800 text-slate-400 border-slate-700'
                                  : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                              }`}
                            >
                              {isAccepted
                                ? '✓ Quote Accepted'
                                : isOutForDelivery
                                ? '🛵 Out for Delivery'
                                : isCompleted
                                ? '🎉 Delivered & Complete'
                                : isRejected
                                ? 'Not Selected'
                                : 'Awaiting Your Decision'}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5 flex items-center space-x-1.5">
                            <MapPin className="w-3.5 h-3.5 text-slate-500" />
                            <span>{quote.seller_address}</span>
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3 mt-3 text-xs text-slate-300">
                        <span className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-slate-950/70 border border-slate-800 font-semibold text-emerald-400">
                          <Clock className="w-3.5 h-3.5" />
                          <span>Delivery ETA: {quote.delivery_time_estimate}</span>
                        </span>
                        <span className="flex items-center space-x-1 text-slate-400">
                          <Phone className="w-3.5 h-3.5 text-slate-500" />
                          <span>{quote.seller_phone}</span>
                        </span>
                      </div>
                    </div>

                    {/* Price Offer & Action Box */}
                    <div className="flex flex-col sm:flex-row md:flex-col items-start md:items-end justify-between gap-3">
                      <div>
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block md:text-right">
                          Total Quoted Price:
                        </span>
                        <div className="text-2xl sm:text-3xl font-black text-emerald-400 font-mono">
                          ₹{Number(quote.total_amount).toFixed(2)}
                        </div>
                        <span className="text-[10px] text-slate-500 block md:text-right">
                          Includes taxes & doorstep packaging
                        </span>
                      </div>

                      {/* ACCEPT QUOTE BUTTON */}
                      {isPending && (
                        <button
                          type="button"
                          onClick={() => handleAcceptQuote(quote)}
                          disabled={isAccepting}
                          className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 flex items-center justify-center space-x-2 transition-all active:scale-95 disabled:opacity-50"
                        >
                          <CheckCircle className="w-4 h-4 text-emerald-300" />
                          <span>
                            {isAccepting ? 'Accepting Quote...' : 'Accept Quote & Order 🚀'}
                          </span>
                        </button>
                      )}

                      {isAccepted && (
                        <div className="text-xs font-bold text-emerald-400 flex items-center space-x-1.5 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/30">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Order Confirmed with This Seller</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Itemized Breakdown Table */}
                  {quote.itemized_quote && quote.itemized_quote.length > 0 && (
                    <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3.5 mb-3">
                      <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                        Vendor Itemized Bill:
                      </p>
                      <div className="space-y-1.5 text-xs">
                        {quote.itemized_quote.map((item, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between py-1 border-b border-slate-800/60 last:border-0"
                          >
                            <span className="text-slate-300 font-medium">
                              {item.item_name || item.product_name || `Item ${idx + 1}`}{' '}
                              <span className="text-slate-500">× {item.quantity || 1}</span>
                            </span>
                            <span className="text-slate-200 font-mono font-semibold">
                              ₹{Number(item.total || item.price || item.unit_price || 0).toFixed(2)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Seller Guarantee & Notes */}
                  {quote.notes && (
                    <p className="text-xs text-slate-400 italic bg-slate-950/40 px-3 py-2 rounded-lg border border-slate-800/50">
                      "{quote.notes}"
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ===================================================================== */}
      {/* ORDER ACCEPTANCE CONFIRMATION SCREEN (MODAL) */}
      {/* ===================================================================== */}
      {showConfirmationModal && acceptedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-gradient-to-b from-slate-900 to-slate-950 border border-emerald-500/40 rounded-3xl max-w-xl w-full p-6 sm:p-8 shadow-2xl relative overflow-hidden">
            {/* Glow decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />

            <button
              type="button"
              onClick={() => setShowConfirmationModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Success Checkmark & Header */}
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-3xl bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center text-emerald-400 mx-auto mb-3 shadow-lg shadow-emerald-500/20">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <span className="inline-block px-3 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold uppercase tracking-wider mb-2">
                Order Accepted & Confirmed
              </span>
              <h2 className="text-2xl sm:text-3xl font-black text-white">
                You're All Set! 🎉
              </h2>
              <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-md mx-auto">
                Your order is officially placed with{' '}
                <strong className="text-emerald-300">
                  {acceptedOrder.seller?.name || acceptedOrder.chosenQuote?.seller_name || 'Selected Merchant'}
                </strong>
                . The seller has been alerted to begin immediate packing and dispatch.
              </p>
            </div>

            {/* Order Details Card */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 mb-5 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs text-slate-400">Order ID:</span>
                <span className="text-xs font-bold font-mono text-white">
                  #{String(acceptedOrder.id).slice(0, 12)}...
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs text-slate-400">Order Status:</span>
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase">
                  {String(acceptedOrder.status || 'ACCEPTED')}
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs text-slate-400">Total Quoted Amount:</span>
                <span className="text-lg font-black text-emerald-400 font-mono">
                  ₹{Number(acceptedOrder.quote_amount || acceptedOrder.chosenQuote?.total_amount || 0).toFixed(2)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Estimated Turnaround:</span>
                <span className="text-xs font-semibold text-slate-200 flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  <span>{acceptedOrder.chosenQuote?.delivery_time_estimate || '15-20 mins'}</span>
                </span>
              </div>
            </div>

            {/* Live Delivery Progress Stepper */}
            <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 mb-6">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
                  <Truck className="w-4 h-4 text-indigo-400" />
                  <span>Doorstep Delivery Progress</span>
                </span>
                <span className="text-[11px] font-bold text-emerald-400">
                  {String(acceptedOrder.status) === 'COMPLETED'
                    ? 'Delivered to Doorstep ✅'
                    : String(acceptedOrder.status) === 'OUT_FOR_DELIVERY'
                    ? 'Rider En Route 🛵'
                    : 'Merchant Packaging Order 🧑‍🍳'}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center text-[11px] font-bold">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  ✓ 1. Quote Accepted
                </div>
                <div
                  className={`p-2.5 rounded-xl border transition-all ${
                    acceptedOrder.status === 'OUT_FOR_DELIVERY' || acceptedOrder.status === 'COMPLETED'
                      ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300 font-bold'
                      : 'bg-slate-900/60 border-slate-800 text-slate-500'
                  }`}
                >
                  {acceptedOrder.status === 'OUT_FOR_DELIVERY' ? '🛵 2. On the Way' : '2. Out for Delivery'}
                </div>
                <div
                  className={`p-2.5 rounded-xl border transition-all ${
                    acceptedOrder.status === 'COMPLETED'
                      ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-bold'
                      : 'bg-slate-900/60 border-slate-800 text-slate-500'
                  }`}
                >
                  {acceptedOrder.status === 'COMPLETED' ? '🎉 3. Delivered' : '3. Doorstep Delivery'}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowConfirmationModal(false)}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs border border-slate-700 transition-colors"
              >
                Close & Track in Portal
              </button>
              {onReset && (
                <button
                  type="button"
                  onClick={() => {
                    setShowConfirmationModal(false);
                    onReset();
                  }}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 transition-all"
                >
                  Create New Request →
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
