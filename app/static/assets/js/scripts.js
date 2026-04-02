// #region Home route scripts
const feedFilters = {};

function updateMatchBar(matchCount, trackedCount) {
  const bar = document.getElementById('match-pct-bar');
  const txt = document.getElementById('match-pct-text');
  const pct = trackedCount > 0 ? Math.round((matchCount / trackedCount) * 100) : 0;
  if (bar) {
    bar.style.width = pct + '%';
    bar.style.background = pct >= 90 ? '#10b981' : pct >= 70 ? '#f59e0b' : '#f43f5e';
  }
  if (txt) {
    txt.textContent = pct + '%';
    txt.className = 'text-sm font-semibold tabular-nums flex-shrink-0 w-10 text-right ' +
      (pct >= 90 ? 'text-emerald-400' : pct >= 70 ? 'text-amber-400' : 'text-rose-400');
  }
}

function updateDeltas(configCounts, diffs, averageDiffs) {
  function delta(arr) {
    return (arr && arr.length >= 2) ? arr[arr.length - 1] - arr[arr.length - 2] : null;
  }
  const items = [
    { id: 'delta-tracked', val: delta(configCounts), upGood: true  },
    { id: 'delta-match',   val: delta(averageDiffs), upGood: true  },
    { id: 'delta-diff',    val: delta(diffs),        upGood: false },
  ];
  items.forEach(({ id, val, upGood }) => {
    const el = document.getElementById(id);
    if (!el || val === null) return;
    const neutral = val === 0;
    const positive = (!neutral && ((val > 0) === upGood));
    const icon = neutral ? 'remove' : (val > 0 ? 'arrow_upward' : 'arrow_downward');
    const cls  = neutral ? 'text-zinc-600' : (positive ? 'text-emerald-400' : 'text-rose-400');
    el.innerHTML = `<span class="flex items-center gap-0.5 ${cls}"><span class="material-icons-round" style="font-size:11px">${icon}</span>${Math.abs(val)} from last</span>`;
  });
}

function renderRecentChanges(changes) {
  const list = document.getElementById('recent-changes-list');
  if (!list) return;
  if (!changes || changes.length === 0) {
    list.innerHTML = '<div class="px-4 py-8 text-center"><p class="text-xs text-zinc-600">No recent changes</p></div>';
    return;
  }
  list.innerHTML = changes.map(c => `
    <a href="/changes" class="flex items-center gap-3 px-4 py-3 hover:bg-zinc-800/30 transition-colors group">
      <div class="w-6 h-6 rounded-lg bg-amber-500/10 ring-1 ring-inset ring-amber-500/20 flex items-center justify-center flex-shrink-0">
        <span class="material-icons-round text-amber-400" style="font-size:12px">edit_note</span>
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-xs font-medium text-zinc-300 group-hover:text-zinc-100 truncate transition-colors">${c.name}</p>
        <p class="text-[10px] text-zinc-600 mt-0.5">${c.type}</p>
      </div>
      <div class="flex items-center gap-2.5 flex-shrink-0">
        ${c.diffCount ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-500/15 text-amber-400 ring-1 ring-inset ring-amber-500/25">${c.diffCount} setting${c.diffCount === 1 ? '' : 's'}</span>` : ''}
        ${c.lastChanged ? `<span class="text-[10px] text-zinc-600">${c.lastChanged}</span>` : ''}
      </div>
    </a>
  `).join('');
}
function drawLineChart(id, labels, data, hexColor) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const color = hexColor || '#a1a1aa';
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  const h = canvas.offsetHeight || 150;

  // Rich gradient fill under the line
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0,    `rgba(${r},${g},${b},0.30)`);
  grad.addColorStop(0.35, `rgba(${r},${g},${b},0.12)`);
  grad.addColorStop(0.7,  `rgba(${r},${g},${b},0.04)`);
  grad.addColorStop(1,    `rgba(${r},${g},${b},0)`);

  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: 'count',
        data,
        fill: true,
        backgroundColor: grad,
        borderColor: color,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: color,
        pointHoverBorderColor: `rgba(${r},${g},${b},0.3)`,
        pointHoverBorderWidth: 6,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(9,9,11,0.95)',
          borderColor: `rgba(${r},${g},${b},0.3)`,
          borderWidth: 1,
          titleColor: '#a1a1aa',
          bodyColor: '#e4e4e7',
          padding: 10,
          cornerRadius: 8,
          displayColors: false,
        }
      },
      interaction: { intersect: false, mode: 'index' },
      scales: {
        y: {
          border: { display: false, dash: [4, 4] },
          grid: { display: true, color: 'rgba(255,255,255,0.03)' },
          ticks: {
            beginAtZero: true,
            padding: 8,
            font: { size: 10, family: "Inter, sans-serif" },
            color: "rgba(255,255,255,0.2)"
          }
        },
        x: {
          border: { display: false },
          grid: { display: false },
          ticks: { display: false }
        }
      }
    }
  });
}

function updateCounts(matchCount, diffCount, trackedCount) {
  const opts = { startVal: 0, duration: 1.5 };
  // countup.js UMD exposes the class as window.countUp.CountUp
  const CU = (typeof countUp !== 'undefined' && countUp.CountUp) || (typeof CountUp !== 'undefined' && CountUp);
  if (!CU) { console.warn('CountUp not loaded'); return; }
  [['match', matchCount], ['diff', diffCount], ['tracked', trackedCount]].forEach(([id, val]) => {
    const counter = new CU(id, val, opts);
    if (!counter.error) counter.start();
    else console.error(counter.error);
  });
}

function handleTenantClick() {
  document.querySelectorAll('a[href^="/home/tenant/"]').forEach(link => {
    link.addEventListener('click', function(event) {
      event.preventDefault();
      const url = this.href;
      const clickedLink = this;

      // Update pill active state immediately
      document.querySelectorAll('a[href^="/home/tenant/"]').forEach(l => {
        l.classList.remove('bg-gradient-to-r', 'from-indigo-600', 'to-indigo-500', 'text-white', 'shadow-md', 'shadow-indigo-900/50', 'ring-1', 'ring-inset', 'ring-white/10');
        l.classList.add('bg-zinc-800/60', 'text-zinc-400', 'hover:text-zinc-100', 'hover:bg-zinc-700/80', 'border', 'border-zinc-700/50', 'hover:border-zinc-600/60');
      });
      clickedLink.classList.remove('bg-zinc-800/60', 'text-zinc-400', 'hover:text-zinc-100', 'hover:bg-zinc-700/80', 'border', 'border-zinc-700/50', 'hover:border-zinc-600/60');
      clickedLink.classList.add('bg-gradient-to-r', 'from-indigo-600', 'to-indigo-500', 'text-white', 'shadow-md', 'shadow-indigo-900/50', 'ring-1', 'ring-inset', 'ring-white/10');

      // Reset feed filters when switching tenant
      Object.keys(feedFilters).forEach(k => delete feedFilters[k]);
      fetch(url, { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
          updateCounts(data.matchCount, data.diffCount, data.trackedCount);
          updateMatchBar(data.matchCount, data.trackedCount);
          updateDeltas(data.configCounts, data.diffs, data.averageDiffs);
          renderRecentChanges(data.recentChanges);
          Object.values(Chart.instances).forEach(i => i.destroy());
          drawLineChart("lineChartTracked", data.labelsConfig, data.configCounts, '#38bdf8');
          drawLineChart("lineChartAverage", data.labelsAverage, data.averageDiffs, '#818cf8');
          drawLineChart("lineChartDiffs", data.labelsDiff, data.diffs, '#fbbf24');
          const diffLen = document.getElementById('diff-len');
          if (diffLen) diffLen.textContent = `change average per last ${data.diff_len} records`;
          const diffLastUpdate = document.getElementById('diff-last-update');
          if (diffLastUpdate) diffLastUpdate.textContent = `Updated on: ${data.diff_data_last_update}`;
          return fetch(url + '/feeds', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feeds: data.feeds })
          });
        })
        .then(r => r.text())
        .then(html => {
          const feeds = document.getElementById('feeds');
          if (feeds) feeds.outerHTML = html;
        })
        .catch(err => { console.error('Tenant load error:', err); alert('An error occurred while loading tenant data.'); });
    });
  });
}

// Maps status → card border, glow, badge, and dot classes
const STATUS_STYLES = {
  error:     { border: 'border-l-rose-500',    glow: 'glow-rose', badge: 'badge-danger',   dot: 'bg-rose-500 status-dot status-dot-rose' },
  cancelled: { border: 'border-l-rose-500',    glow: 'glow-rose', badge: 'badge-danger',   dot: 'bg-rose-500 status-dot status-dot-rose' },
  success:   { border: 'border-l-emerald-500', glow: '',          badge: 'badge-success',  dot: 'bg-emerald-500' },
  running:   { border: 'border-l-sky-500',     glow: 'glow-sky',  badge: 'badge-info',     dot: 'bg-sky-500 status-dot status-dot-sky' },
  pending:   { border: 'border-l-sky-500',     glow: 'glow-sky',  badge: 'badge-info',     dot: 'bg-sky-500 status-dot status-dot-sky' },
  unknown:   { border: 'border-l-amber-500',   glow: '',          badge: 'badge-warning',  dot: 'bg-amber-500 status-dot status-dot-amber' },
  _default:  { border: 'border-l-zinc-700',    glow: '',          badge: '',               dot: 'bg-zinc-600' },
};

const ALL_BORDERS = ['border-l-rose-500','border-l-emerald-500','border-l-sky-500','border-l-amber-500','border-l-zinc-700'];
const ALL_GLOWS   = ['glow-rose','glow-sky'];

function applyCardStatus(tenant_id, status) {
  const card = document.getElementById(`tenant-card-${tenant_id}`);
  const dot  = document.getElementById(`status-dot-${tenant_id}`);
  const ls   = document.getElementById(`last-status-${tenant_id}`);
  const styles = STATUS_STYLES[status] || STATUS_STYLES._default;

  if (card) {
    ALL_BORDERS.forEach(c => card.classList.remove(c));
    ALL_GLOWS.forEach(c => card.classList.remove(c));
    card.classList.add(styles.border);
    if (styles.glow) card.classList.add(styles.glow);
  }
  if (dot) {
    dot.className = `w-2 h-2 rounded-full ${styles.dot} block`;
  }
  if (ls) {
    ls.textContent = status || '—';
    ls.className = styles.badge
      ? `${styles.badge} capitalize flex-shrink-0`
      : 'text-xs text-zinc-600';
  }
}

function updateUI(data) {
  const { status, message, date, tenant_id } = data;
  const el = document.getElementById(`current-message-${tenant_id}`);
  const updateButton = document.getElementById(`update-${tenant_id}`);
  const backupButton = document.getElementById(`backup-${tenant_id}`);
  const cancelButton = document.getElementById(`cancel-${tenant_id}`);
  const spinner = document.getElementById(`spinner-${tenant_id}`);
  const updateDate = document.getElementById(`updateDate-${tenant_id}`);

  if (!el) return;

  el.textContent = message;
  if (updateDate) updateDate.textContent = date;

  // Update card border, dot, and badge
  applyCardStatus(tenant_id, status);

  // Reset visibility
  if (backupButton) backupButton.classList.remove('hidden');
  if (updateButton) updateButton.classList.remove('hidden');
  if (cancelButton) cancelButton.classList.add('hidden');
  if (spinner) spinner.classList.add('hidden');

  const terminal = ['error', 'success', 'cancelled', 'unknown'];
  if (!terminal.includes(status)) {
    // Running / pending
    const updateVisible = updateButton && !updateButton.classList.contains('hidden');
    if (updateVisible) {
      if (spinner) spinner.classList.remove('hidden');
      if (status !== 'pending' && cancelButton) cancelButton.classList.remove('hidden');
      if (updateButton) updateButton.classList.add('hidden');
      if (backupButton) backupButton.classList.add('hidden');
    }
  }

  const stored = JSON.parse(sessionStorage.getItem('statusData') || '{}');
  stored[tenant_id] = { status, message, date };
  sessionStorage.setItem('statusData', JSON.stringify(stored));
}

function handleTaskClick(tenant_id, task_type) {
  fetch('intunecd/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tenant_id, task_type })
  });
}

function handleCancelClick(tenant_id) {
  fetch('intunecd/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tenant_id })
  });
}

function getSessionStorageData() {
  let statusData = {};
  const stored = sessionStorage.getItem('statusData');
  if (stored) {
    statusData = JSON.parse(stored);
    Object.keys(statusData).forEach(tenant_id => {
      const data = statusData[tenant_id];
      const ls = document.getElementById(`last-status-${tenant_id}`);
      const el = document.getElementById(`current-message-${tenant_id}`);
      if (!ls) {
        delete statusData[tenant_id];
        sessionStorage.setItem('statusData', JSON.stringify(statusData));
        return;
      }
      data.status = ls.textContent.toLowerCase();
      data.message = el ? el.textContent : data.message;
      updateUI({ ...data, tenant_id });
    });
  } else {
    document.querySelectorAll('[id^="last-status-"]').forEach(el => {
      const tenant_id = el.id.split('-')[2];
      const st = el.textContent.toLowerCase();
      const cm = document.getElementById(`current-message-${tenant_id}`);
      const dateEl = document.getElementById(`updateDate-${tenant_id}`);
      if (st === 'running' || st === 'pending') {
        statusData[tenant_id] = {
          status: st,
          message: cm ? cm.textContent : '',
          date: dateEl ? dateEl.textContent : ''
        };
      }
    });
    sessionStorage.setItem('statusData', JSON.stringify(statusData));
    Object.keys(statusData).forEach(tenant_id => {
      updateUI({ ...statusData[tenant_id], tenant_id });
    });
  }
}

// #endregion

// #region listeners
function filterFeed(tableId, text, type) {
  if (!feedFilters[tableId]) feedFilters[tableId] = { text: '', type: '' };
  if (text !== null) feedFilters[tableId].text = (text || '').toLowerCase();
  if (type !== null) feedFilters[tableId].type = type || '';
  const table = document.getElementById(tableId);
  if (!table) return;
  const { text: t, type: tp } = feedFilters[tableId];
  table.querySelectorAll('tr').forEach(row => {
    const matchText = !t  || row.textContent.toLowerCase().includes(t);
    const matchType = !tp || row.dataset.feedType === tp;
    row.style.display = (matchText && matchType) ? '' : 'none';
  });
}

function filterAccordion(tenant_id, term) {
  const accordion = document.getElementById(`accordionFlush-${tenant_id}`);
  if (!accordion) return;
  const lower = (term || '').toLowerCase();
  accordion.querySelectorAll('.accordion-item').forEach(item => {
    item.style.display = !lower || item.textContent.toLowerCase().includes(lower) ? '' : 'none';
  });
}

function attachAccordionListener(tenant_id) {
  const searchInput = document.getElementById(`accordionSearch-${tenant_id}`);
  if (!searchInput) return;
  searchInput.addEventListener('keyup', function() {
    filterAccordion(tenant_id, this.value);
  });
}

function attachTableListener(inputId, tableId) {
  const input = document.querySelector(inputId);
  const table = document.querySelector(tableId);
  if (!input || !table) return;
  input.addEventListener('keyup', function() {
    const val = this.value.toLowerCase();
    table.querySelectorAll('tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(val) ? '' : 'none';
    });
  });
}

// #endregion
