
(function() {
    'use strict';

    function closeAllMenus() {
        document.querySelectorAll('.presentation-dropdown.active').forEach(menu => {
            menu.classList.remove('active');
        });
    }

    function toggleMenu(event) {
        event.preventDefault();
        event.stopPropagation();
        
        const button = event.currentTarget;
        const dropdown = button.nextElementSibling;
        const isActive = dropdown.classList.contains('active');
        
        closeAllMenus();
        
        if (!isActive) {
            dropdown.classList.add('active');
        }
    }

    function handleMenuAction(event, action, presentationId) {
        event.preventDefault();
        event.stopPropagation();
        
        closeAllMenus();
        
        switch(action) {
            case 'presentar':
                const presentUrl = event.currentTarget.href;
                if (presentUrl && presentUrl !== '#') {
                    window.open(presentUrl, '_blank');
                } else {
                    console.log('Presentar:', presentationId);
                    alert('Función de presentación en desarrollo');
                }
                break;
                
            case 'editar':
                console.log('Editar presentación:', presentationId);
                alert('Función de edición en desarrollo');
                break;
                
            case 'duplicar':
                console.log('Duplicar presentación:', presentationId);
                alert('Función de duplicación en desarrollo');
                break;
                
            case 'descargar':
                console.log('Descargar presentación:', presentationId);
                alert('Función de descarga en desarrollo');
                break;
                
            case 'compartir':
                console.log('Compartir presentación:', presentationId);
                alert('Función de compartir en desarrollo');
                break;
                
            case 'eliminar':
                if (confirm('¿Estás seguro de que deseas eliminar esta presentación?')) {
                    console.log('Eliminar presentación:', presentationId);
                    alert('Función de eliminación en desarrollo');
                }
                break;
                
            default:
                console.log('Acción desconocida:', action);
        }
    }

    function initializeMenus() {
        document.querySelectorAll('.presentation-menu-btn').forEach(button => {
            button.addEventListener('click', toggleMenu);
        });
        
        document.querySelectorAll('.dropdown-item').forEach(item => {
            const action = item.dataset.action;
            const presentationId = item.closest('.presentation-card').dataset.id;
            
            item.addEventListener('click', (e) => handleMenuAction(e, action, presentationId));
        });
        
        document.addEventListener('click', (event) => {
            if (!event.target.closest('.presentation-dropdown') && 
                !event.target.closest('.presentation-menu-btn')) {
                closeAllMenus();
            }
        });
        
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeAllMenus();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeMenus);
    } else {
        initializeMenus();
    }
})();