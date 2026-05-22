import { cn } from "@/lib/utils";
import { ReactNode } from "react";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("bg-white rounded-2xl shadow-sm border border-gray-100 p-6", className)}>
      {children}
    </div>
  );
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-base font-semibold text-gray-700 mb-1">{children}</h3>;
}

export function CardValue({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("text-2xl font-bold text-gray-900", className)}>{children}</p>;
}
