import { useEffect, useState } from "react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Loader, EmptyState } from "../components/UI";
import { UploadModal } from "./Tasks";

const TABS = ["Brands", "Territories", "Management", "Growth"];
const MONTH_LABELS = { "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec" };

function monthLabel(m) {
  if (!m) return "";
  const [y, mo] = m.split("-");
  return `${MONTH_LABELS[mo] || mo} ${y}`;
}

export default function Performance() {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [months, setMonths] = useState(null);
  const [month, setMonth] = useState(null);
  const [tab, setTab] = useState("Brands");
  const [showUpload, setShowUpload] = useState(false);

  function loadMonths() {
    api.get("/performance/months").then((res) => {
      setMonths(res.data);
      if (!month && res.data.all.length > 0) setMonth(res.data.all[0]);
    }).catch((e) => toast.error(apiErrorMessage(e)));
  }

  useEffect(loadMonths, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ margin: 0 }}>Performance</h1>
        {isAdmin && (
          <button className="btn btn-gold btn-sm" onClick={() => setShowUpload(true)}>Upload Performance Sheet</button>
        )}
      </div>

      {months === null ? (
        <Loader />
      ) : months.all.length === 0 ? (
        <EmptyState text="No performance data uploaded yet." />
      ) : (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
            {months.all.map((m) => (
              <button key={m} className={`chip ${month === m ? "active" : ""}`} onClick={() => setMonth(m)}>
                {monthLabel(m)}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
            {TABS.map((t) => (
              <button key={t} className={`chip ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>

          {tab === "Brands" && <BrandsView month={month} />}
          {tab === "Territories" && <TerritoriesView month={month} />}
          {tab === "Management" && <ManagementView month={month} />}
          {tab === "Growth" && <GrowthView />}
        </>
      )}

      {showUpload && (
        <UploadModal
          endpoint="/performance/upload"
          title="Upload Performance Sheet"
          hint="Auto-detects Brand Performance, Territory Performance, or Management Dashboard format. Multiple month sheets in one workbook are all parsed."
          onClose={() => setShowUpload(false)}
          onDone={loadMonths}
        />
      )}
    </div>
  );
}

function BrandsView({ month }) {
  const toast = useToast();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!month) return;
    setData(null);
    api.get("/performance/brands", { params: { month } }).then((res) => setData(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  if (!data) return <Loader />;
  if (data.items.length === 0) return <EmptyState text="No brand data for this month." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {data.items.map((b) => (
        <div key={b.id} className="card card-pad">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h3 style={{ margin: 0 }}>{b.brand}</h3>
            {b.achievement_pct != null && (
              <span className={`badge ${b.achievement_pct >= 100 ? "badge-completed" : "badge-in_progress"}`}>
                {b.achievement_pct}% achieved
              </span>
            )}
          </div>
          <div style={{ height: 140 }}>
            <ResponsiveContainer>
              <BarChart data={[
                { week: "W1", sales: b.w1 },
                { week: "W2", sales: b.w2 },
                { week: "W3", sales: b.w3 },
                { week: "W4", sales: b.w4 },
              ]}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="sales" fill="#0a6ac2" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px,1fr))", gap: 8, marginTop: 10, fontSize: 12.5 }}>
            <MiniStat label="Target" value={b.target} />
            <MiniStat label="Sales" value={b.sales_total} />
            {b.top_territory && <MiniStat label="Top Territory" value={b.top_territory} />}
            {b.low_territory && <MiniStat label="Low Territory" value={b.low_territory} />}
          </div>
        </div>
      ))}
    </div>
  );
}

function TerritoriesView({ month }) {
  const toast = useToast();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!month) return;
    setData(null);
    api.get("/performance/territories", { params: { month } }).then((res) => setData(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  if (!data) return <Loader />;
  if (data.regions.length === 0) return <EmptyState text="No territory data for this month." />;

  const regionChart = data.regions.map((r) => ({
    region: r.region, Target: r.target_total ?? 0, Sales: r.sales_total ?? 0,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {data.regions.length > 1 && (
        <div className="card card-pad">
          <h3>Target vs Sales by Region</h3>
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={regionChart} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="region" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="Target" fill="#94a3b8" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="Sales" fill="#0a6ac2" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {data.regions.map((r) => {
        const hqChart = r.items.map((it) => ({
          hq: it.hq, Target: it.target ?? 0, Sales: it.sales_total ?? 0,
        }));
        return (
          <div key={r.region} className="card card-pad">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h3 style={{ margin: 0 }}>{r.region}</h3>
              <span className="badge badge-brand">{r.achievement_pct != null ? `${r.achievement_pct}%` : "—"}</span>
            </div>
            <div style={{ height: 200, marginBottom: 12 }}>
              <ResponsiveContainer>
                <BarChart data={hqChart} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="hq" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="Target" fill="#94a3b8" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="Sales" fill="#0a6ac2" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="scroll-x">
              <table className="data-table">
                <thead>
                  <tr><th>HQ</th><th>BE/KAM</th><th>Target</th><th>W1</th><th>W2</th><th>W3</th><th>W4</th><th>Ach %</th></tr>
                </thead>
                <tbody>
                  {r.items.map((it, i) => (
                    <tr key={i}>
                      <td>{it.hq}</td>
                      <td>{it.be_name || "—"}</td>
                      <td>{it.target ?? "—"}</td>
                      <td>{it.w1 ?? "—"}</td>
                      <td>{it.w2 ?? "—"}</td>
                      <td>{it.w3 ?? "—"}</td>
                      <td>{it.w4 ?? "—"}</td>
                      <td>{it.achievement_pct != null ? `${it.achievement_pct}%` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const MGMT_LABELS = {
  primary_sales: "Primary Sales", secondary_sales: "Secondary Sales", run_rate: "Run Rate",
  active_doctors: "Active Doctors", new_prescribers: "New Prescribers",
  top_brand: "Top Brand", lowest_brand: "Lowest Brand", strong_territory: "Strong Territory", weak_territory: "Weak Territory",
};

function ManagementView({ month }) {
  const toast = useToast();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!month) return;
    setData(null);
    api.get("/performance/management", { params: { month } }).then((res) => setData(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  if (!data) return <Loader />;
  if (!data.metrics) return <EmptyState text="No management dashboard data for this month." />;

  const entries = Object.entries(data.metrics);
  const isNumeric = (m) => m.total != null || (m.weeks || []).some((w) => typeof w === "number");
  const numericMetrics = entries.filter(([, m]) => isNumeric(m));
  const textMetrics = entries.filter(([, m]) => !isNumeric(m));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px,1fr))", gap: 14 }}>
        {numericMetrics.map(([key, m]) => {
          const chart = (m.weeks || []).map((w, i) => ({ week: `W${i + 1}`, value: typeof w === "number" ? w : null }));
          return (
            <div key={key} className="card card-pad">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>{MGMT_LABELS[key] || key}</h3>
                {m.total != null && (
                  <span style={{ fontSize: 18, fontWeight: 800, color: "var(--brand-700)" }}>{m.total}</span>
                )}
              </div>
              <div style={{ height: 160 }}>
                <ResponsiveContainer>
                  <LineChart data={chart} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="value" name={MGMT_LABELS[key] || key} stroke="#0a6ac2" strokeWidth={2.5} dot={{ r: 4 }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })}
      </div>

      {textMetrics.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))", gap: 14 }}>
          {textMetrics.map(([key, m]) => (
            <div key={key} className="card card-pad">
              <h3>{MGMT_LABELS[key] || key}</h3>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 13 }}>
                {(m.weeks || []).map((w, i) => (
                  <div key={i}>
                    <div style={{ color: "var(--ink-500)", fontSize: 11 }}>W{i + 1}</div>
                    <div style={{ fontWeight: 700 }}>{w ?? "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GrowthView() {
  const toast = useToast();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/performance/growth").then((res) => setData(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
  }, []);

  if (!data) return <Loader />;
  if (data.brands.length === 0) return <EmptyState text="Not enough data to compute growth yet." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {data.brands.map((b) => (
        <div key={b.brand} className="card card-pad">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h3 style={{ margin: 0 }}>{b.brand}</h3>
            {b.overall_growth_pct != null && (
              <span className={`badge ${b.overall_growth_pct >= 0 ? "badge-completed" : "badge-overdue"}`}>
                {b.overall_growth_pct >= 0 ? "+" : ""}{b.overall_growth_pct}% overall
              </span>
            )}
          </div>
          <div style={{ height: 150 }}>
            <ResponsiveContainer>
              <BarChart data={b.series.map((s) => ({ month: monthLabel(s.month), sales: s.sales }))}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="sales" fill="#c98f12" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 8, fontSize: 12.5 }}>
            {b.series.map((s) => (
              <div key={s.month}>
                <span style={{ color: "var(--ink-500)" }}>{monthLabel(s.month)}: </span>
                <span style={{ fontWeight: 700 }}>
                  {s.growth_pct != null ? `${s.growth_pct >= 0 ? "+" : ""}${s.growth_pct}%` : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div style={{ background: "var(--ink-100)", borderRadius: 8, padding: "6px 10px" }}>
      <div style={{ color: "var(--ink-500)", fontSize: 11 }}>{label}</div>
      <div style={{ fontWeight: 700 }}>{value ?? "—"}</div>
    </div>
  );
}
