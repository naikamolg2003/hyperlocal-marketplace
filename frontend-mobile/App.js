import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  ActivityIndicator,
  Modal,
  Alert,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';

import { DEFAULT_API_URL, PRESET_LOCATIONS } from './src/config';
import { submitRequirement, checkBackendHealth } from './src/api';

const QUICK_PROMPTS = [
  'Need 2 packets of milk and fresh cilantro delivered quickly',
  '1kg organic sugar, 500g paneer, and 6 free-range eggs',
  'Crocin 650mg and 2 rolls of sterile cotton bandage urgent',
];

export default function App() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [backendHealthy, setBackendHealthy] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [tempApiUrl, setTempApiUrl] = useState(DEFAULT_API_URL);

  // Customer Input State
  const [rawText, setRawText] = useState('');
  const [selectedLocation, setSelectedLocation] = useState(PRESET_LOCATIONS[0]);
  const [customLat, setCustomLat] = useState('18.5987');
  const [customLon, setCustomLon] = useState('73.7660');
  const [showCustomCoords, setShowCustomCoords] = useState(false);

  // Submission & Result State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // Health check on mount
  useEffect(() => {
    pingBackend(apiUrl);
  }, [apiUrl]);

  const pingBackend = async (url) => {
    try {
      await checkBackendHealth(url);
      setBackendHealthy(true);
    } catch (_) {
      setBackendHealthy(false);
    }
  };

  const handleSelectLocation = (loc) => {
    setSelectedLocation(loc);
    if (loc.id === 'custom') {
      setShowCustomCoords(true);
    } else {
      setShowCustomCoords(false);
      setCustomLat(loc.latitude.toString());
      setCustomLon(loc.longitude.toString());
    }
  };

  const handleSubmit = async () => {
    if (!rawText.trim()) {
      Alert.alert('Empty Requirement', 'Please type what you need before broadcasting.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const lat = selectedLocation.id === 'custom' ? parseFloat(customLat) : selectedLocation.latitude;
    const lon = selectedLocation.id === 'custom' ? parseFloat(customLon) : selectedLocation.longitude;

    if (isNaN(lat) || isNaN(lon)) {
      Alert.alert('Invalid Location', 'Please provide valid latitude and longitude numbers.');
      setLoading(false);
      return;
    }

    try {
      const response = await submitRequirement({
        rawText,
        latitude: lat,
        longitude: lon,
        radiusKm: 3.0,
        customerName: 'Mobile Customer',
        apiUrl,
      });
      setResult(response);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to submit requirement. Check your backend connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setRawText('');
    setError(null);
  };

  const items = result?.parsed_requirement?.items || [];
  const urgency = result?.parsed_requirement?.urgency || 'medium';
  const additionalNotes = result?.parsed_requirement?.additional_notes;
  const matchSummary = result?.matching_summary;
  const sellers = matchSummary?.sellers || [];

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          style={styles.container}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Top Brand Bar */}
          <View style={styles.header}>
            <View>
              <View style={styles.brandRow}>
                <Text style={styles.logoBadge}>⚡ HYPERLOCAL</Text>
                <TouchableOpacity
                  style={[
                    styles.statusPill,
                    backendHealthy === true ? styles.statusOnline : styles.statusOffline,
                  ]}
                  onPress={() => {
                    setTempApiUrl(apiUrl);
                    setShowConfigModal(true);
                  }}
                >
                  <View
                    style={[
                      styles.statusDot,
                      { backgroundColor: backendHealthy === true ? '#10B981' : '#EF4444' },
                    ]}
                  />
                  <Text style={styles.statusText}>
                    {backendHealthy === true ? 'Backend Connected' : 'Offline / Tap to Fix'}
                  </Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.headerTitle}>Reverse Demand Engine</Text>
              <Text style={styles.headerSubtitle}>
                State what you need. AI parses your list & broadcasts to shops within 3 km.
              </Text>
            </View>
          </View>

          {/* Location Selector Card */}
          <View style={styles.card}>
            <Text style={styles.sectionLabel}>📍 YOUR CURRENT LOCATION (3 KM RADIUS)</Text>
            <View style={styles.chipsRow}>
              {PRESET_LOCATIONS.map((loc) => {
                const isActive = selectedLocation.id === loc.id;
                return (
                  <TouchableOpacity
                    key={loc.id}
                    style={[styles.locationChip, isActive && styles.locationChipActive]}
                    onPress={() => handleSelectLocation(loc)}
                  >
                    <Text
                      style={[
                        styles.locationChipText,
                        isActive && styles.locationChipTextActive,
                      ]}
                    >
                      {loc.name}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {showCustomCoords ? (
              <View style={styles.coordsInputRow}>
                <View style={{ flex: 1, marginRight: 8 }}>
                  <Text style={styles.coordLabel}>Latitude</Text>
                  <TextInput
                    style={styles.coordInput}
                    value={customLat}
                    onChangeText={setCustomLat}
                    keyboardType="numeric"
                    placeholder="18.5987"
                    placeholderTextColor="#64748B"
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.coordLabel}>Longitude</Text>
                  <TextInput
                    style={styles.coordInput}
                    value={customLon}
                    onChangeText={setCustomLon}
                    keyboardType="numeric"
                    placeholder="73.7660"
                    placeholderTextColor="#64748B"
                  />
                </View>
              </View>
            ) : (
              <Text style={styles.selectedLocationDetail}>
                Target: {selectedLocation.subtitle} ({selectedLocation.latitude.toFixed(4)},{' '}
                {selectedLocation.longitude.toFixed(4)})
              </Text>
            )}
          </View>

          {/* Natural Language Requirement Input */}
          <View style={styles.card}>
            <View style={styles.labelRow}>
              <Text style={styles.sectionLabel}>💬 WHAT DO YOU NEED TODAY?</Text>
              {rawText.length > 0 && (
                <TouchableOpacity onPress={() => setRawText('')}>
                  <Text style={styles.clearBtnText}>Clear</Text>
                </TouchableOpacity>
              )}
            </View>

            <TextInput
              style={styles.textArea}
              placeholder="Type anything naturally in English, Hindi, or Hinglish... e.g., 'Need 2 packets of whole milk, fresh coriander, and 1kg basmati rice delivered urgently'"
              placeholderTextColor="#64748B"
              multiline
              numberOfLines={4}
              value={rawText}
              onChangeText={setRawText}
              textAlignVertical="top"
            />

            {/* Quick Inspiration Pills */}
            <Text style={styles.quickPromptLabel}>Try a quick prompt:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.quickScroll}>
              {QUICK_PROMPTS.map((prompt, idx) => (
                <TouchableOpacity
                  key={idx}
                  style={styles.quickChip}
                  onPress={() => setRawText(prompt)}
                >
                  <Text style={styles.quickChipText}>✨ {prompt}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Error Banner */}
            {error && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>⚠️ {error}</Text>
              </View>
            )}

            {/* Submit Action */}
            <TouchableOpacity
              style={[styles.primaryButton, loading && styles.buttonDisabled]}
              onPress={handleSubmit}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <View style={styles.buttonLoadingRow}>
                  <ActivityIndicator color="#FFFFFF" size="small" />
                  <Text style={styles.primaryButtonText}> AI Parsing & Scanning 3 km...</Text>
                </View>
              ) : (
                <Text style={styles.primaryButtonText}>🚀 Broadcast Demand to Local Sellers</Text>
              )}
            </TouchableOpacity>
          </View>

          {/* AI Structured Shopping List Summary View */}
          {result && (
            <View style={styles.resultContainer}>
              {/* Broadcast Confirmation Banner */}
              <View style={styles.broadcastBanner}>
                <Text style={styles.broadcastBannerTitle}>
                  📢 Demand Dispatched Successfully!
                </Text>
                <Text style={styles.broadcastBannerSub}>
                  {result.notified_sellers_count}{' '}
                  {result.notified_sellers_count === 1 ? 'merchant' : 'merchants'} within 3 km
                  received your instant broadcast.
                </Text>
                <View style={styles.statusRow}>
                  <View style={styles.badgeBroadcasting}>
                    <Text style={styles.badgeBroadcastingText}>
                      ● {result.status.toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.badgeUrgency}>
                    <Text style={styles.badgeUrgencyText}>
                      Urgency: {urgency.toUpperCase()}
                    </Text>
                  </View>
                </View>
              </View>

              {/* Parsed Shopping List Items */}
              <View style={styles.card}>
                <Text style={styles.sectionLabel}>
                  📋 AI-PARSED STRUCTURED SHOPPING LIST ({items.length} items)
                </Text>
                {items.length === 0 ? (
                  <Text style={styles.emptyItemsText}>No specific items identified.</Text>
                ) : (
                  items.map((item, index) => (
                    <View key={index} style={styles.itemRow}>
                      <View style={styles.itemBullet}>
                        <Text style={styles.itemBulletText}>{index + 1}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.itemName}>{item.product_name}</Text>
                        <View style={styles.itemMetaRow}>
                          <Text style={styles.itemQuantity}>
                            Qty: {item.quantity} {item.unit || ''}
                          </Text>
                          {item.category && (
                            <View style={styles.itemCategoryChip}>
                              <Text style={styles.itemCategoryText}>{item.category}</Text>
                            </View>
                          )}
                        </View>
                      </View>
                    </View>
                  ))
                )}

                {additionalNotes && (
                  <View style={styles.notesBox}>
                    <Text style={styles.notesLabel}>Special Constraints:</Text>
                    <Text style={styles.notesText}>{additionalNotes}</Text>
                  </View>
                )}
              </View>

              {/* Matched Local Merchants (3 km) */}
              <View style={styles.card}>
                <Text style={styles.sectionLabel}>
                  🏪 LOCAL SELLERS IN 3 KM PERIMETER ({sellers.length})
                </Text>
                {sellers.length === 0 ? (
                  <Text style={styles.emptyItemsText}>
                    No sellers found within 3 km of this coordinate.
                  </Text>
                ) : (
                  sellers.map((seller, idx) => (
                    <View key={idx} style={styles.sellerCard}>
                      <View style={styles.sellerHeader}>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.sellerName}>{seller.name}</Text>
                          <Text style={styles.sellerAddress}>
                            📍 {seller.distance_meters.toFixed(0)}m away •{' '}
                            {seller.address || 'Local Merchant'}
                          </Text>
                        </View>
                        <View
                          style={[
                            styles.sellerMatchBadge,
                            seller.fulfillment_percentage >= 100
                              ? styles.badgeFullMatch
                              : styles.badgePartialMatch,
                          ]}
                        >
                          <Text style={styles.sellerMatchText}>
                            {seller.fulfillment_percentage > 0
                              ? `${seller.fulfillment_percentage}% Match`
                              : 'Nearby'}
                          </Text>
                        </View>
                      </View>

                      {seller.matched_items && seller.matched_items.length > 0 && (
                        <View style={styles.sellerInventoryBox}>
                          <Text style={styles.inventoryTitle}>In-Stock Catalog Matches:</Text>
                          {seller.matched_items.map((inv, i) => (
                            <View key={i} style={styles.inventoryItemRow}>
                              <Text style={styles.inventoryItemName}>• {inv.product_name}</Text>
                              <Text style={styles.inventoryItemPrice}>₹{inv.price.toFixed(2)}</Text>
                            </View>
                          ))}
                        </View>
                      )}

                      <View style={styles.sellerFooter}>
                        <Text style={styles.sellerStatusMessage}>{seller.coverage_summary}</Text>
                        <View style={styles.broadcastPill}>
                          <Text style={styles.broadcastPillText}>
                            {seller.can_receive_broadcasts
                              ? '✓ Broadcast Sent'
                              : '🔒 Subscription Gated'}
                          </Text>
                        </View>
                      </View>
                    </View>
                  ))
                )}
              </View>

              {/* New Search Action */}
              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={handleReset}
                activeOpacity={0.8}
              >
                <Text style={styles.secondaryButtonText}>↺ Submit Another Requirement</Text>
              </TouchableOpacity>
            </View>
          )}

          <View style={styles.footerSpacing} />
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Backend URL Configuration Modal */}
      <Modal
        visible={showConfigModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowConfigModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>⚙️ Backend API Endpoint</Text>
            <Text style={styles.modalSubtitle}>
              Configure the FastAPI server URL (useful for Android Emulators, Expo Go, or LAN):
            </Text>

            <TextInput
              style={styles.modalInput}
              value={tempApiUrl}
              onChangeText={setTempApiUrl}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="http://localhost:8000"
              placeholderTextColor="#64748B"
            />

            <View style={styles.modalHelperRow}>
              <TouchableOpacity
                style={styles.modalChip}
                onPress={() => setTempApiUrl('http://localhost:8000')}
              >
                <Text style={styles.modalChipText}>localhost:8000</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalChip}
                onPress={() => setTempApiUrl('http://10.0.2.2:8000')}
              >
                <Text style={styles.modalChipText}>10.0.2.2 (Android)</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.modalButtonRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setShowConfigModal(false)}
              >
                <Text style={styles.modalCancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSaveBtn}
                onPress={() => {
                  setApiUrl(tempApiUrl.trim());
                  setShowConfigModal(false);
                }}
              >
                <Text style={styles.modalSaveBtnText}>Save & Reconnect</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0B0F19',
  },
  container: {
    flex: 1,
    backgroundColor: '#0B0F19',
  },
  scrollContent: {
    padding: 16,
    paddingTop: Platform.OS === 'android' ? 36 : 12,
  },
  header: {
    marginBottom: 16,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  logoBadge: {
    color: '#818CF8',
    fontWeight: '800',
    fontSize: 12,
    letterSpacing: 1.5,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: '#1E293B',
  },
  statusOnline: {
    borderColor: '#065F46',
    borderWidth: 1,
  },
  statusOffline: {
    borderColor: '#991B1B',
    borderWidth: 1,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  statusText: {
    color: '#CBD5E1',
    fontSize: 10,
    fontWeight: '600',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#F8FAFC',
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#94A3B8',
    marginTop: 4,
    lineHeight: 18,
  },
  card: {
    backgroundColor: '#111827',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderColor: '#1E293B',
    borderWidth: 1,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#94A3B8',
    letterSpacing: 1,
    marginBottom: 10,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  locationChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
  },
  locationChipActive: {
    backgroundColor: '#4338CA',
    borderColor: '#6366F1',
  },
  locationChipText: {
    fontSize: 12,
    color: '#94A3B8',
    fontWeight: '600',
  },
  locationChipTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  selectedLocationDetail: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 4,
  },
  coordsInputRow: {
    flexDirection: 'row',
    marginTop: 8,
  },
  coordLabel: {
    fontSize: 10,
    color: '#94A3B8',
    marginBottom: 4,
  },
  coordInput: {
    backgroundColor: '#1E293B',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    color: '#F8FAFC',
    fontSize: 13,
    borderColor: '#334155',
    borderWidth: 1,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  clearBtnText: {
    fontSize: 11,
    color: '#F43F5E',
    fontWeight: '600',
  },
  textArea: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 12,
    color: '#F8FAFC',
    fontSize: 14,
    lineHeight: 20,
    borderColor: '#334155',
    borderWidth: 1,
    minHeight: 90,
  },
  quickPromptLabel: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 12,
    marginBottom: 6,
  },
  quickScroll: {
    marginBottom: 14,
  },
  quickChip: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 8,
    borderColor: '#334155',
    borderWidth: 1,
  },
  quickChipText: {
    color: '#94A3B8',
    fontSize: 11,
  },
  primaryButton: {
    backgroundColor: '#4F46E5',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#4F46E5',
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 4,
  },
  buttonDisabled: {
    backgroundColor: '#3730A3',
    opacity: 0.7,
  },
  buttonLoadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
  errorBox: {
    backgroundColor: '#450A0A',
    borderColor: '#991B1B',
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  errorText: {
    color: '#FCA5A5',
    fontSize: 12,
  },
  resultContainer: {
    marginTop: 8,
  },
  broadcastBanner: {
    backgroundColor: '#1E1B4B',
    borderColor: '#6366F1',
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  broadcastBannerTitle: {
    color: '#A5B4FC',
    fontSize: 16,
    fontWeight: '800',
    marginBottom: 4,
  },
  broadcastBannerSub: {
    color: '#CBD5E1',
    fontSize: 13,
    marginBottom: 12,
    lineHeight: 18,
  },
  statusRow: {
    flexDirection: 'row',
    gap: 8,
  },
  badgeBroadcasting: {
    backgroundColor: '#064E3B',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeBroadcastingText: {
    color: '#34D399',
    fontSize: 10,
    fontWeight: '700',
  },
  badgeUrgency: {
    backgroundColor: '#78350F',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeUrgencyText: {
    color: '#FBBF24',
    fontSize: 10,
    fontWeight: '700',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomColor: '#1E293B',
    borderBottomWidth: 1,
  },
  itemBullet: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#312E81',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  itemBulletText: {
    color: '#A5B4FC',
    fontSize: 11,
    fontWeight: '700',
  },
  itemName: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '600',
  },
  itemMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 2,
  },
  itemQuantity: {
    color: '#94A3B8',
    fontSize: 11,
  },
  itemCategoryChip: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  itemCategoryText: {
    color: '#CBD5E1',
    fontSize: 10,
  },
  notesBox: {
    marginTop: 10,
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#0F172A',
  },
  notesLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#64748B',
  },
  notesText: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 2,
  },
  emptyItemsText: {
    color: '#64748B',
    fontSize: 12,
    fontStyle: 'italic',
  },
  sellerCard: {
    backgroundColor: '#0F172A',
    borderColor: '#1E293B',
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
  },
  sellerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  sellerName: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '700',
  },
  sellerAddress: {
    color: '#64748B',
    fontSize: 11,
    marginTop: 2,
  },
  sellerMatchBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeFullMatch: {
    backgroundColor: '#064E3B',
  },
  badgePartialMatch: {
    backgroundColor: '#1E293B',
  },
  sellerMatchText: {
    color: '#34D399',
    fontSize: 10,
    fontWeight: '700',
  },
  sellerInventoryBox: {
    marginTop: 8,
    padding: 8,
    borderRadius: 6,
    backgroundColor: '#1E293B',
  },
  inventoryTitle: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '700',
    marginBottom: 4,
  },
  inventoryItemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginVertical: 1,
  },
  inventoryItemName: {
    color: '#CBD5E1',
    fontSize: 11,
  },
  inventoryItemPrice: {
    color: '#34D399',
    fontSize: 11,
    fontWeight: '600',
  },
  sellerFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 6,
    borderTopColor: '#1E293B',
    borderTopWidth: 1,
  },
  sellerStatusMessage: {
    color: '#64748B',
    fontSize: 10,
    flex: 1,
  },
  broadcastPill: {
    backgroundColor: '#312E81',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  broadcastPillText: {
    color: '#A5B4FC',
    fontSize: 9,
    fontWeight: '700',
  },
  secondaryButton: {
    backgroundColor: '#1E293B',
    borderColor: '#334155',
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 20,
  },
  secondaryButtonText: {
    color: '#CBD5E1',
    fontSize: 13,
    fontWeight: '600',
  },
  footerSpacing: {
    height: 40,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 20,
    borderColor: '#334155',
    borderWidth: 1,
  },
  modalTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 6,
  },
  modalSubtitle: {
    color: '#94A3B8',
    fontSize: 12,
    marginBottom: 14,
    lineHeight: 16,
  },
  modalInput: {
    backgroundColor: '#0F172A',
    borderColor: '#475569',
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    color: '#F8FAFC',
    fontSize: 13,
    marginBottom: 10,
  },
  modalHelperRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  modalChip: {
    backgroundColor: '#334155',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  modalChipText: {
    color: '#94A3B8',
    fontSize: 10,
  },
  modalButtonRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  modalCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  modalCancelBtnText: {
    color: '#94A3B8',
    fontSize: 13,
  },
  modalSaveBtn: {
    backgroundColor: '#4F46E5',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  modalSaveBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
});
