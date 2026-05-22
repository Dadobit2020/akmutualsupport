import { cn } from "@/lib/utils";
import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, id, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={id} className="text-sm font-medium text-gray-700">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={id}
          {...props}
          className={cn(
            "w-full px-3 py-2 border rounded-xl text-sm text-gray-900",
            "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-transparent",
            "disabled:bg-gray-50 disabled:cursor-not-allowed",
            error ? "border-red-400" : "border-gray-300",
            className
          )}
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";
