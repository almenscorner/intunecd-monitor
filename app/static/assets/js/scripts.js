// #region Home route scripts
function drawLineChart(id, labels, data) {
    var ctx = document.getElementById(id).getContext("2d");
    var lineChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'count',
                    data: data,
                    fill: false,
                    borderColor: "white",
                    lineTension: 0.1
                },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false,
                }
            },
            interaction: {
                intersect: false,
                mode: 'index',
            },
            scales: {
                y: {
                    grid: {
                        drawBorder: false,
                        display: true,
                        drawOnChartArea: true,
                        drawTicks: false,
                        borderDash: [5,],
                        color: 'rgba(255, 255, 255, .2)'
                    },
                    ticks: {
                        suggestedMin: 0,
                        suggestedMax: 500,
                        beginAtZero: true,
                        padding: 10,
                        font: {
                            size: 14,
                            weight: 300,
                            family: "Roboto",
                            style: 'normal',
                            lineHeight: 2
                        },
                        color: "#fff"
                    },
                },
                x: {
                    grid: {
                        drawBorder: false,
                        display: true,
                        drawOnChartArea: true,
                        drawTicks: false,
                        borderDash: [5, 5],
                        color: 'rgba(255, 255, 255, .2)'
                    },
                    ticks: {
                        display: false
                    },
                }
            }
        }
    });
}

function updateCounts(matchCount, diffCount, trackedCount) {
    var matchCount = new CountUp('match', 0, matchCount);
    if (!matchCount.error) {
        matchCount.start();
    } else {
        console.error(matchCount.error);
    }
    var diffCount = new CountUp('diff', 0, diffCount);
    if (!diffCount.error) {
        diffCount.start();
    } else {
        console.error(diffCount.error);
    }
    var trackedCount = new CountUp('tracked', 0, trackedCount);
    if (!trackedCount.error) {
        trackedCount.start();
    } else {
        console.error(trackedCount.error);
    }
}

function handleTenantClick() {
    $('a[href^="/home/tenant/"]').click(function(event) {
          event.preventDefault(); // Prevent the default behavior of the anchor tag
          var url = this.href;
          $.ajax({
              url: url,
              type: 'GET',
              cache: false,
              success: function(data) {
                  // Return data from AJAX request
                  updateCounts(data.matchCount, data.diffCount, data.trackedCount)
                  // destroy the old chart instance
                  Chart.helpers.each(Chart.instances, function(instance) {
                    instance.destroy();
                  });
                  drawLineChart("lineChartTracked", data.labelsConfig, data.configCounts);
                  drawLineChart("lineChartAverage", data.labelsAverage, data.averageDiffs);
                  drawLineChart("lineChartDiffs", data.labelsDiff, data.diffs);
                  $('#dropdownMenuButton').text(data.selectedTenantName);
                  $('#diff-len').text("change average per last " + data.diff_len + " records");
                  $('#diff-last-update').text("Updated on: " + data.diff_data_last_update);
                  $.ajax({
                    url: url + '/feeds',
                    type: 'POST',
                    cache: false,
                    data: JSON.stringify({feeds: data.feeds}),
                    contentType: "application/json",
                    success: function(data) {
                      $('#feeds').html(data);
                    },
                    error: function() {
                        alert('An error occurred while loading the page.');
                    }
                  });
              },
              error: function() {
                  alert('An error occurred while loading the page.');
              }
          });
      });
}

function updateUI(data) {
    var statusData = {};
  const { status, message, date, tenant_id } = data;
  const el = document.getElementById(`current-message-${tenant_id}`);
  const updateButton = document.getElementById(`update-${tenant_id}`);
  const backupButton = document.getElementById(`backup-${tenant_id}`);
  const cancelButton = document.getElementById(`cancel-${tenant_id}`);
  const ellipsis = document.getElementById(`ellipsis-${tenant_id}`);
  const ls = document.getElementById(`last-status-${tenant_id}`);
  const updateDate = document.getElementById(`updateDate-${tenant_id}`);

  el.innerText = message;
  ls.innerText = status;
  ls.classList.remove('text-success', 'text-danger', 'text-warning');
  updateDate.innerText = date;

  if (backupButton) backupButton.style.removeProperty('display');
  if (updateButton) updateButton.style.removeProperty('display');
  if (cancelButton) cancelButton.style.display = 'none';
  if (ellipsis) ellipsis.style.display = 'none';

  if (status === 'error' || status === 'success' || status === 'cancelled' || status === 'unknown') {
    if (backupButton) backupButton.style.removeProperty('display');
    if (updateButton) updateButton.style.removeProperty('display');
    if (ellipsis) ellipsis.style.display = 'none';
    if (status === 'error') {
      ls.classList.add('text-danger');
      ls.classList.remove('text-warning', 'text-success', 'text-info');
    } else if (status === 'success') {
      ls.classList.add('text-success');
      ls.classList.remove('text-warning', 'text-danger', 'text-info');
    } else if (status === 'cancelled') {
      ls.classList.add('text-danger');
      ls.classList.remove('text-success', 'text-warning', 'text-info');
    }
    else {
      ls.classList.add('text-warning');
      ls.classList.remove('text-success', 'text-danger', 'text-info');
    }
  } else {
    if (!backupButton && ellipsis) {
      if (updateButton.style.display != 'none' && ellipsis.style.display === 'none') {
        ellipsis.style = '';
        if (status != 'pending') {
          cancelButton.style.removeProperty('display');
        }
        ls.innerText = status;
        ls.classList.add('text-info')
        updateButton.style.display = 'none';
      }
    } else if (updateButton && backupButton && ellipsis) {
      if (updateButton.style.display != 'none' && backupButton.style.display != 'none' && ellipsis.style.display === 'none') {
        ellipsis.style = '';
        if (status != 'pending') {
          cancelButton.style.removeProperty('display');
        }
        ls.innerText = status;
        ls.classList.add('text-info')
        updateButton.style.display = 'none';
        backupButton.style.display = 'none';
      }
    }
  }

  // Store the status data in local storage
  statusData[tenant_id] = { status, message, date };
  sessionStorage.setItem('statusData', JSON.stringify(statusData));
}

function handleTaskClick(tenant_id, task_type) {
    const endpoint = 'intunecd/run';
    fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ tenant_id: tenant_id, task_type: task_type }),
    });
}

function handleCancelClick(tenant_id) {
    const endpoint = 'intunecd/cancel';
    fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ tenant_id: tenant_id }),
    });
}

function getSessionStorageData() {
    // Retrieve the status data from session storage when the page is loaded
    var statusData = {};
    var storedStatusData = sessionStorage.getItem('statusData');
    if (storedStatusData) {
      statusData = JSON.parse(storedStatusData);
      Object.keys(statusData).forEach(function(tenant_id) {
        const data = statusData[tenant_id];
        const ls = document.getElementById(`last-status-${tenant_id}`);
        const el = document.getElementById(`current-message-${tenant_id}`);

        if (!ls) {
          // The tenant is not on the page anymore so remove it from data
          delete statusData[tenant_id];
          sessionStorage.setItem('statusData', JSON.stringify(statusData));
          return; // Exit the forEach loop for this tenant
        }

        const lastStatus = ls.innerText.toLowerCase();
        const lastMessage = el.innerText;

        if (data.status != lastStatus) {
          data.status = lastStatus;
        }
        if (data.message != lastMessage) {
          data.message = lastMessage;
        }

        updateUI({ ...data, tenant_id });
      });
    }
    else {
      // No status data in local storage so get it from the page
      const statusElements = document.querySelectorAll('[id^="last-status-"]');
      statusElements.forEach(function(el) {
        const tenant_id = el.id.split('-')[2];
        const st = document.getElementById(`last-status-${tenant_id}`);
        const cm = document.getElementById(`current-message-${tenant_id}`);
        const date = document.getElementById(`updateDate-${tenant_id}`).innerText;
        const status = st.innerText.toLowerCase();
        const message = cm.innerText;
        // do not store if status is success or error
        if (status === 'running' || status == 'pending') {
          statusData[tenant_id] = { status, message, date };
        }
      });
      sessionStorage.setItem('statusData', JSON.stringify(statusData));

      // Update the UI
      Object.keys(statusData).forEach(function(tenant_id) {
        const data = statusData[tenant_id];
        updateUI({ ...data, tenant_id });
      });
    }
}

// #endregion

// #region listeners
function attachAccordionListener(tenant_id) {
  $(document).ready(function(){
    const searchInput = $('#accordionSearch-' + tenant_id);
    const accordion = $('#accordionFlush-' + tenant_id);

    searchInput.on('keyup', function(event) {
      const searchTerm = event.target.value.toLowerCase();
      const accordionItems = accordion.find('.accordion-item');
      accordionItems.each(function() {
        const itemName = $(this).find('.accordion-header p').text().toLowerCase();

        if (itemName.includes(searchTerm)) {
          $(this).css('display', 'block');
        } else {
          $(this).css('display', 'none');
        }
      });
    });
  });
}

function attachTableListener(formId, tableId) {
  $(document).ready(function(){
    $(formId).on("keyup", function() {
      var value = $(this).val().toLowerCase();
      $(`${tableId} tr`).filter(function() {
        $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1)
      });
    });
  });
}

// #endregion