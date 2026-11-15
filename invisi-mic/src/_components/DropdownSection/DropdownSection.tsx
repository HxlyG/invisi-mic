"use clients"

import { useState } from "react";

interface DropdownSectionProps {
  title: string;
  children: React.ReactNode;
}

export default function DropdownSection({ title, children }: DropdownSectionProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border-b border-[var(--color-studio-700)] py-3">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between text-left font-medium text-[var(--color-chalk)]"
      >
        <span>{title}</span>
        <span>{isOpen ? "−" : "+"}</span>
      </button>

      {isOpen && (
        <div className="mt-2 text-[var(--color-slate-400)]">
          {children}
        </div>
      )}
    </div>
  );
}