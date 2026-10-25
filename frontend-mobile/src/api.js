import { DEFAULT_API_URL } from './config';

/**
 * Health check probe to ensure backend connectivity.
 */
export async function checkBackendHealth(apiUrl = DEFAULT_API_URL) {
  try {
    const res = await fetch(`${apiUrl}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Health check failed:', err);
    throw err;
  }
}

/**
 * Submits raw customer requirement text for AI parsing and 3km PostGIS radius matching.
 */
export async function submitRequirement({
  rawText,
  latitude,
  longitude,
  radiusKm = 3.0,
  customerName = 'Mobile Customer',
  customerPhone = null,
  apiUrl = DEFAULT_API_URL,
}) {
  const payload = {
    raw_text: rawText,
    latitude: Number(latitude),
    longitude: Number(longitude),
    radius_km: Number(radiusKm),
    customer_name: customerName,
    customer_phone: customerPhone,
  };

  const res = await fetch(`${apiUrl}/requirements/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    let detail = errorText;
    try {
      const parsed = JSON.parse(errorText);
      detail = parsed.detail || errorText;
    } catch (_) {}
    throw new Error(detail);
  }

  return await res.json();
}

/**
 * Fetches seller billing and freemium subscription quota status.
 */
export async function getSellerBillingStatus(sellerId, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/api/v1/billing/seller/${sellerId}/status`);
  if (!res.ok) throw new Error(`Failed to fetch seller status: ${res.status}`);
  return await res.json();
}

/**
 * Simulates Rs. 1,000 monthly platform fee payment to unlock broadcasts.
 */
export async function paySellerPlatformFee(sellerId, amount = 1000.0, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/api/v1/billing/seller/${sellerId}/pay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, payment_method: 'upi' }),
  });
  if (!res.ok) throw new Error(`Payment failed: ${res.status}`);
  return await res.json();
}

/**
 * Fetches vendor quotations for a customer requirement.
 */
export async function getRequirementQuotes(requirementId, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/requirements/${requirementId}/quotations`);
  if (!res.ok) throw new Error(`Failed to fetch quotes: ${res.status}`);
  return await res.json();
}

/**
 * Customer accepts a specific vendor quote, transitioning order to ACCEPTED.
 */
export async function acceptQuote(quotationId, notes = null, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/orders/accept-quote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quotation_id: quotationId, notes }),
  });
  if (!res.ok) throw new Error(`Failed to accept quote: ${res.status}`);
  return await res.json();
}

/**
 * Updates order delivery lifecycle status (e.g. OUT_FOR_DELIVERY, COMPLETED).
 */
export async function updateOrderStatus(orderId, status, notes = null, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/orders/${orderId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, notes }),
  });
  if (!res.ok) throw new Error(`Failed to update status: ${res.status}`);
  return await res.json();
}

/**
 * Retrieves order details by UUID.
 */
export async function getOrder(orderId, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/orders/${orderId}`);
  if (!res.ok) throw new Error(`Failed to get order: ${res.status}`);
  return await res.json();
}

/**
 * Retrieves completed and active orders for a seller.
 */
export async function getSellerOrders(sellerId, apiUrl = DEFAULT_API_URL) {
  const res = await fetch(`${apiUrl}/orders/seller/${sellerId}`);
  if (!res.ok) throw new Error(`Failed to get seller orders: ${res.status}`);
  return await res.json();
}

