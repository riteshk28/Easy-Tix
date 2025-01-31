document.addEventListener('DOMContentLoaded', function() {
    console.log('Register.js: Script started');
    const emailInput = document.getElementById('email');
    const verifyEmailBtn = document.getElementById('verifyEmailBtn');
    const verificationSection = document.getElementById('verificationSection');
    const otpInput = document.getElementById('otp');
    const verifyOtpBtn = document.getElementById('verifyOtpBtn');
    const emailVerifiedBadge = document.getElementById('emailVerifiedBadge');
    const submitBtn = document.querySelector('button[type="submit"]');
    
    // Check if we're on the registration page
    if (!emailInput || !verifyEmailBtn) {
        console.log('Not on registration page, skipping email verification setup');
        return;
    }
    
    // Initially disable submit button
    submitBtn.disabled = true;
    
    console.log('Register.js: Setting up click handler for verify button');
    
    verifyEmailBtn.addEventListener('click', async function(e) {
        e.preventDefault(); // Prevent any default button behavior
        console.log('Register.js: Verify button clicked');
        const email = emailInput.value;
        if (!email) {
            alert('Please enter an email address');
            return;
        }
        
        try {
            const response = await fetch('/auth/verify-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrf_token]').value
                },
                body: JSON.stringify({ email })
            });
            
            if (response.ok) {
                verificationSection.classList.remove('d-none');
                verifyEmailBtn.disabled = true;
                alert('OTP sent to your email');
            } else {
                const data = await response.json();
                alert(data.message || 'Error sending OTP');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error sending OTP');
        }
    });
    
    verifyOtpBtn.addEventListener('click', async function() {
        const email = emailInput.value;
        const otp = otpInput.value;
        
        try {
            const response = await fetch('/auth/verify-email-otp', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrf_token]').value
                },
                body: JSON.stringify({ email, otp })
            });
            
            if (response.ok) {
                verificationSection.classList.add('d-none');
                emailVerifiedBadge.classList.remove('d-none');
                emailInput.readOnly = true;
                verifyEmailBtn.style.display = 'none';
                submitBtn.disabled = false;
            } else {
                const data = await response.json();
                alert(data.message || 'Invalid OTP');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error verifying OTP');
        }
    });
}); 