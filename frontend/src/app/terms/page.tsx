import React from "react";
import { LegalDocument } from "@/components/LegalDocument";
import { TERMS_MD } from "@/lib/legal-content";

export const metadata = {
  title: "Terms of Service — Kairos",
  description:
    "Terms governing use of a Kairos deployment: access, human approval of executed actions, third-party tools, liability limits, and dispute resolution.",
};

export default function TermsPage() {
  return (
    <LegalDocument
      title="Terms of Service"
      subtitle="Version 1.0 — adapted from the General Legal template library (CC0). Bracketed placeholders are filled by the deployment operator."
      document={TERMS_MD}
    />
  );
}
