import React from 'react';
import { ReportViewer } from '@/components/ReportViewer';

export default function ReportsPage() {
  return (
    <div className="space-y-8 animate-in fade-in duration-700 max-w-5xl mx-auto">
      <header className="mb-10 text-center">
        <h1 className="text-4xl font-light tracking-tight mb-2">
          Model <span className="font-['Reenie_Beanie'] text-5xl text-[var(--accent-coral)]">Reports</span>
        </h1>
        <p className="text-[var(--text-muted)]">View detailed execution reports and generated diagnostic graphs.</p>
      </header>

      <ReportViewer />
    </div>
  );
}
