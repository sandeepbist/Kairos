# Terms of Service

**Last Updated**: August 27, 2026 • **Version**: 1.0.0

## 1. Acceptance of Terms
By accessing, installing, deploying, or utilizing the Kairos Ambient Action Agent software, APIs, or hosted dashboards (collectively, the "Service"), you agree to be bound by these Terms of Service ("Terms"). If you are using the Service on behalf of an organization, you represent that you have authority to bind that entity.

## 2. Autonomous Action Extraction & Human-in-the-Loop
Kairos is an autonomous action extraction and routing engine that parses unstructured text and converts candidate commitments into proposed tool side-effects across Notion, Jira, Google Calendar, and Task Ledger.

- **Mandatory Human Verification**: Kairos incorporates a mandatory human-in-the-loop review workbench. The operator retains ultimate legal and operational responsibility for reviewing, approving, editing, or rejecting proposed side-effects before execution against third-party production systems.

## 3. Third-Party Integrations & Model Context Protocol (MCP)
The Service connects to third-party platforms via Model Context Protocol (MCP) servers and REST APIs. You are responsible for ensuring that all API keys and OAuth tokens provided have appropriate permissions and adhere to the third-party providers' acceptable use policies.

## 4. Credential Vault & Cryptography
All OAuth access tokens and API secrets stored within the Service are encrypted at rest using AES-256 Fernet cryptographic keys. You are responsible for maintaining the confidentiality of your environment keys.

## 5. Disclaimer of Warranties & Limitation of Liability
THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTY OF ANY KIND. UNDER NO CIRCUMSTANCES SHALL THE AUTHORS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES ARISING FROM THE USE OF OR INABILITY TO USE THE SERVICE.

## 6. Open Source Licensing
Core Kairos code is licensed under the terms of the MIT License in the repository root.
