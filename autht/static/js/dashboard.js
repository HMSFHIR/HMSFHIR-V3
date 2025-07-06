function refreshLogs() {
    location.reload();
}

// Auto-refresh every 30 seconds
setInterval(function() {
    // Only auto-refresh if user hasn't interacted recently
    if (document.hidden === false) {
        refreshLogs();
    }
}, 30000);

// Collapse/expand log details
document.addEventListener('DOMContentLoaded', function() {
    const logDetails = document.querySelectorAll('.log-details');
    logDetails.forEach(function(detail) {
        detail.style.cursor = 'pointer';
        detail.addEventListener('click', function() {
            const pre = this.querySelector('pre');
            if (pre.style.display === 'none') {
                pre.style.display = 'block';
            } else {
                pre.style.display = 'none';
            }
        });
    });
});
