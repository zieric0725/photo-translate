'use strict';

// ───────────────────────── 常數與小工具 ─────────────────────────
const MAX_FILES = 6;
const MAX_FILE_BYTES = 15 * 1024 * 1024;
const HISTORY_KEY = 'translate_history_v2';
const MAX_HISTORY = 20;
const POLL_MS = 2000;
const POLL_TIMEOUT_MS = 10000;     // 單次查詢最久等多久（半開連線時 fetch 可能永遠不回）
const GIVE_UP_MS = 45000;         // 連續查詢失敗超過這麼久才放棄
const UPLOAD_BASE_MS = 60000;     // 上傳逾時 = 基本 60 秒 + 依檔案大小（以 100KB/秒估算）
const STAGES = [
  { icon: '📤', label: '上傳中' },
  { icon: '🔍', label: '辨識文字' },
  { icon: '🌐', label: '翻譯中' },
  { icon: '✨', label: '整理結果' },
];

const $ = id => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

// 圖片來源只接受我們自己產生的 data:image（縮圖）或 blob:（本機預覽）
function safeImgSrc(s) {
  if (typeof s !== 'string') return '';
  if (/^data:image\/(jpeg|png);base64,[A-Za-z0-9+/=]+$/.test(s)) return s;
  if (s.startsWith('blob:')) return s;
  return '';
}

async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) { /* 改用備援 */ }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  } catch (e) {
    return false;
  }
}

function makeCopyButton(getText, cls, label) {
  const btn = el('button', cls);
  btn.type = 'button';
  const icon = el('span', null, '📋');
  icon.setAttribute('aria-hidden', 'true');
  const txt = el('span', null, label);
  btn.append(icon, txt);
  btn.addEventListener('click', async () => {
    const ok = await copyText(getText());
    icon.textContent = ok ? '✓' : '⚠️';
    txt.textContent = ok ? '已複製' : '複製失敗';
    btn.classList.toggle('copied', ok);
    setTimeout(() => {
      icon.textContent = '📋';
      txt.textContent = label;
      btn.classList.remove('copied');
    }, 2000);
  });
  return btn;
}

// 結果 = [{src, tgt}]，一律用 textContent 渲染，不會被當成 HTML
function renderBlocks(blocks) {
  const wrap = el('div', 'result-text-bilingual');
  blocks.forEach(b => {
    const src = String((b && b.src) || '');
    const tgt = String((b && b.tgt) || '');
    const block = el('div', 'bilingual-block');
    if (src && src !== tgt) block.appendChild(el('div', 'bilingual-original', src));
    block.appendChild(el('div', 'bilingual-translation', tgt || src));
    wrap.appendChild(block);
  });
  return wrap;
}

function blocksToText(blocks) {
  return blocks.map(b => {
    const src = String((b && b.src) || '');
    const tgt = String((b && b.tgt) || '');
    return src && src !== tgt ? src + '\n' + tgt : (tgt || src);
  }).join('\n\n');
}

// ───────────────────────── 翻譯紀錄（sessionStorage，只存文字與小縮圖） ─────────────────────────
function getHistory() {
  try {
    const v = JSON.parse(sessionStorage.getItem(HISTORY_KEY));
    return Array.isArray(v) ? v : [];
  } catch (e) {
    return [];
  }
}

function saveHistory(list) {
  list = list.slice(0, MAX_HISTORY);
  for (;;) {
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(list));
      return;
    } catch (e) {
      // 空間不足：丟掉最舊的一筆再試
      if (list.length <= 1) {
        try { sessionStorage.removeItem(HISTORY_KEY); } catch (e2) { /* ignore */ }
        return;
      }
      list.pop();
    }
  }
}

function formatTime(ts) {
  const d = new Date(ts);
  const hm = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return '今天 ' + hm;
  return (d.getMonth() + 1) + '/' + d.getDate() + ' ' + hm;
}

function renderHistory() {
  const list = getHistory();
  const container = $('historyList');
  container.querySelectorAll('.history-item').forEach(n => n.remove());
  $('historyEmpty').style.display = list.length ? 'none' : 'block';

  list.forEach((item, idx) => {
    const blocks = Array.isArray(item && item.blocks) ? item.blocks : [];
    const thumb = safeImgSrc(item && item.thumb);
    const bodyId = 'history-body-' + idx;

    const wrap = el('div', 'history-item');

    const head = el('button', 'history-item-header');
    head.type = 'button';
    head.setAttribute('aria-expanded', 'false');
    head.setAttribute('aria-controls', bodyId);
    if (thumb) {
      const t = el('img', 'history-thumb');
      t.src = thumb;
      t.alt = '';
      head.appendChild(t);
    }
    const meta = el('div', 'history-meta');
    meta.appendChild(el('div', 'history-time', formatTime(item && item.ts)));
    const first = blocks[0] || {};
    meta.appendChild(el('div', 'history-preview', String(first.tgt || first.src || '').slice(0, 40) + '…'));
    head.appendChild(meta);
    const chev = el('span', 'history-chevron', '▼');
    chev.setAttribute('aria-hidden', 'true');
    head.appendChild(chev);

    const body = el('div', 'history-body');
    body.id = bodyId;
    if (thumb) {
      const full = el('img', 'history-full-img');
      full.src = thumb;
      full.alt = '原圖縮圖';
      body.appendChild(full);
    }
    body.appendChild(renderBlocks(blocks));
    body.appendChild(makeCopyButton(() => blocksToText(blocks), 'history-copy-btn', '複製'));

    head.addEventListener('click', () => {
      const open = body.classList.toggle('open');
      chev.classList.toggle('open', open);
      head.setAttribute('aria-expanded', String(open));
    });

    wrap.append(head, body);
    container.appendChild(wrap);
  });
}

function clearHistory() {
  if (confirm('確定要清除所有紀錄嗎？')) {
    try { sessionStorage.removeItem(HISTORY_KEY); } catch (e) { /* ignore */ }
    renderHistory();
  }
}

// ───────────────────────── 畫面狀態 ─────────────────────────
function setStage(idx) {
  STAGES.forEach((s, i) => {
    const e = $('stage' + (i + 1));
    e.className = 'stage' + (i < idx ? ' done' : i === idx ? ' active' : '');
    e.textContent = (i < idx ? '✅' : s.icon) + ' ' + s.label;
  });
}

function setLoadingText(t) {
  $('loadingText').textContent = t;
}

function setBusy(busy) {
  const btn = $('submitBtn');
  btn.disabled = busy;
  btn.textContent = busy ? '翻譯中…' : '開始翻譯';
}

function showLoading() {
  $('loadingCard').style.display = 'block';
  $('resultSection').replaceChildren();
  setBusy(true);
}

function hideLoading() {
  $('loadingCard').style.display = 'none';
}

function showMessageBox(message, btnLabel, onClick) {
  const box = el('div', 'error-retry-box');
  box.setAttribute('role', 'alert');
  box.appendChild(el('p', null, message));
  const b = el('button', 'retry-btn', btnLabel);
  b.type = 'button';
  b.addEventListener('click', onClick);
  box.appendChild(b);
  $('resultSection').replaceChildren(box);
  box.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function resetForm() {
  revokeUrls();
  $('resultSection').replaceChildren();
  $('fileInput').value = '';
  $('fileName').style.display = 'none';
  $('uploadZone').classList.remove('has-file');
}

function handleFileChange() {
  const input = $('fileInput');
  const zone = $('uploadZone');
  const nameEl = $('fileName');
  const n = input.files ? input.files.length : 0;
  if (n > 0) {
    zone.classList.add('has-file');
    nameEl.textContent = n === 1 ? '✓ ' + input.files[0].name : '✓ 已選擇 ' + n + ' 張圖片';
    nameEl.style.display = 'block';
  } else {
    zone.classList.remove('has-file');
    nameEl.style.display = 'none';
  }
}

// ───────────────────────── 翻譯流程（單一 run 物件管理所有計時器與請求） ─────────────────────────
let run = null;          // 目前進行中的任務；null 表示沒有
let objectUrls = [];     // 本機預覽用的 blob URL

function revokeUrls() {
  objectUrls.forEach(u => URL.revokeObjectURL(u));
  objectUrls = [];
}

function stopRun() {
  const r = run;
  if (!r) return null;
  run = null;                      // 先清掉，所有還在飛的回呼看到 r !== run 就會放棄
  clearTimeout(r.timer);
  clearTimeout(r.uploadTimer);
  r.ac.abort();
  if (r.pollAc) r.pollAc.abort();
  return r;
}

function sendCancel(id) {
  try {
    fetch('/cancel/' + encodeURIComponent(id), { method: 'POST', keepalive: true }).catch(() => {});
  } catch (e) { /* ignore */ }
}

function showError(message, btnLabel, onClick) {
  hideLoading();
  setBusy(false);
  showMessageBox('⚠️ ' + message, btnLabel || '重試一次', onClick || startTranslation);
}

function fail(r, message) {
  if (r !== run) return;
  const id = r.id;
  stopRun();
  if (id) sendCancel(id);
  showError(message);
}

function cancelTranslation() {
  const r = stopRun();
  if (r && r.id) sendCancel(r.id);
  hideLoading();
  setBusy(false);
  showMessageBox('已取消本次翻譯。', '重新上傳', resetForm);
}

function newTaskId() {
  const a = new Uint8Array(16);
  if (window.crypto && crypto.getRandomValues) crypto.getRandomValues(a);
  else for (let i = 0; i < a.length; i++) a[i] = Math.floor(Math.random() * 256);
  return Array.from(a, b => b.toString(16).padStart(2, '0')).join('');
}

function newRun(total, urls) {
  return {
    id: null,
    ac: new AbortController(),   // 上傳用
    pollAc: null,                // 目前這一次查詢用
    timer: null,
    uploadTimer: null,
    failSince: 0,                // 連續查詢失敗的起點時間
    inflight: false,
    uploaded: false,             // 伺服器已收到並建立任務，才開始輪詢
    wasHidden: false,
    deadline: 0,
    total: total,
    urls: urls,
  };
}

function startTranslation() {
  if (run) return;
  const files = Array.from($('fileInput').files || []);
  if (!files.length) {
    showError('請先選擇圖片。', '重新選擇', resetForm);
    return;
  }
  if (files.length > MAX_FILES) {
    showError('一次最多 ' + MAX_FILES + ' 張圖片，請重新選擇。', '重新選擇', resetForm);
    return;
  }
  const big = files.find(f => f.size > MAX_FILE_BYTES);
  if (big) {
    showError('「' + big.name + '」超過 ' + (MAX_FILE_BYTES / 1024 / 1024) + 'MB，請換一張。', '重新選擇', resetForm);
    return;
  }

  revokeUrls();
  objectUrls = files.map(f => URL.createObjectURL(f));

  const r = newRun(files.length, objectUrls.slice());
  r.id = newTaskId();   // 由前端產生：上傳途中按取消，伺服器也能對應到這個任務
  run = r;

  showLoading();
  setStage(0);
  setLoadingText('上傳中…');

  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  const fd = new FormData();
  fd.append('task_id', r.id);
  files.forEach(f => fd.append('files', f));
  upload(r, fd, Math.min(600000, UPLOAD_BASE_MS + totalBytes / 100));
}

function armUploadTimer(r, ms) {
  clearTimeout(r.uploadTimer);
  r.uploadTimer = setTimeout(() => {
    if (r !== run) return;
    // iOS 切到背景時上傳可能暫停：不要把背景時間算進逾時
    if (document.hidden || r.wasHidden) {
      r.wasHidden = false;
      armUploadTimer(r, UPLOAD_BASE_MS);
      return;
    }
    fail(r, '上傳逾時，請確認網路後重試。');
  }, ms);
}

async function upload(r, fd, timeoutMs) {
  armUploadTimer(r, timeoutMs);
  try {
    const res = await fetch('/upload', { method: 'POST', body: fd, signal: r.ac.signal });
    if (r !== run) return;
    clearTimeout(r.uploadTimer);
    if (res.status === 401) { location.href = '/login'; return; }
    let data = null;
    try { data = await res.json(); } catch (e) { /* 非 JSON */ }
    if (!res.ok || !data || !data.task_id) {
      fail(r, (data && data.message) || '上傳失敗（伺服器回應 ' + res.status + '），請重試。');
      return;
    }
    r.id = data.task_id;
    r.uploaded = true;
    r.deadline = Date.now() + 90000 + 20000 * r.total;
    setStage(1);
    setLoadingText('辨識文字中…');
    poll(r);
  } catch (e) {
    if (r !== run) return;
    fail(r, '上傳失敗，請確認網路後重試。');
  }
}

// 網路一直不通時不要取消伺服器上的任務（取消會讓使用者重傳、重複花 API 費），改讓使用者再查詢一次
function giveUpNetwork(r) {
  if (r !== run) return;
  const saved = { id: r.id, total: r.total, urls: r.urls };
  stopRun();
  showError('網路連線不穩，暫時無法取得翻譯結果。伺服器可能仍在處理，可以再查詢一次（不會重複計費）。',
    '再查詢一次', () => resumeTask(saved));
}

function resumeTask(saved) {
  if (run) return;
  const r = newRun(saved.total, saved.urls);
  r.id = saved.id;
  r.uploaded = true;
  r.deadline = Date.now() + 60000;
  run = r;
  showLoading();
  setStage(1);
  setLoadingText('重新查詢中…');
  poll(r);
}

async function poll(r) {
  if (r !== run || r.inflight || !r.uploaded) return;
  const expired = Date.now() > r.deadline;   // 逾時後仍補查最後一次，避免把剛好完成的任務誤判失敗
  r.inflight = true;
  const ac = new AbortController();
  r.pollAc = ac;
  const tm = setTimeout(() => ac.abort(), POLL_TIMEOUT_MS);
  try {
    const res = await fetch('/status/' + encodeURIComponent(r.id), { signal: ac.signal, cache: 'no-store' });
    if (r !== run) return;
    if (res.status === 401) { location.href = '/login'; return; }
    if (res.status === 404) {
      fail(r, '找不到這個翻譯任務（伺服器可能剛重新啟動），請重新上傳。');
      return;
    }
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();
    r.failSince = 0;

    if (d.status === 'done') {
      stopRun();
      setStage(3);
      showResults(d.results || [], r.urls);
      return;
    }
    if (d.status === 'error' || d.status === 'cancelled') {
      fail(r, d.message || (d.status === 'cancelled' ? '翻譯已取消。' : '翻譯失敗，請重試。'));
      return;
    }
    if (expired) {
      fail(r, '翻譯逾時，請重試或減少圖片張數。');
      return;
    }
    const stage = Math.min(Math.max(d.stage || 1, 1), 2);
    setStage(stage);
    setLoadingText((stage === 1 ? '辨識文字中…' : '翻譯中…') +
      (d.total > 1 ? '（已完成 ' + (d.done || 0) + '/' + d.total + ' 張）' : ''));
  } catch (e) {
    if (r !== run) return;
    if (expired) {
      fail(r, '翻譯逾時，請重試或減少圖片張數。');
      return;
    }
    if (!r.failSince) r.failSince = Date.now();
    if (Date.now() - r.failSince >= GIVE_UP_MS) {
      giveUpNetwork(r);
      return;
    }
  } finally {
    clearTimeout(tm);
    r.inflight = false;
  }
  if (r === run) r.timer = setTimeout(() => poll(r), POLL_MS);
}

// iOS 切到背景時計時器與網路會被凍結；回到前景時立刻查一次，並給一點緩衝避免誤報逾時
document.addEventListener('visibilitychange', () => {
  if (!run) return;
  if (document.hidden) {
    run.wasHidden = true;
    return;
  }
  if (run.uploaded) {
    run.failSince = 0;
    run.deadline = Math.max(run.deadline, Date.now() + 15000);
    clearTimeout(run.timer);
    poll(run);
  }
});

function showResults(results, urls) {
  hideLoading();
  setBusy(false);

  const section = $('resultSection');
  section.replaceChildren();
  const history = getHistory();

  results.forEach((item, idx) => {
    const n = idx + 1;
    const thumb = safeImgSrc(item.thumb);

    const imgCard = el('div', 'card');
    imgCard.appendChild(el('div', 'card-label', '第 ' + n + ' 張 — 原始圖片'));
    if (item.size_info) imgCard.appendChild(el('div', 'size-info', '⚡ 已壓縮：' + item.size_info));
    const img = el('img', 'original-img');
    img.alt = '圖片 ' + n;
    let fellBack = false;
    img.addEventListener('error', () => {      // 例如瀏覽器無法顯示 HEIC 原檔時，改用伺服器縮圖
      if (!fellBack && thumb) { fellBack = true; img.src = thumb; }
    });
    img.src = safeImgSrc(urls && urls[idx]) || thumb;
    imgCard.appendChild(img);

    const resCard = el('div', 'card');
    resCard.appendChild(el('div', 'card-label', '第 ' + n + ' 張 — 翻譯結果'));
    const blocks = Array.isArray(item.blocks) ? item.blocks : [];
    if (item.error || !blocks.length) {
      resCard.appendChild(el('div', 'error-box', item.error || '沒有翻譯結果。'));
    } else {
      resCard.appendChild(renderBlocks(blocks));
      resCard.appendChild(makeCopyButton(() => blocksToText(blocks), 'copy-btn', '複製文字'));
      history.unshift({ ts: Date.now() + idx, thumb: thumb, blocks: blocks });
    }
    section.append(imgCard, resCard);
  });

  saveHistory(history);
  renderHistory();
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ───────────────────────── 初始化 ─────────────────────────
function init() {
  setStage(0);
  $('mainForm').addEventListener('submit', e => { e.preventDefault(); startTranslation(); });
  $('fileInput').addEventListener('change', handleFileChange);
  $('cancelBtn').addEventListener('click', cancelTranslation);
  $('clearBtn').addEventListener('click', clearHistory);
  renderHistory();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
