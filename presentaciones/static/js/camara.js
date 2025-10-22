
(function() {
    'use strict';

    async function checkCameraAvailability() {
        const cameraDot = document.querySelector('.camera-dot');
        const cameraText = document.querySelector('.camera-text');
        
        if (!cameraDot) {
            console.log('Indicador de cámara no encontrado');
            return;
        }

        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                updateCameraStatus(false, cameraDot, cameraText);
                return;
            }

            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(device => device.kind === 'videoinput');

            if (videoDevices.length > 0) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        video: true,
                        audio: false 
                    });
                    
                    updateCameraStatus(true, cameraDot, cameraText);
                    
                    stream.getTracks().forEach(track => track.stop());
                } catch (permissionError) {
                    console.log('Cámara detectada pero:', permissionError.name);
                    if (permissionError.name === 'NotAllowedError') {
                        updateCameraStatus(false, cameraDot, cameraText, 'Sin permisos');
                    } else if (permissionError.name === 'NotReadableError') {
                        updateCameraStatus(false, cameraDot, cameraText, 'Cámara en uso');
                    } else {
                        updateCameraStatus(false, cameraDot, cameraText);
                    }
                }
            } else {
                updateCameraStatus(false, cameraDot, cameraText, 'No detectada');
            }
        } catch (error) {
            console.error('Error al verificar la cámara:', error);
            updateCameraStatus(false, cameraDot, cameraText);
        }
    }

    function updateCameraStatus(isAvailable, dotElement, textElement, customMessage = null) {
        if (isAvailable) {
            dotElement.classList.add('active');
            if (textElement) {
                textElement.innerHTML = '<i class="fas fa-video"></i> Cámara detectada';
            }
        } else {
            dotElement.classList.remove('active');
            if (textElement) {
                const message = customMessage || 'Sin cámara';
                textElement.innerHTML = `<i class="fas fa-video-slash"></i> ${message}`;
            }
        }
    }

    function startCameraMonitoring() {
        checkCameraAvailability();

        setInterval(checkCameraAvailability, 5000);

        window.addEventListener('focus', checkCameraAvailability);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startCameraMonitoring);
    } else {
        startCameraMonitoring();
    }
})();