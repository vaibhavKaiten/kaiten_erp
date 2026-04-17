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