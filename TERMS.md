# Terms of Service

**Effective Date**: August 27, 2026 • **Master Subscription & License Agreement** (Version 2.4)

## 1. Introduction & Acceptance of Terms
These Terms of Service ("Terms", "Agreement") constitute a legally binding agreement between you ("Customer", "User", or "You") and Kairos Systems Inc. ("Kairos", "we", "us", or "our"), governing your access to and use of the Kairos Ambient Action Agent software, backend orchestration microservices, web dashboards, CLI tools, and Model Context Protocol (MCP) bridges (collectively, the "Service").

BY INSTALLING, DEPLOYING, ACCESSING, OR CLICKING "APPROVE", YOU EXPRESSLY ACKNOWLEDGE AND AGREE TO BE BOUND BY ALL PROVISIONS OF THIS AGREEMENT.

## 2. Architectural Overview & Nature of the Ambient Action Agent
Kairos utilizes Large Language Model (LLM) pipelines, LangGraph state graphs, and Temporal durable workflow orchestration to parse unstructured text inputs, identify prospective action items, calculate routing confidence scores, and format tool-specific payloads.

- **Autonomous Ingestion vs. Execution**: Extraction, candidate scoring, and routing reasoning are autonomous. Side-effect execution against external target systems is strictly contingent upon operator verification.

## 3. Mandatory Human-in-the-Loop (HITL) Verification & Operator Liability
The Service implements a Human-in-the-Loop review workbench designed to prevent unintended side-effects across connected production environments.
- **Verification Obligation**: Generative AI models may produce hallucinations or misinterpret nuance. You assume sole operational and legal responsibility for reviewing, modifying, approving, or rejecting every extracted action item.
- **Execution Authorization**: Clicking "Execute" constitutes your explicit authorization for the Service to transmit the finalized payload to the designated connector.
- **Waiver of Downstream Claims**: Kairos shall not be liable for any consequences, data corruption, unauthorized issue creation, calendar scheduling conflicts, or operational disruptions arising from approved actions.

## 4. Third-Party Integrations & Model Context Protocol (MCP) Connectors
The Service interfaces with third-party software platforms using official APIs and Model Context Protocol servers. You acknowledge that:
- You must hold valid, active accounts in good standing with each connected provider (Atlassian, Notion Labs, Google LLC).
- Kairos does not control, and is not responsible for, rate limiting, service downtime, API deprecations, or modifications imposed by third-party providers.

## 5. OAuth Credential Vault & Cryptographic Key Management
All access tokens, refresh tokens, and API credentials provided to the Service are stored in an internal PostgreSQL database encrypted at rest using AES-256 Fernet symmetric encryption.
- **Operator Key Custody**: In self-hosted deployments, you are solely responsible for generating, safeguarding, and backing up your master encryption key (`ENCRYPTION_KEY`).

## 6. Acceptable Use & Prompt Injection Defense
You agree not to use the Service to transmit malicious payloads, exploit prompt injection vulnerabilities, process classified or military data without appropriate agreements, or engage in automated harassment or unauthorized scraping.

## 7. Intellectual Property & Customer Data Ownership
- **Customer Data**: You retain all right, title, and interest in and to all text inputs, transcripts, and custom action configurations.
- **Open Source Software**: Kairos open-source components are distributed under the MIT License.

## 8. Disclaimer of Warranties
TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE", WITH ALL FAULTS AND WITHOUT WARRANTY OF ANY KIND. KAIROS DISCLAIMS ALL WARRANTIES, EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.

## 9. Limitation of Liability
IN NO EVENT SHALL KAIROS, ITS OFFICERS, DIRECTORS, EMPLOYEES, OR AFFILIATES BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING OUT OF OR RELATING TO YOUR ACCESS TO OR USE OF THE SERVICE.

## 10. Indemnification
You agree to defend, indemnify, and hold harmless Kairos from any third-party claims, liabilities, damages, losses, and expenses arising out of or related to your Customer Data, violation of these Terms, or approved side-effects dispatched to external tools.

## 11. Governing Law & Dispute Resolution
These Terms shall be governed by the laws of the State of Delaware. Any dispute shall be resolved exclusively through binding arbitration administered by the American Arbitration Association (AAA).
