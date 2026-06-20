import React from 'react';

export const SoftCard = ({ children, className = '' }: { children: React.ReactNode, className?: string }) => (
  <div className={`bg-white p-6 shadow-[var(--shadow-soft)] rounded-[var(--radius-card)] border border-stone-100 hover:scale-[1.01] transition-transform duration-500 ${className}`}>
    {children}
  </div>
);
