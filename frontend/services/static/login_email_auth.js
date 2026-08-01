(() => {
  const emailOk = v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  const passwordOk = v => /^[A-Za-z0-9!@#$]{6,20}$/.test(v);
  const phoneOk = v => /^[0-9-]{8,20}$/.test(v);
  const employeeOk = v => /^\d{1,10}$/.test(v) && Number(v) <= 2147483647;
  let csrf = '';
  const state = { verified: false, email: '', employeeAvailable: false };

  const byId = id => document.getElementById(id);
  const text = (element, value = '', type = '') => {
    element.textContent = value;
    element.className = element.className.replace(/\b(error|success)\b/g, '').trim();
    if (type) element.classList.add(type);
  };

  async function refreshCsrf() {
    const response = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
    const data = await response.json();
    if (!response.ok || !data.csrf_token) throw new Error('보안 토큰을 준비하지 못했습니다. 페이지를 새로고침해 주세요.');
    csrf = data.csrf_token;
  }

  async function post(url, payload) {
    if (!csrf) await refreshCsrf();
    const response = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || '요청을 처리하지 못했습니다.');
    return data;
  }

  function render() {
    document.body.className = 'login-page';
    document.body.innerHTML = `
      <main class="login-shell"><section class="login-panel">
        <div class="login-brand"><span class="login-brand-kicker">AI Patrol Control</span><h1>AI 자율순찰 로봇 관제 센터</h1></div>
        <form class="login-form" id="emailLoginForm" novalidate>
          <label class="auth-field" for="loginEmail"><span>이메일 (로그인 ID)</span><input id="loginEmail" type="email" autocomplete="username" maxlength="100" required></label>
          <label class="auth-field" for="loginPassword"><span>비밀번호</span><input id="loginPassword" type="password" autocomplete="current-password" maxlength="20" required></label>
          <p class="auth-login-message" id="loginMessage" role="status"></p>
          <div class="auth-actions"><button class="auth-btn secondary" type="button" id="openSignup">회원가입</button><button class="auth-btn primary" id="loginSubmit">로그인</button></div>
        </form>
      </section></main>
      <div class="signup-modal" id="signupModal" aria-hidden="true"><div class="signup-modal-backdrop" data-close></div>
        <section class="signup-dialog" role="dialog" aria-modal="true"><div class="signup-header"><h2>회원가입</h2><button class="signup-close" type="button" id="closeSignup" aria-label="닫기">&times;</button></div>
          <p class="auth-dialog-subtitle">이메일 전체가 로그인 ID입니다. 별도의 ID는 입력하지 않습니다.</p>
          <form class="signup-form" id="emailSignupForm" novalidate>
            <div class="auth-inline-action"><label class="auth-field" for="signupEmail"><span>이메일</span><input id="signupEmail" type="email" autocomplete="email" maxlength="100" required></label><button class="email-send-btn" type="button" id="sendCode">인증번호 발송</button></div>
            <div class="auth-verify-row" id="verificationRow" hidden><div class="auth-inline-action"><label class="auth-field" for="verificationCode"><span>인증번호</span><input id="verificationCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6"></label><button class="email-send-btn" type="button" id="verifyCode">인증 확인</button></div></div>
            <p class="auth-signup-message" id="signupMessage" role="status"></p>
            <fieldset class="auth-protected-fields" id="signupFields" disabled>
              <div class="auth-verified-email" id="verifiedEmail" hidden></div>
              <label class="auth-field" for="signupPassword"><span>비밀번호</span><input id="signupPassword" type="password" autocomplete="new-password" maxlength="20" required><small class="auth-field-hint">6~20자 영문, 숫자, ! @ # $ 사용 가능</small></label>
              <label class="auth-field" for="passwordConfirm"><span>비밀번호 2차 확인</span><input id="passwordConfirm" type="password" autocomplete="new-password" maxlength="20" required><small class="auth-field-hint" id="passwordHint"></small></label>
              <label class="auth-field" for="signupName"><span>이름</span><input id="signupName" autocomplete="name" maxlength="20" required></label>
              <label class="auth-field" for="signupPhone"><span>전화번호</span><input id="signupPhone" type="tel" autocomplete="tel" maxlength="20" placeholder="010-1234-5678" required></label>
              <label class="auth-field" for="employeeNumber"><span>사번</span><input id="employeeNumber" inputmode="numeric" maxlength="10" required><small class="auth-field-hint" id="employeeHint"></small></label>
              <button class="auth-btn primary signup-submit" id="signupSubmit">가입하기</button>
            </fieldset>
          </form>
        </section>
      </div>`;
  }

  function init() {
    render();
    const loginMessage = byId('loginMessage');
    const signupMessage = byId('signupMessage');
    const email = byId('signupEmail');
    const password = byId('signupPassword');
    const confirm = byId('passwordConfirm');
    const employee = byId('employeeNumber');
    const employeeHint = byId('employeeHint');
    const submit = byId('signupSubmit');
    const protectedFields = byId('signupFields');

    const canSubmit = () => state.verified && state.email === email.value.trim().toLowerCase() && passwordOk(password.value) && password.value === confirm.value && byId('signupName').value.trim() && phoneOk(byId('signupPhone').value.trim()) && employeeOk(employee.value.trim()) && state.employeeAvailable;
    const sync = () => { submit.disabled = !canSubmit(); };
    const reset = () => {
      state.verified = false; state.email = ''; state.employeeAvailable = false;
      byId('verificationRow').hidden = true; protectedFields.disabled = true;
      byId('verifiedEmail').hidden = true; byId('verificationCode').value = '';
      text(employeeHint); sync();
    };

    byId('openSignup').onclick = () => { byId('signupModal').classList.add('open'); byId('signupModal').setAttribute('aria-hidden', 'false'); email.focus(); };
    const close = () => { byId('signupModal').classList.remove('open'); byId('signupModal').setAttribute('aria-hidden', 'true'); };
    byId('closeSignup').onclick = close;
    byId('signupModal').onclick = event => { if (event.target.matches('[data-close]')) close(); };
    email.oninput = reset;

    byId('sendCode').onclick = async () => {
      const value = email.value.trim().toLowerCase();
      if (!emailOk(value)) return text(signupMessage, '올바른 이메일 주소를 입력해 주세요.', 'error');
      const button = byId('sendCode'); button.disabled = true;
      try {
        const result = await post('/api/auth/email/send', { email: value });
        byId('verificationRow').hidden = false;
        text(signupMessage, `인증번호를 발송했습니다. ${Math.ceil(result.expires_in_sec / 60)}분 안에 입력해 주세요.`, 'success');
        byId('verificationCode').focus();
      } catch (error) { text(signupMessage, error.message, 'error'); }
      finally { button.disabled = false; }
    };

    byId('verifyCode').onclick = async () => {
      const value = email.value.trim().toLowerCase();
      const code = byId('verificationCode').value.trim();
      if (!/^\d{6}$/.test(code)) return text(signupMessage, '6자리 인증번호를 입력해 주세요.', 'error');
      try {
        await post('/api/auth/email/verify', { email: value, code });
        state.verified = true; state.email = value; protectedFields.disabled = false;
        byId('verifiedEmail').hidden = false; byId('verifiedEmail').textContent = `인증된 로그인 ID: ${value}`;
        text(signupMessage, '이메일 인증이 완료되었습니다. 비밀번호와 가입 정보를 입력해 주세요.', 'success');
        password.focus(); sync();
      } catch (error) { text(signupMessage, error.message, 'error'); }
    };

    let employeeTimer;
    employee.oninput = () => {
      state.employeeAvailable = false; clearTimeout(employeeTimer);
      if (!employeeOk(employee.value.trim())) { text(employeeHint, '사번은 최대 10자리 숫자로 입력해 주세요.', 'error'); return sync(); }
      employeeTimer = setTimeout(async () => {
        try {
          const result = await post('/api/auth/availability', { field: 'employee_number', value: employee.value.trim() });
          state.employeeAvailable = result.available;
          text(employeeHint, result.available ? '사용 가능합니다.' : '이미 사용 중입니다.', result.available ? 'success' : 'error');
        } catch (error) { text(employeeHint, error.message, 'error'); }
        sync();
      }, 350);
      sync();
    };
    [password, confirm, byId('signupName'), byId('signupPhone')].forEach(input => input.oninput = () => {
      if (confirm.value) text(byId('passwordHint'), password.value === confirm.value ? '비밀번호가 일치합니다.' : '비밀번호가 일치하지 않습니다.', password.value === confirm.value ? 'success' : 'error');
      sync();
    });

    byId('emailSignupForm').onsubmit = async event => {
      event.preventDefault();
      if (!canSubmit()) return text(signupMessage, '필수 정보를 올바르게 입력해 주세요.', 'error');
      submit.disabled = true;
      try {
        await post('/api/auth/register', { email: state.email, password: password.value, password_confirm: confirm.value, name: byId('signupName').value.trim(), phone_number: byId('signupPhone').value.trim(), employee_number: employee.value.trim() });
        text(signupMessage, '회원가입이 완료되었습니다. 이메일과 비밀번호로 로그인해 주세요.', 'success');
        setTimeout(() => { close(); byId('loginEmail').focus(); }, 800);
      } catch (error) { text(signupMessage, error.message, 'error'); sync(); }
    };

    byId('emailLoginForm').onsubmit = async event => {
      event.preventDefault();
      const loginEmail = byId('loginEmail').value.trim().toLowerCase();
      const loginPassword = byId('loginPassword').value;
      if (!emailOk(loginEmail) || !loginPassword) return text(loginMessage, '이메일과 비밀번호를 입력해 주세요.', 'error');
      byId('loginSubmit').disabled = true;
      try {
        const result = await post('/api/auth/login', { login_id: loginEmail, password: loginPassword });
        window.location.assign(result.redirect_url);
      } catch (error) { text(loginMessage, error.message, 'error'); byId('loginSubmit').disabled = false; }
    };
    refreshCsrf().catch(error => text(loginMessage, error.message, 'error'));
  }

  document.addEventListener('DOMContentLoaded', init);
})();
