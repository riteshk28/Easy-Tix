// Empty file to prevent 404 errors
// You can add JavaScript functionality here later 

if (typeof url === 'undefined') {
    var url = window.location.pathname;
}

function copyPortalLink() {
    var copyText = document.getElementById("portalLink");
    copyText.select();
    copyText.setSelectionRange(0, 99999); // For mobile devices
    document.execCommand("copy");
    
    // Optional: Show feedback
    var button = event.target;
    var originalText = button.innerHTML;
    button.innerHTML = "Copied!";
    setTimeout(function() {
        button.innerHTML = originalText;
    }, 2000);
} 

document.addEventListener('DOMContentLoaded', function() {
    // Make table rows clickable
    const clickableRows = document.querySelectorAll('.clickable-row');
    console.log('Found clickable rows:', clickableRows.length);
    
    clickableRows.forEach(row => {
        // Add visual cue for clickable rows
        row.style.cursor = 'pointer';
        
        row.addEventListener('click', function(e) {
            // Don't trigger if they clicked a link, button, or form element
            if (!e.target.closest('a') && !e.target.closest('.btn') && !e.target.closest('form')) {
                e.preventDefault();
                const href = this.dataset.href;
                if (href) {
                    window.location.href = href;
                }
            }
        });
    });
}); 

document.addEventListener('DOMContentLoaded', function() {
    const navbar = document.querySelector('.navbar');
    
    // Only add scroll listener if navbar exists
    if (navbar) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }
}); 

fetch(url, {
    method: 'POST',
    headers: {
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
    },
    // ...
}) 

function updateEmailSettings() {
    $.ajax({
        url: '/admin/update-email-settings',
        method: 'POST',
        data: {
            'csrf_token': $('meta[name=csrf-token]').attr('content'),
            // other form data
        },
        success: function(response) {
            // handle success
        }
    });
} 

// Set up CSRF token for all AJAX requests
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", $('meta[name=csrf-token]').attr('content'));
        }
    }
}); 

function setupDeleteOrgModal() {
    const deleteOrgModal = document.getElementById('deleteOrgModal');
    if (deleteOrgModal) {
        deleteOrgModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const orgId = button.getAttribute('data-org-id');
            const form = document.getElementById('deleteOrgForm');
            form.action = `/superadmin/delete-org/${orgId}`;
        });
    }
} 

// Sidebar toggle functionality 
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const content = document.getElementById('content');
    const toggle = document.getElementById('sidebarToggle');
    
    // Get sidebar state from localStorage
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    
    if (sidebarCollapsed) {
        sidebar.classList.add('collapsed');
        content.classList.add('sidebar-collapsed');
        document.documentElement.classList.remove('sidebar-collapsed-init');
    }
    
    // Enable transitions after initial state is set
    setTimeout(() => {
        sidebar.classList.add('transition-enabled');
        content.classList.add('transition-enabled');
    }, 100);

    toggle.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        content.classList.toggle('sidebar-collapsed');
        
        // Save state
        localStorage.setItem('sidebarCollapsed', 
            sidebar.classList.contains('collapsed'));
    });
}); 