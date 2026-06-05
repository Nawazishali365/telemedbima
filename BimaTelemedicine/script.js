/**
 * Bima Sehat Mobile Webpage Scripts
 * Focuses on phone validation, input formatting, and success transition.
 */

document.addEventListener('DOMContentLoaded', () => {
  initPhoneValidation();
});

/**
 * Initializes real-time phone validation and form submission handling.
 */
function initPhoneValidation() {
  const form = document.getElementById('subscription-form');
  const phoneInput = document.getElementById('phone-number');
  const errorMsg = document.getElementById('phone-error');
  const errorText = errorMsg.querySelector('span');
  const btnSubmit = document.getElementById('btn-continue');
  const formInner = document.getElementById('form-inner');
  const formSuccess = document.getElementById('form-success');

  // Real-time keypress filtering: allow only digits, check prefix, and limit length dynamically
  phoneInput.addEventListener('input', (e) => {
    let value = e.target.value.replace(/\D/g, '');
    
    if (value.length > 0) {
      if (value.startsWith('0')) {
        // Must start with 03
        if (value.length > 1 && value[1] !== '3') {
          value = '0';
          showValidationError("Mobile number must start with 03.");
        } else {
          hideValidationError();
        }
        // Limit to 11 digits (03XXXXXXXXX)
        if (value.length > 11) {
          value = value.substring(0, 11);
        }
      } else if (value.startsWith('3')) {
        hideValidationError();
        // Limit to 10 digits (3XXXXXXXXX)
        if (value.length > 10) {
          value = value.substring(0, 10);
        }
      } else {
        value = '';
        showValidationError("Mobile number must start with 3 or 03.");
      }
    } else {
      hideValidationError();
    }
    
    e.target.value = value;
    
    // Check if the current typed length matches the required length
    const isCompleted = (value.startsWith('0') && value.length === 11) || (value.startsWith('3') && value.length === 10);
    
    if (value.length === 0) {
      phoneInput.classList.remove('is-invalid', 'is-valid');
    } else if (isCompleted) {
      phoneInput.classList.remove('is-invalid');
      phoneInput.classList.add('is-valid');
      hideValidationError();
    } else {
      phoneInput.classList.remove('is-valid');
    }
  });

  // Check validity on input blur
  phoneInput.addEventListener('blur', () => {
    validatePhoneNumber();
  });

  // Handle Form Submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const isValid = validatePhoneNumber();
    if (!isValid) return;

    const value = phoneInput.value.trim();
    const msisdn = value.startsWith('3') ? '0' + value : value;

    // Show loading state
    setLoadingState(true);

    // Track submission event on TikTok Pixel
    if (window.ttq) {
      window.ttq.track('InitiateCheckout');
    }

    try {
      // 1. Get Auth Token
      const tokenRes = await fetch('/api/token', { method: 'POST' });
      const tokenData = await tokenRes.json().catch(() => ({}));
      
      if (!tokenRes.ok) {
        throw new Error(tokenData.message || tokenData.error || 'Token request failed: ' + tokenRes.status);
      }

      const authToken = (tokenData.result && tokenData.result.token)
          || tokenData.token
          || tokenData.auth_token
          || tokenData.authToken
          || tokenData.access_token
          || tokenData.accessToken;

      if (!authToken) {
        throw new Error('Auth token not found in response.');
      }

      // 2. Service Search
      const serviceRes = await fetch(`/api/service-search/${msisdn}`, {
        method: 'GET',
        headers: { 'auth-token': authToken }
      });
      const serviceData = await serviceRes.json().catch(() => ({}));

      if (!serviceRes.ok) {
        throw new Error(serviceData.message || serviceData.error || 'Service request failed: ' + serviceRes.status);
      }

      // 3. Build & submit JazzCash DTC form
      const transId = (serviceData.result && (serviceData.result.transId || serviceData.result.requestId || serviceData.result.transaction_id))
          || serviceData.transId
          || serviceData.requestId
          || serviceData.transaction_id
          || '';

      const formRes = await fetch(`/api/jazzcash-form?msisdn=${encodeURIComponent(msisdn)}&transId=${encodeURIComponent(transId)}`);
      const formData = await formRes.json().catch(() => ({}));

      if (!formRes.ok) {
        throw new Error(formData.error || 'Failed to build JazzCash form.');
      }

      // Store source in localStorage so callback knows where to redirect
      localStorage.setItem('jazzcash_source', 'BimaTelemedicine/');

      // Create and submit JazzCash form
      const jcForm = document.createElement('form');
      jcForm.method = 'POST';
      jcForm.action = formData.actionUrl;

      const exclude = ['actionUrl'];
      Object.entries(formData).forEach(([key, val]) => {
        if (exclude.includes(key)) return;
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = val || '';
        jcForm.appendChild(input);
      });

      document.body.appendChild(jcForm);
      setTimeout(() => jcForm.submit(), 500);

    } catch (err) {
      console.error('BIMA Family Telemedicine activation error:', err);
      showValidationError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoadingState(false);
    }
  });

  /**
   * Validates the phone number format.
   * Returns true if valid, false otherwise.
   */
  function validatePhoneNumber() {
    const value = phoneInput.value.trim();
    
    if (value === '') {
      showValidationError("Phone number is required.");
      phoneInput.classList.add('is-invalid');
      phoneInput.classList.remove('is-valid');
      return false;
    }
    
    // Matches 10 digits starting with 3, or 11 digits starting with 03
    const phoneRegex = /^(03|3)\d{9}$/;
    if (!phoneRegex.test(value)) {
      showValidationError("Mobile number must be 10 digits (starts with 3) or 11 digits (starts with 03).");
      phoneInput.classList.add('is-invalid');
      phoneInput.classList.remove('is-valid');
      return false;
    }
    
    hideValidationError();
    phoneInput.classList.remove('is-invalid');
    phoneInput.classList.add('is-valid');
    return true;
  }

  function showValidationError(message) {
    errorText.textContent = message;
    errorMsg.classList.add('show');
  }

  function hideValidationError() {
    errorMsg.classList.remove('show');
  }

  /**
   * Sets the loading UI on the submit button.
   */
  function setLoadingState(isLoading) {
    if (isLoading) {
      btnSubmit.disabled = true;
      phoneInput.disabled = true;
      btnSubmit.classList.add('is-loading');
    } else {
      btnSubmit.disabled = false;
      phoneInput.disabled = false;
      btnSubmit.classList.remove('is-loading');
    }
  }

  /**
   * Transitions form area to success confirmation view.
   */
  function showSuccessState() {
    // Fade out form content smoothly
    formInner.style.transition = 'opacity 0.25s ease';
    formInner.style.opacity = '0';
    
    setTimeout(() => {
      formInner.style.display = 'none';
      
      // Show and animate success container
      formSuccess.style.display = 'flex';
    }, 250);
  }
}
