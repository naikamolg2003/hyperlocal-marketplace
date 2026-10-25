/**
 * API Service Client for Hyperlocal Marketplace FastAPI Backend.
 * Communicates with backend at http://localhost:8000 by default.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: `HTTP error ${response.status}: ${response.statusText}` };
      }
      let detailMsg = errorData.detail;
      if (Array.isArray(detailMsg)) {
        detailMsg = detailMsg.map((d) => d.msg || JSON.stringify(d)).join('; ');
      } else if (typeof detailMsg === 'object' && detailMsg !== null) {
        detailMsg = JSON.stringify(detailMsg);
      }
      throw new Error(detailMsg || 'API request failed');
    }

    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (err) {
    console.error(`[API Error] ${options.method || 'GET'} ${url}:`, err);
    throw err;
  }
}

export const api = {
  // Health & System
  getHealth: () => request('/health'),
  getRoot: () => request('/'),

  // Customer Requirements & AI Geospatial Pipeline
  submitRequirement: (payload) =>
    request('/requirements/submit', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getNearbyRequirements: (params) => {
    const query = new URLSearchParams(params).toString();
    return request(`/api/v1/requirements/nearby?${query}`);
  },

  updateRequirementStatus: (id, status) =>
    request(`/api/v1/requirements/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  // Inventory Management
  getNearbyItems: (params) => {
    const query = new URLSearchParams(params).toString();
    return request(`/api/v1/items/nearby?${query}`);
  },

  getSellerItems: (sellerId) => request(`/api/v1/items/seller/${sellerId}`),

  createItem: (itemData) =>
    request('/api/v1/items', {
      method: 'POST',
      body: JSON.stringify(itemData),
    }),

  bulkUploadItems: (payload) =>
    request('/api/v1/items/bulk', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateItem: (itemId, updateData) =>
    request(`/api/v1/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(updateData),
    }),

  toggleItemAvailability: (itemId, isAvailable) =>
    request(`/api/v1/items/${itemId}/availability`, {
      method: 'PATCH',
      body: JSON.stringify({ is_available: isAvailable }),
    }),

  deleteItem: (itemId) =>
    request(`/api/v1/items/${itemId}`, {
      method: 'DELETE',
    }),

  // Orders, Quotes & Escrow Payment Loop
  submitOrderQuote: (quoteData) =>
    request('/api/v1/orders/quote', {
      method: 'POST',
      body: JSON.stringify(quoteData),
    }),

  getRequirementQuotes: (requirementId) =>
    request(`/api/v1/orders/requirement/${requirementId}`),

  // Dedicated Vendor Quotations Endpoints
  submitVendorQuotation: (payload) =>
    request('/quotations/submit', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getRequirementVendorQuotations: (requirementId) =>
    request(`/requirements/${requirementId}/quotations`),

  // Order Acceptance & Delivery Status Lifecycle
  acceptQuote: (payload) =>
    request('/orders/accept-quote', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateOrderStatus: (orderId, statusData) =>
    request(`/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify(statusData),
    }),

  getOrder: (orderId) => request(`/orders/${orderId}`),

  getSellerOrders: (sellerId) => request(`/api/v1/orders/seller/${sellerId}`),

  getSellerBroadcasts: (sellerId, radiusKm = 3.0) =>
    request(`/requirements/broadcasts/seller/${sellerId}?radius_km=${radiusKm}`),

  payAndSettleOrder: (orderId, paymentData = { payment_method: 'upi' }) =>
    request(`/api/v1/orders/${orderId}/pay`, {
      method: 'POST',
      body: JSON.stringify(paymentData),
    }),

  // Billing & Freemium Platform Fee
  getSellerBillingStatus: (sellerId) =>
    request(`/api/v1/billing/seller/${sellerId}/status`),

  paySellerPlatformFee: (sellerId, payload = { amount: 1000.0, payment_method: 'upi' }) =>
    request(`/api/v1/billing/seller/${sellerId}/pay`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Users
  getUsers: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/api/v1/users?${query}`);
  },

  createUser: (userData) =>
    request('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),
};
