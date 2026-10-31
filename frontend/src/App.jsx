import { useState } from "react";
import DecisionView from "./components/DecisionView.jsx";
import AccuracyView from "./components/AccuracyView.jsx";

/**
 * Two tabs, one per business need from the brief:
 *   1. Decision view  - "What is the latest forecast I can use right now?"
 *   2. Accuracy view  - "How much can I trust these forecasts?"
 */
const TABS = [
  { id: "decision", label: "Decision view", component: DecisionView },
  { id: "accuracy", label: "Forecast accuracy", component: AccuracyView },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("decision");
  const Active = TABS.find((t) => t.id === activeTab).component;

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Wind Forecast Monitor</h1>
          <p className="subtitle">
            UK national wind generation · forecasts vs actuals · January 2026 · source: Elexon BMRS
          </p>
        </div>
        <nav className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={tab.id === activeTab ? "tab active" : "tab"}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        <Active />
      </main>

      <footer className="footer">
        Actuals: Elexon FUELHH (fuelType WIND, half-hourly) · Forecasts: Elexon WINDFOR (hourly).
        All times UTC.
      </footer>
    </div>
  );
}
