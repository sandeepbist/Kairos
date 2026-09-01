import React from "react";
import { LegalDocument } from "@/components/LegalDocument";
import { PRIVACY_MD } from "@/lib/legal-content";

export const metadata = {
  title: "Privacy Policy — Kairos",
  description:
    "How a Kairos deployment collects, uses, shares, retains, and deletes data — including LLM processing, connector credentials, and state privacy rights.",
};

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      subtitle="Version 1.0 — adapted from the General Legal template library (CC0). Bracketed placeholders are filled by the deployment operator."
      document={PRIVACY_MD}
    />
  );
}
