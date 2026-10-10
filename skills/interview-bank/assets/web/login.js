// Login page of a hosted reader. The page is served at the reader's own address, so a successful login reloads it.
'use strict';

const LOGIN_TEXT = {
  zh: {
    tagline: '每一次积累，都算数。', title: '登录你的题库', lead: '题目、参考答案和练习进度，只对你本人可见。',
    username: '用户名', password: '密码', show: '显示', hide: '隐藏', submit: '登录', busy: '正在登录…',
    foot: 'HTTPS 加密连接 · 连续输错会暂时锁定', repo: '开源项目 · 在 GitHub 上查看', empty: '请输入用户名和密码。', offline: '暂时连不上服务器，请稍后重试。',
  },
  en: {
    tagline: 'Every question counts.', title: 'Sign in to your bank', lead: 'Questions, answers and practice are visible to you only.',
    username: 'Username', password: 'Password', show: 'Show', hide: 'Hide', submit: 'Sign in', busy: 'Signing in…',
    foot: 'Encrypted over HTTPS · repeated mistakes lock sign-in for a while', repo: 'Open source · view on GitHub', empty: 'Enter your username and password.',
    offline: 'The server cannot be reached right now. Try again shortly.',
  },
};
const lang = (navigator.language || 'zh').toLowerCase().startsWith('zh') ? 'zh' : 'en';
const say = key => LOGIN_TEXT[lang][key];

document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
document.querySelectorAll('[data-login]').forEach(node => { node.textContent = say(node.dataset.login); });

const form = document.getElementById('login-form');
const username = document.getElementById('login-username');
const password = document.getElementById('login-password');
const reveal = document.getElementById('login-reveal');
const submit = document.getElementById('login-submit');
const error = document.getElementById('login-error');

function showError(text) {
  error.textContent = text;
  error.hidden = !text;
  form.classList.toggle('shake', Boolean(text));
  if (text) setTimeout(() => form.classList.remove('shake'), 400);
}

reveal.addEventListener('click', () => {
  const visible = password.type === 'text';
  password.type = visible ? 'password' : 'text';
  reveal.textContent = say(visible ? 'show' : 'hide');
  reveal.setAttribute('aria-pressed', String(!visible));
  password.focus();
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!username.value.trim() || !password.value) return showError(say('empty'));
  submit.disabled = true;
  submit.textContent = say('busy');
  showError('');
  try {
    const response = await fetch('api/login', {
      method: 'POST', cache: 'no-store', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    });
    const result = await response.json().catch(() => ({}));
    if (response.ok) return location.reload();
    password.value = '';
    showError(result.error || say('offline'));
  } catch (_) {
    showError(say('offline'));
  } finally {
    submit.disabled = false;
    submit.textContent = say('submit');
  }
});

username.focus();
