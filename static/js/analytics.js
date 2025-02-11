// Keep existing chart initialization code at the top
const charts = {};
let grid;
let currentDays = 30;

// Define available metrics based on actual DB fields
const customMetricConfigs = {
    tickets_by_status: {
        label: 'Tickets by Status',
        type: 'pie',
        endpoint: '/analytics/api/custom/tickets-by-status'
    },
    tickets_by_priority: {
        label: 'Tickets by Priority',
        type: 'bar',
        endpoint: '/analytics/api/custom/tickets-by-priority'
    },
    tickets_by_assignee: {
        label: 'Tickets by Assignee',
        type: 'bar',
        endpoint: '/analytics/api/custom/tickets-by-assignee'
    },
    response_time_trend: {
        label: 'Response Time Trend',
        type: 'line',
        endpoint: '/analytics/api/custom/response-time-trend'
    },
    resolution_time_trend: {
        label: 'Resolution Time Trend',
        type: 'line',
        endpoint: '/analytics/api/custom/resolution-time-trend'
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // Initialize grid exactly like the default charts
    grid = GridStack.init({
        cellHeight: 100,
        minRow: 1,
        margin: 10,
        draggable: {
            handle: '.handle'
        },
        float: true
    });

    // Initialize date range picker exactly like Export Raw Data
    $('#metricDateRange').daterangepicker({
        autoUpdateInput: false,
        locale: {
            format: 'YYYY-MM-DD'
        },
        ranges: {
            'Today': [moment(), moment()],
            'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        }
    });

    $('#addMetricsBtn').on('click', async function() {
        const selectedMetrics = $('#customMetricSelect').val();
        const dateRange = $('#metricDateRange').val();

        if (!selectedMetrics || selectedMetrics.length === 0) {
            alert('Please select at least one metric');
            return;
        }

        if (!dateRange) {
            alert('Please select a date range');
            return;
        }

        // Add each selected metric as a new chart
        for (const metricId of selectedMetrics) {
            const config = customMetricConfigs[metricId];
            const widgetHtml = `
                <div class="grid-stack-item-content">
                    <div class="card shadow-sm">
                        <div class="card-header bg-transparent d-flex justify-content-between align-items-center handle">
                            <h6 class="mb-0">${config.label}</h6>
                            <div>
                                <button class="btn btn-sm" onclick="removeWidget(this)">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                        <div class="card-body">
                            <div class="chart-container">
                                <canvas id="${metricId}Chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Add widget to grid
            const node = grid.addWidget({
                w: 6,
                h: 4,
                content: widgetHtml
            });

            // Initialize chart
            await initializeCustomChart(metricId, config, dateRange);
        }

        // Close modal and reset form
        $('#metricsModal').modal('hide');
        $('#customMetricSelect').val(null).trigger('change');
        $('#metricDateRange').val('');
    });
});

// Function to initialize custom chart
async function initializeCustomChart(metricId, config, dateRange) {
    const ctx = document.getElementById(`${metricId}Chart`).getContext('2d');
    const container = ctx.canvas.closest('.chart-container');
    
    try {
        container.classList.add('loading');
        const response = await fetch(`${config.endpoint}?dateRange=${dateRange}`);
        if (!response.ok) throw new Error('Failed to fetch data');
        
        const data = await response.json();
        charts[metricId] = new Chart(ctx, {
            type: config.type,
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<div class="alert alert-danger">Failed to load chart</div>';
    } finally {
        container.classList.remove('loading');
    }
}

// Function to remove custom chart
function removeCustomChart(metricId) {
    const chartContainer = document.getElementById(`${metricId}Chart`).closest('.grid-stack-item');
    grid.removeWidget(chartContainer);
    if (charts[metricId]) {
        charts[metricId].destroy();
        delete charts[metricId];
    }
}

// Function to download chart
function downloadChart(metricId) {
    const canvas = document.getElementById(`${metricId}Chart`);
    if (canvas) {
        const link = document.createElement('a');
        link.download = `${metricId}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
    }
} 