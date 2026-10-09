# TelemedBima / BIMA Health - System Flow Diagrams & Architecture Specifications

> [!NOTE]
> This document provides visual Mermaid flowcharts, sequence diagrams, and architecture specifications for the entire **TelemedBima / BIMA Health Campaign Platform** repository ([memory.md](file:///d:/web/telemedbima/memory.md)).

---

## 1. High-Level System Architecture & Component Interactions

This component diagram details the interaction boundaries between browser clients, Express.js (`server.js`) / Flask (`app.py`) application servers, internal security & rate-limiting middleware, BIMA Core APIs (`pkcm.milvik.io`), JazzCash Payment Gateway (`onlinepayments.jazzcash.com.pk`), AWS Header Enrichment proxy (`54.154.2.113:8000`), and analytics tracking pixels.

```mermaid
graph TD
    subgraph Clients["Web Clients / User Interfaces"]
        C1["Ad Viewers / Mobile Users"]
        C2["Consultation Portal (consultation.html)"]
        C3["Voucher Landing Pages (index.html, index2.html, index3.html)"]
        C4["Transaction Result Page (callback.html)"]
    end

    subgraph Middleware["Backend Application Layer (server.js / app.py)"]
        M1["Security & File Blocking Middleware"]
        M2["CORS & Content Security Policy (CSP)"]
        M3["IP Rate Limiter (10 req/min)"]
        M4["Campaign Config Manager (campaigns_qa / campaigns_prod)"]
        M5["HMAC SHA-256 Token Auth & Payment Session Manager"]
    end

    subgraph APIEndpoints["Backend API Routes"]
        E1["GET /api/detect-msisdn"]
        E2["POST /api/service-search"]
        E3["GET /api/jazzcash-form"]
        E4["POST/GET /jcms/callback"]
        E5["POST /api/grant-access"]
        E6["GET /api/campaign/:code"]
    end

    subgraph ExternalServices["External APIs & Services"]
        EXT1["BIMA Core API Gateway (pkcm.milvik.io)"]
        EXT2["JazzCash Payment Gateway (onlinepayments.jazzcash.com.pk)"]
        EXT3["AWS Header Detection Proxy (54.154.2.113:8000)"]
    end

    subgraph Analytics["Pixel Tracking & Analytics Networks"]
        P1["TikTok Pixel (Advanced Matching & VSA)"]
        P2["Meta (Facebook) Pixel"]
        P3["Google Analytics 4 & Google Ads Conversion"]
        P4["Firebase Web SDK"]
    end

    C1 --> C3
    C1 --> C2
    C3 --> E1
    C3 --> E2
    E1 --> EXT3
    E2 --> M3
    E2 --> EXT1
    E2 --> M5
    C3 --> E3
    E3 --> M5
    E3 --> EXT2
    EXT2 --> E4
    E4 --> C4
    C4 --> Analytics
    C2 --> E5
    E5 --> EXT1
    C3 --> E6
    E6 --> M4
```

---

## 2. End-to-End User Conversion & DTC Payment Sequence

The sequence diagram below traces the complete lifecycle of a user clicking an ad, auto-detecting phone number via Mobile Header Enrichment (HE), initiating subscription search, securing payment session token, redirecting to JazzCash, returning to callback page, and triggering conversion tracking.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Mobile Browser
    participant App as TelemedBima App / Server
    participant HE as AWS HE Proxy (54.154.2.113)
    participant BIMA as BIMA Core API (pkcm.milvik.io)
    participant JC as JazzCash Payment Gateway
    participant Pixels as Analytics / Pixels

    User->>App: Visit Campaign Page (e.g. /BimaVoucher/index2.html)
    App->>App: Check HTTP Headers for MSISDN
    alt Header Not Found
        App->>HE: GET / (Header Detection Proxy)
        HE-->>App: Return detected MSISDN
    end
    App-->>User: Inject SERVER_DETECTED_MSISDN into HTML head

    User->>App: Submit MSISDN / Click Subscribe
    App->>App: Validate Rate Limit (10 req/min/IP)
    App->>BIMA: GET /tp/service/search/{msisdn}/{productCode}
    BIMA-->>App: Return Subscription Status & transId
    App->>App: Generate Signed HMAC paymentSessionToken (5 min exp)
    App-->>User: Return status & paymentSessionToken

    User->>App: GET /api/jazzcash-form?token={paymentSessionToken}
    App->>App: Verify HMAC Signature & Expiry
    App->>App: Calculate pp_SecureHash with INTEGRITY_SALT
    App-->>User: Return Form Parameters & Action URL

    User->>JC: Auto-submit POST to onlinepayments.jazzcash.com.pk
    Note over User,JC: User enters PIN / OTP to complete JazzCash DTC Payment
    JC->>App: POST /jcms/callback (Response Params)
    App-->>User: Redirect 302 to /callback.html?status=...&trxRefNo=...

    User->>User: Render Result Card (Success/Failure)
    User->>Pixels: Fire TikTok, Meta, GA4, Google Ads, Firebase Purchase Pixels
```

---

## 3. Mobile Network Header Enrichment (HE) MSISDN Auto-Detection

This diagram outlines how cellular mobile network headers (`x-msisdn`, `x-up-calling-line-id`, `msisdn`) are checked locally and forwarded to AWS Header Enrichment proxy (`54.154.2.113:8000`) for auto-filling subscriber numbers.

```mermaid
flowchart TD
    A[Client Requests Page /api/detect-msisdn] --> B{Check Local HTTP Request Headers}
    B -- Found Header e.g. x-msisdn --> C[Extract MSISDN Value]
    B -- Not Found --> D[Query AWS HE Proxy at 54.154.2.113:8000]
    D --> E{Proxy Responds with 200 OK?}
    E -- Yes --> F[Parse msisdn-val HTML Element via Regex]
    E -- No / Timeout --> G[Return msisdn: null]
    F --> H{MSISDN Matched?}
    H -- Yes --> C
    H -- No --> G
    C --> I[Inject window.SERVER_DETECTED_MSISDN or Return JSON]
```

---

## 4. BIMA Service Search & Cryptographic Payment Session Flow

This flowchart illustrates rate-limiting checks, cached BIMA auth token handling, BIMA service search API calls, and signed HMAC SHA-256 `paymentSessionToken` generation (5-minute expiration window).

```mermaid
flowchart TD
    A[Client POST /api/service-search] --> B{Check IP Rate Limit 10/min}
    B -- Exceeded --> C[Return 429 Too Many Requests]
    B -- Passed --> D[Determine Environment & Load Campaign Config]
    D --> E[Fetch cached BIMA API Auth Token]
    E --> F{Token Valid?}
    F -- Expired/401 --> G[Re-authenticate with BIMA Core /authorize/tp/login]
    F -- Valid --> H[Call BIMA Service Search API]
    G --> H
    H --> I{BIMA Returns Status 200 & transId?}
    I -- No --> J[Return Error to Client]
    I -- Yes --> K[Construct Payload: msisdn, transId, exp: Date.now + 5m]
    K --> L[Generate HMAC SHA-256 Signature using INTEGRITY_SALT]
    L --> M[Combine Base64 Payload + Signature = paymentSessionToken]
    M --> N[Return Result & paymentSessionToken to Client]
```

---

## 5. Payment Return Callback & Multi-Pixel Conversion Engine

This diagram details the post-payment redirection flow handled by `/jcms/callback` and how `callback.html` processes query strings to fire conversion events across TikTok, Meta, GA4, Google Ads, and Firebase.

```mermaid
flowchart TD
    A[JazzCash Payment Gateway Completed] --> B[JazzCash POST/GET to /jcms/callback]
    B --> C[Extract status, message, trxRefNo, source]
    C --> D[Sanitize & Format Query Parameters]
    D --> E[302 Redirect Browser to /callback.html]
    E --> F[Client JS Reads URL Search Params]
    F --> G{Is Transaction Status Success?}
    G -- Yes --> H[Display Success Confirmation & Hero Graphic]
    G -- No --> I[Display Error Message & Retry Prompt]
    H --> J[Fire TikTok Pixel: Purchase / CompletePayment + SHA256 Phone]
    H --> K[Fire Meta Pixel: Purchase + Advanced Matching]
    H --> L[Fire GA4 Event: purchase + Google Ads Conversion]
    H --> M[Fire Firebase Event: purchase]
```

---

## 6. Telemedicine 24/7 Doctor Consultation & Video Call Deep-Link Flow

This flowchart illustrates how subscribers verify eligibility via `/api/grant-access` and receive authorized video portal deep-links.

```mermaid
flowchart TD
    A[User on /consultation Enters Mobile Number] --> B[POST /api/grant-access]
    B --> C[Fetch BIMA Auth Token]
    C --> D[Call BIMA Eligibility API: check_consultation_eligibility]
    D --> E{User Eligible & Active Subscriber?}
    E -- No / Unregistered --> F[Return status: unregistered & Redirect URL to Campaign Page]
    E -- Yes --> G[Generate v4 UUID Correlation ID]
    G --> H[Call BIMA Video Grant API: /service-access/grant]
    H --> I{Deep-link Generated?}
    I -- Success --> J[Return status: success & deep_link URL]
    I -- Error --> K[Return 500 Consultation Service Error]
    J --> L[Browser Launches Video Call Consultation Portal]
```

---

## 7. Dynamic Campaign Configuration & Selection Engine

This flowchart shows how backend servers determine environment mode (`APP_ENV`), inspect `campaigns_qa.json` vs `campaigns_prod.json`, strip comments, and serve dynamic campaign settings.

```mermaid
flowchart TD
    A[Client Request GET /api/campaign/:code] --> B[Inspect APP_ENV Environment Variable]
    B --> C{Is Environment QA / Staging / Dev?}
    C -- Yes --> D[Select campaigns_qa.json]
    C -- No --> E[Select campaigns_prod.json]
    D --> F[Sanitize JSON strip comments]
    E --> F
    F --> G[Lookup requested code or fallback qa_default / default]
    G --> H{Campaign Config Found?}
    H -- Yes --> I[Return JSON config: campaignCode, productCode, price, artwork, pixel overrides]
    H -- No --> J[Return 404 Campaign Not Found]
```

---

## 8. Diagram Update Protocol for Future Changes

> [!IMPORTANT]
> To ensure the flow diagrams remain continuously aligned with future changes, maintainers and AI assistants must follow this protocol:

1. **Adding Backend API Routes**:
   - Update **Diagram 1 (System Architecture)** with the new endpoint node.
   - Add a dedicated flowchart diagram if the route introduces multi-step asynchronous processing or external third-party API calls.

2. **Modifying Payment Gateway Logic**:
   - Update **Diagram 2 (Sequence)** and **Diagram 5 (Callback & Conversion)** if parameters, signature hashing, or return routes (`/jcms/callback`) are changed.

3. **Updating Conversion Tracking & Pixels**:
   - Update **Diagram 5 (Callback & Conversion)** when adding new pixel networks (e.g. Snapchat, Twitter/X, Pinterest) or updating SHA-256 hashed parameters.

4. **Updating BIMA Core Integration**:
   - Update **Diagram 4 (Service Search)** or **Diagram 6 (Telemedicine)** if authentication headers, grant UUID generation, or eligibility API endpoints change.

5. **Updating Memory Documentation**:
   - Whenever editing system logic, sync modifications into [memory.md](file:///d:/web/telemedbima/memory.md) under Section 9 (`System Flow Diagrams & Workflows`).
