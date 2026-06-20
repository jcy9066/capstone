document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const signupModal = document.getElementById('signupModal');
    const openSignupBtn = document.getElementById('openSignupBtn');
    const closeSignupBtn = document.getElementById('closeSignupBtn');
    const signupForm = document.getElementById('signupForm');
    const sendEmailBtn = document.getElementById('sendEmailBtn');
    const signupMessage = document.getElementById('signupMessage');
    const signupEmail = document.getElementById('signupEmail');

    function setSignupMessage(message, type) {
        signupMessage.textContent = message;
        signupMessage.classList.remove('error', 'success');
        if (type) signupMessage.classList.add(type);
    }

    function openSignupModal() {
        signupModal.classList.add('open');
        signupModal.setAttribute('aria-hidden', 'false');
        setSignupMessage('', '');
        setTimeout(() => signupEmail.focus(), 0);
    }

    function closeSignupModal() {
        signupModal.classList.remove('open');
        signupModal.setAttribute('aria-hidden', 'true');
    }

    loginForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!loginForm.reportValidity()) return;
        window.location.href = '/main';
    });

    openSignupBtn.addEventListener('click', openSignupModal);
    closeSignupBtn.addEventListener('click', closeSignupModal);
    signupModal.addEventListener('click', (event) => {
        if (event.target.matches('[data-close-signup]')) closeSignupModal();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && signupModal.classList.contains('open')) closeSignupModal();
    });

    sendEmailBtn.addEventListener('click', () => {
        if (!signupEmail.reportValidity()) return;
        setSignupMessage('이메일 형식을 확인했습니다.', 'success');
    });

    signupForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!signupForm.reportValidity()) return;

        const password = document.getElementById('signupPassword').value;
        const passwordConfirm = document.getElementById('signupPasswordConfirm').value;

        if (password !== passwordConfirm) {
            setSignupMessage('비밀번호가 일치하지 않습니다.', 'error');
            document.getElementById('signupPasswordConfirm').focus();
            return;
        }

        setSignupMessage('입력값이 확인되었습니다.', 'success');
    });
});
