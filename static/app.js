// ── 翻譯紀錄（存在 sessionStorage，關閉分頁即清除）──

const HISTORY_KEY = 'translate_history';

function getHistory() {
  try { return JSON.parse(sessionStorage.getItem(HISTORY_KEY)) || []; }
  catch { return []; }
}

function saveHistory(list) {
  sessionStorage.setItem(HISTORY_KEY, JSON.stringify(list));
}

function formatTime(ts) {
  const d = new Date(ts);
  const h = String(d.getHours()).padStart(2,'0');
  const m = String(d.getMinutes()).padStart(2,'0');
  return '今天 ' + h + ':' + m;
}

function renderHistory() {
  const list = getHistory();
  const container = document.getElementById('historyList');
  const empty = document.getElementById('historyEmpty');

  Array.from(container.querySelectorAll('.history-item')).forEach(el => el.remove());

  if (list.length === 0) {
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  list.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'history-item';
    div.innerHTML =
      '<div class="history-item-header" onclick="toggleItem(' + idx + ')">' +
      '<img class="history-thumb" src="' + item.image + '" alt="縮圖">' +
      '<div class="history-meta">' +
      '<div class="history-time">' + formatTime(item.ts) + '</div>' +
      '<div class="history-preview">' + item.text.slice(0, 40) + '…</div>' +
      '</div>' +
      '<span class="history-chevron" id="chev-' + idx + '">▼</span>' +
      '</div>' +
      '<div class="history-body" id="body-' + idx + '">' +
      '<img class="history-full-img" src="' + item.image + '" alt="原圖">' +
      '<div class="history-full-text">' + item.text + '</div>' +
      '<button class="history-copy-btn" onclick="copyHistory(' + idx + ')">📋 複製</button>' +
      '</div>';
    container.appendChild(div);
  });
}

function toggleItem(idx) {
  const body = document.getElementById('body-' + idx);
  const chev = document.getElementById('chev-' + idx);
  body.classList.toggle('open');
  chev.classList.toggle('open');
}

function copyHistory(idx) {
  const list = getHistory();
  navigator.clipboard.writeText(list[idx].text);
}

function clearHistory() {
  if (confirm('確定要清除所有紀錄嗎？')) {
    sessionStorage.removeItem(HISTORY_KEY);
    renderHistory();
  }
}

window.addEventListener('DOMContentLoaded', () => {
  renderHistory();
});

let currentInterval = null;
let currentTaskId = null;
let cancelled = false;

const STAGES = ['stage1', 'stage2', 'stage3', 'stage4'];
const STAGE_LABELS = ['📤 上傳中', '🔍 辨識文字', '🌐 翻譯中', '✨ 整理結果'];
const STAGE_DELAYS = [0, 3000, 8000, 25000];
const TIMEOUT_MS = 120000;

function setStage(idx) {
  STAGES.forEach((id, i) => {
    const el = document.getElementById(id);
    if (i < idx) {
      el.className = 'stage done';
      el.textContent = '✅ ' + STAGE_LABELS[i].slice(3);
    } else if (i === idx) {
      el.className = 'stage active';
      el.textContent = STAGE_LABELS[i];
    } else {
      el.className = 'stage';
      el.textContent = STAGE_LABELS[i];
    }
  });
}

function startStageAnimation() {
  setStage(0);
  STAGE_DELAYS.forEach((delay, idx) => {
    const t = setTimeout(() => {
      if (!cancelled) setStage(idx);
    }, delay);
    if (!window._stageTimers) window._stageTimers = [];
    window._stageTimers.push(t);
  });
}

function clearStageTimers() {
  (window._stageTimers || []).forEach(t => clearTimeout(t));
  window._stageTimers = [];
}

function showLoading() {
  document.getElementById('loadingCard').style.display = 'block';
  document.getElementById('cancelBtn').style.display = 'inline-block';
  document.getElementById('resultSection').innerHTML = '';
  cancelled = false;
  startStageAnimation();
}

function hideLoading() {
  document.getElementById('loadingCard').style.display = 'none';
  clearStageTimers();
}

function cancelTranslation() {
  cancelled = true;
  if (currentInterval) clearInterval(currentInterval);
  hideLoading();
  const btn = document.getElementById('submitBtn');
  btn.disabled = false;
  btn.textContent = '開始翻譯';
  document.getElementById('resultSection').innerHTML =
    '<div class="error-retry-box"><p>⚠️ 已取消本次翻譯。</p>' +
    '<button class="retry-btn" onclick="resetForm()">重新上傳</button></div>';
}

function showError(reason) {
  hideLoading();
  const btn = document.getElementById('submitBtn');
  btn.disabled = false;
  btn.textContent = '開始翻譯';
  document.getElementById('resultSection').innerHTML =
    '<div class="error-retry-box"><p>⚠️ ' + reason + '</p>' +
    '<button class="retry-btn" onclick="retryTranslation()">重試一次</button></div>';
}

function resetForm() {
  document.getElementById('resultSection').innerHTML = '';
  document.getElementById('fileInput').value = '';
  document.getElementById('fileName').style.display = 'none';
  document.getElementById('uploadZone').classList.remove('has-file');
}

function retryTranslation() {
  document.getElementById('resultSection').innerHTML = '';
  document.getElementById('submitBtn').click();
}

function handleFileChange(input) {
  const zone = document.getElementById('uploadZone');
  const nameEl = document.getElementById('fileName');
  if (input.files && input.files.length > 0) {
    zone.classList.add('has-file');
    const count = input.files.length;
    nameEl.textContent = count === 1
      ? '✓ ' + input.files[0].name
      : '✓ 已選擇 ' + count + ' 張圖片';
    nameEl.style.display = 'block';
  }
}

function handleSubmit(e) {
  e.preventDefault();
  const fileInput = document.getElementById('fileInput');
  if (!fileInput.files || !fileInput.files.length) return;

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = '上傳中…';
  showLoading();

  const formData = new FormData();
  for (const file of fileInput.files) {
    formData.append('files', file);
  }

  const timeout = setTimeout(() => {
    if (currentInterval) clearInterval(currentInterval);
    showError('翻譯逾時（超過2分鐘），請重試或換一張圖片。');
  }, TIMEOUT_MS);

  fetch('/upload', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      currentTaskId = data.task_id;
      btn.textContent = '翻譯中…';
      setStage(1);
      currentInterval = setInterval(() => {
        if (cancelled) { clearInterval(currentInterval); clearTimeout(timeout); return; }
        fetch('/status/' + currentTaskId)
          .then(r => r.json())
          .then(data => {
            if (data.status === 'done') {
              clearInterval(currentInterval);
              clearTimeout(timeout);
              setStage(3);
              setTimeout(() => {
                if (!cancelled) showResults(data.results);
              }, 800);
            } else if (data.status === 'error') {
              clearInterval(currentInterval);
              clearTimeout(timeout);
              showError(data.message || '翻譯失敗，請重試。');
            }
          })
          .catch(() => {
            clearInterval(currentInterval);
            clearTimeout(timeout);
            showError('網路連線中斷，請確認網路後重試。');
          });
      }, 2000);
    })
    .catch(() => {
      clearTimeout(timeout);
      showError('上傳失敗，請確認網路後重試。');
    });
}

function renderBilingual(text) {
  const lines = text.split('\n');
  let html = '<div class="result-text-bilingual">';
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    if (line === '---完整翻譯結束---') {
      html += '<div class="bilingual-end">✅ 完整翻譯結束</div>';
      i++;
      continue;
    }

    if (line === '') {
      i++;
      continue;
    }

    const nextLine = (lines[i + 1] || '').trim();
    if (nextLine && nextLine !== '---完整翻譯結束---') {
      html += '<div class="bilingual-block">' +
        '<div class="bilingual-original">' + line + '</div>' +
        '<div class="bilingual-translation">' + nextLine + '</div>' +
        '</div>';
      i += 2;
    } else {
      html += '<div class="bilingual-block">' +
        '<div class="bilingual-translation">' + line + '</div>' +
        '</div>';
      i++;
    }
  }

  html += '</div>';
  return html;
}

function showResults(results) {
  hideLoading();
  const btn = document.getElementById('submitBtn');
  btn.disabled = false;
  btn.textContent = '開始翻譯';

  const section = document.getElementById('resultSection');
  section.innerHTML = '';

  results.forEach((item, idx) => {
    const n = idx + 1;
    const isError = item.result && item.result.startsWith('發生錯誤');
    const sizeInfo = item.size_info
      ? '<div style="font-size:12px;color:#7D5C42;background:#F5EDE6;border:1px solid #DEC4B0;border-radius:8px;padding:6px 12px;margin-bottom:12px;display:inline-block;">⚡ 已壓縮：' + item.size_info + '</div>'
      : '';
    const resultHtml = isError
      ? '<div class="error-box">' + item.result + '</div>'
      : '<div id="resultText' + n + '">' + renderBilingual(item.result) + '</div>' +
        '<button class="copy-btn" onclick="copyResult(\'resultText' + n + '\')"><span>📋</span> 複製文字</button>';

    section.innerHTML +=
      '<div class="card"><div class="card-label">第 ' + n + ' 張 — 原始圖片</div>' +
      sizeInfo +
      '<img class="original-img" src="' + item.image + '" alt="圖片 ' + n + '"></div>' +
      '<div class="card"><div class="card-label">第 ' + n + ' 張 — 翻譯結果</div>' +
      resultHtml + '</div>';

    if (!isError) {
      const list = getHistory();
      list.unshift({ text: item.result, image: item.image, ts: Date.now() + idx });
      while (list.length > 20) list.pop();
      saveHistory(list);
    }
  });

  renderHistory();
}

function copyResult(id) {
  const text = document.getElementById(id).innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btns = document.querySelectorAll('.copy-btn');
    btns.forEach(btn => {
      if (btn.getAttribute('onclick') === "copyResult('" + id + "')") {
        btn.classList.add('copied');
        btn.innerHTML = '<span>✓</span> 已複製';
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerHTML = '<span>📋</span> 複製文字';
        }, 2000);
      }
    });
  });
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
