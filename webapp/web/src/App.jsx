import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { getMeta, runQuery } from "./api.js";

const DIMENSIONS = [
  ["zone", "Zone"],
  ["region", "Region"],
  ["chapter_type", "Type"],
  ["country", "Country"],
];
const EMPTY = { zone: [], region: [], chapter_type: [], country: [] };

function FilterGroup({ label, dim, options, selected, onToggle }) {
  return (
    <div className="filter-group">
      <div className="filter-label">{label}</div>
      <div className="filter-options">
        {options.map((opt) => (
          <label key={opt} className="opt">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onChange={() => onToggle(dim, opt)}
            />
            <span>{opt}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState(EMPTY);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMeta().then(setMeta).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!meta) return;
    runQuery(filters).then(setResult).catch((e) => setError(e.message));
  }, [filters, meta]);

  const toggle = (dim, opt) =>
    setFilters((f) => {
      const has = f[dim].includes(opt);
      return { ...f, [dim]: has ? f[dim].filter((x) => x !== opt) : [...f[dim], opt] };
    });

  const applyRecipe = (recipe) =>
    setFilters({ ...EMPTY, ...Object.fromEntries(
      DIMENSIONS.map(([d]) => [d, recipe.filters[d] || []])
    )});

  const downloadTxt = () => {
    const blob = new Blob([(result?.names || []).join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "chapters.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const center = useMemo(() => [20, -40], []);

  if (error) return <div className="error">Error: {error}</div>;
  if (!meta) return <div className="loading">Loading…</div>;

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>NSBE Chapters</h1>
        <p className="snap">
          {meta.snapshot_date} · {meta.total} active
        </p>
        <h2>Saved recipes</h2>
        {meta.recipes.map((r) => (
          <button key={r.name} className="recipe" onClick={() => applyRecipe(r)}>
            {r.name}
          </button>
        ))}
        <button className="clear" onClick={() => setFilters(EMPTY)}>
          Clear filters
        </button>
      </aside>

      <main className="content">
        <div className="filters">
          {DIMENSIONS.map(([dim, label]) => (
            <FilterGroup
              key={dim}
              dim={dim}
              label={label}
              options={meta.options[dim]}
              selected={filters[dim]}
              onToggle={toggle}
            />
          ))}
        </div>

        <div className="metric">
          <strong>{result?.count ?? 0}</strong> chapters match
          {result && result.mapped < result.count
            ? ` · ${result.count - result.mapped} not mappable`
            : ""}
        </div>

        <div className="map-wrap">
          <MapContainer center={center} zoom={2} scrollWheelZoom style={{ height: "100%" }}>
            <TileLayer
              attribution='&copy; OpenStreetMap'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {(result?.points || []).map((p, i) => (
              <CircleMarker
                key={i}
                center={[p.lat, p.lon]}
                radius={5}
                pathOptions={{ color: "#c81e50", fillOpacity: 0.6 }}
              >
                <Popup>
                  <strong>{p.name}</strong>
                  <br />
                  {[p.city, p.state, p.country].filter(Boolean).join(", ")}
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        <div className="list-head">
          <h2>Chapters ({result?.names?.length ?? 0})</h2>
          <button onClick={downloadTxt} disabled={!result?.names?.length}>
            Download .txt
          </button>
        </div>
        <ul className="chapter-list">
          {(result?.names || []).map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </main>
    </div>
  );
}
