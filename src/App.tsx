import React, { useState, useEffect, useMemo } from 'react';
import {
  Activity, TrendingUp, AlertTriangle,
  Map, BarChart3, Eye, Shield, Camera, Clock, Store,
  ChevronRight, ArrowUp, ArrowDown, Minus, RefreshCw,
  Bell, Search, Layers, Upload, Loader2
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts';
import {
  STORES, generateKPIMetrics, generateEvent, EVENT_TYPE_COLORS,
  generateFunnelData, generateHeatmapData, ANOMALIES,
  generateHourlyTraffic, generateZoneDwellData, generateTimeSeriesData,
  type Event, type KPIMetric, type FunnelStep, type HeatmapCell,
  type Anomaly
} from './data/mockData';

type VideoAnalysisResult = {
  store_id: string;
  camera_id: string;
  filename: string;
  duration_seconds: number;
  fps: number;
  frames_processed: number;
  events_generated: number;
  events_ingested: number;
  unique_visitors: number;
  event_type_counts: Record<string, number>;
  zone: string;
};

function VideoUploadPanel({ storeId }: { storeId: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [cameraId, setCameraId] = useState('entry_cam_01');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VideoAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append('file', file);
    form.append('store_id', storeId);
    form.append('camera_id', cameraId);
    form.append('ingest', 'true');
    try {
      const res = await fetch('/detect/analyze', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Analysis failed');
      }
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Upload className="w-4 h-4 text-accent-cyan" />
        <h3 className="text-sm font-semibold">Upload &amp; Analyze Video</h3>
      </div>
      <p className="text-xs text-apex-400 mb-4">
        Apna CCTV clip upload karein — pipeline visitors, zones, aur events detect karegi aur API mein save karegi.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 mb-3">
        <input
          type="file"
          accept="video/mp4,video/webm,video/quicktime,.avi,.mkv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-xs text-apex-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-apex-700 file:text-white"
        />
        <select
          value={cameraId}
          onChange={(e) => setCameraId(e.target.value)}
          className="bg-apex-900 border border-apex-700 rounded-lg px-3 py-2 text-xs text-white"
        >
          <option value="entry_cam_01">Entry camera</option>
          <option value="floor_cam_01">Floor camera</option>
          <option value="billing_cam_01">Billing camera</option>
        </select>
        <button
          type="button"
          disabled={!file || loading}
          onClick={analyze}
          className="px-4 py-2 rounded-lg bg-accent-blue text-white text-xs font-medium disabled:opacity-40 flex items-center justify-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          {loading ? 'Analyzing…' : 'Analyze video'}
        </button>
      </div>
      {error && <p className="text-xs text-accent-red mb-2">{error}</p>}
      {result && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="bg-apex-900 rounded-lg p-3 border border-apex-700/30">
            <p className="text-apex-500">Duration</p>
            <p className="text-lg font-bold">{result.duration_seconds}s</p>
          </div>
          <div className="bg-apex-900 rounded-lg p-3 border border-apex-700/30">
            <p className="text-apex-500">Events</p>
            <p className="text-lg font-bold">{result.events_ingested}</p>
          </div>
          <div className="bg-apex-900 rounded-lg p-3 border border-apex-700/30">
            <p className="text-apex-500">Visitors</p>
            <p className="text-lg font-bold">{result.unique_visitors}</p>
          </div>
          <div className="bg-apex-900 rounded-lg p-3 border border-apex-700/30">
            <p className="text-apex-500">Zone</p>
            <p className="text-lg font-bold capitalize">{result.zone}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Utility ─────────────────────────────────────────────────────
function cn(...classes: (string | false | undefined | null)[]) {
  return classes.filter(Boolean).join(' ');
}

// ─── Animated Counter ────────────────────────────────────────────
function AnimatedValue({ value, suffix = '' }: { value: number | string; suffix?: string }) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    setDisplay(value);
  }, [value]);
  return <span>{display}{suffix}</span>;
}

// ─── Status Badge ────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    online: 'bg-green-500/20 text-green-400 border-green-500/30',
    stale: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    offline: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs border font-medium', colors[status] || colors.online)}>
        <span className={cn(
        'inline-block w-1.5 h-1.5 rounded-full mr-1',
        status === 'online' ? 'bg-green-400 animate-pulse' : '',
        status === 'stale' ? 'bg-amber-400 animate-pulse' : '',
        status === 'offline' ? 'bg-red-400' : '',
      )} />
      {status.toUpperCase()}
    </span>
  );
}

// ─── Severity Badge ──────────────────────────────────────────────
function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    LOW: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    MEDIUM: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return (
    <span className={cn('px-2 py-0.5 rounded text-xs border font-mono', colors[severity])}>
      {severity}
    </span>
  );
}

// ─── KPI Card ────────────────────────────────────────────────────
function KPICard({ metric, index }: { metric: KPIMetric; index: number }) {
  const trendIcon = metric.trend === 'up' ? <ArrowUp className="w-3 h-3" /> :
    metric.trend === 'down' ? <ArrowDown className="w-3 h-3" /> :
    <Minus className="w-3 h-3" />;
  const trendColor = metric.trend === 'up' ? 'text-green-400' :
    metric.trend === 'down' ? 'text-red-400' : 'text-slate-400';

  return (
    <div
      className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4 hover:border-apex-600/80 transition-all duration-300"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-apex-400 uppercase tracking-wider font-medium">{metric.label}</p>
          <p className="text-2xl font-bold mt-1 text-white">
            <AnimatedValue value={metric.value} />
          </p>
        </div>
        <div className="text-2xl">{metric.icon}</div>
      </div>
      <div className={cn('flex items-center gap-1 mt-2 text-xs font-medium', trendColor)}>
        {trendIcon}
        <span>{Math.abs(metric.change)}% vs last hour</span>
      </div>
    </div>
  );
}

// ─── Live Event Stream ───────────────────────────────────────────
function LiveEventStream({ events }: { events: Event[] }) {
  return (
    <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-apex-700/50 flex items-center gap-2">
        <Activity className="w-4 h-4 text-accent-cyan animate-pulse" />
        <h3 className="text-sm font-semibold">Live Event Stream</h3>
        <span className="ml-auto text-xs text-apex-400 font-mono">{events.length} events</span>
      </div>
      <div className="h-80 overflow-y-auto p-2 space-y-1">
        {events.slice(0, 50).map((evt) => (
          <div
            key={evt.event_id}
            className="event-item flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-apex-700/30 transition-colors text-xs"
          >
            <div
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: EVENT_TYPE_COLORS[evt.event_type] || '#64748b' }}
            />
            <span className="font-mono text-apex-400 w-28 truncate">{evt.event_id}</span>
            <span className="font-semibold min-w-[90px]" style={{ color: EVENT_TYPE_COLORS[evt.event_type] || '#94a3b8' }}>
              {evt.event_type}
            </span>
            <span className="text-apex-500 w-20">{evt.zone}</span>
            <span className="text-apex-400 ml-auto">{evt.visitor_id.slice(0, 10)}</span>
            {evt.is_staff && <Shield className="w-3 h-3 text-accent-amber" />}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Funnel Chart ────────────────────────────────────────────────
function FunnelVisualization({ data }: { data: FunnelStep[] }) {
  const maxCount = Math.max(...data.map(d => d.count), 1);

  return (
    <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-accent-purple" />
        <h3 className="text-sm font-semibold">Conversion Funnel</h3>
      </div>
      <div className="space-y-3">
        {data.map((step, i) => {
          const widthPct = (step.count / maxCount) * 100;
          const colors = ['#22c55e', '#a855f7', '#f59e0b', '#10b981'];
          return (
            <div key={step.step} className="animate-slide-in" style={{ animationDelay: `${i * 100}ms` }}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-apex-300 font-medium">{step.step}</span>
                <div className="flex items-center gap-3">
                  <span className="font-bold text-white">{step.count}</span>
                  <span className="text-apex-400">{step.percentage}%</span>
                  {step.drop_off > 0 && (
                    <span className="text-red-400 font-mono">-{step.drop_off}%</span>
                  )}
                </div>
              </div>
              <div className="h-6 bg-apex-900 rounded-md overflow-hidden">
                <div
                  className="h-full rounded-md transition-all duration-1000 ease-out flex items-center px-2"
                  style={{
                    width: `${widthPct}%`,
                    backgroundColor: colors[i] || '#64748b',
                  }}
                >
                  {widthPct > 15 && (
                    <span className="text-xs font-bold text-white/90">{step.count} visitors</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Heatmap Grid ────────────────────────────────────────────────
function HeatmapGrid({ cells }: { cells: HeatmapCell[] }) {
  const cellMap: Record<string, HeatmapCell> = {};
  cells.forEach(c => { cellMap[`${c.x},${c.y}`] = c; });

  return (
    <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <Map className="w-4 h-4 text-accent-cyan" />
        <h3 className="text-sm font-semibold">Store Heatmap</h3>
      </div>
      <div className="grid grid-cols-10 gap-0.5">
        {Array.from({ length: 100 }).map((_, i) => {
          const x = i % 10;
          const y = Math.floor(i / 10);
          const cell = cellMap[`${x},${y}`];
          const intensity = cell?.intensity || 0;
          const hue = 200 - intensity * 180; // blue → red
          const lightness = 15 + intensity * 35;
          return (
            <div
              key={i}
              className="heatmap-cell aspect-square rounded-sm cursor-pointer"
              style={{
                backgroundColor: `hsl(${hue}, 70%, ${lightness}%)`,
                opacity: intensity > 0 ? 0.4 + intensity * 0.6 : 0.15,
              }}
              title={`(${x},${y}) Freq: ${cell?.frequency || 0} | Dwell: ${cell?.avg_dwell_ms || 0}ms`}
            />
          );
        })}
      </div>
      <div className="flex items-center justify-between mt-3 text-xs text-apex-400">
        <span>Low Traffic</span>
        <div className="flex-1 mx-3 h-2 rounded-full bg-gradient-to-r from-blue-900 via-amber-600 to-red-500" />
        <span>High Traffic</span>
      </div>
    </div>
  );
}

// ─── Anomaly Alerts ──────────────────────────────────────────────
function AnomalyPanel({ anomalies }: { anomalies: Anomaly[] }) {
  const severityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
  const sorted = [...anomalies].sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

  return (
    <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-apex-700/50 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-accent-red" />
        <h3 className="text-sm font-semibold">Active Anomalies</h3>
        <span className="ml-auto bg-accent-red/20 text-accent-red px-2 py-0.5 rounded-full text-xs font-bold">
          {anomalies.length}
        </span>
      </div>
      <div className="divide-y divide-apex-700/30 max-h-96 overflow-y-auto">
        {sorted.map((a) => (
          <div key={a.id} className="p-4 hover:bg-apex-700/20 transition-colors">
            <div className="flex items-start gap-3">
              <div className={cn(
                'w-2 h-2 rounded-full mt-1.5 flex-shrink-0',
                a.severity === 'CRITICAL' ? 'bg-red-500 animate-pulse' : '',
                a.severity === 'HIGH' ? 'bg-orange-500 animate-pulse' : '',
                a.severity === 'MEDIUM' ? 'bg-amber-500' : '',
                a.severity === 'LOW' ? 'bg-slate-500' : '',
              )} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono font-bold text-accent-red">{a.type}</span>
                  <SeverityBadge severity={a.severity} />
                </div>
                <p className="text-xs text-apex-300">{a.description}</p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-xs text-accent-amber">→ {a.action_items}</span>
                  <span className="text-xs text-apex-500 ml-auto">{a.detected_at}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Camera Feed Simulation ──────────────────────────────────────
function CameraFeed({ storeName, cameraLabel, index }: { storeName: string; cameraLabel: string; index: number }) {
  const [detections, setDetections] = useState<Array<{ x: number; y: number; w: number; h: number; id: string }>>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      const count = 1 + Math.floor(Math.random() * 4);
      const dets = Array.from({ length: count }, () => ({
        x: 10 + Math.random() * 60,
        y: 10 + Math.random() * 60,
        w: 8 + Math.random() * 12,
        h: 15 + Math.random() * 15,
        id: Math.random().toString(36).substring(2, 6),
      }));
      setDetections(dets);
    }, 1500 + index * 300);
    return () => clearInterval(interval);
  }, [index]);

  return (
    <div className="bg-apex-900 rounded-xl overflow-hidden border border-apex-700/50">
      <div className="camera-feed relative h-40 bg-gradient-to-br from-apex-900 via-apex-800 to-apex-900">
        {/* Simulated floor plan */}
        <div className="absolute inset-4 border border-apex-700/30 rounded-lg">
          {/* Grid lines */}
          <div className="absolute inset-0 grid grid-cols-4 grid-rows-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="border border-apex-700/10" />
            ))}
          </div>
          {/* Detection boxes */}
          {detections.map((d) => (
            <div
              key={d.id}
              className="absolute border-2 border-green-400/80 rounded-sm transition-all duration-1000"
              style={{
                left: `${d.x}%`,
                top: `${d.y}%`,
                width: `${d.w}%`,
                height: `${d.h}%`,
              }}
            >
              <span className="absolute -top-4 left-0 text-[8px] bg-green-500/80 text-white px-1 rounded font-mono">
                {d.id}
              </span>
            </div>
          ))}
        </div>
        {/* Scan line effect */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute inset-x-0 h-px bg-accent-cyan/20"
            style={{ animation: 'scan-line 4s linear infinite', animationDelay: `${index * 0.5}s` }}
          />
        </div>
        {/* Camera label */}
        <div className="absolute top-2 left-2 flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-[10px] font-mono text-white/80 bg-black/40 px-1.5 py-0.5 rounded">
            {cameraLabel}
          </span>
        </div>
        {/* Timestamp */}
        <div className="absolute bottom-2 right-2">
          <span className="text-[10px] font-mono text-white/60 bg-black/40 px-1.5 py-0.5 rounded">
            {new Date().toLocaleTimeString()}
          </span>
        </div>
      </div>
      <div className="px-3 py-2 flex items-center justify-between">
        <span className="text-xs text-apex-300">{storeName}</span>
        <span className="text-[10px] text-accent-green font-mono">{detections.length} detected</span>
      </div>
    </div>
  );
}

// ─── Zone Dwell Chart ────────────────────────────────────────────
function ZoneDwellChart() {
  const data = generateZoneDwellData();
  const COLORS = ['#22c55e', '#a855f7', '#3b82f6', '#f59e0b', '#ef4444'];

  return (
    <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-4 h-4 text-accent-amber" />
        <h3 className="text-sm font-semibold">Avg Dwell by Zone</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
          <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <YAxis type="category" dataKey="zone" tick={{ fill: '#94a3b8', fontSize: 11 }} width={70} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
          />
          <Bar dataKey="avgMinutes" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────
export default function App() {
  const [selectedStore, setSelectedStore] = useState(STORES[0].id);
  const [events, setEvents] = useState<Event[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'analytics' | 'cameras' | 'anomalies'>('overview');
  const [searchQuery, setSearchQuery] = useState('');

  const currentStore = STORES.find(s => s.id === selectedStore)!;
  const kpis = useMemo(() => generateKPIMetrics(selectedStore), [selectedStore]);
  const funnel = useMemo(() => generateFunnelData(selectedStore), [selectedStore]);
  const heatmap = useMemo(() => generateHeatmapData(selectedStore), [selectedStore]);
  const hourlyTraffic = useMemo(() => generateHourlyTraffic(selectedStore), [selectedStore]);
  const [timeSeries, setTimeSeries] = useState(generateTimeSeriesData());

  // Simulate real-time events
  useEffect(() => {
    const interval = setInterval(() => {
      const newEvent = generateEvent(selectedStore);
      setEvents(prev => [newEvent, ...prev].slice(0, 200));
    }, 800 + Math.random() * 1200);
    return () => clearInterval(interval);
  }, [selectedStore]);

  // Update time series
  useEffect(() => {
    const interval = setInterval(() => {
      setTimeSeries(prev => {
        const newData = [...prev.slice(1)];
        newData.push({
          time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
          count: Math.floor(5 + Math.random() * 25),
        });
        return newData;
      });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredAnomalies = ANOMALIES.filter(
    a => !selectedStore || a.store_id === selectedStore
  );

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: BarChart3 },
    { id: 'analytics' as const, label: 'Analytics', icon: TrendingUp },
    { id: 'cameras' as const, label: 'Cameras', icon: Camera },
    { id: 'anomalies' as const, label: 'Anomalies', icon: AlertTriangle },
  ];

  return (
    <div className="min-h-screen bg-apex-900 flex">
      {/* ─── Sidebar ─────────────────────────────────────── */}
      <aside className={cn(
        'bg-apex-800/90 backdrop-blur border-r border-apex-700/50 flex flex-col transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}>
        {/* Logo */}
        <div className="px-4 py-4 border-b border-apex-700/50 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-blue to-accent-cyan flex items-center justify-center flex-shrink-0">
            <Eye className="w-4 h-4 text-white" />
          </div>
          {sidebarOpen && (
            <div className="animate-fade-in">
              <h1 className="text-sm font-bold text-white">Apex Retail</h1>
              <p className="text-[10px] text-apex-400">Intelligence System</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all',
                activeTab === tab.id
                  ? 'bg-accent-blue/15 text-accent-blue font-medium'
                  : 'text-apex-400 hover:text-white hover:bg-apex-700/50'
              )}
            >
              <tab.icon className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span>{tab.label}</span>}
              {tab.id === 'anomalies' && sidebarOpen && (
                <span className="ml-auto bg-accent-red/20 text-accent-red text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {ANOMALIES.length}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Store Selector */}
        {sidebarOpen && (
          <div className="p-3 border-t border-apex-700/50">
            <p className="text-[10px] text-apex-500 uppercase tracking-wider font-medium mb-2">Stores</p>
            <div className="space-y-1">
              {STORES.map(store => (
                <button
                  key={store.id}
                  onClick={() => setSelectedStore(store.id)}
                  className={cn(
                    'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-all',
                    selectedStore === store.id
                      ? 'bg-apex-700/80 text-white'
                      : 'text-apex-400 hover:text-white hover:bg-apex-700/30'
                  )}
                >
                  <Store className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate">{store.name}</span>
                  <StatusBadge status={store.status} />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-3 border-t border-apex-700/50 text-apex-400 hover:text-white transition-colors"
        >
          {sidebarOpen ? <ChevronRight className="w-4 h-4 rotate-180" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </aside>

      {/* ─── Main Content ────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <header className="sticky top-0 z-10 bg-apex-900/90 backdrop-blur border-b border-apex-700/50 px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-lg font-bold">{currentStore.name}</h2>
              <StatusBadge status={currentStore.status} />
              <span className="text-xs text-apex-400">{currentStore.location}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-apex-500" />
                <input
                  type="text"
                  placeholder="Search events..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="bg-apex-800 border border-apex-700/50 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-apex-500 focus:outline-none focus:border-accent-blue/50 w-48"
                />
              </div>
              <button className="relative p-2 text-apex-400 hover:text-white transition-colors">
                <Bell className="w-4 h-4" />
                <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-accent-red rounded-full text-[8px] text-white flex items-center justify-center font-bold">
                  {ANOMALIES.length}
                </span>
              </button>
              <button className="p-2 text-apex-400 hover:text-white transition-colors">
                <RefreshCw className="w-4 h-4" />
              </button>
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-[10px] font-bold">
                AR
              </div>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* ─── Overview Tab ────────────────────────────── */}
          {activeTab === 'overview' && (
            <>
              {/* KPI Grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                {kpis.map((kpi, i) => (
                  <KPICard key={kpi.label} metric={kpi} index={i} />
                ))}
              </div>

              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Real-time Events Chart */}
                <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <Activity className="w-4 h-4 text-accent-green" />
                    <h3 className="text-sm font-semibold">Events Per Minute</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={timeSeries}>
                      <defs>
                        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 10 }} interval={9} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#10b981"
                        strokeWidth={2}
                        fill="url(#areaGrad)"
                        dot={false}
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* Hourly Traffic */}
                <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <BarChart3 className="w-4 h-4 text-accent-blue" />
                    <h3 className="text-sm font-semibold">Hourly Traffic</h3>
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={hourlyTraffic}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                      <XAxis dataKey="hour" tick={{ fill: '#94a3b8', fontSize: 10 }} interval={3} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                      />
                      <Bar dataKey="visitors" fill="#3b82f6" radius={[3, 3, 0, 0]} name="Visitors" />
                      <Bar dataKey="purchases" fill="#10b981" radius={[3, 3, 0, 0]} name="Purchases" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Second Row */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-1">
                  <FunnelVisualization data={funnel} />
                </div>
                <div className="lg:col-span-1">
                  <HeatmapGrid cells={heatmap} />
                </div>
                <div className="lg:col-span-1">
                  <LiveEventStream events={events} />
                </div>
              </div>

              {/* Anomalies */}
              <AnomalyPanel anomalies={filteredAnomalies} />
            </>
          )}

          {/* ─── Analytics Tab ──────────────────────────── */}
          {activeTab === 'analytics' && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <FunnelVisualization data={funnel} />
                <ZoneDwellChart />
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <HeatmapGrid cells={heatmap} />
                <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-accent-cyan" />
                    <h3 className="text-sm font-semibold">Store Comparison</h3>
                  </div>
                  <div className="space-y-3">
                    {STORES.map((store) => {
                      const storeKpis = generateKPIMetrics(store.id);
                      const visitors = storeKpis[0].value as number;
                      const convRate = storeKpis[1].value as string;
                      return (
                        <div
                          key={store.id}
                          onClick={() => setSelectedStore(store.id)}
                          className={cn(
                            'flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all',
                            selectedStore === store.id ? 'bg-apex-700/50 border border-accent-blue/30' : 'hover:bg-apex-700/20'
                          )}
                        >
                          <Store className="w-4 h-4 text-apex-400 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium">{store.name}</p>
                            <p className="text-xs text-apex-500">{store.location}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-bold">{visitors}</p>
                            <p className="text-xs text-apex-400">{convRate} conv</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ─── Cameras Tab ────────────────────────────── */}
          {activeTab === 'cameras' && (
            <>
              <VideoUploadPanel storeId={selectedStore} />
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {STORES.filter(s => s.status === 'online').slice(0, 6).map((store, i) => (
                  <React.Fragment key={store.id}>
                    <CameraFeed storeName={store.name} cameraLabel="ENTRY_CAM" index={i * 3} />
                    <CameraFeed storeName={store.name} cameraLabel="FLOOR_CAM" index={i * 3 + 1} />
                    <CameraFeed storeName={store.name} cameraLabel="BILLING_CAM" index={i * 3 + 2} />
                  </React.Fragment>
                ))}
              </div>
              <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
                <h3 className="text-sm font-semibold mb-4">Detection Pipeline Status</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: 'YOLOv8-n', status: 'Running', fps: '35', latency: '28ms' },
                    { label: 'ByteTrack', status: 'Running', fps: '30', latency: '33ms' },
                    { label: 'OSNet Re-ID', status: 'Running', fps: '25', latency: '40ms' },
                    { label: 'Staff Filter', status: 'Running', fps: '40', latency: '25ms' },
                  ].map((component) => (
                    <div key={component.label} className="bg-apex-900 rounded-lg p-3 border border-apex-700/30">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
                        <span className="text-xs font-mono font-bold">{component.label}</span>
                      </div>
                      <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-apex-500">Status</span>
                          <span className="text-accent-green">{component.status}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-apex-500">FPS</span>
                          <span className="text-white font-mono">{component.fps}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-apex-500">Latency</span>
                          <span className="text-white font-mono">{component.latency}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* ─── Anomalies Tab ──────────────────────────── */}
          {activeTab === 'anomalies' && (
            <div className="space-y-4">
              <AnomalyPanel anomalies={ANOMALIES} />
              <div className="bg-apex-800/80 backdrop-blur border border-apex-700/50 rounded-xl p-4">
                <h3 className="text-sm font-semibold mb-4">Anomaly Summary</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {['BILLING_QUEUE_SPIKE', 'CONVERSION_DROP', 'DEAD_ZONE'].map(type => {
                    const count = ANOMALIES.filter(a => a.type === type).length;
                    const maxSev = ANOMALIES.filter(a => a.type === type).reduce(
                      (max, a) => {
                        const order = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
                        return (order[a.severity] || 0) > max ? order[a.severity] || 0 : max;
                      }, 0
                    );
                    return (
                      <div key={type} className="bg-apex-900 rounded-lg p-4 border border-apex-700/30">
                        <p className="text-xs font-mono text-apex-400 mb-1">{type}</p>
                        <p className="text-2xl font-bold">{count}</p>
                        <div className="flex items-center gap-1 mt-2">
                          <div className={cn(
                            'w-2 h-2 rounded-full',
                            maxSev >= 4 ? 'bg-red-500' : maxSev === 3 ? 'bg-orange-500' : maxSev === 2 ? 'bg-amber-500' : 'bg-slate-500',
                          )} />
                          <span className="text-xs text-apex-500">Max severity</span>
                        </div>
                      </div>
                    );
                  })}
                  <div className="bg-apex-900 rounded-lg p-4 border border-apex-700/30">
                    <p className="text-xs font-mono text-apex-400 mb-1">Total Active</p>
                    <p className="text-2xl font-bold text-accent-red">{ANOMALIES.length}</p>
                    <div className="flex items-center gap-1 mt-2">
                      <AlertTriangle className="w-3 h-3 text-accent-red animate-pulse" />
                      <span className="text-xs text-apex-500">Requires attention</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
