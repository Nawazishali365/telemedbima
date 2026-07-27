# System Memory & Architecture Documentation (`memory.md`)

This file serves as a comprehensive system memory and architecture reference for the **TelemedBima / BIMA Health (Milvik Mobile Pakistan)** web application. All agents working on this codebase MUST review this documentation before making modifications.

---

## 1. Project Overview

- **Project Name**: TelemedBima / BIMA Health Campaign Platform
- **Owner**: Milvik Mobile Pakistan Private Limited (BIMA Health)
- **Primary Domain**: `jzmhealth.milvikpakistan.com`
- **Core Functionality**:
  - Telemedicine 24/7 doctor consultation eligibility check & video call deep-link generation.
  - JazzCash DTC (Direct to Consumer) subscription payment integration & voucher campaigns.
  - Pixel tracking & conversion reporting (TikTok, Meta, Google Ads/Analytics, Firebase).

---

## 2. Technology Stack

- **Backend**: Node.js, Express.js, Native `https`/`http` modules, `crypto` (HMAC SHA-256), `dotenv`.
- **Frontend**: Vanilla HTML5, CSS3 (Container Queries, Clamp Typography, Flexbox), JavaScript (ES6+ Modules).
- **Security & Cryptography**: Signed HMAC payment session tokens, strict Content Security Policy (CSP), HSTS, CORS control, IP rate limiting.
- **Analytics & Conversion Tracking**:
  - TikTok Pixel (`D8J9AARC77UAEKHUNU60`) with Video Shopping Ads (VSA) `content_id` parameters & Manual Advanced Matching.
  - Meta (Facebook) Pixel (`1048814397473573`) with Advanced Matching (`ph`).
  - Google Analytics (`G-FLKEQYY9E9`) & Google Ads Conversion (`AW-10779246142`).
  - Firebase Web SDK v10 (`bima-telemedicine` / `G-3HF87WXJPG`).

---

## 3. Complete Route & API Reference

### A. Frontend Page Routes & Static Handlers

| HTTP Method | Route / Pattern | Handler Description | Target Resource |
| :--- | :--- | :--- | :--- |
| **GET** | `/` | Serves the primary consultation landing page | [consultation.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/consultation.html) |
| **GET** | `/consultation` | Serves the consultation landing page | [consultation.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/consultation.html) |
| **GET** | `/landingpage` | Redirects to campaign landing page with query string | `/BimaVoucher/landingpage.html` |
| **GET** | `/.*index2(\.html)?$` | Serves the Campaign 2 Voucher page | [BimaVoucher/index2.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/index2.html) |
| **POST** | `/.*index2(\.html)?$` | Receives POST MSISDN payload and injects `window.SERVER_DETECTED_MSISDN` into HTML head | [BimaVoucher/index2.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/index2.html) |
| **GET** | `/bima-sehat`, `/bima_sehat` | Redirects to BIMA Telemedicine folder | `/BimaTelemedicine/` |
| **GET** | `/bima-family`, `/bima_family` | Redirects to BIMA Telemedicine folder | `/BimaTelemedicine/` |
| **GET** | `/callback.html` | Displays JazzCash transaction result & fires conversion pixels | [callback.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/callback.html) |
| **GET** | `/BimaVoucher/terms_and_conditions_bima.html` | Campaign Terms & Conditions document | [BimaVoucher/terms_and_conditions_bima.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/terms_and_conditions_bima.html) |

---

### B. Backend API Routes & Proxies

#### 1. `GET /api/detect-msisdn`
- **Purpose**: Mobile Data Header Enrichment (HE) MSISDN auto-detection.
- **Header Inspection**: Checks local headers (`x-msisdn`, `x-up-calling-line-id`, `msisdn`, `x-device-msisdn`, `x-hcl-msisdn`, etc.).
- **Fallback**: Queries external header detector proxy at `54.154.2.113:8000`.
- **Response**: `{ msisdn: "03XXXXXXXXX" }` or `{ msisdn: null }`.

#### 2. `POST /api/service-search`
- **Rate Limit**: 10 requests / 60 seconds per IP.
- **Purpose**: Queries BIMA Core API (`pkcm.milvik.io/tp/service/search/{msisdn}/PAKISTAN_BIMA_JAZZDTC_TELEMEDICINE_FAMILY?deductionFrequency=MONTHLY`) using cached BIMA auth token.
- **Security**: Validates subscription status (`subscriptionStatus`). Generates a signed HMAC payment token (`paymentSessionToken`) valid for 5 minutes.
- **Response**: BIMA search payload + `{ paymentSessionToken: "<signed_token>" }`.

#### 3. `GET /api/jazzcash-form`
- **Rate Limit**: 10 requests / 60 seconds per IP.
- **Query Parameter**: `token` (`paymentSessionToken`).
- **Security**: Decrypts & verifies HMAC signature + expiration timestamp of `paymentSessionToken`.
- **Function**: Calculates JazzCash `pp_SecureHash` using `INTEGRITY_SALT` (`salt & msisdn & merchantId & password & transId & returnUrl`).
- **Response**: JSON form payload containing `actionUrl`, `pp_MerchantID`, `pp_Password`, `pp_RequestID`, `pp_ReturnURL`, `pp_MSISDN`, `pp_SecureHash`.

#### 4. `POST /jcms/callback` & `GET /jcms/callback`
- **Purpose**: JazzCash Payment Gateway post-back return endpoint.
- **Parameter Resolution**: Extracts `status` (`status`, `pp_ResponseCode`), `message` (`message`, `pp_ResponseMessage`), `trxRefNo` (`trxRefNo`, `pp_TxnRefNo`, `pp_RetrievalReferenceNo`), and `source` (`source`, `ppmp_1`).
- **Behavior**: Constructs clean URL search parameters and redirects the user browser to `/callback.html?status=...&message=...&trxRefNo=...`.

#### 5. `POST /api/grant-access`
- **Purpose**: Telemedicine consultation eligibility check & video deep-link generation.
- **Step 1**: Calls BIMA Eligibility API (`pkcm.milvik.io/tp/service/api/v1/check_consultation_eligibility?msisdn=...`).
- **Step 2**: If eligible, calls Video Grant API (`pkcm.milvik.io/authorize/partners/v1/service-access/grant`) with a generated v4 UUID correlation ID.
- **Response**: `{ status: "success", deep_link: "https://..." }` or `{ status: "unregistered", redirect_url: "..." }`.

#### 6. `POST /api/token`
- **Status**: 403 Forbidden (Retired for security reasons).

---

## 4. Security Architecture & Middlewares

1. **Blocked Files Middleware**:
   Direct HTTP access to sensitive files (`/package.json`, `/.env`, `/server.js`, `/app.py`, `/.git`, `/security-audit-report.html`) is blocked with `403 Forbidden`.

2. **CORS & Header Security**:
   - Origin restricted to `jzmhealth.milvikpakistan.com`, `milvikpakistan.com`, `milvik.io`, `localhost`.
   - Strict `Content-Security-Policy` enforcing trusted scripts (`gstatic.com`, `googletagmanager.com`, `tiktok.com`).
   - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`.
   - `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.

3. **In-Memory IP Rate Limiter**:
   Endpoints `/api/service-search` and `/api/jazzcash-form` enforce a limit of 10 requests per minute per IP address.

4. **Cryptographic Payment Session Tokens**:
   - `generatePaymentToken(msisdn, transId)` creates a base64 payload signed with `INTEGRITY_SALT` via HMAC SHA-256.
   - Expiration window: 5 minutes.
   - Prevents unauthorized client-side payload or signature forgery.

---

## 5. Pixel Tracking & Conversion Architecture

### A. Events Fired Across User Journey

| User Action | Target Events | Pixel Networks | Parameters / Payload |
| :--- | :--- | :--- | :--- |
| **Page Visit** | `View Content_d`, `PageView` | TikTok, Meta, GA4 | `content_id: 'bima_telemed_voucher'`, `content_type: 'product'`, `price: 300`, `currency: 'PKR'` |
| **Input Phone / Submit** | `Initiate Checkout_d`, `InitiateCheckout` | TikTok, Meta, GA4 | Includes Manual Advanced Matching (`phone_number: SHA256(+923XXXXXXXXX)`), `content_id`, `price: 300` |
| **Successful Payment** | `Purchase`, `CompletePayment`, `conversion` | TikTok, Meta, GA4, Google Ads, Firebase | `value: 300`, `currency: 'PKR'`, `transaction_id`, `content_id: 'bima_telemed_voucher'`, `send_to: 'AW-10779246142/purchase'` |
| **Failed Payment** | `Purchase Failed`, `Subscribe_Failed` | TikTok, Meta, GA4, Firebase | Error status & message tracking |

---

## 6. Campaign 2 Artwork & UI Design Tokens

- **Artwork File**: [BimaVoucher/campaign2 artwork.jpg](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/campaign2%20artwork.jpg) (Dimensions: 900 x 1600, Aspect Ratio 9:16).
- **Sub-Pixel Element Positioning**:
  - **Input Box Overlay**: `top: 72.25%`, `height: 6.56%`, `left: 13.78%`, `width: 70.00%`. Text field starts at `left: 20.5%` with `background: transparent`.
  - **Subscribe Button**: `top: 81.125%`, `height: 6.68%`, `left: 13.67%`, `width: 70.22%` with `background: transparent`.
  - **Price Info**: `top: 88.4%`.
  - **Consent Container**: `top: 90.8%`.
- **Dynamic Terms & Conditions Navigation**:
  - Link in `index2.html`: `terms_and_conditions_bima.html?returnUrl=index2.html`.
  - [terms_and_conditions_bima.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/terms_and_conditions_bima.html) inspects URL query parameter `returnUrl`, `sessionStorage` (`tc_return_url`), and `document.referrer`, ensuring seamless rollback to `index2.html`.

---

## 7. Media & Design Assets Inventory

| Asset Relative Path | Dimensions | File Size | Primary Purpose & Usage |
| :--- | :--- | :--- | :--- |
| **`BimaVoucher/campaign2 artwork.jpg`** | 900 x 1600 (9:16) | 139.9 KB | Primary background artwork image for Campaign 2 landing page ([BimaVoucher/index2.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/index2.html)). |
| **`BimaVoucher/landing_page.png`** | 1080 x 1920 (9:16) | 725.9 KB | Primary background artwork image for Campaign 1 landing page ([BimaVoucher/index.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/index.html)). |
| **`BimaVoucher/bima_logo.jpg`** | 1600 x 545 | 82.2 KB | BIMA Health brand header logo used in [terms_and_conditions_bima.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/terms_and_conditions_bima.html). |
| **`bima_logo.jpg`** | 1600 x 545 | 82.2 KB | Root-level brand logo image displayed in [callback.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/callback.html). |
| **`doctor.webp`** | 480 x 600 | 73.0 KB | Specialist doctor hero graphic displayed on transaction result cards in [callback.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/callback.html). |
| **`logo.png`** | 458 x 91 | 5.3 KB | BIMA app logo icon used in header sections across consultation landing pages. |
| **`BimaTelemedicine/family_protection.png`** | 1024 x 1024 | 721.4 KB | Background graphics for BIMA Family Telemedicine campaign landing page. |
| **`BimaTelemedicine/bima_logo.jpg`** | 1600 x 545 | 82.2 KB | Brand logo asset inside `BimaTelemedicine/` module. |
| **`Bima Artwork.png`** | 514 x 800 | 305.6 KB | Source design artwork asset for BIMA health campaign graphics. |
| **`Landing page BIMA voucher.png`** | 1080 x 1920 | 820.6 KB | Raw design composition / mockup for BIMA voucher campaign landing page. |
| **`Landing page final.png`** | 1080 x 1920 | 3.23 MB | High-resolution master design reference composition for BIMA landing page. |

---

## 8. Key Files Index

- [server.js](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/server.js): Primary Express backend server & proxy API gateway.
- [BimaVoucher/index2.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/index2.html): Campaign 2 responsive landing page & payment trigger.
- [BimaVoucher/index.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/index.html): Campaign 1 landing page.
- [callback.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/callback.html): Transaction result page & conversion pixel emitter.
- [consultation.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/consultation.html): Telemedicine consultation portal landing page.
- [BimaVoucher/terms_and_conditions_bima.html](file:///c:/Users/Nawazish%20Ali/Downloads/telemedBima/BimaVoucher/terms_and_conditions_bima.html): Campaign Terms & Conditions document.