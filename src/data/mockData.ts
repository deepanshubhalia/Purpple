// Mock data for the Apex Retail Store Intelligence Dashboard
// Simulates real-time data from the backend API

export interface Store {
  id: string;
  name: string;
  location: string;
  status: 'online' | 'offline' | 'stale';
  lastEvent: string;
}

export interface KPIMetric {
  label: string;
  value: number | string;
  change: number;
  trend: 'up' | 'down' | 'stable';
  icon: string;
  unit?: string;
}

export interface Event {
  event_id: string;
  visitor_id: string;
  store_id: string;
  event_type: string;
  zone: string;
  timestamp: string;
  is_staff: boolean;
  dwell_ms: number;
  confidence: number;
}

export interface FunnelStep {
  step: string;
  count: number;
  percentage: number;
  drop_off: number;
}

export interface HeatmapCell {
  x: number;
  y: number;
  frequency: number;
  avg_dwell_ms: number;
  intensity: number;
}

export interface Anomaly {
  id: string;
  type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  description: string;
  action_items: string;
  store_id: string;
  detected_at: string;
  resolved: boolean;
}

// Store definitions
export const STORES: Store[] = [
  { id: 'store_001', name: 'Apex Downtown', location: 'Manhattan, NY', status: 'online', lastEvent: '2s ago' },
  { id: 'store_002', name: 'Apex Mall', location: 'Brooklyn, NY', status: 'online', lastEvent: '5s ago' },
  { id: 'store_003', name: 'Apex Suburban', location: 'Queens, NY', status: 'online', lastEvent: '3s ago' },
  { id: 'store_004', name: 'Apex Express', location: 'Bronx, NY', status: 'stale', lastEvent: '12m ago' },
  { id: 'store_005', name: 'Apex Premium', location: 'Staten Island, NY', status: 'online', lastEvent: '1s ago' },
];

// KPI data per store
export const generateKPIMetrics = (storeId: string): KPIMetric[] => {
  const seed = storeId.charCodeAt(6) + storeId.charCodeAt(7);
  return [
    { label: 'Unique Visitors', value: 142 + (seed % 50), change: 12.5, trend: 'up', icon: '👥' },
    { label: 'Conversion Rate', value: `${(28 + (seed % 15))}%`, change: 3.2, trend: 'up', icon: '📈' },
    { label: 'Avg Dwell Time', value: `${18 + (seed % 12)}m`, change: -2.1, trend: 'down', icon: '⏱️' },
    { label: 'Queue Depth', value: 2 + (seed % 5), change: 0, trend: 'stable', icon: '🧑‍🤝‍🧑' },
    { label: 'Revenue', value: `$${4200 + seed * 100}`, change: 8.7, trend: 'up', icon: '💰' },
    { label: 'Staff On Floor', value: 3 + (seed % 3), change: 0, trend: 'stable', icon: '👔' },
  ];
};

// Event types with colors
export const EVENT_TYPE_COLORS: Record<string, string> = {
  ENTRY: '#22c55e',
  REENTRY: '#3b82f6',
  ZONE_ENTRY: '#a855f7',
  ZONE_EXIT: '#f59e0b',
  BILLING_QUEUE: '#ef4444',
  BILLING_EXIT: '#ec4899',
  PURCHASE: '#10b981',
  GROUP_ENTRY: '#06b6d4',
};

// Generate live events
const EVENT_TYPES = ['ENTRY', 'REENTRY', 'ZONE_ENTRY', 'ZONE_EXIT', 'BILLING_QUEUE', 'BILLING_EXIT', 'PURCHASE', 'GROUP_ENTRY'];
const ZONES = ['entry', 'floor', 'billing'];

let eventIdCounter = 1000;

export const generateEvent = (storeId?: string): Event => {
  eventIdCounter++;
  const store = storeId || `store_00${1 + Math.floor(Math.random() * 5)}`;
  const eventType = EVENT_TYPES[Math.floor(Math.random() * EVENT_TYPES.length)];
  return {
    event_id: `evt_${eventIdCounter.toString(16)}`,
    visitor_id: `vis_${Math.random().toString(36).substring(2, 10)}`,
    store_id: store,
    event_type: eventType,
    zone: ZONES[Math.floor(Math.random() * ZONES.length)],
    timestamp: new Date().toISOString(),
    is_staff: Math.random() < 0.15,
    dwell_ms: Math.floor(Math.random() * 600000),
    confidence: 0.75 + Math.random() * 0.24,
  };
};

// Funnel data
export const generateFunnelData = (storeId: string): FunnelStep[] => {
  const seed = storeId.charCodeAt(6) + storeId.charCodeAt(7);
  const base = 142 + (seed % 50);
  return [
    { step: 'Entry', count: base, percentage: 100, drop_off: 0 },
    { step: 'Zone Visit', count: Math.floor(base * 0.72), percentage: 72, drop_off: 28 },
    { step: 'Billing Queue', count: Math.floor(base * 0.41), percentage: 41, drop_off: 31 },
    { step: 'Purchase', count: Math.floor(base * 0.31), percentage: 31, drop_off: 10 },
  ];
};

// Heatmap data
export const generateHeatmapData = (storeId: string): HeatmapCell[] => {
  const seed = storeId.charCodeAt(6);
  const cells: HeatmapCell[] = [];
  for (let x = 0; x < 10; x++) {
    for (let y = 0; y < 10; y++) {
      // Create hotspots
      const distToCenter = Math.sqrt((x - 5) ** 2 + (y - 5) ** 2);
      const distToBilling = Math.sqrt((x - 8) ** 2 + (y - 2) ** 2);
      const freq = Math.max(0, Math.floor(
        20 * Math.exp(-distToCenter / 3) +
        15 * Math.exp(-distToBilling / 2) +
        Math.random() * 5 +
        (seed % 3)
      ));
      cells.push({
        x,
        y,
        frequency: freq,
        avg_dwell_ms: Math.floor(30000 + freq * 2000),
        intensity: Math.min(1, freq / 25),
      });
    }
  }
  return cells;
};

// Anomaly data
export const ANOMALIES: Anomaly[] = [
  {
    id: 'ano_001',
    type: 'BILLING_QUEUE_SPIKE',
    severity: 'HIGH',
    description: 'Queue depth at Apex Mall (store_002) reached 8 customers — 3x the average of 2.7',
    action_items: 'Open register #3; redirect floor staff to billing',
    store_id: 'store_002',
    detected_at: '2 min ago',
    resolved: false,
  },
  {
    id: 'ano_002',
    type: 'CONVERSION_DROP',
    severity: 'HIGH',
    description: 'Conversion rate at Apex Downtown (store_001) dropped to 18% from baseline 31%',
    action_items: 'Check stock levels on popular items; review pricing',
    store_id: 'store_001',
    detected_at: '8 min ago',
    resolved: false,
  },
  {
    id: 'ano_003',
    type: 'DEAD_ZONE',
    severity: 'MEDIUM',
    description: 'Zone C (electronics) at Apex Suburban (store_003) has only 2 visits in the last 30 min',
    action_items: 'Review product placement; adjust digital signage',
    store_id: 'store_003',
    detected_at: '15 min ago',
    resolved: false,
  },
  {
    id: 'ano_004',
    type: 'BILLING_QUEUE_SPIKE',
    severity: 'CRITICAL',
    description: 'Queue depth at Apex Express (store_004) reached 12 customers — STALE feed suspected',
    action_items: 'Verify camera feed; open all registers; deploy manager',
    store_id: 'store_004',
    detected_at: '12 min ago',
    resolved: false,
  },
  {
    id: 'ano_005',
    type: 'DEAD_ZONE',
    severity: 'LOW',
    description: 'Zone A (entrance display) at Apex Premium (store_005) shows below-average engagement',
    action_items: 'Update display merchandising; test interactive elements',
    store_id: 'store_005',
    detected_at: '22 min ago',
    resolved: false,
  },
];

// Hourly traffic data for charts
export const generateHourlyTraffic = (storeId: string): { hour: string; visitors: number; purchases: number }[] => {
  const seed = storeId.charCodeAt(6);
  const hours = ['6AM', '7AM', '8AM', '9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM', '4PM', '5PM', '6PM', '7PM', '8PM', '9PM'];
  return hours.map((hour, i) => ({
    hour,
    visitors: Math.floor(10 + Math.sin((i + seed) / 3) * 15 + Math.random() * 10 + 15),
    purchases: Math.floor(3 + Math.sin((i + seed) / 3) * 5 + Math.random() * 5 + 5),
  }));
};

// Zone dwell time data
export const generateZoneDwellData = (): { zone: string; avgMinutes: number; visitors: number }[] => [
  { zone: 'Entrance', avgMinutes: 2.3, visitors: 142 },
  { zone: 'Main Floor', avgMinutes: 14.7, visitors: 102 },
  { zone: 'Electronics', avgMinutes: 8.2, visitors: 45 },
  { zone: 'Clothing', avgMinutes: 11.5, visitors: 38 },
  { zone: 'Billing', avgMinutes: 4.1, visitors: 58 },
];

// Time-series data for real-time chart
export const generateTimeSeriesData = (): { time: string; count: number }[] => {
  const data = [];
  const now = new Date();
  for (let i = 59; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60000);
    data.push({
      time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      count: Math.floor(5 + Math.random() * 25),
    });
  }
  return data;
};
