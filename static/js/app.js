/**
 * MediCare HMS - Client Application Scripts
 * Manages UI interactions, mobile drawer, toast dismissals, and quick actions.
 */

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // 1. MOBILE SIDEBAR DRAWER TOGGLE
    // -------------------------------------------------------------
    const sidebar = document.querySelector('.app-sidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    const backdrop = document.querySelector('.sidebar-backdrop');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
            if (backdrop) backdrop.classList.toggle('show');
        });
    }

    if (backdrop) {
        backdrop.addEventListener('click', () => {
            if (sidebar) sidebar.classList.remove('show');
            backdrop.classList.remove('show');
        });
    }

    // -------------------------------------------------------------
    // 2. AUTO-DISMISS FLASH TOAST ALERTS
    // -------------------------------------------------------------
    const flashAlerts = document.querySelectorAll('.alert-auto-dismiss');
    flashAlerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 400);
        }, 5000);
    });

    // -------------------------------------------------------------
    // 3. PASSWORD VISIBILITY TOGGLE (LOGIN)
    // -------------------------------------------------------------
    const togglePasswordBtn = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');

    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            const icon = togglePasswordBtn.querySelector('i');
            if (icon) {
                icon.className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
            }
        });
    }

    // -------------------------------------------------------------
    // 4. QUICK DEMO LOGIN BUTTONS (EVALUATION / PRESENTATION HELPER)
    // -------------------------------------------------------------
    window.fillCredentials = function(username, password) {
        const uInput = document.getElementById('username');
        const pInput = document.getElementById('password');
        if (uInput && pInput) {
            uInput.value = username;
            pInput.value = password;
            // Visual feedback
            uInput.classList.add('border-primary');
            pInput.classList.add('border-primary');
            setTimeout(() => {
                uInput.classList.remove('border-primary');
                pInput.classList.remove('border-primary');
            }, 600);
        }
    };

    // -------------------------------------------------------------
    // 5. CLIENT-SIDE LIVE TABLE FILTER
    // -------------------------------------------------------------
    const liveSearchInput = document.getElementById('liveTableSearch');
    const filterableTable = document.querySelector('.table-filterable tbody');

    if (liveSearchInput && filterableTable) {
        liveSearchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase().trim();
            const rows = filterableTable.querySelectorAll('tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(term) ? '' : 'none';
            });
        });
    }
});
