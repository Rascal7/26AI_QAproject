const form = document.querySelector('[data-testid="login-form"]');
const email = form.elements.email, password = form.elements.password;
const button = form.querySelector('button'), common = form.querySelector('[role="alert"]');
const genericError = '요청을 처리하지 못했습니다. 다시 시도하세요.';
function fieldError(input, message) {
  document.getElementById(`${input.name}-error`).textContent = message;
  input.setAttribute('aria-invalid', message ? 'true' : 'false');
}
for (const input of [email, password]) input.addEventListener('input', () => fieldError(input, ''));
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (form.dataset.state === 'submitting') return;
  common.textContent = '';
  const normalizedEmail = email.value.trim().toLowerCase();
  const emailError = !normalizedEmail ? '이메일을 입력하세요.' :
    (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail) ? '올바른 이메일 형식을 입력하세요.' : '');
  const passwordError = password.value === '' ? '비밀번호를 입력하세요.' : '';
  fieldError(email, emailError); fieldError(password, passwordError);
  if (emailError || passwordError) {
    form.dataset.state = 'invalid'; (emailError ? email : password).focus(); return;
  }
  form.dataset.state = 'submitting'; button.disabled = true; button.textContent = '로그인 중…';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:normalizedEmail,password:password.value}), signal:controller.signal});
    const data = await response.json();
    if (response.status === 200 && data.ok === true) {
      form.dataset.state = 'success'; window.location.assign('/home'); return;
    }
    if (response.status === 400 && data.field_errors) {
      fieldError(email, data.field_errors.email || ''); fieldError(password, data.field_errors.password || '');
      form.dataset.state = 'invalid'; (data.field_errors.email ? email : password).focus();
    } else {
      common.textContent = response.status >= 500 ? genericError : data.message || genericError;
      form.dataset.state = [401,403].includes(response.status) ? 'rejected' : 'error';
    }
  } catch { common.textContent = genericError; form.dataset.state = 'error'; }
  finally { clearTimeout(timer); button.disabled = false; button.textContent = '로그인'; }
});
