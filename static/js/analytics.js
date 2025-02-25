// Global variables
var grid;
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
    },
    sla_breach_priority: {
        label: 'SLA Breach by Priority',
        type: 'bar',
        endpoint: '/analytics/api/custom/sla-breach-priority'
    },
    first_response_sla: {
        label: 'First Response vs SLA',
        type: 'line',
        endpoint: '/analytics/api/custom/first-response-sla'
    },
    resolution_sla: {
        label: 'Resolution Time vs SLA',
        type: 'line',
        endpoint: '/analytics/api/custom/resolution-sla'
    },
    source_distribution: {
        label: 'Source Distribution',
        type: 'pie',
        endpoint: '/analytics/api/custom/source-distribution'
    },
    word_cloud: {
        label: 'Common Ticket Subjects',
        type: 'wordcloud',
        endpoint: '/analytics/api/custom/word-cloud'
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

const chartMappings = {
    'ticketTrend': 'ticketTrendContainer',
    'statusDistribution': 'statusDistributionContainer',
    'agentPerformance': 'agentPerformanceContainer',
    'responseTime': 'responseTimeContainer',
    'slaBreachPriority': 'slaBreachContainer',
    'firstResponseSLA': 'responseVsSLAContainer',
    'sourceDistribution': 'sourceDistributionContainer',
    'wordCloud': 'wordCloudContainer'
};

// Initialize everything when the document is ready
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Load Plotly.js first
        loadScript('https://cdn.plot.ly/plotly-latest.min.js')
            .then(() => {
                console.log('Plotly loaded successfully');
                initializeDashboard();
                initializeEventListeners();
            })
            .catch(error => {
                console.error('Error loading Plotly:', error);
            });
    } catch (error) {
        console.error('Error in initialization:', error);
    }

    // Initialize grid with draggable and removable options
    const gridContainer = document.querySelector('.grid-stack');
    if (gridContainer) {
        grid = GridStack.init({
            cellHeight: 100,
            minRow: 1,
            margin: 10,
            float: true,
            column: 12,
            animate: true,
            draggable: {
                handle: '.card-header'  // Make cards draggable by header
            }
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

    // Add this after your existing event listeners
    $('#selectAllStatus').change(function() {
        const isChecked = $(this).prop('checked');
        $('input[name="status"]').prop('checked', isChecked).trigger('change');
    });

    $('#selectAllPriority').change(function() {
        const isChecked = $(this).prop('checked');
        $('input[name="priority"]').prop('checked', isChecked).trigger('change');
    });

    // Add change event for individual checkboxes to update "Select All"
    $('input[name="status"]').change(function() {
        const allChecked = $('input[name="status"]').length === $('input[name="status"]:checked').length;
        $('#selectAllStatus').prop('checked', allChecked);
    });

    $('input[name="priority"]').change(function() {
        const allChecked = $('input[name="priority"]').length === $('input[name="priority"]:checked').length;
        $('#selectAllPriority').prop('checked', allChecked);
    });

    // Initialize chart preferences
    loadChartPreferences();
});

// Add helper function to load scripts
function loadScript(url) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Update the initializeDashboard function
async function initializeDashboard() {
    try {
        console.log('Initializing dashboard...');
        
        // Make sure Plotly is loaded
        if (typeof Plotly === 'undefined') {
            throw new Error('Plotly is not loaded');
        }

        // Get all chart containers
        const chartElements = document.querySelectorAll('[data-chart]');
        console.log('Found chart elements:', chartElements.length);

        for (const element of chartElements) {
            const chartType = element.dataset.chart;
            console.log('Processing chart:', chartType);

            try {
                const response = await fetch(`/analytics/data/${chartType}`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                console.log('Chart data received:', chartType, data);

                const containerId = chartMappings[chartType];
                const container = document.getElementById(containerId);

                if (!container) {
                    console.error(`Container not found for ${chartType}:`, containerId);
                    continue;
                }

                // Create the chart based on type
                if (chartType === 'wordCloud') {
                    createWordCloud(container, data);
                } else {
                    const plotData = Array.isArray(data) ? data : [data];
                    Plotly.newPlot(container, plotData, {
                        margin: { t: 20, r: 20, l: 40, b: 40 },
                        showlegend: data.type === 'pie',
                        height: 300,
                        yaxis: {
                            tickformat: data.type === 'bar' ? ',.0f' : undefined
                        }
                    });
                }
            } catch (error) {
                console.error(`Error creating chart ${chartType}:`, error);
            }
        }
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        throw error;
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
    const containers = ['ticketTrendContainer', 'statusDistributionContainer', 
                       'agentPerformanceContainer', 'responseTimeContainer'];
    
    containers.forEach(id => {
        const container = document.getElementById(id);
        if (container) {
            container.innerHTML = '<div class="loading-spinner">Loading...</div>';
        }
    });
}

function showError() {
    // Add a more visible error message
    const errorAlert = document.createElement('div');
    errorAlert.className = 'alert alert-danger position-fixed top-0 end-0 m-3';
    errorAlert.textContent = 'Failed to load some charts. Please try refreshing the page.';
    document.body.appendChild(errorAlert);
    setTimeout(() => errorAlert.remove(), 5000);
}

function updateDashboard(data) {
    // Update summary metrics
    if (data.summary) {
        document.getElementById('openTickets').textContent = data.summary.openTickets;
        document.getElementById('inProgress').textContent = data.summary.inProgress;
        document.getElementById('avgResponseTime').textContent = formatDuration(data.summary.avgResponseTime);
        document.getElementById('avgResolutionTime').textContent = formatDuration(data.summary.avgResolutionTime);
    }

    // Initialize charts
    if (data.charts) {
        initializeCharts(data.charts);
    }
}

function initializeCharts(chartData) {
    // Remove loading spinners first
    document.querySelectorAll('.loading-spinner').forEach(spinner => {
        spinner.remove();
    });

    if (chartData.ticketTrend) {
        const trendLayout = {
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
        Plotly.newPlot('ticketTrendContainer', [chartData.ticketTrend], trendLayout, {responsive: true});
    }

    // Status Distribution
    if (chartData.statusDistribution) {
        const pieLayout = {
            margin: { t: 20, r: 20, l: 20, b: 20 },
            showlegend: true
        };
        Plotly.newPlot('statusDistributionContainer', [chartData.statusDistribution], pieLayout, {responsive: true});
    }

    // Agent Performance
    if (chartData.agentPerformance) {
        const barLayout = {
            margin: { t: 20, r: 20, l: 40, b: 100 },
            showlegend: true,
            xaxis: {
                tickangle: -45
            },
            yaxis: {
                title: 'Tickets Handled'
            }
        };
        Plotly.newPlot('agentPerformanceContainer', [chartData.agentPerformance], barLayout, {responsive: true});
    }

    // Response Time
    if (chartData.responseTime) {
        const boxLayout = {
            margin: { t: 20, r: 20, l: 40, b: 40 },
            showlegend: false,
            yaxis: {
                title: 'Response Time (hours)'
            }
        };
        Plotly.newPlot('responseTimeContainer', [chartData.responseTime], boxLayout, {responsive: true});
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

// Add window resize handler
window.addEventListener('resize', function() {
    const containers = document.querySelectorAll('.chart-container');
    containers.forEach(container => {
        if (container.firstChild) {
            Plotly.Plots.resize(container);
        }
    });
});

// Initialize date range picker for export modal
$('#dateRange').daterangepicker({
    autoUpdateInput: false,
    showDropdowns: true,
    ranges: {
        'Today': [moment(), moment()],
        'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
        'Last 7 Days': [moment().subtract(6, 'days'), moment()],
        'Last 30 Days': [moment().subtract(29, 'days'), moment()],
        'This Month': [moment().startOf('month'), moment().endOf('month')],
        'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
    }
});

// Apply handler for export modal
$('#dateRange').on('apply.daterangepicker', function(ev, picker) {
    $(this).val(picker.startDate.format('MM/DD/YYYY') + ' - ' + picker.endDate.format('MM/DD/YYYY'));
});

// Cancel handler for export modal
$('#dateRange').on('cancel.daterangepicker', function(ev, picker) {
    $(this).val('');
});

// Add this function for export functionality
async function exportFilteredData() {
    const dateRange = $('#dateRange').val();
    const statuses = $('input[name="status"]:checked').map(function() {
        return this.value;
    }).get();
    const priorities = $('input[name="priority"]:checked').map(function() {
        return this.value;
    }).get();

    if (!dateRange) {
        alert('Please select a date range');
        return;
    }

    if (statuses.length === 0 || priorities.length === 0) {
        alert('Please select at least one status and priority');
        return;
    }

    try {
        const response = await fetch('/analytics/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({
                dateRange,
                statuses,
                priorities
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'ticket_data.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('exportModal'));
        modal.hide();
    } catch (error) {
        console.error('Export error:', error);
        alert(error.message || 'Failed to export data. Please try again.');
    }
}

// Add this function for date range quick selection
function setDateRange(range) {
    const picker = $('#dateRange').data('daterangepicker');
    switch(range) {
        case 'today':
            picker.setStartDate(moment());
            picker.setEndDate(moment());
            break;
        case 'yesterday':
            picker.setStartDate(moment().subtract(1, 'days'));
            picker.setEndDate(moment().subtract(1, 'days'));
            break;
        case 'last7':
            picker.setStartDate(moment().subtract(6, 'days'));
            picker.setEndDate(moment());
            break;
        case 'last30':
            picker.setStartDate(moment().subtract(29, 'days'));
            picker.setEndDate(moment());
            break;
        case 'thisMonth':
            picker.setStartDate(moment().startOf('month'));
            picker.setEndDate(moment().endOf('month'));
            break;
    }
    $('#dateRange').val(picker.startDate.format('MM/DD/YYYY') + ' - ' + picker.endDate.format('MM/DD/YYYY'));
}

// Add this function to handle word cloud specifically
function createWordCloud(container, data) {
    const layout = {
        margin: { t: 20, r: 20, l: 20, b: 20 },
        showlegend: false,
        hovermode: 'closest',
        xaxis: { showgrid: false, showticklabels: false },
        yaxis: { showgrid: false, showticklabels: false }
    };
    
    Plotly.newPlot(container, [data], layout, {responsive: true});
}

// Add this function near the other fetch functions
async function fetchData(endpoint) {
    try {
        const response = await fetch(`${endpoint}?days=${currentDays}`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch data');
        }
        return response.json();
    } catch (error) {
        console.error(`Error fetching from ${endpoint}:`, error);
        showError();
        throw error;
    }
}

// Add this function to handle chart removal
function removeChartWidget(button) {
    const card = button.closest('.grid-stack-item');
    if (card && grid) {
        grid.removeWidget(card);
        // Trigger resize event to adjust other charts
        window.dispatchEvent(new Event('resize'));
    }
}

// Add these functions for chart management
function saveChartPreferences() {
    const visibleCharts = {};
    document.querySelectorAll('#chartsModal input[type="checkbox"]').forEach(checkbox => {
        visibleCharts[checkbox.value] = checkbox.checked;
    });
    localStorage.setItem('chartPreferences', JSON.stringify(visibleCharts));
}

function loadChartPreferences() {
    const savedPreferences = localStorage.getItem('chartPreferences');
    if (savedPreferences) {
        const preferences = JSON.parse(savedPreferences);
        document.querySelectorAll('#chartsModal input[type="checkbox"]').forEach(checkbox => {
            if (preferences.hasOwnProperty(checkbox.value)) {
                checkbox.checked = preferences[checkbox.value];
            }
        });
        updateVisibleCharts();
    }
}

function updateVisibleCharts() {
    const checkboxes = document.querySelectorAll('#chartsModal input[type="checkbox"]');
    let needsRefresh = false;

    checkboxes.forEach(checkbox => {
        const chartContainer = document.querySelector(`.grid-stack-item[data-chart="${checkbox.value}"]`);
        if (chartContainer) {
            const wasVisible = chartContainer.style.display !== 'none';
            const shouldBeVisible = checkbox.checked;
            
            if (wasVisible !== shouldBeVisible) {
                chartContainer.style.display = shouldBeVisible ? '' : 'none';
                needsRefresh = true;
            }
        }
    });
    
    saveChartPreferences();
    
    if (needsRefresh) {
        // Reinitialize visible charts
        initializeDashboard().catch(error => {
            console.error('Error refreshing charts:', error);
        });
    }

    const modal = bootstrap.Modal.getInstance(document.getElementById('chartsModal'));
    if (modal) modal.hide();
}

function selectAllCharts(select) {
    document.querySelectorAll('#chartsModal input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = select;
    });
} 