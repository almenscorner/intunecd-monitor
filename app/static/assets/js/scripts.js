// #region Home route scripts
function drawLineChart(id, labels, data) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: 'count',
        data: data,
        fill: false,
        borderColor: "rgba(255,255,255,0.7)",
        borderWidth: 2,
        pointRadius: 2,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      interaction: {
        intersect: false,
        mode: 'index',
      },
      scales: {
        y: {
          border: { display: false, dash: [5, 5] },
          grid: { display: true, color: 'rgba(255,255,255,0.08)' },
          ticks: {
            beginAtZero: true,
            padding: 8,
            font: { size: 11, family: "Inter, sans-serif" },
            color: "rgba(255,255,255,0.4)"
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
  [['match', matchCount], ['diff', diffCount], ['tracked', trackedCount]].forEach(([id, val]) => {
    const counter = new CountUp(id, val, opts);
    if (!counter.error) counter.start();
    else console.error(counter.error);
  });
}

function handleTenantClick() {
  document.querySelectorAll('a[href^="/home/tenant/"]').forEach(link => {
    link.addEventListener('click', function(event) {
      event.preventDefault();
      const url = this.href;
      fetch(url, { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
          updateCounts(data.matchCount, data.diffCount, data.trackedCount);
          Object.values(Chart.instances).forEach(i => i.destroy());
          drawLineChart("lineChartTracked", data.labelsConfig, data.configCounts);
          drawLineChart("lineChartAverage", data.labelsAverage, data.averageDiffs);
          drawLineChart("lineChartDiffs", data.labelsDiff, data.diffs);
          const btn = document.getElementById('tenantDropdownBtn');
          if (btn) btn.childNodes[0].textContent = data.selectedTenantName + ' ';
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
          if (feeds) feeds.innerHTML = html;
        })
        .catch(() => alert('An error occurred while loading tenant data.'));
    });
  });
}

function updateUI(data) {
  const { status, message, date, tenant_id } = data;
  const el = document.getElementById(`current-message-${tenant_id}`);
  const updateButton = document.getElementById(`update-${tenant_id}`);
  const backupButton = document.getElementById(`backup-${tenant_id}`);
  const cancelButton = document.getElementById(`cancel-${tenant_id}`);
  const spinner = document.getElementById(`spinner-${tenant_id}`);
  const ls = document.getElementById(`last-status-${tenant_id}`);
  const updateDate = document.getElementById(`updateDate-${tenant_id}`);

  if (!el || !ls) return;

  el.textContent = message;
  ls.textContent = status;
  ls.classList.remove('text-emerald-400', 'text-rose-400', 'text-amber-400', 'text-sky-400');
  if (updateDate) updateDate.textContent = date;

  // Reset visibility
  if (backupButton) backupButton.classList.remove('hidden');
  if (updateButton) updateButton.classList.remove('hidden');
  if (cancelButton) cancelButton.classList.add('hidden');
  if (spinner) spinner.classList.add('hidden');

  const terminal = ['error', 'success', 'cancelled', 'unknown'];
  if (terminal.includes(status)) {
    if (status === 'error' || status === 'cancelled') ls.classList.add('text-rose-400');
    else if (status === 'success') ls.classList.add('text-emerald-400');
    else ls.classList.add('text-amber-400');
  } else {
    // Running / pending
    const updateVisible = updateButton && !updateButton.classList.contains('hidden');
    if (updateVisible) {
      if (spinner) spinner.classList.remove('hidden');
      if (status !== 'pending' && cancelButton) cancelButton.classList.remove('hidden');
      ls.textContent = status;
      ls.classList.add('text-sky-400');
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
function attachAccordionListener(tenant_id) {
  const searchInput = document.getElementById(`accordionSearch-${tenant_id}`);
  const accordion = document.getElementById(`accordionFlush-${tenant_id}`);
  if (!searchInput || !accordion) return;
  searchInput.addEventListener('keyup', function() {
    const term = this.value.toLowerCase();
    accordion.querySelectorAll('.accordion-item').forEach(item => {
      item.style.display = item.textContent.toLowerCase().includes(term) ? '' : 'none';
    });
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
