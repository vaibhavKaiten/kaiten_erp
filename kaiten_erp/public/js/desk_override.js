// Wait for Frappe to be fully loaded before executing
(function() {
    function initLogoOverride() {
        if (typeof frappe !== 'undefined' && frappe.ready) {
            frappe.ready(() => {
                const interval = setInterval(() => {
                    let logo = document.querySelector('.app-loading img');
                    if (logo) {
                        logo.src = '/assets/kaiten_erp/images/Kaiten.png';
                        logo.style.maxWidth = "180px";   // optional sizing
                        logo.style.height = "auto";
                        clearInterval(interval);
                    }
                }, 100);
            });
        } else {
            // Frappe not ready yet, try again after 100ms
            setTimeout(initLogoOverride, 100);
        }
    }
    
    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLogoOverride);
    } else {
        initLogoOverride();
    }
})();