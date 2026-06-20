"use client";

import React, { useState, useEffect } from "react";

export default function FieldOperativeHUD() {
  // Mobile device simulated state
  const [activeTask, setActiveTask] = useState({
    title: "Deploy 10 Barricades",
    location: "Richmond Circle Divergence A",
    distance: "150m",
    eta: "3 mins",
    details: "Divert light traffic to double lanes on the Richmond Flyover bypass.",
  });

  const [taskCompleted, setTaskCompleted] = useState(false);

  // Quick Action logs
  const [logs, setLogs] = useState([
    { id: 1, type: "Status", text: "Officer Ramesh K. arrived at Hudson Circle", time: "1 min ago" },
    { id: 2, type: "Deployment", text: "Barricade Set #4 deployed at Kanteerava Venue Gate 2", time: "5 mins ago" },
    { id: 3, type: "Dispatch", text: "Richmond Circle signal manual override active", time: "8 mins ago" },
  ]);

  // Turn-by-turn navigation simulation
  const [navStep, setNavStep] = useState(0);
  const navDirections = [
    "Proceed north on Queens Rd toward Richmond Cir (50m)",
    "Turn left at Richmond Circle toward Bypass Lane (100m)",
    "Arrive at Richmond Circle Divergence A on the left",
  ];

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (!taskCompleted) {
      interval = setInterval(() => {
        setNavStep((step) => (step + 1) % navDirections.length);
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [taskCompleted]);

  // Handle reporting actions
  const handleReport = (reportType: string) => {
    const newLog = {
      id: Date.now(),
      type: "Alert",
      text: `Report: [${reportType}] at Richmond Circle Divergence A`,
      time: "Just now",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  const handleCompleteTask = () => {
    setTaskCompleted(true);
    const completionLog = {
      id: Date.now(),
      type: "Task",
      text: `Task Complete: [${activeTask.title}] at ${activeTask.location}`,
      time: "Just now",
    };
    setLogs((prev) => [completionLog, ...prev]);
  };

  return (
    <div className="flex flex-col items-center gap-6 font-['Outfit'] select-none">
      {/* Page Title info */}
      <div className="text-center">
        <p className="text-xs uppercase tracking-[0.25em] text-[var(--text-muted)] font-medium">Field Operative Hub</p>
        <h1 className="text-3xl font-bold text-[var(--text-main)] mb-1">Operative Mobile HUD</h1>
        <p className="text-xs text-[var(--text-muted)] max-w-md">
          Mobile-first interface designed for boots-on-the-ground officers to report incidents and execute diversions.
        </p>
      </div>

      {/* Simulated iPhone Frame */}
      <div className="relative w-full max-w-[390px] h-[780px] bg-stone-950 rounded-[3rem] border-[10px] border-stone-800 shadow-2xl overflow-hidden flex flex-col">
        {/* Notch */}
        <div className="absolute top-0 left-1/2 transform -translate-x-1/2 w-40 h-6 bg-stone-800 rounded-b-2xl z-50 flex items-center justify-center">
          <div className="w-16 h-1.5 bg-stone-900 rounded-full"></div>
        </div>

        {/* Smartphone Screen Content */}
        <div className="flex-1 flex flex-col bg-[#FDFCF8] overflow-y-auto pt-10 pb-6 px-4 no-scrollbar">
          {/* Header Pill */}
          <div className="flex justify-between items-center bg-stone-100 rounded-2xl px-4 py-3 mb-4 mt-2">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
              <span className="text-[11px] font-bold text-stone-700 uppercase tracking-wider">Officer Connected</span>
            </div>
            <span className="text-[11px] font-bold text-stone-500 font-mono">SECTOR: STADIUM-B</span>
          </div>

          {/* Action HUD / Task Card */}
          {!taskCompleted ? (
            <div className="bg-stone-900 text-white rounded-3xl p-5 shadow-lg relative overflow-hidden mb-4">
              <div className="absolute top-0 right-0 w-24 h-24 bg-orange-500/10 rounded-full -mr-8 -mt-8"></div>
              <div className="flex justify-between items-start mb-3">
                <span className="px-2 py-0.5 rounded bg-orange-500 text-[10px] font-bold uppercase tracking-wider">
                  Active Dispatch
                </span>
                <span className="text-[11px] font-bold text-orange-400 font-mono">ETA: {activeTask.eta}</span>
              </div>
              <h3 className="text-lg font-extrabold tracking-tight mb-1">{activeTask.title}</h3>
              <p className="text-xs text-stone-400 mb-4">{activeTask.location}</p>

              <div className="bg-stone-800 p-3 rounded-2xl mb-4 border border-stone-700">
                <p className="text-[11px] text-stone-300 leading-relaxed">{activeTask.details}</p>
              </div>

              <div className="flex gap-2">
                <div className="flex-1 text-center bg-stone-800 rounded-xl py-2 border border-stone-700 text-xs">
                  <div className="text-[9px] uppercase text-stone-400 font-bold">Distance</div>
                  <div className="font-extrabold">{activeTask.distance}</div>
                </div>
                <button
                  onClick={handleCompleteTask}
                  className="flex-[2] py-2 bg-orange-500 hover:bg-orange-600 active:scale-95 transition-all text-white text-xs font-bold rounded-xl shadow-md"
                >
                  ✓ Complete Task
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-green-600 text-white rounded-3xl p-5 shadow-lg text-center mb-4">
              <span className="text-3xl">🎉</span>
              <h3 className="text-lg font-bold mt-2">All Assigned Tasks Complete</h3>
              <p className="text-xs text-green-100 mt-1">Standing by for next dispatch commands from Command Center.</p>
            </div>
          )}

          {/* Augmented Turn-by-Turn Navigation Simulator */}
          <div className="bg-white border border-stone-100 rounded-3xl p-4 shadow-sm mb-4">
            <h4 className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2">Augmented Navigation HUD</h4>
            <div className="h-32 bg-stone-100 rounded-2xl relative overflow-hidden flex items-center justify-center">
              {/* Mock Street Grid */}
              <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#292524_1px,transparent_1px)] [background-size:16px_16px]"></div>
              {/* Simulated turn arrow */}
              <div className="flex flex-col items-center gap-1 z-10">
                <span className="text-3xl animate-bounce">
                  {navStep === 0 ? "⬆️" : navStep === 1 ? "⬅️" : "📍"}
                </span>
                <span className="text-[10px] font-bold text-stone-800 bg-white/80 backdrop-blur-md px-2 py-1 rounded-full border border-stone-200">
                  {navDirections[navStep]}
                </span>
              </div>
            </div>
          </div>

          {/* One-Tap Incident Reporting Grid */}
          <div className="bg-white border border-stone-100 rounded-3xl p-4 shadow-sm mb-4">
            <h4 className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-3">One-Tap Sector Reporting</h4>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleReport("Road Blocked")}
                className="py-3 bg-red-50 hover:bg-red-100 active:scale-95 transition-all border border-red-100 text-red-700 text-xs font-extrabold rounded-2xl flex flex-col items-center justify-center gap-1"
              >
                <span>🚫</span>
                Road Blocked
              </button>
              <button
                onClick={() => handleReport("Clearance Achieved")}
                className="py-3 bg-green-50 hover:bg-green-100 active:scale-95 transition-all border border-green-100 text-green-700 text-xs font-extrabold rounded-2xl flex flex-col items-center justify-center gap-1"
              >
                <span>✅</span>
                Lane Clear
              </button>
              <button
                onClick={() => handleReport("Personnel Request")}
                className="py-3 bg-blue-50 hover:bg-blue-100 active:scale-95 transition-all border border-blue-100 text-blue-700 text-xs font-extrabold rounded-2xl flex flex-col items-center justify-center gap-1"
              >
                <span>👮</span>
                Request Backup
              </button>
              <button
                onClick={() => handleReport("Accident / Break-down")}
                className="py-3 bg-amber-50 hover:bg-amber-100 active:scale-95 transition-all border border-amber-100 text-amber-700 text-xs font-extrabold rounded-2xl flex flex-col items-center justify-center gap-1"
              >
                <span>⚠️</span>
                Vehicle Stall
              </button>
            </div>
          </div>

          {/* Live Sector Log Feed */}
          <div className="bg-white border border-stone-100 rounded-3xl p-4 shadow-sm flex-1 flex flex-col">
            <h4 className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2">Live Sector Incident Log</h4>
            <div className="flex-1 overflow-y-auto space-y-2.5 max-h-[170px] pr-1">
              {logs.map((log) => (
                <div key={log.id} className="text-[11px] p-2.5 bg-stone-50 border border-stone-100/50 rounded-xl flex flex-col gap-0.5">
                  <div className="flex justify-between items-center">
                    <span
                      className={`font-extrabold text-[9px] uppercase px-1.5 py-0.2 rounded-md ${
                        log.type === "Alert"
                          ? "bg-red-100 text-red-800"
                          : log.type === "Task"
                          ? "bg-green-100 text-green-800"
                          : "bg-stone-200 text-stone-700"
                      }`}
                    >
                      {log.type}
                    </span>
                    <span className="text-[9px] text-stone-400 font-medium">{log.time}</span>
                  </div>
                  <p className="text-stone-600 font-medium leading-tight">{log.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Smartphone Home Bar indicator */}
        <div className="h-6 bg-stone-950 flex items-center justify-center pb-2">
          <div className="w-32 h-1 bg-stone-800 rounded-full"></div>
        </div>
      </div>
    </div>
  );
}
