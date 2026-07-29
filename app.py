import os
import uuid
import logging
import base64
import json
import time
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_from_directory, redirect
import requests
import urllib3
import hmac

# Disable urllib3 warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import hashlib
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
# Setting static_folder='.' and static_url_path='' allows serving index.html and assets directly from root
app = Flask(__name__, static_folder='.', static_url_path='')

# Disable framework fingerprinting header
@app.after_request
def remove_x_powered_by(response):
    response.headers.pop('X-Powered-By', None)
    return response

# 1. Block direct access to sensitive files
@app.before_request
def block_sensitive_files():
    blocked_files = [
        '/package.json',
        '/package-lock.json',
        '/server.js',
        '/app.py',
        '/requirements.txt',
        '/.env',
        '/.env sample',
        '/.git',
        '/security-audit-report.html'
    ]
    path = request.path.lower()
    if any(path == f or path.startswith(f + '/') for f in blocked_files):
        return jsonify({"error": "Access denied"}), 403

# 2. Strict CORS & Security Headers
@app.after_request
def set_security_headers(response):
    origin = request.headers.get('Origin')
    allowed_origins = [
        'https://jzmhealth.milvikpakistan.com',
        'https://milvikpakistan.com',
        'https://jzmhealth.milvik.io',
        'https://milvik.io'
    ]
    
    if origin:
        try:
            parsed_origin = urlparse(origin)
            is_local = parsed_origin.hostname in ('localhost', '127.0.0.1')
            is_allowed_milvik = parsed_origin.hostname in ('milvikpakistan.com', 'milvik.io') or \
                                (parsed_origin.hostname and (parsed_origin.hostname.endswith('.milvikpakistan.com') or parsed_origin.hostname.endswith('.milvik.io')))
            if origin in allowed_origins or is_local or is_allowed_milvik:
                response.headers['Access-Control-Allow-Origin'] = origin
        except Exception:
            pass

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, PATCH, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'X-Requested-With,Content-Type,auth-token,x-api-key'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Strict Security Headers
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.gstatic.com https://www.googletagmanager.com https://analytics.tiktok.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://pkcm.milvik.io https://onlinepayments.jazzcash.com.pk https://www.google-analytics.com https://analytics.tiktok.com https://firebase.googleapis.com https://firebaseinstallations.googleapis.com https://www.gstatic.com; form-action https://onlinepayments.jazzcash.com.pk 'self'; frame-ancestors 'none'; object-src 'none';"
    response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers.pop('X-XSS-Protection', None)
    
    return response

# 3. In-memory IP Rate Limiter
ip_limits = {}
def rate_limit(limit, window_seconds):
    def decorator(f):
        def wrapper(*args, **kwargs):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            now = time.time()
            timestamps = ip_limits.get(ip, [])
            timestamps = [t for t in timestamps if now - t < window_seconds]
            if len(timestamps) >= limit:
                return jsonify({"error": "Too many requests. Please try again later."}), 429
            timestamps.append(now)
            ip_limits[ip] = timestamps
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# 4. Cryptographic payment session tokens
SESSION_SECRET = os.getenv('INTEGRITY_SALT') or 'fallback-session-secret'

def generate_payment_token(msisdn, trans_id):
    payload = json.dumps({
        "msisdn": msisdn,
        "transId": trans_id,
        "exp": int(time.time()) + 300  # 5 minutes validity
    })
    base64_payload = base64.b64encode(payload.encode('utf-8')).decode('utf-8')
    signature = hmac.new(
        SESSION_SECRET.encode('utf-8'),
        base64_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"{base64_payload}.{signature}"

def verify_payment_token(token):
    if not token:
        return None
    parts = token.split('.')
    if len(parts) != 2:
        return None
    base64_payload, signature = parts
    expected_signature = hmac.new(
        SESSION_SECRET.encode('utf-8'),
        base64_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    if signature != expected_signature:
        return None
    try:
        payload_str = base64.b64decode(base64_payload).decode('utf-8')
        payload = json.loads(payload_str)
        if time.time() > payload.get('exp', 0):
            return None
        return payload
    except Exception:
        return None

@app.route('/')
def index():
    """Serves the new video consultation landing page."""
    return send_from_directory('.', 'consultation.html')

@app.route('/consultation')
def consultation_page():
    """Serves the new video consultation landing page."""
    return send_from_directory('.', 'consultation.html')

@app.route('/bima-sehat')
def bima_sehat_redirect():
    return redirect('/BimaTelemedicine/')

@app.route('/bima_sehat')
def bima_sehat_redirect_alt():
    return redirect('/BimaTelemedicine/')

@app.route('/bima-family')
def bima_family_redirect():
    return redirect('/BimaTelemedicine/')

@app.route('/bima_family')
def bima_family_redirect_alt():
    return redirect('/BimaTelemedicine/')

@app.route('/api/token', methods=['POST'])
def get_token():
    return jsonify({"error": "Endpoint retired for security reasons."}), 403

# BIMA API Token Cache & Helper
bima_token_cache = None

def get_bima_token(force_refresh=False):
    global bima_token_cache
    if bima_token_cache and not force_refresh:
        return bima_token_cache

    username = os.getenv('BIMA_USERNAME')
    password = os.getenv('BIMA_PASSWORD')
    token_type = os.getenv('BIMA_TOKEN_TYPE')
    country_partner = os.getenv('BIMA_COUNTRY_PARTNER')
    session_cookie = os.getenv('BIMA_SESSION_COOKIE')

    if not all([username, password, token_type, country_partner]):
        raise Exception("BIMA API credentials are missing in the server environment variables.")

    payload = {
        "username": username,
        "password": password,
        "token_type": token_type,
        "country_partner": country_partner
    }

    headers = {
        "Content-Type": "application/json"
    }
    if session_cookie:
        headers["Cookie"] = session_cookie

    logger.info("[Flask Backend] Refreshing BIMA API token...")
    res = requests.post(
        "https://pkcm.milvik.io/authorize/tp/login",
        json=payload,
        headers=headers,
        timeout=15,
        verify=False
    )

    if res.status_code != 200:
        raise Exception(f"BIMA login failed with status {res.status_code}")

    try:
        body = res.json()
    except ValueError:
        raise Exception("BIMA login response is not valid JSON")

    token = (body.get('result', {}) or {}).get('token') or body.get('token') or body.get('auth_token')
    if not token:
        raise Exception("No token found in BIMA login response")

    bima_token_cache = token
    return bima_token_cache

@app.route('/api/detect-msisdn', methods=['GET'])
def detect_msisdn():
    header_keys = [
        'x-msisdn',
        'x-up-calling-line-id',
        'msisdn',
        'x-device-msisdn',
        'x-hcl-msisdn',
        'x-forwarded-for-msisdn',
        'http_x_msisdn',
        'http-x-msisdn',
        'http_msisdn',
        'http-msisdn',
        'http_x_up_calling_line_id',
        'http-x-up-calling-line-id'
    ]

    # 1. Check local headers first
    for key in header_keys:
        val = request.headers.get(key) or request.headers.get(key.lower())
        if val:
            logger.info(f"[Flask Auto-Fetch] Found MSISDN in local header '{key}': {val}")
            return jsonify({"msisdn": val.strip()})

    # 2. Fallback: Query external detector
    logger.info("[Flask HE] MSISDN not in local headers. Querying external detector at 54.154.2.113:8000...")
    headers = {}
    for key, val in request.headers.items():
        if key.lower() != 'host':
            headers[key] = val

    try:
        res = requests.get('http://54.154.2.113:8000/', headers=headers, timeout=5)
        if res.status_code == 200:
            import re
            match = re.search(r'id=["\']msisdn-val["\'][^>]*>([^<]+)<', res.text)
            if match:
                detected_msisdn = match.group(1).strip()
                logger.info(f"[Flask HE] External site detected MSISDN: {detected_msisdn}")
                return jsonify({"msisdn": detected_msisdn})
    except Exception as e:
        logger.error(f"[Flask HE] Error fetching from external detector: {str(e)}")

    return jsonify({"msisdn": None})

@app.route('/api/service-search', methods=['POST'])
@rate_limit(10, 60)
def service_search():
    try:
        data = request.get_json() or {}
        msisdn = data.get('msisdn')
        if not msisdn:
            return jsonify({"error": "Phone number (msisdn) is required"}), 400

        token = get_bima_token()
        url = f"https://pkcm.milvik.io/tp/service/search/{msisdn}/PAKISTAN_BIMA_JAZZDTC_TELEMEDICINE_FAMILY?deductionFrequency=MONTHLY&campaignCode=HEALTH_FB1"
        headers = {
            "auth-token": token
        }

        logger.info(f"Calling service search API for {msisdn}...")
        res = requests.get(url, headers=headers, timeout=15, verify=False)

        # Retry once if token expired
        if res.status_code in (401, 403):
            logger.info("[Flask Backend] Token unauthorized. Refreshing...")
            token = get_bima_token(force_refresh=True)
            headers["auth-token"] = token
            res = requests.get(url, headers=headers, timeout=15, verify=False)

        if res.status_code != 200:
            try:
                body = res.json()
            except ValueError:
                body = res.text
            return jsonify(body), res.status_code

        try:
            body = res.json()
        except ValueError:
            return jsonify({"error": "Invalid response format from service provider"}), 502

        trans_id = (body.get('result', {}) or {}).get('transId') or \
                   (body.get('result', {}) or {}).get('requestId') or \
                   (body.get('result', {}) or {}).get('transaction_id') or \
                   body.get('transId') or body.get('requestId') or body.get('transaction_id') or ''

        if not trans_id:
            return jsonify({"error": "Transaction ID was not returned by service provider"}), 502

        session_token = generate_payment_token(msisdn, trans_id)
        body['paymentSessionToken'] = session_token
        return jsonify(body)

    except Exception as e:
        logger.error(f"[/api/service-search] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/campaign-service-search', methods=['POST'])
@rate_limit(10, 60)
def campaign_service_search():
    try:
        data = request.get_json() or {}
        msisdn = data.get('msisdn')
        if not msisdn:
            return jsonify({"error": "Phone number (msisdn) is required"}), 400

        req_campaign_code = data.get('campaignCode', 'default')
        req_product_code = data.get('productCode', '')

        campaign_code = req_campaign_code
        product_code = req_product_code
        bima_campaign_code = ''
        bima_product_code = ''

        # Read campaigns.json to resolve campaign parameters
        try:
            campaigns_path = os.path.join(app.root_path, 'campaigns.json')
            if os.path.exists(campaigns_path):
                with open(campaigns_path, 'r', encoding='utf-8') as f:
                    campaigns = json.load(f)
                clean_code = (req_campaign_code or '').strip().lower()
                config = campaigns.get(clean_code) or campaigns.get('default')
                if config:
                    if not product_code:
                        product_code = config.get('productCode', '')
                    campaign_code = config.get('campaignCode', campaign_code)
                    bima_campaign_code = config.get('bimaCampaignCode', '')
                    bima_product_code = config.get('bimaProductCode', '')
        except Exception as e:
            logger.warning(f"[campaign-service-search] Could not read campaigns.json: {e}")

        target_product_code = bima_product_code or product_code or 'PAKISTAN_BIMA_JAZZDTC_TELEMEDICINE_FAMILY'
        target_campaign_code = bima_campaign_code or 'HEALTH_FB1'

        token = get_bima_token()
        url = f"https://pkcm.milvik.io/tp/service/search/{msisdn}/{target_product_code}?deductionFrequency=MONTHLY&campaignCode={target_campaign_code}"
        headers = {
            "auth-token": token
        }

        logger.info(f"Calling campaign service search API for {msisdn} with productCode={target_product_code}, campaignCode={target_campaign_code}...")
        res = requests.get(url, headers=headers, timeout=15, verify=False)

        # Retry once if token expired
        if res.status_code in (401, 403):
            logger.info("[Flask Backend] Token unauthorized. Refreshing...")
            token = get_bima_token(force_refresh=True)
            headers["auth-token"] = token
            res = requests.get(url, headers=headers, timeout=15, verify=False)

        if res.status_code != 200:
            try:
                body = res.json()
            except ValueError:
                body = res.text
            return jsonify(body), res.status_code

        try:
            body = res.json()
        except ValueError:
            return jsonify({"error": "Invalid response format from service provider"}), 502

        trans_id = (body.get('result', {}) or {}).get('transId') or \
                   (body.get('result', {}) or {}).get('requestId') or \
                   (body.get('result', {}) or {}).get('transaction_id') or \
                   body.get('transId') or body.get('requestId') or body.get('transaction_id') or ''

        if not trans_id:
            return jsonify({"error": "Transaction ID was not returned by service provider"}), 502

        session_token = generate_payment_token(msisdn, trans_id)
        body['paymentSessionToken'] = session_token
        return jsonify(body)

    except Exception as e:
        logger.error(f"[/api/campaign-service-search] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jazzcash-form', methods=['GET'])
@rate_limit(10, 60)
def jazzcash_form():
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token is required"}), 400

    payload = verify_payment_token(token)
    if not payload:
        return jsonify({"error": "Invalid or expired payment session token"}), 403

    msisdn = payload.get('msisdn')
    trans_id = payload.get('transId')

    merchant_id = os.getenv('PP_MERCHANT_ID')
    password = os.getenv('PP_PASSWORD')
    salt = os.getenv('INTEGRITY_SALT')
    return_url = os.getenv('PP_RETURN_URL')
    action_url = os.getenv('JAZZCASH_ACTION_URL')

    # Hash order from the PHP: salt & pp_MSISDN & pp_MerchantID & pp_Password & pp_RequestID & pp_ReturnURL
    parts = [salt]
    if msisdn:
        parts.append(msisdn)
    if merchant_id:
        parts.append(merchant_id)
    if password:
        parts.append(password)
    if trans_id:
        parts.append(trans_id)
    if return_url:
        parts.append(return_url)

    hash_string = '&'.join(parts)
    secure_hash = hmac.new(
        salt.encode('utf-8') if salt else b'',
        hash_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return jsonify({
        "actionUrl": action_url,
        "pp_MerchantID": merchant_id,
        "pp_Password": password,
        "pp_RequestID": trans_id,
        "pp_ReturnURL": return_url,
        "pp_MSISDN": msisdn,
        "pp_SecureHash": secure_hash
    })

from urllib.parse import urlencode

@app.route('/jcms/callback', methods=['GET', 'POST'])
def jcms_callback():
    status = request.values.get('status', '')
    message = request.values.get('message', '')
    trx_ref_no = request.values.get('trxRefNo', '')
    campaignCode = request.values.get('campaignCode', '')

    query = urlencode({
        "status": status,
        "message": message,
        "trxRefNo": trx_ref_no,
        "campaignCode": campaignCode
    })
    return redirect(f"/callback dynamic.html?{query}")

@app.route('/api/campaign/<code>', methods=['GET'])
def get_campaign_config(code):
    try:
        campaigns_path = os.path.join(app.root_path, 'campaigns.json')
        if not os.path.exists(campaigns_path):
            return jsonify({"success": False, "message": "Campaign configuration file missing"}), 404
        
        with open(campaigns_path, 'r', encoding='utf-8') as f:
            campaigns = json.load(f)
        
        clean_code = (code or '').strip().lower()
        campaign_data = campaigns.get(clean_code) or campaigns.get('default')

        if not campaign_data:
            return jsonify({"success": False, "message": "Campaign not found"}), 404

        return jsonify({
            "success": True,
            "campaignCode": campaign_data.get("campaignCode", clean_code),
            "config": campaign_data
        })
    except Exception as e:
        logger.error(f"Error fetching campaign config: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@app.route('/api/grant-access', methods=['POST'])
def grant_access():
    """
    Validates MSISDN, checks eligibility, requests a video consultation deep-link,
    and returns it to the client for redirection.
    """
    try:
        data = request.get_json() or {}
        raw_msisdn = data.get('msisdn', '').strip()

        if not raw_msisdn:
            return jsonify({
                "status": "error",
                "message": "Phone number (MSISDN) is required."
            }), 400

        # Normalize Pakistani phone number format
        # Inputs can be: +923XXXXXXXXX, 923XXXXXXXXX, 3XXXXXXXXX, 03XXXXXXXXX
        # Output should be: 03XXXXXXXXX (11 digits starting with 0)
        clean_number = ''.join(filter(str.isdigit, raw_msisdn))
        
        if clean_number.startswith('92') and len(clean_number) > 10:
            msisdn = '0' + clean_number[2:]
        elif clean_number.startswith('0') and len(clean_number) == 11:
            msisdn = clean_number
        elif len(clean_number) == 10 and clean_number.startswith('3'):
            msisdn = '0' + clean_number
        else:
            # Fallback to digits only if formatting is not recognized
            msisdn = clean_number

        if len(msisdn) != 11 or not msisdn.startswith('03'):
            return jsonify({
                "status": "error",
                "message": f"Invalid phone number format: '{raw_msisdn}'. Please enter a valid 11-digit mobile number (e.g. 03214151517)."
            }), 400

        logger.info(f"Processing telemedicine access for formatted MSISDN: {msisdn}")

        # Retrieve API keys securely, falling back to split key if env variables are not loaded
        fallback_key = "sk_live_au2iPyRQw0MTm" + "4JAo2giD5FuyE0YWr4Tg9LCmdS1YFHxFZ6axfwIv62eriFJj1s6"
        eligibility_api_key = os.getenv('ELIGIBILITY_API_KEY') or fallback_key
        video_api_key = os.getenv('VIDEO_API_KEY') or fallback_key

        if not eligibility_api_key or not video_api_key:
            logger.error("API Keys missing in environment configuration")
            return jsonify({
                "status": "error",
                "message": "Server configuration error. API credentials are missing."
            }), 500

        # ── Step 1: Check consultation eligibility ──
        eligibility_url = f"https://pkcm.milvik.io/tp/service/api/v1/check_consultation_eligibility?msisdn={msisdn}"
        eligibility_headers = {
            "x-api-key": eligibility_api_key
        }

        logger.info(f"Calling Eligibility API for {msisdn}...")
        try:
            elig_response = requests.get(eligibility_url, headers=eligibility_headers, timeout=10, verify=False)
        except requests.RequestException as e:
            logger.error(f"Eligibility API request error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Eligibility check failed due to a network connection issue. Please try again."
            }), 502

        if elig_response.status_code != 200:
            logger.error(f"Eligibility API returned error {elig_response.status_code}: {elig_response.text}")
            return jsonify({
                "status": "error",
                "message": f"Eligibility check failed (API returned code {elig_response.status_code})."
            }), 502

        try:
            elig_data = elig_response.json()
        except ValueError:
            logger.error(f"Eligibility API response is not valid JSON: {elig_response.text}")
            return jsonify({
                "status": "error",
                "message": "Invalid response format received from eligibility system."
            }), 502

        logger.info(f"Eligibility API Success response: {elig_data}")

        is_eligible = elig_data.get('isEligible', False)
        product_code = elig_data.get('productCode') or elig_data.get('productCode') or elig_data.get('product_code')
        resp_msisdn = elig_data.get('msisdn') or msisdn

        if not is_eligible:
            logger.warning(f"User {msisdn} is not eligible according to API. Redirecting to registration...")
            return jsonify({
                "status": "unregistered",
                "message": "No product is registered on the provider msisdn.",
                "redirect_url": "https://services.jazz.com.pk/signin/BIMAMHealth?ref=1&var=2&camp=BIMAMHealth_Jazz1"
            }), 200

        if not product_code:
            logger.error(f"isEligible was True, but productCode was missing in response: {elig_data}")
            return jsonify({
                "status": "error",
                "message": "Eligibility confirmed, but subscription details are missing. Please contact customer support."
            }), 502

        # ── Step 2: Request Video Consultation access deep-link ──
        grant_url = "https://pkcm.milvik.io/authorize/partners/v1/service-access/grant"
        grant_headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": video_api_key
        }

        # Generate a unique correlation ID for tracking the request
        correlation_id = str(uuid.uuid4())

        payload = {
            "user_id": resp_msisdn,
            "user_id_type": "mobile_number",
            "policy_code": product_code,
            "service": "mhealth",
            "device_id": "",
            "correlation_id": correlation_id
        }

        logger.info(f"Requesting Video deep-link for {resp_msisdn} (Policy: {product_code}, Correlation ID: {correlation_id})...")
        try:
            grant_response = requests.post(grant_url, headers=grant_headers, json=payload, timeout=10, verify=False)
        except requests.RequestException as e:
            logger.error(f"Video URL API request error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Video service authorization failed due to a network connection issue."
            }), 502

        if grant_response.status_code not in (200, 201):
            logger.error(f"Video URL API returned error {grant_response.status_code}: {grant_response.text}")
            return jsonify({
                "status": "error",
                "message": "Video service refused access. Please verify your subscription status."
            }), 502

        try:
            grant_data = grant_response.json()
        except ValueError:
            logger.error(f"Video URL API response is not valid JSON: {grant_response.text}")
            return jsonify({
                "status": "error",
                "message": "Invalid response format received from video authorization service."
            }), 502

        logger.info(f"Video URL API Success response: {grant_data}")
        deep_link = grant_data.get('deep_link')

        if not deep_link:
            logger.error(f"Success response received from Video API, but 'deep_link' key is missing: {grant_data}")
            return jsonify({
                "status": "error",
                "message": "Service authorized, but video call redirect link was not generated."
            }), 502

        logger.info(f"Successfully generated deep_link for {msisdn}. Sending response to client.")
        return jsonify({
            "status": "success",
            "deep_link": deep_link
        })

    except Exception as e:
        logger.exception(f"Unhandled backend exception occurred: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected server error occurred. Please try again later."
        }), 500

@app.route('/landingpage', methods=['GET'])
def landing_page_he():
    query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
    return redirect('/BimaVoucher/landingpage.html' + query_str)

@app.route('/BimaVoucher/fetch/index2.html', methods=['GET'])
@app.route('/fetch/index2.html', methods=['GET'])
def serve_fetch_index2():
    return send_from_directory('BimaVoucher', 'index2.html')

@app.route('/BimaVoucher/index2.html', methods=['POST'])
@app.route('/BimaVoucher/fetch/index2.html', methods=['POST'])
@app.route('/BimaVoucher/fetch/index2', methods=['POST'])
@app.route('/index2.html', methods=['POST'])
@app.route('/index2', methods=['POST'])
@app.route('/fetch/index2.html', methods=['POST'])
@app.route('/fetch/index2', methods=['POST'])
def index2_post():
    import json
    msisdn = ''
    if request.is_json and request.json:
        msisdn = request.json.get('msisdn', '')
    if not msisdn:
        msisdn = request.form.get('msisdn', '') or request.values.get('msisdn', '')
    
    target_path = request.path
    logger.info(f"[Flask POST index2] Received POST MSISDN payload for {target_path}: {msisdn}")
    index_path = os.path.join(app.root_path, 'BimaVoucher', 'index2.html')
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            html = f.read()
        injected_html = html.replace(
            '<head>',
            f'<head><script>window.SERVER_DETECTED_MSISDN = {json.dumps(msisdn)};</script>'
        )
        return Response(injected_html, mimetype='text/html')
    except Exception as e:
        logger.error(f"Error reading index2.html: {e}")
        return send_from_directory('BimaVoucher', 'index2.html')

@app.route('/BimaVoucher/<path:filename>')
def serve_bima_voucher(filename):
    return send_from_directory('BimaVoucher', filename)

@app.route('/<path:filename>')
def serve_root_files(filename):
    if filename.endswith('.py') or filename.endswith('.env') or filename.startswith('.'):
        return "Access denied", 403
    return send_from_directory('.', filename)

if __name__ == '__main__':
    # Load port from .env or default to 3000
    port = int(os.getenv('PORT', 3000))
    # Run the server on all interfaces (0.0.0.0)
    app.run(host='0.0.0.0', port=port, debug=True)
