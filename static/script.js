function ballClass(n) {
  if (n <= 10) return 'ball ball-1';
  if (n <= 20) return 'ball ball-11';
  if (n <= 30) return 'ball ball-21';
  if (n <= 40) return 'ball ball-31';
  return 'ball ball-41';
}

function renderLottoBalls(containerId, numbers) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  numbers.forEach((n, i) => {
    const ball = document.createElement('div');
    ball.className = ballClass(n);
    ball.textContent = n;
    ball.style.animationDelay = `${i * 0.07}s`;
    el.appendChild(ball);
  });
}

function renderPensionDigits(containerId, numbers) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  const labels = ['십만', '만', '천', '백', '십', '일'];
  numbers.forEach((d, i) => {
    const wrap = document.createElement('div');
    wrap.className = 'pension-digit';
    wrap.style.animationDelay = `${i * 0.07}s`;
    wrap.innerHTML = `
      <div class="pension-pos">${labels[i]}</div>
      <div class="pension-num">${d}</div>
    `;
    el.appendChild(wrap);
  });
}

function setLoading(btnId, isLoading) {
  const btn = document.getElementById(btnId);
  if (isLoading) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>생성 중...';
  } else {
    btn.disabled = false;
    btn.textContent = '번호 생성하기';
  }
}

function renderFreqBalls(containerId, items) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  items.forEach(({ number, count }) => {
    const wrap = document.createElement('div');
    wrap.className = 'freq-ball';
    wrap.innerHTML = `
      <div class="${ballClass(number)}">${number}</div>
      <div class="freq-ball-count">${count}회</div>
    `;
    el.appendChild(wrap);
  });
}

function renderLottoDataInfo(data) {
  const panel = document.getElementById('lotto-data-info');
  panel.hidden = false;
  document.getElementById('lotto-round-range').textContent =
    `1회 ~ ${data.round_range.end}회`;

  renderFreqBalls('lotto-top5', data.top5);
  renderFreqBalls('lotto-bottom5', data.bottom5);
}

function renderPensionDataInfo(data) {
  const panel = document.getElementById('pension-data-info');
  panel.hidden = false;
  document.getElementById('pension-round-range').textContent = data.total_rounds > 0
    ? `1회 ~ ${data.round_range.end}회`
    : '통계 데이터 없음';


  const topEl = document.getElementById('pension-pos-stats-top');
  const bottomEl = document.getElementById('pension-pos-stats-bottom');
  const labels = ['십만', '만', '천', '백', '십', '일'];
  topEl.innerHTML = '';
  bottomEl.innerHTML = '';
  if (data.position_stats?.length) {
    const topTitle = document.createElement('span');
    topTitle.className = 'freq-label up';
    topTitle.textContent = '자주 나온 번호:';
    topEl.appendChild(topTitle);
    data.position_stats.forEach(({ pos, top_digit, top_count }) => {
      const span = document.createElement('span');
      span.className = 'pension-pos-stat';
      span.innerHTML = `${labels[pos - 1]} <strong>${top_digit}</strong>(${top_count}회)`;
      topEl.appendChild(span);
    });

    const bottomTitle = document.createElement('span');
    bottomTitle.className = 'freq-label down';
    bottomTitle.textContent = '덜 나온 번호:';
    bottomEl.appendChild(bottomTitle);
    data.position_stats.forEach(({ pos, bottom_digit, bottom_count }) => {
      const span = document.createElement('span');
      span.className = 'pension-pos-stat';
      span.innerHTML = `${labels[pos - 1]} <strong>${bottom_digit}</strong>(${bottom_count}회)`;
      bottomEl.appendChild(span);
    });
  }
}

async function loadDeployTime() {
  try {
    const res = await fetch('/api/deploy-time');
    if (res.ok) {
      const { deploy_time } = await res.json();
      document.getElementById('deploy-time').textContent = `최종 배포: ${deploy_time}`;
    }
  } catch {}
}
loadDeployTime();

async function generateLotto() {
  setLoading('lotto-btn', true);

  try {
    const res = await fetch('/api/lotto');
    if (!res.ok) throw new Error((await res.json()).error || '서버 오류');
    const data = await res.json();

    renderLottoBalls('lotto-high', data.high_freq);
    renderLottoBalls('lotto-low', data.low_freq);
    renderLottoDataInfo(data);
  } catch (e) {
    document.getElementById('lotto-high').innerHTML =
      `<span class="placeholder" style="color:#c00">${e.message}</span>`;
    document.getElementById('lotto-low').innerHTML = '';
  } finally {
    setLoading('lotto-btn', false);
  }
}

async function generatePension() {
  setLoading('pension-btn', true);

  try {
    const res = await fetch('/api/pension');
    if (!res.ok) throw new Error((await res.json()).error || '서버 오류');
    const data = await res.json();

    renderPensionDigits('pension-high', data.high_freq);
    renderPensionDigits('pension-low', data.low_freq);
    renderPensionDataInfo(data);
  } catch (e) {
    document.getElementById('pension-high').innerHTML =
      `<span class="placeholder" style="color:#c00">${e.message}</span>`;
    document.getElementById('pension-low').innerHTML = '';
  } finally {
    setLoading('pension-btn', false);
  }
}
