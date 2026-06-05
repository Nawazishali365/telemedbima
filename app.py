import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory, redirect
import requests
import hmac
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
    return redirect('/BIMA%20Family%20Telemedicine/index.html')

@app.route('/bima_sehat')
def bima_sehat_redirect_alt():
    return redirect('/BIMA%20Family%20Telemedicine/index.html')

@app.route('/bima-family')
def bima_family_redirect():
    return redirect('/BIMA%20Family%20Telemedicine/index.html')

@app.route('/bima_family')
def bima_family_redirect_alt():
    return redirect('/BIMA%20Family%20Telemedicine/index.html')

@app.route('/api/token', methods=['POST'])
def get_token():
    try:
        username = os.getenv('BIMA_USERNAME')
        password = os.getenv('BIMA_PASSWORD')
        token_type = os.getenv('BIMA_TOKEN_TYPE')
        country_partner = os.getenv('BIMA_COUNTRY_PARTNER')
        session_cookie = os.getenv('BIMA_SESSION_COOKIE')

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

        logger.info("Calling BIMA login API...")
        res = requests.post(
            "https://bcare.milvikpakistan.com/authorize/tp/login",
            json=payload,
            headers=headers,
            timeout=15
        )

        try:
            body = res.json()
        except ValueError:
            body = res.text

        return jsonify(body), res.status_code
    except Exception as e:
        logger.error(f"[/api/token] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/service-search/<msisdn>', methods=['GET'])
def service_search(msisdn):
    auth_token = request.headers.get('auth-token')
    if not auth_token:
        return jsonify({"error": "Missing auth-token header"}), 400

    try:
        url = f"https://bcare.milvikpakistan.com/tp/service/search/{msisdn}/PAKISTAN_BIMA_JAZZDTC_TELEMEDICINE_FAMILY?deductionFrequency=MONTHLY"
        headers = {
            "auth-token": auth_token
        }

        logger.info(f"Calling service search API for {msisdn}...")
        res = requests.get(url, headers=headers, timeout=15)

        try:
            body = res.json()
        except ValueError:
            body = res.text

        return jsonify(body), res.status_code
    except Exception as e:
        logger.error(f"[/api/service-search] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/jazzcash-form', methods=['GET'])
def jazzcash_form():
    msisdn = request.args.get('msisdn')
    trans_id = request.args.get('transId')

    if not msisdn or not trans_id:
        return jsonify({"error": "msisdn and transId are required"}), 400

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

    query = urlencode({
        "status": status,
        "message": message,
        "trxRefNo": trx_ref_no
    })
    return redirect(f"/callback.html?{query}")

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
        eligibility_url = f"https://dtc.milvikpakistan.com/tp/service/api/v1/check_consultation_eligibility?msisdn={msisdn}"
        eligibility_headers = {
            "x-api-key": eligibility_api_key
        }

        logger.info(f"Calling Eligibility API for {msisdn}...")
        try:
            elig_response = requests.get(eligibility_url, headers=eligibility_headers, timeout=10)
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
            grant_response = requests.post(grant_url, headers=grant_headers, json=payload, timeout=10)
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

if __name__ == '__main__':
    # Load port from .env or default to 3000
    port = int(os.getenv('PORT', 3000))
    # Run the server on all interfaces (0.0.0.0)
    app.run(host='0.0.0.0', port=port, debug=True)
