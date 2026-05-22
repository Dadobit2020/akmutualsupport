"use client";

import Script from "next/script";

const FORM_ID = "137fb36c-d645-4d7d-abda-810d89026428";

export function TithelyButton({ label = "Make a Payment" }: { label?: string }) {
  return (
    <>
      <Script
        src="https://static.tithely.com/give/give.js"
        strategy="lazyOnload"
      />
      {/* give.js looks for class="tithely-give-button" + data-form to open the modal */}
      <button
        className="tithely-give-button w-full"
        data-form={FORM_ID}
        style={{
          backgroundColor: "#15803d",
          color: "white",
          fontWeight: 600,
          fontSize: "0.875rem",
          padding: "12px 24px",
          borderRadius: "12px",
          cursor: "pointer",
          border: "none",
          display: "block",
          textAlign: "center",
          fontFamily: "inherit",
        }}
      >
        {label}
      </button>
    </>
  );
}
