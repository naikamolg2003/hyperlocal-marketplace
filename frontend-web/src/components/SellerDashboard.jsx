import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  Store,
  Radio,
  Clock,
  MapPin,
  CheckCircle2,
  DollarSign,
  Package,
  AlertTriangle,
  RefreshCw,
  ShoppingBag,
  Send,
  X,
  Sparkles,
  Layers,
  Plus,
  Trash2,
  Edit2,
  Upload,
  Check,
  CreditCard,
  FileSpreadsheet,
  Truck,
  ArrowRight,
} from 'lucide-react';

const SELLER_LOCATIONS = [
  {
    id: 'a0000000-0000-0000-0000-000000000001',
    name: 'Green Valley Organic Store',
    locationName: 'Indiranagar, Bangalore',
    lat: 12.9784,
    lon: 77.6408,
    categories: ['Dairy', 'Grocery', 'Bakery'],
  },
  {
    id: '74f96b66-4f29-43c8-b24e-438f04b79837',
    name: 'Wakad Daily Fresh & Grocers',
    locationName: 'Wakad, Pune',
    lat: 18.5987,
    lon: 73.7660,
    categories: ['Produce', 'Dairy', 'Snacks'],
  },
];

const PRESET_CATALOGS = {
  dairy: [
    { product_name: 'A2 Organic Farm Fresh Milk 1L', price: 72.0, category_names: ['Dairy', 'Breakfast Essentials'], is_available: true },
    { product_name: 'Farm Fresh Paneer 250g', price: 110.0, category_names: ['Dairy', 'Cooking Essentials'], is_available: true },
    { product_name: 'Natural Desi Cow Ghee 500ml', price: 420.0, category_names: ['Dairy', 'Organic Staples'], is_available: true },
    { product_name: 'Greek Yogurt Natural 400g', price: 95.0, category_names: ['Dairy', 'Healthy Snacks'], is_available: true },
  ],
  bakery: [
    { product_name: 'Artisan Sourdough Loaf 400g', price: 140.0, category_names: ['Bakery & Breads', 'Artisan Foods'], is_available: true },
    { product_name: 'Multigrain Brown Bread 400g', price: 55.0, category_names: ['Bakery & Breads', 'Breakfast Essentials'], is_available: true },
    { product_name: 'Fresh Butter Croissant (Pack of 2)', price: 120.0, category_names: ['Bakery & Breads', 'Snacks'], is_available: true },
  ],
  groceries: [
    { product_name: 'Organic Sona Masoori Rice 5kg', price: 385.0, category_names: ['Groceries', 'Organic Staples'], is_available: true },
    { product_name: 'Cold Pressed Mustard Oil 1L', price: 210.0, category_names: ['Cooking Oils', 'Groceries'], is_available: true },
    { product_name: 'Organic Toor Dal 1kg', price: 165.0, category_names: ['Pulses & Dals', 'Organic Staples'], is_available: true },
  ],
};

export function SellerDashboard() {
  const [selectedSeller, setSelectedSeller] = useState(SELLER_LOCATIONS[0]);
  const [activeTab, setActiveTab] = useState('radar'); // 'radar' | 'inventory'
  const [radiusKm, setRadiusKm] = useState(3.0);
  const [demands, setDemands] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Billing & Freemium State
  const [billingStatus, setBillingStatus] = useState(null);
  const [payingFee, setPayingFee] = useState(false);

  // Inventory State
  const [inventory, setInventory] = useState([]);
  const [loadingInventory, setLoadingInventory] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null);

  // Add Item Form State
  const [newProductName, setNewProductName] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [newCategories, setNewCategories] = useState('Daily Essentials, Dairy');
  const [newIsAvailable, setNewIsAvailable] = useState(true);
  const [submittingItem, setSubmittingItem] = useState(false);

  // Quote Modal State
  const [activeQuoteDemand, setActiveQuoteDemand] = useState(null);
  const [quotePrice, setQuotePrice] = useState('');
  const [deliveryMinutes, setDeliveryMinutes] = useState('20');
  const [quoteNotes, setQuoteNotes] = useState('All items in stock. Packed fresh.');
  const [lineItems, setLineItems] = useState([]);
  const [submittingQuote, setSubmittingQuote] = useState(false);
  const [quotedOrderIds, setQuotedOrderIds] = useState(new Set());

  // Orders & Delivery Lifecycle State
  const [orders, setOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [orderStatusFilter, setOrderStatusFilter] = useState('ALL');
  const [updatingOrderId, setUpdatingOrderId] = useState(null);

  // Fetch billing & subscription status
  const fetchBillingStatus = async () => {
    try {
      const status = await api.getSellerBillingStatus(selectedSeller.id);
      setBillingStatus(status);
    } catch (err) {
      console.warn('Could not load billing status for seller:', err);
    }
  };

  // Fetch live inventory for seller
  const fetchInventory = async () => {
    setLoadingInventory(true);
    try {
      const items = await api.getSellerItems(selectedSeller.id);
      setInventory(items || []);
    } catch (err) {
      console.warn('Could not load inventory:', err);
    } finally {
      setLoadingInventory(false);
    }
  };

  // Fetch orders for seller
  const fetchSellerOrders = async () => {
    setLoadingOrders(true);
    try {
      const orderList = await api.getSellerOrders(selectedSeller.id);
      setOrders(orderList || []);
    } catch (err) {
      console.warn('Could not load orders for seller:', err);
    } finally {
      setLoadingOrders(false);
    }
  };

  // Fetch nearby demands within 3 km
  const fetchNearbyDemands = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getNearbyRequirements({
        lat: selectedSeller.lat,
        lon: selectedSeller.lon,
        radius_km: radiusKm,
        seller_id: selectedSeller.id,
      });
      setDemands(response.requirements || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch incoming customer demands.');
    } finally {
      setLoading(false);
    }
  };

  // Update order delivery lifecycle status
  const handleUpdateDeliveryStatus = async (orderId, nextStatus) => {
    setUpdatingOrderId(orderId);
    try {
      await api.updateOrderStatus(orderId, {
        status: nextStatus,
        notes: `Status updated to ${nextStatus} by merchant ${selectedSeller.name}`,
      });
      await fetchSellerOrders();
      await fetchBillingStatus();
      if (nextStatus === 'COMPLETED') {
        alert('Order marked as COMPLETED! Your completed order count has been incremented.');
      }
    } catch (err) {
      alert(`Failed to update order status: ${err.message}`);
    } finally {
      setUpdatingOrderId(null);
    }
  };

  useEffect(() => {
    fetchNearbyDemands();
    fetchBillingStatus();
    fetchInventory();
    fetchSellerOrders();

    const interval = setInterval(() => {
      fetchNearbyDemands();
      fetchBillingStatus();
      fetchSellerOrders();
    }, 6000);
    return () => clearInterval(interval);
  }, [selectedSeller, radiusKm]);

  // Handle Monthly Platform Fee Payment
  const handlePayPlatformFee = async () => {
    setPayingFee(true);
    try {
      await api.paySellerPlatformFee(selectedSeller.id, {
        amount: 1000.0,
        payment_method: 'upi',
      });
      await fetchBillingStatus();
      alert('Payment of Rs. 1,000 received! Your platform subscription is active for 30 days.');
    } catch (err) {
      alert(`Payment failed: ${err.message}`);
    } finally {
      setPayingFee(false);
    }
  };

  // Handle In-Stock Availability Toggle
  const handleToggleAvailability = async (item) => {
    const nextState = !item.is_available;
    // Optimistic UI update
    setInventory((prev) =>
      prev.map((it) => (it.id === item.id ? { ...it, is_available: nextState } : it))
    );
    try {
      await api.toggleItemAvailability(item.id, nextState);
    } catch (err) {
      alert(`Failed to toggle availability: ${err.message}`);
      fetchInventory();
    }
  };

  // Handle Edit Price
  const handleUpdatePrice = async (itemId, newPriceVal) => {
    const cleanPrice = parseFloat(newPriceVal);
    if (isNaN(cleanPrice) || cleanPrice <= 0) return;
    try {
      await api.updateItem(itemId, { price: cleanPrice });
      setInventory((prev) =>
        prev.map((it) => (it.id === itemId ? { ...it, price: cleanPrice } : it))
      );
      setEditingItem(null);
    } catch (err) {
      alert(`Failed to update price: ${err.message}`);
    }
  };

  // Handle Delete Item
  const handleDeleteItem = async (itemId) => {
    if (!window.confirm('Delete this product from your inventory catalog?')) return;
    try {
      await api.deleteItem(itemId);
      setInventory((prev) => prev.filter((it) => it.id !== itemId));
    } catch (err) {
      alert(`Failed to delete item: ${err.message}`);
    }
  };

  // Handle Add Single Product
  const handleAddProduct = async (e) => {
    e.preventDefault();
    if (!newProductName.trim() || !newPrice) return;

    setSubmittingItem(true);
    try {
      const catList = newCategories
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean);

      const created = await api.createItem({
        seller_id: selectedSeller.id,
        product_name: newProductName.trim(),
        price: parseFloat(newPrice),
        is_available: newIsAvailable,
        category_names: catList.length > 0 ? catList : ['General'],
      });

      setInventory((prev) => [created, ...prev]);
      setShowAddModal(false);
      setNewProductName('');
      setNewPrice('');
      setNewCategories('Daily Essentials, Dairy');
    } catch (err) {
      alert(`Failed to add item: ${err.message}`);
    } finally {
      setSubmittingItem(false);
    }
  };

  // Handle Bulk Preset Ingest
  const handleLoadPreset = async (presetKey) => {
    const items = PRESET_CATALOGS[presetKey];
    if (!items) return;
    setSubmittingItem(true);
    try {
      const res = await api.bulkUploadItems({
        seller_id: selectedSeller.id,
        items: items,
      });
      alert(`Successfully bulk-uploaded ${res.total_uploaded} items to your catalog!`);
      setShowBulkModal(false);
      fetchInventory();
    } catch (err) {
      alert(`Bulk upload failed: ${err.message}`);
    } finally {
      setSubmittingItem(false);
    }
  };

  // Open Quote Modal
  const handleOpenQuoteModal = (demand) => {
    setActiveQuoteDemand(demand);
    const parsedItems = demand.requirement.structured_json?.items || [];
    const initialLineItems = parsedItems.map((it) => ({
      product_name: it.product_name,
      quantity: it.quantity || 1,
      unit_price: 65.0,
      total: (it.quantity || 1) * 65.0,
    }));

    if (initialLineItems.length === 0) {
      initialLineItems.push({
        product_name: 'Fulfillment Order Items',
        quantity: 1,
        unit_price: 150.0,
        total: 150.0,
      });
    }

    setLineItems(initialLineItems);
    const total = initialLineItems.reduce((acc, curr) => acc + curr.total, 0);
    setQuotePrice(String(total));
    setDeliveryMinutes('20');
    setQuoteNotes('All items packed fresh and ready for immediate delivery.');
  };

  // Submit Official Itemized Quote
  const handleSubmitQuote = async (e) => {
    e.preventDefault();
    if (!activeQuoteDemand) return;

    setSubmittingQuote(true);
    try {
      const totalAmount = parseFloat(quotePrice);
      await api.submitOrderQuote({
        requirement_id: activeQuoteDemand.requirement.id,
        seller_id: selectedSeller.id,
        quote_amount: totalAmount,
        delivery_estimate_minutes: parseInt(deliveryMinutes, 10) || 20,
        itemized_items: lineItems,
        notes: quoteNotes,
      });

      setQuotedOrderIds((prev) => new Set(prev).add(activeQuoteDemand.requirement.id));
      setActiveQuoteDemand(null);
      alert('Official itemized quote dispatched! The customer can now approve and settle via Escrow.');
      fetchNearbyDemands();
      fetchBillingStatus();
    } catch (err) {
      alert(`Error submitting quote: ${err.message}`);
    } finally {
      setSubmittingQuote(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Top Banner & Radar Status */}
      <div className="bg-gradient-to-r from-emerald-950/70 via-slate-900 to-slate-950 border border-emerald-500/30 rounded-3xl p-6 mb-8 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center space-x-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 flex-shrink-0 shadow-lg shadow-emerald-500/10">
              <Store className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl sm:text-2xl font-black text-white">{selectedSeller.name}</h1>
                <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-[11px] font-bold">
                  <Radio className="w-3 h-3 animate-pulse text-emerald-400" />
                  <span>3 km Radar Live</span>
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-1 flex items-center space-x-1.5">
                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                <span>
                  {selectedSeller.locationName} • WGS84 ({selectedSeller.lat}, {selectedSeller.lon})
                </span>
              </p>
            </div>
          </div>

          {/* Store Switcher */}
          <div className="flex items-center space-x-2 self-start md:self-auto bg-slate-950/80 p-1.5 rounded-2xl border border-slate-800">
            <span className="text-xs text-slate-400 pl-2 font-medium">Switch Store:</span>
            {SELLER_LOCATIONS.map((store) => (
              <button
                key={store.name}
                type="button"
                onClick={() => setSelectedSeller(store)}
                className={`text-xs px-3 py-1.5 rounded-xl font-semibold transition-all ${
                  selectedSeller.name === store.name
                    ? 'bg-emerald-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {store.name.split(' ')[0]}
              </button>
            ))}
            <button
              onClick={() => {
                fetchNearbyDemands();
                fetchInventory();
                fetchBillingStatus();
              }}
              title="Refresh Dashboard"
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* Freemium Billing & Milestone Quota Bar */}
        {billingStatus && (
          <div className="mt-6 p-4 rounded-2xl bg-slate-950/90 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center space-x-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${
                  billingStatus.subscription_status === 'subscribed'
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : billingStatus.subscription_status === 'pending_payment'
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                    : 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                }`}
              >
                <CreditCard className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Freemium Lifecycle:
                  </span>
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                      billingStatus.subscription_status === 'subscribed'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : billingStatus.subscription_status === 'pending_payment'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-indigo-500/20 text-indigo-300'
                    }`}
                  >
                    {billingStatus.subscription_status.toUpperCase()}
                  </span>
                  <span className="text-xs text-slate-400">
                    ({billingStatus.completed_orders_count} completed orders)
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">{billingStatus.status_message}</p>
              </div>
            </div>

            {/* Platform Fee Action Button */}
            {(billingStatus.subscription_status === 'pending_payment' ||
              billingStatus.subscription_status === 'trial_expired' ||
              !billingStatus.can_receive_broadcasts) && (
              <button
                onClick={handlePayPlatformFee}
                disabled={payingFee}
                className="inline-flex items-center justify-center space-x-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-slate-950 font-bold px-4 py-2 rounded-xl shadow-lg shadow-amber-500/20 transition-all text-xs"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{payingFee ? 'Processing Payment...' : 'Pay Platform Fee (Rs. 1,000)'}</span>
              </button>
            )}
          </div>
        )}

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4 pt-4 border-t border-slate-800/80">
          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Perimeter Radius</p>
            <p className="text-xl font-bold text-white mt-0.5">{radiusKm} km</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Broadcasts</p>
            <p className="text-xl font-bold text-emerald-400 mt-0.5">{demands.length}</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Catalog Products</p>
            <p className="text-xl font-bold text-indigo-400 mt-0.5">{inventory.length}</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Store Orders</p>
            <p className="text-xl font-bold text-amber-400 mt-0.5">{orders.length}</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Broadcast Gate</p>
            <p
              className={`text-xl font-bold mt-0.5 ${
                billingStatus?.can_receive_broadcasts ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {billingStatus?.can_receive_broadcasts ? 'Unlocked' : 'Locked'}
            </p>
          </div>
        </div>
      </div>

      {/* Main View Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-800 mb-6 overflow-x-auto pb-1">
        <button
          onClick={() => setActiveTab('radar')}
          className={`pb-3 px-4 text-sm font-bold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
            activeTab === 'radar'
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Radio className="w-4 h-4" />
          <span>📡 3 km Live Demand Radar ({demands.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('inventory')}
          className={`pb-3 px-4 text-sm font-bold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
            activeTab === 'inventory'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>📦 Inventory Catalog ({inventory.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('orders')}
          className={`pb-3 px-4 text-sm font-bold border-b-2 transition-all flex items-center space-x-2 whitespace-nowrap ${
            activeTab === 'orders'
              ? 'border-amber-500 text-amber-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Truck className="w-4 h-4" />
          <span>🛵 Orders & Delivery Lifecycle ({orders.length})</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: RADAR FEED */}
      {/* ========================================================================= */}
      {activeTab === 'radar' && (
        <div>
          {/* Feed Header */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                <span>Incoming Customer Demand Broadcasts</span>
              </h2>
              <p className="text-xs text-slate-400">
                Filtered strictly to customer orders submitted within {radiusKm} km of your store
              </p>
            </div>
            <span className="text-xs text-slate-400 font-mono">Auto-refreshing every 8s</span>
          </div>

          {/* Demands List */}
          {demands.length === 0 ? (
            <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-12 text-center">
              <ShoppingBag className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <h3 className="text-base font-bold text-white mb-1">Radar Scanning 3 km Perimeter</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                No active buyer requests currently within your 3 km perimeter. Submit a demand from the
                Customer Portal to see it appear here in real time.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {demands.map((item) => {
                const req = item.requirement;
                const distanceMeters = item.distance_meters;
                const structured = req.structured_json || {};
                const parsedItems = structured.items || [];
                const urgency = structured.urgency || 'medium';
                const hasQuoted = quotedOrderIds.has(req.id);

                return (
                  <div
                    key={req.id}
                    className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between hover:border-slate-700 transition-all"
                  >
                    <div>
                      {/* Card Header */}
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <div className="flex items-center space-x-2">
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                          <span className="text-xs font-bold text-white">
                            {req.customer?.name || 'Local Customer'}
                          </span>
                          <span className="text-xs text-slate-400">• {distanceMeters.toFixed(0)}m away</span>
                        </div>
                        <span
                          className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full ${
                            urgency === 'urgent'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                          }`}
                        >
                          {urgency}
                        </span>
                      </div>

                      {/* Raw Customer Text */}
                      <p className="text-sm font-medium text-slate-200 mb-3 bg-slate-950/70 p-3 rounded-xl border border-slate-800/80">
                        "{req.raw_text}"
                      </p>

                      {/* Parsed Shopping Items */}
                      {parsedItems.length > 0 && (
                        <div className="mb-4">
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                            AI-Extracted Items ({parsedItems.length}):
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {parsedItems.map((pi, idx) => (
                              <span
                                key={idx}
                                className="text-xs bg-slate-800 text-slate-200 px-2.5 py-1 rounded-lg border border-slate-700 flex items-center space-x-1"
                              >
                                <span>{pi.product_name}</span>
                                <span className="text-indigo-400 font-bold">
                                  x{pi.quantity} {pi.unit || ''}
                                </span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Action Bar */}
                    <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                      <span className="text-[11px] text-slate-400 font-mono">
                        Status: <span className="text-emerald-400 font-bold">{req.status}</span>
                      </span>

                      {hasQuoted ? (
                        <span className="text-xs font-bold text-emerald-400 flex items-center space-x-1 bg-emerald-500/10 px-3 py-1.5 rounded-xl border border-emerald-500/20">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Quote Dispatched</span>
                        </span>
                      ) : (
                        <button
                          onClick={() => handleOpenQuoteModal(item)}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-md transition-all flex items-center space-x-1.5"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Accept & Quote Price</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: INVENTORY & CATALOG MANAGEMENT */}
      {/* ========================================================================= */}
      {activeTab === 'inventory' && (
        <div>
          {/* Inventory Top Action Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                <span>Merchant Catalog & Real-Time Availability</span>
              </h2>
              <p className="text-xs text-slate-400">
                Products mapped across multiple categories without duplication. Toggle stock on/off in real time.
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setShowBulkModal(true)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold text-xs px-3.5 py-2 rounded-xl transition-all flex items-center space-x-1.5"
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" />
                <span>Bulk Upload</span>
              </button>
              <button
                onClick={() => setShowAddModal(true)}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-md shadow-indigo-600/20 transition-all flex items-center space-x-1.5"
              >
                <Plus className="w-4 h-4" />
                <span>Add Product</span>
              </button>
            </div>
          </div>

          {/* Catalog Table */}
          {loadingInventory ? (
            <div className="p-12 text-center text-slate-400">Loading catalog...</div>
          ) : inventory.length === 0 ? (
            <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-12 text-center">
              <Package className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <h3 className="text-base font-bold text-white mb-1">No Products in Catalog Yet</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto mb-4">
                Add products one-by-one or load our curated demo catalog to test instant 3 km matching.
              </p>
              <button
                onClick={() => handleLoadPreset('dairy')}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-md inline-flex items-center space-x-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Load Organic Dairy Essentials Pack</span>
              </button>
            </div>
          ) : (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider">
                      <th className="py-3.5 px-4">Product Name</th>
                      <th className="py-3.5 px-4">Multi-Category Mapping</th>
                      <th className="py-3.5 px-4">Price (₹)</th>
                      <th className="py-3.5 px-4 text-center">Stock Availability</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 text-slate-300">
                    {inventory.map((item) => {
                      const categories = item.categories || [];
                      const isEditing = editingItem?.id === item.id;

                      return (
                        <tr key={item.id} className="hover:bg-slate-800/40 transition-colors">
                          {/* Product Name */}
                          <td className="py-3 px-4 font-semibold text-white">
                            {item.product_name}
                          </td>

                          {/* Categories (No duplication) */}
                          <td className="py-3 px-4">
                            <div className="flex flex-wrap gap-1">
                              {categories.length > 0 ? (
                                categories.map((cat, i) => (
                                  <span
                                    key={i}
                                    className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded-md text-[10px] border border-slate-700/60"
                                  >
                                    {cat.category}
                                    {cat.sub_category ? ` • ${cat.sub_category}` : ''}
                                  </span>
                                ))
                              ) : (
                                <span className="text-slate-500 italic text-[11px]">Uncategorized</span>
                              )}
                            </div>
                          </td>

                          {/* Price */}
                          <td className="py-3 px-4 font-mono font-bold text-emerald-400">
                            {isEditing ? (
                              <div className="flex items-center space-x-1">
                                <span>₹</span>
                                <input
                                  type="number"
                                  defaultValue={item.price}
                                  id={`price-edit-${item.id}`}
                                  className="w-16 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-white"
                                />
                                <button
                                  onClick={() => {
                                    const val = document.getElementById(`price-edit-${item.id}`).value;
                                    handleUpdatePrice(item.id, val);
                                  }}
                                  className="p-1 text-emerald-400 hover:text-emerald-300"
                                >
                                  <Check className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => setEditingItem(null)}
                                  className="p-1 text-slate-400 hover:text-slate-300"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            ) : (
                              <div className="flex items-center space-x-1.5 group">
                                <span>₹{parseFloat(item.price).toFixed(2)}</span>
                                <button
                                  onClick={() => setEditingItem(item)}
                                  className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-500 hover:text-slate-300 transition-opacity"
                                >
                                  <Edit2 className="w-3 h-3" />
                                </button>
                              </div>
                            )}
                          </td>

                          {/* Availability Toggle */}
                          <td className="py-3 px-4 text-center">
                            <button
                              onClick={() => handleToggleAvailability(item)}
                              className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-[11px] font-bold transition-all border ${
                                item.is_available
                                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30'
                                  : 'bg-rose-500/20 text-rose-300 border-rose-500/40 hover:bg-rose-500/30'
                              }`}
                            >
                              <span
                                className={`w-2 h-2 rounded-full ${
                                  item.is_available ? 'bg-emerald-400' : 'bg-rose-400'
                                }`}
                              />
                              <span>{item.is_available ? 'In Stock (Onboarded)' : 'Offboarded (Out)'}</span>
                            </button>
                          </td>

                          {/* Delete Action */}
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={() => handleDeleteItem(item.id)}
                              className="text-slate-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
                              title="Delete Item"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: ORDERS & DELIVERY LIFECYCLE */}
      {/* ========================================================================= */}
      {activeTab === 'orders' && (
        <div className="space-y-6">
          {/* Header & Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                <span>Orders & Delivery Lifecycle Tracking</span>
              </h2>
              <p className="text-xs text-slate-400">
                Track orders accepted from your quotes, dispatch delivery riders, and mark deliveries complete.
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={fetchSellerOrders}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:text-white hover:bg-slate-800 transition-all"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingOrders ? 'animate-spin text-amber-400' : ''}`} />
                <span>Refresh Orders</span>
              </button>
            </div>
          </div>

          {/* Status Filter Pills */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
            {['ALL', 'ACCEPTED', 'OUT_FOR_DELIVERY', 'COMPLETED', 'PENDING'].map((filterKey) => {
              const count =
                filterKey === 'ALL'
                  ? orders.length
                  : orders.filter((o) => (o.status || '').toUpperCase() === filterKey).length;
              const isActive = orderStatusFilter === filterKey;
              return (
                <button
                  key={filterKey}
                  onClick={() => setOrderStatusFilter(filterKey)}
                  className={`px-3 py-1.5 rounded-xl font-bold transition-all whitespace-nowrap flex items-center space-x-1.5 border ${
                    isActive
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm'
                      : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  <span>{filterKey.replace(/_/g, ' ')}</span>
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                      isActive ? 'bg-amber-400 text-slate-950 font-black' : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Orders Feed */}
          {loadingOrders && orders.length === 0 ? (
            <div className="py-16 text-center">
              <RefreshCw className="w-8 h-8 text-amber-400 animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-white">Loading orders from store ledger...</p>
            </div>
          ) : orders.filter(
              (o) => orderStatusFilter === 'ALL' || (o.status || '').toUpperCase() === orderStatusFilter
            ).length === 0 ? (
            <div className="bg-slate-900/40 border border-slate-800/80 rounded-3xl p-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mx-auto mb-4">
                <Truck className="w-8 h-8" />
              </div>
              <h3 className="text-base font-bold text-white mb-1">No Orders Found</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                {orderStatusFilter === 'ALL'
                  ? 'Your store does not have any active or completed orders yet. Respond to nearby customer demands in the Radar tab to receive orders!'
                  : `No orders matching status filter "${orderStatusFilter}". Select "ALL" to view full history.`}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {orders
                .filter(
                  (o) => orderStatusFilter === 'ALL' || (o.status || '').toUpperCase() === orderStatusFilter
                )
                .map((order) => {
                  const statusUpper = (order.status || '').toUpperCase();
                  const isAccepted = statusUpper === 'ACCEPTED' || statusUpper === 'PAID';
                  const isOut = statusUpper === 'OUT_FOR_DELIVERY';
                  const isCompleted = statusUpper === 'COMPLETED';
                  const isPending = statusUpper === 'PENDING';

                  const lineItems =
                    order.itemized_quote?.items ||
                    (Array.isArray(order.itemized_quote) ? order.itemized_quote : []);

                  return (
                    <div
                      key={order.id}
                      className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 shadow-xl transition-all"
                    >
                      {/* Order Card Header */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                        <div className="flex items-center space-x-3">
                          <div
                            className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                              isCompleted
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : isOut
                                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 animate-pulse'
                                : isAccepted
                                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                : 'bg-slate-800 text-slate-400'
                            }`}
                          >
                            <Truck className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="flex items-center space-x-2">
                              <span className="text-sm font-bold text-white font-mono">
                                #{order.id.slice(0, 8)}...
                              </span>
                              <span className="text-xs text-slate-400">•</span>
                              <span className="text-xs text-slate-400 flex items-center space-x-1">
                                <Clock className="w-3 h-3 text-slate-500" />
                                <span>{new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              </span>
                            </div>
                            <p className="text-xs text-slate-400 mt-0.5">
                              Customer: <span className="text-slate-300 font-semibold">{order.customer?.name || order.customer_id.slice(0, 8)}</span>
                            </p>
                          </div>
                        </div>

                        {/* Status Badge */}
                        <div className="flex items-center space-x-2">
                          <span
                            className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                              isCompleted
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                : isOut
                                ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                                : isAccepted
                                ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                : 'bg-slate-800 text-slate-300 border-slate-700'
                            }`}
                          >
                            <span
                              className={`w-2 h-2 rounded-full ${
                                isCompleted
                                  ? 'bg-emerald-400'
                                  : isOut
                                  ? 'bg-indigo-400 animate-ping'
                                  : isAccepted
                                  ? 'bg-amber-400'
                                  : 'bg-slate-400'
                              }`}
                            />
                            <span>{statusUpper.replace(/_/g, ' ')}</span>
                          </span>
                        </div>
                      </div>

                      {/* Items & Notes */}
                      <div className="py-4">
                        {lineItems.length > 0 ? (
                          <div className="space-y-1.5 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 mb-3">
                            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                              Ordered Items:
                            </span>
                            {lineItems.map((item, idx) => (
                              <div
                                key={idx}
                                className="flex items-center justify-between text-xs py-1 border-b border-slate-800/40 last:border-0"
                              >
                                <span className="text-slate-300 font-medium">
                                  {item.item_name || item.product_name} <span className="text-slate-500">× {item.quantity}</span>
                                </span>
                                <span className="text-slate-200 font-mono font-semibold">
                                  ₹{Number(item.total || item.price || 0).toFixed(2)}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : order.notes ? (
                          <p className="text-xs text-slate-300 mb-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                            {order.notes}
                          </p>
                        ) : null}

                        {order.notes && lineItems.length > 0 && (
                          <p className="text-xs text-slate-400 italic mb-2">
                            "{order.notes}"
                          </p>
                        )}

                        <div className="flex items-center justify-between pt-1">
                          <span className="text-xs text-slate-400">Total Billed / Quote Amount:</span>
                          <span className="text-base font-black text-emerald-400 font-mono">
                            ₹{parseFloat(order.quote_amount || 0).toFixed(2)}
                          </span>
                        </div>
                      </div>

                      {/* Lifecycle Progress Stepper & Action Controls */}
                      <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        {/* Stepper Dots */}
                        <div className="flex items-center space-x-2 text-[11px] font-semibold text-slate-400">
                          <span className={isAccepted || isOut || isCompleted ? 'text-emerald-400 font-bold' : ''}>
                            ✓ Accepted
                          </span>
                          <span>→</span>
                          <span className={isOut || isCompleted ? 'text-indigo-400 font-bold' : ''}>
                            {isOut ? '🛵 Out for Delivery' : 'Out for Delivery'}
                          </span>
                          <span>→</span>
                          <span className={isCompleted ? 'text-emerald-400 font-bold' : ''}>
                            {isCompleted ? '✅ Delivered' : 'Delivered'}
                          </span>
                        </div>

                        {/* Interactive Buttons */}
                        <div className="flex items-center space-x-2">
                          {isAccepted && (
                            <button
                              onClick={() => handleUpdateDeliveryStatus(order.id, 'OUT_FOR_DELIVERY')}
                              disabled={updatingOrderId === order.id}
                              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-lg shadow-indigo-600/20 transition-all"
                            >
                              <Truck className="w-3.5 h-3.5" />
                              <span>{updatingOrderId === order.id ? 'Dispatching...' : 'Dispatch: Out for Delivery 🛵'}</span>
                            </button>
                          )}

                          {isOut && (
                            <button
                              onClick={() => handleUpdateDeliveryStatus(order.id, 'COMPLETED')}
                              disabled={updatingOrderId === order.id}
                              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-lg shadow-emerald-600/20 transition-all"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>{updatingOrderId === order.id ? 'Fulfilling...' : 'Mark Delivered & Complete ✅'}</span>
                            </button>
                          )}

                          {isCompleted && (
                            <span className="text-xs font-semibold text-emerald-400 flex items-center space-x-1.5 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Order Completed & Added to Quota Ledger</span>
                            </span>
                          )}

                          {isPending && (
                            <span className="text-xs text-slate-400 italic">
                              Awaiting customer quote approval...
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* ADD PRODUCT MODAL */}
      {/* ========================================================================= */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setShowAddModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-white mb-1 flex items-center space-x-2">
              <Plus className="w-5 h-5 text-indigo-400" />
              <span>Add Inventory Item</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Item will be mapped to selected categories without database duplication.
            </p>

            <form onSubmit={handleAddProduct} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Product Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Organic Cow Milk 1L"
                  value={newProductName}
                  onChange={(e) => setNewProductName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Price (₹ INR)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  placeholder="e.g. 75.00"
                  value={newPrice}
                  onChange={(e) => setNewPrice(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Categories (Comma-separated for multi-taxonomy mapping)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Daily Essentials, Dairy, Breakfast"
                  value={newCategories}
                  onChange={(e) => setNewCategories(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Product will be searchable under each of these categories without duplicating the product record.
                </p>
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <input
                  type="checkbox"
                  id="avail-check"
                  checked={newIsAvailable}
                  onChange={(e) => setNewIsAvailable(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 bg-slate-950 border-slate-700"
                />
                <label htmlFor="avail-check" className="text-xs text-slate-300 font-medium">
                  Available in stock immediately
                </label>
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingItem}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-5 py-2 rounded-xl transition-all shadow-md"
                >
                  {submittingItem ? 'Adding...' : 'Add to Catalog'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* BULK UPLOAD MODAL */}
      {/* ========================================================================= */}
      {showBulkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setShowBulkModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-white mb-1 flex items-center space-x-2">
              <FileSpreadsheet className="w-5 h-5 text-indigo-400" />
              <span>Bulk Inventory Upload</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Instantly seed or bulk ingest products with multi-category mapping.
            </p>

            {/* Curated Presets */}
            <div className="space-y-3 mb-6">
              <p className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                1-Click Preset Catalog Ingest:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  onClick={() => handleLoadPreset('dairy')}
                  disabled={submittingItem}
                  className="p-3 bg-slate-950 border border-slate-800 hover:border-indigo-500 rounded-xl text-left transition-all"
                >
                  <p className="text-xs font-bold text-white">🥛 Organic Dairy</p>
                  <p className="text-[10px] text-slate-400 mt-1">Milk, Paneer, Ghee, Yogurt</p>
                </button>
                <button
                  onClick={() => handleLoadPreset('bakery')}
                  disabled={submittingItem}
                  className="p-3 bg-slate-950 border border-slate-800 hover:border-indigo-500 rounded-xl text-left transition-all"
                >
                  <p className="text-xs font-bold text-white">🥖 Artisan Bakery</p>
                  <p className="text-[10px] text-slate-400 mt-1">Sourdough, Brown Bread, Croissants</p>
                </button>
                <button
                  onClick={() => handleLoadPreset('groceries')}
                  disabled={submittingItem}
                  className="p-3 bg-slate-950 border border-slate-800 hover:border-indigo-500 rounded-xl text-left transition-all"
                >
                  <p className="text-xs font-bold text-white">🍚 Staples & Oils</p>
                  <p className="text-[10px] text-slate-400 mt-1">Rice, Mustard Oil, Dals</p>
                </button>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 text-[11px] text-slate-400">
              <p className="font-semibold text-slate-300 mb-1">CSV Bulk File Format:</p>
              <code>product_name, price, is_available, categories</code>
              <p className="mt-1">
                Multiple categories can be comma-separated. The system links all categories without duplicating product records.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ACCEPT & QUOTE PRICE MODAL */}
      {/* ========================================================================= */}
      {activeQuoteDemand && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setActiveQuoteDemand(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-white mb-1 flex items-center space-x-2">
              <Send className="w-5 h-5 text-emerald-400" />
              <span>Submit Official Itemized Quote</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Break down the bill and dispatch your formal quote to the buyer.
            </p>

            <form onSubmit={handleSubmitQuote} className="space-y-4">
              {/* Buyer Requirement Recap */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Customer Demand:
                </p>
                <p className="text-xs text-slate-200">"{activeQuoteDemand.requirement.raw_text}"</p>
              </div>

              {/* Itemized Line Items Breakdown */}
              <div>
                <p className="text-xs font-bold text-slate-300 mb-2">Itemized Bill Breakdown:</p>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                  {lineItems.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800 text-xs"
                    >
                      <span className="text-slate-200 font-medium">{item.product_name}</span>
                      <div className="flex items-center space-x-2 font-mono">
                        <span className="text-slate-400">Qty: {item.quantity}</span>
                        <span className="text-emerald-400 font-bold">₹{item.total.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quote Total Price */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Total Quote Amount (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={quotePrice}
                    onChange={(e) => setQuotePrice(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white font-bold font-mono focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Turnaround Time
                  </label>
                  <select
                    value={deliveryMinutes}
                    onChange={(e) => setDeliveryMinutes(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="15">⚡ 15 mins</option>
                    <option value="20">⚡ 20 mins</option>
                    <option value="30">30 mins</option>
                    <option value="45">45 mins</option>
                  </select>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Fulfillment Notes & Guarantee
                </label>
                <textarea
                  rows={2}
                  value={quoteNotes}
                  onChange={(e) => setQuoteNotes(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-white resize-none focus:outline-none focus:border-emerald-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setActiveQuoteDemand(null)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingQuote}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-emerald-600/20"
                >
                  {submittingQuote ? 'Submitting Quote...' : 'Dispatch Quote to Customer 🚀'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
