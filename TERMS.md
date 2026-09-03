# Terms of Service

**Version 1.0 &middot; Effective date:** `[EFFECTIVE DATE]`

> **How to use this document.** Kairos is open-source, self-hosted software
> (MIT license). When you deploy it, **you** operate the Service and these
> terms become yours to publish. Replace every `[bracketed placeholder]`,
> choose the arbitration option that fits your deployment (delete the other
> before publishing), and have counsel review the result. This document is
> adapted from the
> [General Legal](https://github.com/General-Legal/legal-templates)
> terms-of-use template (CC0) for the Kairos project. It is a template, not
> legal advice.

The Service located at `[DOMAIN]` (the "**Service**") is owned and operated
by `[OPERATOR LEGAL NAME]` ("**Company**," "**we**," "**us**," "**our**").
The Service is a deployment of Kairos, an open-source ambient action engine
that extracts action items from unstructured text and executes approved
items in connected third-party tools. Certain features may be subject to
additional guidelines posted on the Service and incorporated by reference
into these Terms.

These Terms of Service (the "**Terms**") govern your use of the Service. By
accessing or using the Service, or by clicking "I agree" where that option
is presented, you agree to these Terms on behalf of yourself or the entity
you represent, and you confirm you have authority to do so. You must be at
least 18 years old to use the Service. If you do not agree, do not use the
Service.

**IMPORTANT — PLEASE READ SECTION 12 CAREFULLY.** It contains an agreement
to resolve disputes through binding individual arbitration instead of in
court, and includes a waiver of class-action and jury-trial rights. You
have 30 days to opt out of the arbitration agreement, as described in
Section 12.

**The software itself.** The Kairos source code is distributed under the MIT
License, which governs your use, modification, and redistribution of the
code. These Terms govern your use of the Service operated by Company — a
running deployment — not your rights in the source code. Nothing in these
Terms limits your MIT License rights in the software.

1. **Accounts and access keys**

    1. **Access model.** The Service is a single-operator system: access is
       granted through a shared operator API key. If Company issues you a
       key, it is for you personally and may not be shared. If you believe
       a key has been accessed without authorization, notify Company
       immediately. Company is not liable for losses resulting from a
       failure to keep credentials secure.
    2. **Account security.** You are responsible for all activity that
       occurs under your access, including actions approved through your
       session. Company may suspend or terminate access as described in
       Section 9.
    3. **No multi-user support.** The Service has no user accounts, no
       per-user permissions, and one shared batch history. Everyone who can
       reach the Service sees the same batches, decisions, and connected
       tools. Do not expose the Service to people whose data should be
       isolated from each other.

2. **License to use the Service; restrictions**

    1. **License.** Subject to these Terms, Company grants you a limited,
       personal, non-exclusive, non-transferable, revocable license to
       access and use the Service for your own lawful purposes.
    2. **Restrictions.** You may not: (i) license, sell, rent, lease,
       transfer, or commercially exploit access to the Service; (ii)
       attempt to bypass authentication, rate limits, or the network
       isolation of internal services; (iii) use the Service to access or
       build a competing product; or (iv) copy, reproduce, or redistribute
       any part of the Service except as expressly permitted by these
       Terms or by the MIT License as it applies to the source code.
    3. **Changes to the Service.** Company may modify, suspend, or
       discontinue the Service (or any part of it) at any time, with or
       without notice. Company is not liable for any such modification,
       suspension, or discontinuation.
    4. **No support obligation.** Company has no obligation to provide
       support or maintenance for the Service beyond what it voluntarily
       offers.
    5. **Ownership.** The Service's deployment, configuration, and
       operator data belong to Company. The Kairos source code remains
       under its open-source license; these Terms transfer no ownership
       rights in the software.
    6. **Feedback.** If you share feedback or suggestions about the Service
       with Company, you grant Company a perpetual, irrevocable, worldwide,
       non-exclusive, fully-paid, royalty-free license to use that feedback
       freely, in any manner, without attribution. Do not submit feedback
       you consider proprietary or confidential.

3. **Human approval and executed actions**

    1. **The Service proposes; you decide.** The Service extracts candidate
       action items from text you submit and suggests destinations, but
       **nothing executes without an explicit human approval** through the
       review screen. When you click approve, you instruct the Service to
       transmit the finalized payload to the destination tool.
    2. **Your responsibility for approvals.** Extraction is performed by
       statistical models or deterministic parsers and may be wrong, incomplete,
       or misleading. You are solely responsible for reviewing every proposed
       action, its verbatim source quote, and its payload before approving
       it, and for the consequences of actions you approve. This includes
       content filed to Jira, pages created in Notion, events scheduled in
       Google Calendar, and tasks written to the internal ledger.
    3. **Irreversibility.** Approved actions produce real side effects in
       third-party systems. The Service cannot automatically undo an issue,
       page, event, or task that has been created, and its idempotency
       mechanism prevents duplicates — it does not reverse executions.
       Verify carefully before approving.
    4. **Content standards.** You may not submit content you know to be
       unlawful, or content containing malicious instructions intended to
       manipulate the extraction pipeline (prompt injection). Submitted text
       is treated as untrusted data and delimited as such, but you remain
       responsible for what you paste.

4. **Third-party tools and services**

    1. **Connected tools.** The Service integrates with the destination
       providers the operator configures — Notion; Atlassian (Jira,
       Confluence); Google (Calendar, Gmail, Google Tasks); Linear;
       Todoist; GitHub; Asana; ClickUp; Slack; and LLM providers
       (Google Gemini, OpenAI). You must hold valid accounts in good
       standing with each provider whose tools you direct actions to.
       Provider rate limits, downtime, API changes, and terms apply; Company
       does not control them and is not responsible for them.
    2. **Provider terms.** Actions executed in a provider's system are
       additionally governed by that provider's own terms of service. A
       conflict between these Terms and a provider's terms as to conduct
       within that provider's system is resolved in favor of the provider's
       terms for that conduct.
    3. **Credentials.** Connector credentials you save are encrypted at
       rest and decrypted only for approved executions. Company does not
       transmit credentials to any party other than the provider they
       authenticate to.
    4. **Other users.** The Service is single-operator; if Company permits
       additional individuals to use it, interactions and shared visibility
       are solely among those individuals. Company reserves the right, but
       has no obligation, to intervene in disputes.

5. **Indemnification**

   You agree to defend, indemnify, and hold harmless Company and its
   officers, employees, and agents from any claims and reasonable costs or
   attorneys' fees arising out of: (i) your use of the Service; (ii)
   actions you approved for execution in third-party tools, including any
   content those actions created, filed, or scheduled; (iii) content you
   submitted, including any personal information of other people it
   contained; (iv) your violation of these Terms; or (v) your violation of
   any applicable law or regulation. Company may assume control of the
   defense of any such claim at your expense, and you agree to cooperate
   with the defense and not to settle without Company's prior written
   consent. Company will make reasonable efforts to notify you promptly of
   any claim it becomes aware of.

6. **Disclaimers**

   THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE." TO THE FULLEST EXTENT
   PERMITTED BY LAW, COMPANY AND ITS SUPPLIERS DISCLAIM ALL WARRANTIES,
   EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR
   A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. COMPANY DOES NOT
   WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE,
   OR THAT EXTRACTED ACTION ITEMS WILL BE ACCURATE OR APPROPRIATE. EXTRACTION
   QUALITY DEPENDS ON CONFIGURED PROVIDERS AND INPUT; VERIFY BEFORE
   APPROVING. WHERE APPLICABLE LAW REQUIRES WARRANTIES, THEY ARE LIMITED
   TO 90 DAYS FROM YOUR FIRST USE OF THE SERVICE.

7. **Limitation of liability**

   TO THE MAXIMUM EXTENT PERMITTED BY LAW: (A) COMPANY AND ITS SUPPLIERS
   WILL NOT BE LIABLE FOR ANY LOST PROFITS, LOST DATA, COSTS OF SUBSTITUTE
   PRODUCTS, OR ANY INDIRECT, CONSEQUENTIAL, INCIDENTAL, SPECIAL,
   EXEMPLARY, OR PUNITIVE DAMAGES ARISING OUT OF OR RELATED TO THESE TERMS
   OR THE USE OF (OR INABILITY TO USE) THE SERVICE — INCLUDING DAMAGE
   ARISING FROM ACTIONS EXECUTED IN THIRD-PARTY TOOLS AFTER YOUR
   APPROVAL; AND (B) COMPANY'S TOTAL LIABILITY TO YOU FOR ANY CLAIM
   ARISING UNDER THESE TERMS IS CAPPED AT THE GREATER OF (i) $50 USD AND
   (ii) THE AMOUNT YOU PAID TO COMPANY FOR THE SERVICE IN THE SIX MONTHS
   BEFORE THE INCIDENT. THE EXISTENCE OF MULTIPLE CLAIMS DOES NOT INCREASE
   THIS CAP. SOME JURISDICTIONS DO NOT ALLOW CERTAIN LIMITATIONS; IN THOSE
   JURISDICTIONS THE LIMITS APPLY TO THE EXTENT PERMITTED BY LAW.

8. **Privacy**

   Your use of the Service is governed by the Privacy Policy at
   `[PRIVACY POLICY URL]`, incorporated by reference. It describes the
   data the Service collects (submitted text, extracted items, decisions,
   credentials, execution logs), how it is used, when it leaves the
   deployment (configured LLM, tool, and tracing providers), and how to
   delete it. If a conflict between these Terms and the Privacy Policy
   arises as to data handling, the Privacy Policy controls.

9. **Term and termination**

   These Terms remain in effect while you use the Service. Company may
   suspend or terminate your access at any time, for any reason, including
   suspected violation of these Terms, without liability to you. Upon
   termination, Sections 2 through 8 and 10 through 12 survive. You may
   stop using the Service at any time; deleting your batches through the
   API does not terminate these Terms as a whole.

10. **State-specific legal notices**

    The provisions in this Section 10 apply only to users subject to the
    laws of the identified states. If a provision here conflicts with
    another provision of these Terms, the state-specific provision controls
    for users subject to that state's laws.

    1. **California.** California users may report complaints to the
       Complaint Assistance Unit of the Division of Consumer Services,
       California Department of Consumer Affairs, 1625 N. Market Blvd. Suite
       N112, Sacramento, CA 95834, or (800) 952-5210. Under California
       Civil Code Section 1789.3, users are entitled to this notice: the
       provider of the Service is `[OPERATOR LEGAL NAME]`, `[ADDRESS]`;
       complaints or information requests may be sent to that address or
       `[CONTACT EMAIL]`. California residents may have additional rights
       under the CCPA/CPRA, described in the Privacy Policy.
    2. **Colorado.** Colorado residents may have rights under the Colorado
       Privacy Act, including opting out of targeted advertising, sale, and
       certain profiling. See the Privacy Policy.
    3. **Connecticut.** Connecticut residents may have rights under the
       Connecticut Data Privacy Act, including access, correction,
       deletion, portability, and opting out of sale, targeted advertising,
       and profiling. See the Privacy Policy.
    4. **Virginia.** Virginia residents may have rights under the Virginia
       Consumer Data Protection Act, including access, correction,
       deletion, portability, and opting out of targeted advertising, sale,
       and profiling. See the Privacy Policy.
    5. **Nevada.** Nevada residents may direct, under Nevada Revised
       Statutes Chapter 603A, that certain information not be sold. The
       Service does not sell personal information; opt-out requests may be
       sent to `[CONTACT EMAIL]`.
    6. **Other states.** Additional state privacy laws (Texas, Oregon,
       Montana, Utah, Iowa, Indiana, Tennessee, and others) may grant
       residents similar rights; see the State privacy rights notice in
       the Privacy Policy. `[OPERATORS: add state-specific provisions as
       your user base requires.]`

11. **General**

    1. **Changes to Terms.** Company may update these Terms. Material
       changes will be notified by email (to the address on file) or by
       prominent notice on the Service. Continued use after notice means
       you accept the updated Terms.
    2. **Governing law.** These Terms and any dispute arising out of them
       or the Service are governed by the laws of the State of
       `[GOVERNING STATE]`, without regard to conflict-of-law principles.
       For claims not subject to arbitration under Section 12, the parties
       consent to the exclusive jurisdiction of the state and federal courts
       in `[COUNTY]`, `[GOVERNING STATE]`; either party may also bring
       equitable claims to protect intellectual property, or individual
       small-claims actions, in any court of competent jurisdiction.
    3. **Export.** You agree not to export, re-export, or transfer any
       technical data or products acquired via the Service in violation of
       U.S. export control laws or other applicable regulations.
    4. **Electronic communications.** You consent to receive
       communications from Company electronically (email or notices posted
       on the Service). These satisfy any legal requirement for written
       notice.
    5. **Accessibility.** Company endeavors to conform to WCAG 2.1 Level
       AA. If you experience difficulty accessing or navigating the
       Service, contact `[ACCESSIBILITY CONTACT]`; reasonable efforts will
       be made to address concerns promptly.
    6. **Assignment; entire agreement; severability.** These Terms
       (together with the Privacy Policy) are the entire agreement
       regarding your use of the Service. If a provision is found invalid
       or unenforceable, it will be modified to the minimum extent
       necessary and the remainder continues in effect. Failure to enforce
       is not a waiver. "Including" means "including without limitation."
       You may not assign these Terms without prior written consent;
       Company may assign freely. These Terms bind permitted assignees.
    7. **Copyright.** Copyright `[YEAR]` `[OPERATOR LEGAL NAME]`. The Kairos
       software is MIT-licensed; all trademarks displayed on the Service
       belong to their owners.

12. **Dispute resolution — arbitration**

    `[OPERATORS: choose Option A (JAMS) or Option B (DecisionLayer) and
    delete the other and this bracketed note before publishing.]`

    **[OPTION A — JAMS Arbitration].** Please read this section carefully;
    it affects your legal rights, including your right to sue in court and
    to a jury trial.

    1. **Applicability.** Except as described below, you and Company agree
       to resolve all disputes arising out of or relating to the Service or
       these Terms through binding individual arbitration — not in court.
       Exceptions: (i) claims qualifying for small-claims court, brought
       individually; and (ii) requests for equitable relief related to
       intellectual property. This agreement covers all claims, including
       those arising before you accepted these Terms.
    2. **Try to resolve first.** Before starting arbitration, the parties
       will attempt informal resolution: the disputing party sends written
       notice ("Informal Notice") to the other; within 45 days the parties
       meet by phone or video in good faith. Company's notice address:
       `[DISPUTES EMAIL]` or `[ADDRESS]`. If unresolved after 60 days,
       either party may start arbitration.
    3. **Arbitration rules.** Arbitrations are administered by JAMS
       (www.jamsadr.com). Claims under $250,000 (excluding fees and
       interest) use JAMS' Streamlined Arbitration Rules; larger claims use
       the Comprehensive Rules. Unless agreed otherwise, arbitration is
       conducted in the county where you live. Materials are confidential.
    4. **Demand contents.** The arbitration request must include: (i) your
       contact information; (ii) the claims and supporting facts; (iii) the
       relief sought and a good-faith damages estimate; (iv) confirmation
       the informal process was completed; and (v) filing-fee proof.
    5. **Authority of the arbitrator.** The arbitrator resolves all
       arbitrable disputes, including scope and enforceability of this
       arbitration agreement — except that courts decide: (i) challenges to
       the class-action waiver; (ii) fee disputes; (iii) whether conditions
       precedent were satisfied; and (iv) which agreement version applies.
       The award is final and binding; judgment may be entered in any
       court of competent jurisdiction.
    6. **Waiver of jury trial.** BY AGREEING TO ARBITRATION, YOU AND
       COMPANY WAIVE THE RIGHT TO A TRIAL BY JUDGE OR JURY FOR ALL COVERED
       CLAIMS.
    7. **Waiver of class actions.** ALL DISPUTES MUST BE BROUGHT
       INDIVIDUALLY. NEITHER YOU NOR COMPANY MAY BRING CLAIMS AS A
       PLAINTIFF OR CLASS MEMBER IN ANY CLASS, REPRESENTATIVE, OR
       COLLECTIVE PROCEEDING. If the class-action waiver is found
       unenforceable as to a specific claim, that claim may be litigated in
       state or federal court in `[GOVERNING STATE]`; all other claims
       remain arbitrable.
    8. **Attorneys' fees.** Each party bears its own attorneys' fees unless
       the arbitrator finds a claim was frivolous or brought for an
       improper purpose.
    9. **Batch arbitration.** If 100 or more substantially similar demands
       are filed against Company within 30 days by the same firm or a
       coordinated group, JAMS will batch them into groups of 100 with one
       arbitrator and one fee set per batch.
    10. **Opt-out.** You may opt out of this arbitration agreement within
        30 days of first accepting these Terms by written notice to
        `[ADDRESS]` or `[EMAIL]`, including your name, address, and a clear
        statement that you wish to opt out. Opting out does not affect the
        rest of these Terms.
    11. **Severability.** If any part of this arbitration agreement is
        invalid, it will be modified to the minimum extent necessary; the
        rest remains in effect.

    **[OPTION B — DecisionLayer Arbitration].** This agreement requires
    individual arbitration of disputes arising out of or relating to the
    agreement, not class arbitration. By accepting these Terms you waive
    any right to a jury trial and to participate in a class action.

    1. **Arbitration of disputes.** Any dispute arising out of, relating
       to, or in connection with these Terms — including interpretation,
       formation, breach, termination, validity, enforceability, or
       arbitrability — will be resolved by binding arbitration administered
       by Decision Science Research Corporation ("DecisionLayer") under its
       rules at https://www.decisionlayer.ai/rules (the "Rules"). The
       arbitrator determines all threshold questions of arbitrability.
       Judgment on an award may be entered in any state or federal court in
       New York County, New York, or any court of competent jurisdiction.
       These Terms are governed by the Rules, the Federal Arbitration Act,
       applicable federal law, and the internal laws of the State of New
       York. By agreeing to arbitration under this clause, you acknowledge
       DecisionLayer may resolve disputes using an artificial intelligence
       or large language model acting under human supervision, a human
       arbitrator, or both, as selected by the parties under the Rules; all
       information reviewed by any AI is also reviewed by a human case
       manager, and every award is reviewed by a human case manager before
       issuance and accompanied by a written opinion. Your relationship
       with DecisionLayer is governed by its Terms of Service at
       https://www.decisionlayer.ai/terms.
    2. `[OPERATORS: mirror Option A's informal-resolution, fees,
       class-waiver, and opt-out mechanics here if choosing Option B.]`

13. **Contact**

    Questions about these Terms: `[CONTACT EMAIL]` &middot;
    `[OPERATOR POSTAL ADDRESS]`.
