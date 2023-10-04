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