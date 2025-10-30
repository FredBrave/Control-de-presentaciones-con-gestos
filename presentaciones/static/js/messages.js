document.addEventListener('DOMContentLoaded', function() {
    initializeMessages();
});

/**
 * Inicializa el sistema de mensajes
 */
function initializeMessages() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            closeAlert(alert);
        }, 6000);
    });
}

/**
 * Cierra un mensaje con animación
 * @param {HTMLElement} alert - Elemento de alerta a cerrar
 */
function closeAlert(alert) {
    alert.style.animation = 'slideOutRight 0.3s ease-out';
    setTimeout(() => {
        alert.remove();
    }, 300);
}

/**
 * Crea y muestra un mensaje dinámicamente
 * @param {string} message - Texto del mensaje
 * @param {string} type - Tipo: 'success', 'error', 'warning', 'info'
 */
function showMessage(message, type = 'info') {
    let container = document.querySelector('.messages-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'messages-container';
        document.body.appendChild(container);
    }

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span class="alert-message">${message}</span>
        <button class="alert-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(alert);

    setTimeout(() => {
        closeAlert(alert);
    }, 6000);
}

/**
 * Muestra un mensaje de éxito
 * @param {string} message - Texto del mensaje
 */
function showSuccess(message) {
    showMessage(message, 'success');
}

/**
 * Muestra un mensaje de error
 * @param {string} message - Texto del mensaje
 */
function showError(message) {
    showMessage(message, 'error');
}

/**
 * Muestra un mensaje de advertencia
 * @param {string} message - Texto del mensaje
 */
function showWarning(message) {
    showMessage(message, 'warning');
}

/**
 * Muestra un mensaje informativo
 * @param {string} message - Texto del mensaje
 */
function showInfo(message) {
    showMessage(message, 'info');
}

window.showMessage = showMessage;
window.showSuccess = showSuccess;
window.showError = showError;
window.showWarning = showWarning;
window.showInfo = showInfo;