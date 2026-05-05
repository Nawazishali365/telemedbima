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

app.listen(PORT, () => {
    console.log(`\n✅  Server running → http://localhost:${PORT}\n`);
});
