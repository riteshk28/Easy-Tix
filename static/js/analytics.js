// Global variables
let grid;
const charts = {};
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
    agent_performance: {
        label: 'Agent Performance',
        type: 'bar',
        endpoint: '/analytics/api/custom/agent-performance'
    },
    response_time_trend: {
        label: 'Response Time Trend',
        type: 'line',
        endpoint: '/analytics/api/custom/first-response-trend'
    },
    resolution_time: {
        label: 'Resolution Time by Priority',
        type: 'bar',
        endpoint: '/analytics/api/custom/resolution-time-by-priority'
    }
};

// Color scheme
const colors = {
    primary: '#4e73df',
    success: '#1cc88a',
    info: '#36b9cc',
    warning: '#f6c23e',
    danger: '#e74a3b'
};

// Initialize everything when the document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Remove Select2 initialization since we're not using it
    initializeDashboard();
    initializeEventListeners();

    // Initialize grid only if container exists
    const gridContainer = document.querySelector('.grid-stack');
    if (gridContainer) {
        grid = GridStack.init({
            cellHeight: 100,
            minRow: 1,
            margin: 10,
            float: true,
            column: 12,
            animate: true
        });

        // Add resize handler for Plotly
        grid.on('resizestop', function() {
            const containers = document.querySelectorAll('.chart-container');
            containers.forEach(container => {
                if (container.firstChild) {
                    Plotly.Plots.resize(container.firstChild);
                }
            });
        });
    }

    // Get the modal instance
    const metricsModal = new bootstrap.Modal(document.getElementById('metricsModal'));

    // Handle add metrics button click
    $('#addMetricsBtn').on('click', async function() {
        const selectedMetrics = $('#customMetricSelect').val();
        const dateRange = $('#metricDateRange').val();
        
        console.log('Button clicked');
        console.log('Selected metrics:', selectedMetrics);
        console.log('Date range:', dateRange);

        if (!selectedMetrics || selectedMetrics.length === 0) {
            alert('Please select at least one metric');
            return;
        }

        if (!dateRange) {
            alert('Please select a date range');
            return;
        }

        try {
            // Get current grid items to calculate next position
            const items = grid.engine.nodes;
            console.log('Current grid items:', items);
            
            let nextY = 0;
            if (items.length > 0) {
                const maxY = Math.max(...items.map(item => item.y + item.h));
                nextY = maxY;
            }
            console.log('Next Y position:', nextY);

            for (const metricId of selectedMetrics) {
                console.log('Processing metric:', metricId);
                const config = customMetricConfigs[metricId];
                if (!config) {
                    console.error('No config found for metric:', metricId);
                    continue;
                }

                // Create unique ID for this instance
                const uniqueId = `${metricId}_${Date.now()}`;
                console.log('Generated unique ID:', uniqueId);

                const widgetHtml = `
                    <div class="grid-stack-item-content">
                        <div class="card h-100 border-0 shadow-sm">
                            <div class="card-header bg-transparent d-flex justify-content-between align-items-center handle">
                                <h6 class="mb-0">${config.label}</h6>
                                <div>
                                    <button type="button" class="btn btn-sm btn-icon" onclick="removeWidget(this)">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="chart-container" style="position: relative; height: 100%; width: 100%;">
                                    <canvas id="${uniqueId}Chart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                console.log('Adding widget to grid at y:', nextY);
                const widget = grid.addWidget({
                    w: 6,
                    h: 4,
                    y: nextY,
                    x: nextY % 2 * 6,
                    content: widgetHtml,
                    id: uniqueId
                });
                console.log('Widget added:', widget);

                // Wait for DOM update
                await new Promise(resolve => setTimeout(resolve, 100));

                // Initialize chart with the unique ID
                console.log('Initializing chart with ID:', uniqueId);
                await initializeCustomChart(uniqueId, config, dateRange);
                
                nextY = nextY + (nextY % 2 === 1 ? 4 : 0);
            }

            // Success handling
            $('#customMetricSelect').val(null).trigger('change');
            $('#metricDateRange').val('');
            metricsModal.hide();

            const toast = document.createElement('div');
            toast.className = 'alert alert-success position-fixed bottom-0 end-0 m-3';
            toast.style.zIndex = '1050';
            toast.textContent = 'Metrics added successfully';
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);

        } catch (error) {
            console.error('Error adding metrics:', error);
            alert('Failed to add metrics. Please try again.');
        }
    });

    // Handle modal hidden event to reset form
    $('#metricsModal').on('hidden.bs.modal', function () {
        $('#customMetricSelect').val(null).trigger('change');
        $('#metricDateRange').val('');
    });
});

async function initializeDashboard() {
    try {
        showLoading();
        const data = await fetchDashboardData();
        updateDashboard(data);
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showError();
    }
}

function initializeEventListeners() {
    // Time range selector
    document.querySelectorAll('[data-time-range]').forEach(button => {
        button.addEventListener('click', function() {
            const days = this.dataset.timeRange;
            updateTimeRange(days);
        });
    });
}

async function fetchDashboardData() {
    try {
        const response = await fetch(`/analytics/data/dashboard?days=${currentDays}`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch dashboard data');
        }
        return response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

function showLoading() {
    // Show loading state for summary tiles
    document.querySelectorAll('.summary-tile h2').forEach(el => {
        el.textContent = '...';
    });
    
    // Show loading state for charts
    document.querySelectorAll('.chart-container').forEach(container => {
        container.innerHTML = `
            <div class="d-flex justify-content-center align-items-center h-100">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    });
}

function showError() {
    document.querySelectorAll('.summary-tile h2').forEach(el => {
        el.textContent = 'Error';
    });
    
    document.querySelectorAll('.chart-container').forEach(container => {
        container.innerHTML = `
            <div class="alert alert-danger m-3">
                Failed to load data. Please try again later.
            </div>
        `;
    });
}

function updateDashboard(data) {
    updateSummaryTiles(data.summary);
    initializeCharts(data.charts);
}

function updateSummaryTiles(summary) {
    // Update summary tiles with formatted values
    if (summary.openTickets !== undefined) {
        document.getElementById('openTicketsCount').textContent = summary.openTickets;
    }
    if (summary.avgResponseTime !== undefined) {
        document.getElementById('avgResponseTime').textContent = 
            formatDuration(summary.avgResponseTime);
    }
    if (summary.resolutionRate !== undefined) {
        document.getElementById('resolutionRate').textContent = 
            `${(summary.resolutionRate * 100).toFixed(1)}%`;
    }
    if (summary.slaCompliance !== undefined) {
        document.getElementById('slaCompliance').textContent = 
            `${(summary.slaCompliance * 100).toFixed(1)}%`;
    }
}

function initializeCharts(chartData) {
    if (chartData.ticketTrend) {
        const layout = {
            margin: { t: 20, r: 20, l: 40, b: 40 },
            showlegend: true,
            hovermode: 'x unified',
            xaxis: {
                showgrid: false,
                zeroline: false
            },
            yaxis: {
                showgrid: true,
                zeroline: false,
                title: 'Number of Tickets'
            }
        };
        
        const container = document.getElementById('ticketTrendContainer');
        if (container) {
            Plotly.newPlot(container, [chartData.ticketTrend], layout, {responsive: true});
        }
    }

    if (chartData.statusDistribution) {
        const layout = {
            margin: { t: 20, r: 20, l: 20, b: 20 },
            showlegend: true
        };
        Plotly.newPlot('statusDistributionContainer', [chartData.statusDistribution], layout, {responsive: true});
    }

    if (chartData.agentPerformance) {
        const layout = {
            margin: { t: 20, r: 20, l: 40, b: 100 },
            showlegend: true,
            xaxis: {
                tickangle: -45
            },
            yaxis: {
                title: 'Tickets Handled'
            }
        };
        Plotly.newPlot('agentPerformanceContainer', [chartData.agentPerformance], layout, {responsive: true});
    }

    if (chartData.responseTime) {
        const layout = {
            margin: { t: 20, r: 20, l: 40, b: 40 },
            showlegend: false,
            yaxis: {
                title: 'Response Time (hours)'
            }
        };
        Plotly.newPlot('responseTimeContainer', [chartData.responseTime], layout, {responsive: true});
    }
}

// Utility functions
function formatDuration(hours) {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${Math.round(hours)}h`;
    return `${Math.round(hours / 24)}d`;
}

async function updateTimeRange(days) {
    currentDays = days;
    const btn = document.getElementById('timeRangeBtn');
    if (btn) {
        btn.textContent = `Last ${days} Days`;
    }
    await initializeDashboard();
}

// Update initializeCustomChart to use Plotly instead of Chart.js
async function initializeCustomChart(metricId, config, dateRange) {
    const container = document.getElementById(`${metricId}Container`);
    if (!container) {
        console.error('Container not found for:', metricId);
        return;
    }
    
    try {
        container.innerHTML = '<div class="loading-spinner">Loading...</div>';
        const url = `${config.endpoint}?dateRange=${dateRange}`;
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('Failed to fetch data');
        }
        
        const data = await response.json();
        
        const layout = {
            margin: { t: 20, r: 20, l: 40, b: 40 },
            showlegend: true,
            height: container.clientHeight,
            width: container.clientWidth
        };

        Plotly.newPlot(container, [data], layout, {responsive: true});
    } catch (error) {
        console.error('Error creating chart:', error);
        container.innerHTML = '<div class="alert alert-danger">Failed to load chart</div>';
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

// Add this function to handle widget removal
window.removeWidget = function(button) {
    const gridItem = button.closest('.grid-stack-item');
    const canvas = gridItem.querySelector('canvas');
    const chartId = canvas.id.replace('Chart', '');
    
    // Remove from grid
    grid.removeWidget(gridItem);
    
    // Destroy chart instance
    if (charts[chartId]) {
        charts[chartId].destroy();
        delete charts[chartId];
    }
}; 