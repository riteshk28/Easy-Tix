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

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Select2
    $('#customMetricSelect').select2({
        dropdownParent: $('#metricsModal'),
        placeholder: 'Select metrics...',
        width: '100%'
    });

    // Initialize grid with proper options
    grid = GridStack.init({
        cellHeight: 100,
        minRow: 1,
        margin: 10,
        draggable: {
            handle: '.handle'
        },
        float: true,
        column: 12,
        animate: true,
        resizable: {
            handles: 'e,se,s,sw,w'
        }
    });

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

// Function to initialize custom chart
async function initializeCustomChart(metricId, config, dateRange) {
    console.log('Starting chart initialization:', metricId);
    const canvas = document.getElementById(`${metricId}Chart`);
    if (!canvas) {
        console.error('Canvas not found for:', metricId);
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const container = canvas.closest('.chart-container');
    
    try {
        container.classList.add('loading');
        const url = `${config.endpoint}?dateRange=${dateRange}`;
        console.log('Fetching data from:', url);
        
        const response = await fetch(url);
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API response not ok:', response.status, errorText);
            throw new Error('Failed to fetch data');
        }
        
        const data = await response.json();
        console.log('Received data for', metricId, ':', data);
        
        if (charts[metricId]) {
            console.log('Destroying existing chart:', metricId);
            charts[metricId].destroy();
        }
        
        console.log('Creating new chart:', metricId);
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
                },
                animation: {
                    duration: 750,
                    easing: 'easeInOutQuart'
                }
            }
        });
        console.log('Chart created successfully:', metricId);
    } catch (error) {
        console.error('Error creating chart:', error);
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