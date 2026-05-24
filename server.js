require('dotenv').config();

const express = require('express');
const path    = require('path');
const https   = require('https');
const crypto  = require('crypto');

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname)));

/* ── helper: HTTPS request → { status, body } ── */
function httpsRequest(options, postBody) {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let raw = '';
            res.on('data', chunk => raw += chunk);
            res.on('end', () => {
                try { resolve({ status: res.statusCode, body: JSON.parse(raw) }); }
                catch { resolve({ status: res.statusCode, body: raw }); }
            });
        });
        req.on('error', reject);
        if (postBody) req.write(postBody);
        req.end();
    });
}

/* ──────────────────────────────────────────────────────────────────
   PROXY 1: Token endpoint
   POST /api/token  →  bcare.milvikpakistan.com/authorize/tp/login
   ────────────────────────────────────────────────────────────────── */
app.post('/api/token', async (req, res) => {
    try {
        const payload = JSON.stringify({
            username:        process.env.BIMA_USERNAME,
            password:        process.env.BIMA_PASSWORD,
            token_type:      process.env.BIMA_TOKEN_TYPE,
            country_partner: process.env.BIMA_COUNTRY_PARTNER
        });

        const { status, body } = await httpsRequest({
            hostname: 'bcare.milvikpakistan.com',
            path:     '/authorize/tp/login',
            method:   'POST',
            headers: {
                'Content-Type':   'application/json',
                'Content-Length': Buffer.byteLength(payload),
                'Cookie':         process.env.BIMA_SESSION_COOKIE
            }
        }, payload);

        res.status(status).json(body);
    } catch (err) {
        console.error('[/api/token]', err.message);
        res.status(500).json({ error: err.message });
    }
});

/* ──────────────────────────────────────────────────────────────────
   PROXY 2: Service search
   GET /api/service-search/:msisdn
       →  bcare.milvikpakistan.com/tp/service/search/{msisdn}/...
   ────────────────────────────────────────────────────────────────── */
app.get('/api/service-search/:msisdn', async (req, res) => {
    const { msisdn }  = req.params;
    const authToken   = req.headers['auth-token'];

    if (!authToken) {
        return res.status(400).json({ error: 'Missing auth-token header' });
    }

    try {
        const apiPath =
            `/tp/service/search/${msisdn}/PAKISTAN_BIMA_JAZZDTC_TELEMEDICINE_FAMILY?deductionFrequency=MONTHLY`;

        const { status, body } = await httpsRequest({
            hostname: 'bcare.milvikpakistan.com',
            path:     apiPath,
            method:   'GET',
            headers:  { 'auth-token': authToken }
        });

        res.status(status).json(body);
    } catch (err) {
        console.error('[/api/service-search]', err.message);
        res.status(500).json({ error: err.message });
    }
});

/* ──────────────────────────────────────────────────────────────────
   JAZZCASH FORM DATA
   GET /api/jazzcash-form?msisdn=0300...&transId=abc123
   Returns all JazzCash form fields + SecureHash (computed server-side)
   ────────────────────────────────────────────────────────────────── */
app.get('/api/jazzcash-form', (req, res) => {
    const { msisdn, transId } = req.query;

    if (!msisdn || !transId) {
        return res.status(400).json({ error: 'msisdn and transId are required' });
    }

    const merchantId = process.env.PP_MERCHANT_ID;
    const password   = process.env.PP_PASSWORD;
    const salt       = process.env.INTEGRITY_SALT;
    const returnUrl  = process.env.PP_RETURN_URL;
    const actionUrl  = process.env.JAZZCASH_ACTION_URL;

    // Hash order from the PHP: salt & pp_MSISDN & pp_MerchantID & pp_Password & pp_RequestID & pp_ReturnURL
    const parts = [salt];
    if (msisdn)     parts.push(msisdn);
    if (merchantId) parts.push(merchantId);
    if (password)   parts.push(password);
    if (transId)    parts.push(transId);
    if (returnUrl)  parts.push(returnUrl);

    const hashString = parts.join('&');
    const secureHash = crypto
        .createHmac('sha256', salt)
        .update(hashString)
        .digest('hex');

    console.log('[/api/jazzcash-form] hashString:', hashString);
    console.log('[/api/jazzcash-form] secureHash:', secureHash);

    res.json({
        actionUrl,
        pp_MerchantID: merchantId,
        pp_Password:   password,
        pp_RequestID:  transId,
        pp_ReturnURL:  returnUrl,
        pp_MSISDN:     msisdn,
        pp_SecureHash: secureHash
    });
});

/* ──────────────────────────────────────────────────────────────────
   CALLBACK ENDPOINT
   POST /jcms/callback
   ────────────────────────────────────────────────────────────────── */
app.post('/jcms/callback', (req, res) => {
    // Extract parameters from body (POST) or query (GET)
    const status = req.body.status || req.query.status || '';
    const message = req.body.message || req.query.message || '';
    const trxRefNo = req.body.trxRefNo || req.query.trxRefNo || '';

    // Pass them to the frontend HTML page via query parameters
    const query = new URLSearchParams({ status, message, trxRefNo }).toString();
    res.redirect(`/callback.html?${query}`);
});

/* ──────────────────────────────────────────────────────────────────
   TELEMEDICINE REDIRECT & SECURE PROXY ROUTE
   ────────────────────────────────────────────────────────────────── */

// Serve consultation.html as the primary landing page on root '/' and '/consultation'
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'consultation.html'));
});

app.get('/consultation', (req, res) => {
    res.sendFile(path.join(__dirname, 'consultation.html'));
});

app.post('/api/grant-access', async (req, res) => {
    try {
        let rawMsisdn = (req.body.msisdn || '').toString().trim();
        if (!rawMsisdn) {
            return res.status(400).json({ status: 'error', message: 'Phone number (MSISDN) is required.' });
        }

        // Format to Pakistani local format 03XXXXXXXXX
        let cleanNumber = rawMsisdn.replace(/[^0-9]/g, '');
        let msisdn = cleanNumber;
        
        if (cleanNumber.startsWith('92') && cleanNumber.length > 10) {
            msisdn = '0' + cleanNumber.substring(2);
        } else if (cleanNumber.startsWith('0') && cleanNumber.length === 11) {
            msisdn = cleanNumber;
        } else if (cleanNumber.length === 10 && cleanNumber.startsWith('3')) {
            msisdn = '0' + cleanNumber;
        }

        if (msisdn.length !== 11 || !msisdn.startsWith('03')) {
            return res.status(400).json({
                status: 'error',
                message: `Invalid phone number format: '${rawMsisdn}'. Please enter a valid 11-digit mobile number.`
            });
        }

        const eligibilityApiKey = process.env.ELIGIBILITY_API_KEY;
        const videoApiKey = process.env.VIDEO_API_KEY;

        if (!eligibilityApiKey || !videoApiKey) {
            console.error("API Keys missing in environment configuration (.env)");
            return res.status(500).json({
                status: 'error',
                message: 'Server configuration error. API credentials are missing.'
            });
        }

        // ── Step 1: Check Eligibility ──
        console.log(`[Node.js Proxy] Calling Eligibility API for ${msisdn}...`);
        const eligResult = await httpsRequest({
            hostname: 'dtc.milvikpakistan.com',
            path: `/tp/service/api/v1/check_consultation_eligibility?msisdn=${msisdn}`,
            method: 'GET',
            headers: {
                'x-api-key': eligibilityApiKey
            }
        });

        if (eligResult.status !== 200) {
            console.error(`[Node.js Proxy] Eligibility API returned status ${eligResult.status}:`, eligResult.body);
            return res.status(502).json({
                status: 'error',
                message: `Eligibility check failed (API returned code ${eligResult.status}).`
            });
        }

        const eligData = eligResult.body;
        const isEligible = eligData.isEligible;
        const productCode = eligData.productCode || eligData.product_code;
        const respMsisdn = eligData.msisdn || msisdn;

        if (!isEligible) {
            console.warn(`[Node.js Proxy] User ${msisdn} is not eligible.`);
            return res.json({
                status: 'error',
                message: 'Your phone number is not eligible for telemedicine consultations at this time.'
            });
        }

        if (!productCode) {
            console.error(`[Node.js Proxy] productCode was missing in eligibility response:`, eligData);
            return res.status(502).json({
                status: 'error',
                message: 'Eligibility confirmed, but subscription details are missing. Please contact customer support.'
            });
        }

        // ── Step 2: Request Video deep-link ──
        const correlationId = crypto.randomUUID ? crypto.randomUUID() : require('uuid').v4(); // fallback
        const payload = JSON.stringify({
            user_id: respMsisdn,
            user_id_type: 'mobile_number',
            policy_code: productCode,
            service: 'mhealth',
            device_id: '',
            correlation_id: correlationId
        });

        console.log(`[Node.js Proxy] Requesting Video deep-link for ${respMsisdn}...`);
        const grantResult = await httpsRequest({
            hostname: 'pkcm.milvik.io',
            path: '/authorize/partners/v1/service-access/grant',
            method: 'POST',
            headers: {
                'accept': 'application/json',
                'Content-Type': 'application/json',
                'x-api-key': videoApiKey,
                'Content-Length': Buffer.byteLength(payload)
            }
        }, payload);

        if (grantResult.status !== 200 && grantResult.status !== 201) {
            console.error(`[Node.js Proxy] Video API returned status ${grantResult.status}:`, grantResult.body);
            return res.status(502).json({
                status: 'error',
                message: 'Video service refused access. Please verify your subscription status.'
            });
        }

        const grantData = grantResult.body;
        const deepLink = grantData.deep_link;

        if (!deepLink) {
            console.error(`[Node.js Proxy] deep_link key missing in Video API response:`, grantData);
            return res.status(502).json({
                status: 'error',
                message: 'Service authorized, but video call redirect link was not generated.'
            });
        }

        console.log(`[Node.js Proxy] Successfully generated deep_link for ${msisdn}.`);
        return res.json({
            status: 'success',
            deep_link: deepLink
        });

    } catch (err) {
        console.error('[Node.js Proxy] Unhandled backend error:', err);
        return res.status(500).json({
            status: 'error',
            message: 'An unexpected server error occurred. Please try again later.'
        });
    }
});

app.listen(PORT, () => {
    console.log(`\n✅  Server running → http://localhost:${PORT}\n`);
});
