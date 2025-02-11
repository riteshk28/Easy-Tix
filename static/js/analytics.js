// Keep existing chart initialization code at the top
const charts = {};
let grid;
let currentDays = 30;

// Add custom metric configurations
const customMetricConfigs = {
    tickets_by_category: {
        label: 'Tickets by Category',
        type: 'pie',
        endpoint: '/analytics/api/custom/tickets-by-category'
    },
    tickets_by_priority: {
        label: 'Tickets by Priority',
        type: 'bar',
        endpoint: '/analytics/api/custom/tickets-by-priority'
    },
    // Add other metric configurations...
};

document.addEventListener('DOMContentLoaded', function() {
    // Keep existing initialization code
    initializeExistingCharts();
    
    // Initialize grid (keep existing configuration)
    grid = GridStack.init({
        cellHeight: 100,
        minRow: 1,
        margin: 10,
        draggable: {
            handle: '.handle'
        }
    });

    // Initialize Select2 for metric selection
    $('#customMetricSelect').select2({
        placeholder: 'Search and select metrics...',
        width: '100%'
    });

    // Initialize date range picker (matching Export Raw Data style)
    $('#metricDateRange').daterangepicker({
        ranges: {
            'Today': [moment(), moment()],
            'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        locale: {
            format: 'YYYY-MM-DD'
        }
    });

    // Handle add metrics button click
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

        try {
            // Add each selected metric as a new chart
            for (const metricId of selectedMetrics) {
                await addCustomMetric(metricId, dateRange);
            }

            // Close modal and reset selections
            $('#metricsModal').modal('hide');
            $('#customMetricSelect').val(null).trigger('change');
            $('#metricDateRange').val('');
        } catch (error) {
            console.error('Error adding metrics:', error);
            alert('Error adding metrics. Please try again.');
        }
    });
});

async function addCustomMetric(metricId, dateRange) {
    const config = customMetricConfigs[metricId];
    if (!config) return;

    // Create widget HTML
    const widgetHtml = `
        <div class="grid-stack-item-content">
            <div class="card h-100 border-0 shadow-sm">
                <div class="card-header bg-transparent border-0 handle d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">${config.label}</h5>
                    <div class="chart-controls">
                        <button class="btn btn-sm btn-icon" onclick="downloadChart('${metricId}')">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-sm btn-icon" onclick="removeCustomChart('${metricId}')">
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
    const widget = grid.addWidget({
        w: 6,
        h: 4,
        content: widgetHtml
    });

    // Initialize the chart with actual data
    await initializeCustomChart(metricId, config, dateRange);
}

async function initializeCustomChart(metricId, config, dateRange) {
    const ctx = document.getElementById(`${metricId}Chart`).getContext('2d');
    
    try {
        // Show loading state
        const chartContainer = ctx.canvas.closest('.chart-container');
        chartContainer.classList.add('loading');
        
        // Fetch actual data from the backend
        const response = await fetch(`${config.endpoint}?dateRange=${dateRange}`);
        if (!response.ok) throw new Error('Failed to fetch chart data');
        
        const chartData = await response.json();
        
        // Create chart with actual data
        charts[metricId] = new Chart(ctx, {
            type: config.type,
            data: chartData,
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
        console.error('Error initializing chart:', error);
        const chartContainer = ctx.canvas.closest('.chart-container');
        chartContainer.innerHTML = `
            <div class="alert alert-danger">
                Failed to load chart data. Please try again.
            </div>
        `;
    } finally {
        const chartContainer = ctx.canvas.closest('.chart-container');
        chartContainer.classList.remove('loading');
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