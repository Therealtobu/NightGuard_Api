// NightGuard V2 — main.js
// Calls POST /obfuscate → real Python CLI engine on server

// ── Elements ──────────────────────────────────────────────────────────────────
const inputEl   = document.getElementById('inputCode');
const outputEl  = document.getElementById('outputCode');
const runBtn    = document.getElementById('runBtn');
const clearBtn  = document.getElementById('clearBtn');
const copyBtn   = document.getElementById('copyBtn');
const statusDot = document.getElementById('statusDot');
const statusTxt = document.getElementById('statusText');
const resultMeta= document.getElementById('resultMeta');
const inputSize = document.getElementById('inputSize');
const seedToggle= document.getElementById('opt-seed');
const seedVal   = document.getElementById('seed-val');

// ── Seed toggle ───────────────────────────────────────────────────────────────
seedToggle.addEventListener('change', () => {
  seedVal.disabled = !seedToggle.checked;
  if (!seedToggle.checked) seedVal.value = '';
});
seedVal.disabled = true;

// ── Input size counter ────────────────────────────────────────────────────────
inputEl.addEventListener('input', () => {
  const bytes = new Blob([inputEl.value]).size;
  inputSize.textContent = bytes < 1024
    ? `${bytes} B`
    : `${(bytes / 1024).toFixed(1)} KB`;
});

// ── Status helper ─────────────────────────────────────────────────────────────
function setStatus(state, msg) {
  statusDot.className = 'status-dot ' + state;
  statusTxt.textContent = msg;
}

// ── Format bytes ──────────────────────────────────────────────────────────────
function fmtBytes(n) {
  if (n < 1024)       return `${n} B`;
  if (n < 1024*1024)  return `${(n/1024).toFixed(1)} KB`;
  return `${(n/1024/1024).toFixed(2)} MB`;
}

// ── Clear ─────────────────────────────────────────────────────────────────────
clearBtn.addEventListener('click', () => {
  inputEl.value  = '';
  outputEl.value = '';
  resultMeta.style.display = 'none';
  inputSize.textContent = '0 B';
  setStatus('', 'Ready');
});

// ── Copy ──────────────────────────────────────────────────────────────────────
copyBtn.addEventListener('click', async () => {
  if (!outputEl.value) return;
  try {
    await navigator.clipboard.writeText(outputEl.value);
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1800);
  } catch {
    // fallback
    outputEl.select();
    document.execCommand('copy');
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1800);
  }
});

// ── FAQ ───────────────────────────────────────────────────────────────────────
document.querySelectorAll('.faq-item').forEach(item => {
  item.querySelector('.faq-q').addEventListener('click', () => {
    const wasOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
    if (!wasOpen) item.classList.add('open');
  });
});

// ── MAIN: call /obfuscate ─────────────────────────────────────────────────────
runBtn.addEventListener('click', async () => {
  const code = inputEl.value.trim();
  if (!code) {
    setStatus('error', 'Paste a Lua script first');
    return;
  }

  // Build request payload
  const payload = { code };
  if (seedToggle.checked && seedVal.value !== '') {
    const s = parseInt(seedVal.value, 10);
    if (!isNaN(s) && s >= 0) payload.seed = s;
  }

  // UI: loading state
  runBtn.disabled = true;
  outputEl.value  = '';
  resultMeta.style.display = 'none';
  setStatus('busy', 'Compiling to VM bytecode…');

  const t0 = Date.now();

  try {
    const res = await fetch('/obfuscate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      // Server returned an error
      const msg = data.detail || data.error || `HTTP ${res.status}`;
      setStatus('error', `Error: ${msg}`);
      outputEl.value = `-- Error: ${msg}`;
      return;
    }

    // Success
    const elapsed = ((Date.now() - t0) / 1000).toFixed(2);
    outputEl.value = data.result;
    setStatus('ok', `Done in ${elapsed}s`);

    // Show meta
    const ratio = (data.output_bytes / data.input_bytes).toFixed(1);
    document.getElementById('metaIn').textContent    = fmtBytes(data.input_bytes);
    document.getElementById('metaOut').textContent   = fmtBytes(data.output_bytes);
    document.getElementById('metaRatio').textContent = `${ratio}×`;
    resultMeta.style.display = 'flex';

  } catch (err) {
    setStatus('error', `Network error: ${err.message}`);
    outputEl.value = `-- Network error: ${err.message}`;
  } finally {
    runBtn.disabled = false;
  }
});
