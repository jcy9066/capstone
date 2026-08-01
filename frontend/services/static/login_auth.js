(() => {
    const LOGIN_ID_PATTERN = /^(?=.*[A-Za-z])[A-Za-z0-9]{4,20}$/;
    const PASSWORD_PATTERN = /^[A-Za-z0-9!@#$]{6,20}$/;
    const PHONE_PATTERN = /^[0-9-]{8,20}$/;
    const EMPLOYEE_NUMBER_PATTERN = /^[0-9]{1,10}$/;
    const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    let csrfToken = '';
    let resendTimer = null;
    const state = {
        emailVerified: false,
        verifiedEmail: '',
        loginIdAvailable: false,
        employeeNumberAvailable: false,
    };

    function loadStylesheet() {
        const stylesheet = document.createElement('link');
        stylesheet.rel = 'stylesheet';
        stylesheet.href = '/static/login_auth.css?v=20260731-auth';
        document.head.appendChild(stylesheet);
    }

    async function refreshCsrfToken() {
        const response = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
        const data = await response.json();
        if (!response.ok || !data.csrf_token) throw new Error('보안 토큰을 준비하지 못했습니다. 페이지를 새로고침해 주세요.');
        csrfToken = data.csrf_token;
    }

    async function requestJson(url, payload) {
        if (!csrfToken) await refreshCsrfToken();
        const response = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
            body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) throw new Error(data.detail || '요청을 처리하지 못했습니다.');
        return data;
    }

    function message(element, text = '', type = '') {
        element.textContent = text;
        element.className = element.className.replace(/\b(error|success)\b/g, '').trim();
        if (type) element.classList.add(type);
    }

    function render() {
        document.body.className = 'login-page';
        document.body.innerHTML = `
            <main class="login-shell">
                <section class="login-panel" aria-labelledby="login-title">
                    <div class="login-brand">
                        <span class="login-brand-kicker">AI Patrol Control</span>
                        <h1 id="login-title">AI 순찰 로봇 관제 센터</h1>
                    </div>
                    <form class="login-form" id="loginForm" novalidate>
                        <label class="auth-field" for="loginId"><span>로그인 ID</span><input id="loginId" autocomplete="username" maxlength="20" required></label>
                        <label class="auth-field" for="loginPassword"><span>비밀번호</span><input id="loginPassword" type="password" autocomplete="current-password" maxlength="20" required></label>
                        <p class="auth-login-message" id="loginMessage" role="status" aria-live="polite"></p>
                        <div class="auth-actions"><button class="auth-btn secondary" type="button" id="openSignupBtn">회원가입</button><button class="auth-btn primary" type="submit" id="loginSubmit">로그인</button></div>
                    </form>
                </section>
            </main>
            <div class="signup-modal" id="signupModal" aria-hidden="true">
                <div class="signup-modal-backdrop" data-close-signup></div>
                <section class="signup-dialog" role="dialog" aria-modal="true" aria-labelledby="signup-title">
                    <div class="signup-header"><h2 id="signup-title">회원가입</h2><button class="signup-close" type="button" id="closeSignupBtn" aria-label="회원가입 닫기">&times;</button></div>
                    <p class="auth-dialog-subtitle">이메일 인증 후 로그인 정보를 입력할 수 있습니다.</p>
                    <form class="signup-form" id="signupForm" novalidate>
                        <div class="auth-inline-action">
                            <label class="auth-field" for="signupEmail"><span>이메일</span><input id="signupEmail" type="email" autocomplete="email" maxlength="100" required></label>
                            <button class="email-send-btn" type="button" id="sendEmailBtn">인증번호 발송</button>
                        </div>
                        <div class="auth-verify-row" id="verifyRow" hidden>
                            <div class="auth-inline-action">
                                <label class="auth-field" for="verificationCode"><span>이메일 인증번호</span><input id="verificationCode" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6"></label>
                                <button class="email-send-btn" type="button" id="verifyEmailBtn">인증 확인</button>
                            </div>
                        </div>
                        <p class="auth-signup-message" id="signupMessage" role="status" aria-live="polite"></p>
                        <fieldset class="auth-protected-fields" id="protectedFields" disabled>
                            <div class="auth-verified-email" id="verifiedEmailLabel" hidden></div>
                            <label class="auth-field" for="signupLoginId"><span>로그인 ID</span><input id="signupLoginId" autocomplete="username" maxlength="20" required><small class="auth-field-hint" id="loginIdHint">영문 포함 4~20자의 영문·숫자</small></label>
                            <label class="auth-field" for="signupPassword"><span>비밀번호</span><input id="signupPassword" type="password" autocomplete="new-password" maxlength="20" required><small class="auth-field-hint">6~20자, 영문·숫자·! @ # $만 사용 가능</small></label>
                            <label class="auth-field" for="signupPasswordConfirm"><span>비밀번호 확인</span><input id="signupPasswordConfirm" type="password" autocomplete="new-password" maxlength="20" required><small class="auth-field-hint" id="passwordHint"></small></label>
                            <label class="auth-field" for="signupName"><span>이름</span><input id="signupName" autocomplete="name" maxlength="20" required></label>
                            <label class="auth-field" for="signupPhone"><span>전화번호</span><input id="signupPhone" type="tel" autocomplete="tel" inputmode="tel" maxlength="20" placeholder="010-1234-5678" required></label>
                            <label class="auth-field" for="employeeNumber"><span>사번</span><input id="employeeNumber" inputmode="numeric" maxlength="10" required><small class="auth-field-hint" id="employeeHint"></small></label>
                            <button class="auth-btn primary signup-submit" type="submit" id="signupSubmit" disabled>가입하기</button>
                        </fieldset>
                    </form>
                </section>
            </div>`;
    }

    function initialize() {
        render();
        const byId = (id) => document.getElementById(id);
        const loginForm = byId('loginForm');
        const loginMessage = byId('loginMessage');
        const signupModal = byId('signupModal');
        const signupForm = byId('signupForm');
        const signupMessage = byId('signupMessage');
        const email = byId('signupEmail');
        const verifyRow = byId('verifyRow');
        const code = byId('verificationCode');
        const protectedFields = byId('protectedFields');
        const signupLoginId = byId('signupLoginId');
        const employeeNumber = byId('employeeNumber');
        const loginIdHint = byId('loginIdHint');
        const employeeHint = byId('employeeHint');
        const password = byId('signupPassword');
        const passwordConfirm = byId('signupPasswordConfirm');
        const passwordHint = byId('passwordHint');
        const signupSubmit = byId('signupSubmit');
        const verifiedEmailLabel = byId('verifiedEmailLabel');
        const sendEmailBtn = byId('sendEmailBtn');

        function resetVerification() {
            state.emailVerified = false;
            state.verifiedEmail = '';
            state.loginIdAvailable = false;
            state.employeeNumberAvailable = false;
            protectedFields.disabled = true;
            verifyRow.hidden = true;
            verifiedEmailLabel.hidden = true;
            verifiedEmailLabel.textContent = '';
            code.value = '';
            message(loginIdHint, '영문 포함 4~20자의 영문·숫자');
            message(employeeHint);
            syncSignupButton();
        }

        function validSignupForm() {
            return state.emailVerified && state.verifiedEmail === email.value.trim().toLowerCase()
                && LOGIN_ID_PATTERN.test(signupLoginId.value)
                && state.loginIdAvailable
                && PASSWORD_PATTERN.test(password.value)
                && password.value === passwordConfirm.value
                && byId('signupName').value.trim().length >= 1
                && PHONE_PATTERN.test(byId('signupPhone').value.trim())
                && EMPLOYEE_NUMBER_PATTERN.test(employeeNumber.value.trim())
                && Number(employeeNumber.value) <= 2147483647
                && state.employeeNumberAvailable;
        }

        function syncSignupButton() { signupSubmit.disabled = !validSignupForm(); }

        function closeSignup() { signupModal.classList.remove('open'); signupModal.setAttribute('aria-hidden', 'true'); }
        function openSignup() { signupModal.classList.add('open'); signupModal.setAttribute('aria-hidden', 'false'); email.focus(); }

        async function checkAvailability(field, input, hint, validator) {
            if (!validator(input.value.trim())) { state[field === 'login_id' ? 'loginIdAvailable' : 'employeeNumberAvailable'] = false; syncSignupButton(); return; }
            try {
                const result = await requestJson('/api/auth/availability', { field, value: input.value.trim() });
                const stateKey = field === 'login_id' ? 'loginIdAvailable' : 'employeeNumberAvailable';
                state[stateKey] = result.available;
                message(hint, result.available ? '사용 가능합니다.' : '이미 사용 중입니다.', result.available ? 'success' : 'error');
            } catch (error) {
                state[field === 'login_id' ? 'loginIdAvailable' : 'employeeNumberAvailable'] = false;
                message(hint, error.message, 'error');
            }
            syncSignupButton();
        }

        byId('openSignupBtn').addEventListener('click', openSignup);
        byId('closeSignupBtn').addEventListener('click', closeSignup);
        signupModal.addEventListener('click', (event) => { if (event.target.matches('[data-close-signup]')) closeSignup(); });
        document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSignup(); });
        email.addEventListener('input', resetVerification);

        byId('sendEmailBtn').addEventListener('click', async () => {
            const emailValue = email.value.trim().toLowerCase();
            if (!EMAIL_PATTERN.test(emailValue)) { message(signupMessage, '올바른 이메일 주소를 입력해 주세요.', 'error'); email.focus(); return; }
            try {
                sendEmailBtn.disabled = true;
                const result = await requestJson('/api/auth/email/send', { email: emailValue });
                verifyRow.hidden = false;
                message(signupMessage, `인증번호를 발송했습니다. ${Math.ceil(result.expires_in_sec / 60)}분 안에 입력해 주세요.`, 'success');
                code.focus();
                let remaining = result.resend_after_sec;
                clearInterval(resendTimer);
                resendTimer = setInterval(() => {
                    remaining -= 1;
                    if (remaining <= 0) { clearInterval(resendTimer); sendEmailBtn.disabled = false; sendEmailBtn.textContent = '인증번호 재발송'; return; }
                    sendEmailBtn.textContent = `재발송 (${remaining}s)`;
                }, 1000);
            } catch (error) {
                sendEmailBtn.disabled = false;
                message(signupMessage, error.message, 'error');
            }
        });

        byId('verifyEmailBtn').addEventListener('click', async () => {
            if (!/^\d{6}$/.test(code.value.trim())) { message(signupMessage, '6자리 인증번호를 입력해 주세요.', 'error'); return; }
            try {
                await requestJson('/api/auth/email/verify', { email: email.value.trim().toLowerCase(), code: code.value.trim() });
                state.emailVerified = true;
                state.verifiedEmail = email.value.trim().toLowerCase();
                protectedFields.disabled = false;
                verifiedEmailLabel.hidden = false;
                verifiedEmailLabel.textContent = `이메일 인증 완료: ${state.verifiedEmail}`;
                message(signupMessage, '이메일 인증이 완료되었습니다. 가입 정보를 입력해 주세요.', 'success');
                signupLoginId.focus();
                syncSignupButton();
            } catch (error) { message(signupMessage, error.message, 'error'); }
        });

        let loginIdTimer;
        signupLoginId.addEventListener('input', () => {
            state.loginIdAvailable = false;
            const valid = LOGIN_ID_PATTERN.test(signupLoginId.value);
            message(loginIdHint, valid ? '중복 여부를 확인 중입니다.' : '영문 포함 4~20자의 영문·숫자만 사용할 수 있습니다.', valid ? '' : 'error');
            clearTimeout(loginIdTimer);
            if (valid) loginIdTimer = setTimeout(() => checkAvailability('login_id', signupLoginId, loginIdHint, (value) => LOGIN_ID_PATTERN.test(value)), 450);
            syncSignupButton();
        });
        let employeeTimer;
        employeeNumber.addEventListener('input', () => {
            state.employeeNumberAvailable = false;
            const valid = EMPLOYEE_NUMBER_PATTERN.test(employeeNumber.value) && Number(employeeNumber.value) <= 2147483647;
            message(employeeHint, valid ? '중복 여부를 확인 중입니다.' : '사번은 최대 10자리 숫자로 입력해 주세요.', valid ? '' : 'error');
            clearTimeout(employeeTimer);
            if (valid) employeeTimer = setTimeout(() => checkAvailability('employee_number', employeeNumber, employeeHint, (value) => EMPLOYEE_NUMBER_PATTERN.test(value) && Number(value) <= 2147483647), 450);
            syncSignupButton();
        });
        [password, passwordConfirm, byId('signupName'), byId('signupPhone')].forEach((input) => input.addEventListener('input', () => {
            if (passwordConfirm.value) message(passwordHint, password.value === passwordConfirm.value ? '비밀번호가 일치합니다.' : '비밀번호가 일치하지 않습니다.', password.value === passwordConfirm.value ? 'success' : 'error');
            syncSignupButton();
        }));

        signupForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!validSignupForm()) { message(signupMessage, '모든 가입 정보를 올바르게 입력하고 중복 확인을 완료해 주세요.', 'error'); return; }
            try {
                signupSubmit.disabled = true;
                await requestJson('/api/auth/register', {
                    email: state.verifiedEmail,
                    login_id: signupLoginId.value.trim(), password: password.value, password_confirm: passwordConfirm.value,
                    name: byId('signupName').value.trim(), phone_number: byId('signupPhone').value.trim(), employee_number: employeeNumber.value.trim(),
                });
                message(signupMessage, '회원가입이 완료되었습니다. 로그인해 주세요.', 'success');
                setTimeout(() => { closeSignup(); byId('loginId').focus(); }, 900);
            } catch (error) { message(signupMessage, error.message, 'error'); syncSignupButton(); }
        });

        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const loginId = byId('loginId').value.trim();
            const loginPassword = byId('loginPassword').value;
            if (!loginId || !loginPassword) { message(loginMessage, '로그인 ID와 비밀번호를 입력해 주세요.', 'error'); return; }
            try {
                byId('loginSubmit').disabled = true;
                const result = await requestJson('/api/auth/login', { login_id: loginId, password: loginPassword });
                window.location.assign(result.redirect_url);
            } catch (error) { message(loginMessage, error.message, 'error'); byId('loginSubmit').disabled = false; }
        });
        refreshCsrfToken().catch((error) => message(loginMessage, error.message, 'error'));
    }

    loadStylesheet();
    document.addEventListener('DOMContentLoaded', initialize);
})();
