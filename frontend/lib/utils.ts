export function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(" ");
}

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  partially_paid: "Partially Paid",
  paid: "Paid",
  waived: "Waived",
  written_off: "Written Off",
  cancelled: "Cancelled",
};

export const STATUS_COLORS: Record<string, string> = {
  open: "bg-amber-100 text-amber-800",
  partially_paid: "bg-blue-100 text-blue-800",
  paid: "bg-green-100 text-green-800",
  waived: "bg-gray-100 text-gray-600",
  written_off: "bg-gray-100 text-gray-500",
  cancelled: "bg-gray-100 text-gray-500",
};
