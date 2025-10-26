// ============================================
// PRESENTAR.JS - Control de presentación con gestos
// ============================================

console.log('Iniciando presentar.js...');

// Configurar worker de PDF.js
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.8.162/pdf.worker.min.js';

// ============================================
// VARIABLES GLOBALES DE URL
// ============================================
const url = typeof PDF_URL !== 'undefined' ? PDF_URL : '';
const comandoGestoUrl = typeof COMANDO_GESTO_URL !== 'undefined' ? COMANDO_GESTO_URL : '/presentaciones/comando_gesto/';

// ============================================
// VARIABLES DE ESTADO
// ============================================
let pdfDoc = null;
let currentPage = 1;
let baseScale = 1.5;
let gestureZoom = 1.0;
let pointerX = 0.5;
let pointerY = 0.5;
let isPointerActive = false;
let currentMode = 'navigation';

let drawingMode = false;
let isDrawing = false;
let isErasing = false;
let drawingPath = [];
let drawingPaths = new Map();
let currentStroke = null;

let isMoving = false;
let moveStartX = 0;
let moveStartY = 0;
let moveOffsetX = 0;
let moveOffsetY = 0;

// ============================================
// ELEMENTOS DEL DOM
// ============================================
const canvas = document.getElementById("pdf-canvas");
const drawingCanvas = document.getElementById("drawing-canvas");
const ctx = canvas ? canvas.getContext("2d") : null;
const drawingCtx = drawingCanvas ? drawingCanvas.getContext("2d") : null;
const canvasContainer = document.getElementById("canvas-container");
const pageInfoDisplay = document.getElementById("page-info");
const zoomInfoDisplay = document.getElementById("zoom-info");
const lastCommandDisplay = document.getElementById("last-command");

// CORREGIDO: Usar los IDs correctos del HTML
const prevButton = document.getElementById("prev-page");
const nextButton = document.getElementById("next-page");
const zoomInButton = document.getElementById("zoom-in");
const zoomOutButton = document.getElementById("zoom-out");
const resetZoomButton = document.getElementById("reset-zoom");
const toggleDrawingButton = document.getElementById("toggle-drawing");
const clearDrawingsButton = document.getElementById("clear-drawings");

const errorMessage = document.getElementById("error-message");
const pointerDot = document.getElementById("pointer-dot");
const pdfContainer = document.getElementById("pdf-container");
const modeIndicator = document.getElementById("mode-indicator");
const drawingModeIndicator = document.getElementById("drawing-mode-indicator");
const zoomIndicator = document.getElementById("zoom-indicator");
const drawingControls = document.getElementById("drawing-controls");

// ============================================
// FUNCIONES DE ACTUALIZACIÓN DE UI
// ============================================
const updateModeIndicator = (mode) => {
    if (!modeIndicator) return;
    
    currentMode = mode;
    modeIndicator.className = 'status-indicator';
    
    switch (mode) {
        case 'pointer':
            modeIndicator.className += ' status-pointer';
            modeIndicator.textContent = 'PUNTERO';
            break;
        case 'zoom':
            modeIndicator.className += ' status-zoom';
            modeIndicator.textContent = 'ZOOM';
            break;
        case 'drawing':
            modeIndicator.className += ' status-drawing';
            modeIndicator.textContent = 'DIBUJANDO';
            break;
        case 'erasing':
            modeIndicator.className += ' status-erasing';
            modeIndicator.textContent = 'BORRANDO';
            break;
        case 'moving':
            modeIndicator.className += ' status-pointer';
            modeIndicator.textContent = 'MOVIENDO';
            break;
        default:
            modeIndicator.className += ' status-navigation';
            modeIndicator.textContent = 'NAVEGACIÓN';
    }
};

const updateDrawingModeIndicator = (active) => {
    drawingMode = active;
    
    if (drawingModeIndicator) {
        if (active) {
            drawingModeIndicator.textContent = 'MODO DIBUJO: ON';
            drawingModeIndicator.classList.add('drawing-mode-active');
        } else {
            drawingModeIndicator.textContent = 'MODO DIBUJO: OFF';
            drawingModeIndicator.classList.remove('drawing-mode-active');
            isDrawing = false;
            isErasing = false;
            currentStroke = null;
        }
    }
    
    if (drawingControls) {
        if (active) {
            drawingControls.classList.add('active');
        } else {
            drawingControls.classList.remove('active');
        }
    }
};

const updateZoomDisplay = () => {
    const totalZoom = baseScale * gestureZoom;
    const zoomPercentage = Math.round(totalZoom * 100 / 1.5);
    
    if (zoomInfoDisplay) {
        zoomInfoDisplay.textContent = `Zoom: ${zoomPercentage}%`;
    }
    if (zoomIndicator) {
        zoomIndicator.textContent = `${zoomPercentage}%`;
    }
};

const updatePointer = (x, y, active = true, mode = 'pointer') => {
    if (!canvas || !canvasContainer || !pointerDot) return;
    
    pointerX = Math.max(0, Math.min(1, x));
    pointerY = Math.max(0, Math.min(1, y));
    isPointerActive = active;

    if (active) {
        const canvasRect = canvas.getBoundingClientRect();
        const containerRect = canvasContainer.getBoundingClientRect();

        const pixelX = pointerX * canvasRect.width;
        const pixelY = pointerY * canvasRect.height;
        
        pointerDot.style.left = `${canvasRect.left - containerRect.left + pixelX}px`;
        pointerDot.style.top = `${canvasRect.top - containerRect.top + pixelY}px`;
        pointerDot.style.display = 'block';

        pointerDot.className = 'pointer-dot';
        if (mode === 'drawing') {
            pointerDot.classList.add('drawing-pointer');
        } else if (mode === 'erasing') {
            pointerDot.classList.add('erasing-pointer');
        }

        if (lastCommandDisplay) {
            const modeText = drawingMode ? `(Modo Dibujo)` : '';
            lastCommandDisplay.textContent = `Puntero ${mode}: (${(pointerX*100).toFixed(1)}%, ${(pointerY*100).toFixed(1)}%) ${modeText}`;
        }
    } else {
        pointerDot.style.display = 'none';
        if (currentMode === 'pointer') updateModeIndicator('navigation');
    }
};

// ============================================
// FUNCIONES DE DIBUJO
// ============================================
const initializeDrawingCanvas = () => {
    if (!drawingCanvas || !canvas) return;
    
    drawingCanvas.width = canvas.width;
    drawingCanvas.height = canvas.height;
    drawingCanvas.style.position = 'absolute';
    drawingCanvas.style.top = '0';
    drawingCanvas.style.left = '0';
    drawingCanvas.style.pointerEvents = 'none';
    drawingCanvas.style.zIndex = '15';
    
    if (drawingCtx) {
        drawingCtx.lineCap = 'round';
        drawingCtx.lineJoin = 'round';
        drawingCtx.strokeStyle = '#ff0000';
        drawingCtx.lineWidth = 3;
    }
};

const redrawCanvas = () => {
    if (!drawingCtx || !drawingCanvas) return;
    
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);

    if (isMoving) {
        drawingCtx.save();
        const pixelOffsetX = moveOffsetX * drawingCanvas.width;
        const pixelOffsetY = moveOffsetY * drawingCanvas.height;
        drawingCtx.translate(pixelOffsetX, pixelOffsetY);
    }

    const pageDrawings = drawingPaths.get(currentPage);
    
    if (pageDrawings) {
        pageDrawings.forEach(path => {
            if (path.type === 'draw') {
                drawingCtx.globalCompositeOperation = 'source-over';
                drawingCtx.strokeStyle = path.color || '#ff0000';
                drawingCtx.lineWidth = path.width || 3;
            } else if (path.type === 'erase') {
                drawingCtx.globalCompositeOperation = 'destination-out';
                drawingCtx.lineWidth = path.width || 50; 
            }
            
            if (path.points.length > 1) {
                drawingCtx.beginPath();
                drawingCtx.moveTo(
                    path.points[0].x * drawingCanvas.width, 
                    path.points[0].y * drawingCanvas.height
                );
                
                for (let i = 1; i < path.points.length; i++) {
                    drawingCtx.lineTo(
                        path.points[i].x * drawingCanvas.width, 
                        path.points[i].y * drawingCanvas.height
                    );
                }
                drawingCtx.stroke();
            }
        });
    }
    
    if (isMoving) {
        drawingCtx.restore();
    }

    drawingCtx.globalCompositeOperation = 'source-over';
};

const startDrawing = (x, y) => {
    if (!drawingMode || !drawingCtx) return;
    
    if (isErasing) {
        stopErasing();
    }

    isDrawing = true;
    drawingCtx.globalCompositeOperation = 'source-over';
    currentStroke = {
        type: 'draw',
        points: [{ x, y }],
        color: '#ff0000',
        width: 3
    };
    updateModeIndicator('drawing');
};

const addDrawingPoint = (x, y) => {
    if (!drawingMode || !isDrawing || !currentStroke || !drawingCtx || !drawingCanvas) return;
    
    currentStroke.points.push({ x, y });
    
    drawingCtx.strokeStyle = currentStroke.color;
    drawingCtx.lineWidth = currentStroke.width;
    drawingCtx.beginPath();
    
    if (currentStroke.points.length >= 2) {
        const prev = currentStroke.points[currentStroke.points.length - 2];
        const curr = currentStroke.points[currentStroke.points.length - 1];
        drawingCtx.moveTo(prev.x * drawingCanvas.width, prev.y * drawingCanvas.height);
        drawingCtx.lineTo(curr.x * drawingCanvas.width, curr.y * drawingCanvas.height);
        drawingCtx.stroke();
    }
};

const stopDrawing = () => {
    if (!drawingMode || !isDrawing || !currentStroke) return;
    isDrawing = false;
    
    if (currentStroke.points.length > 1) {
        if (!drawingPaths.has(currentPage)) {
            drawingPaths.set(currentPage, []);
        }
        drawingPaths.get(currentPage).push(currentStroke);
    }
    currentStroke = null;
};

const startErasing = (x, y) => {
    if (!drawingMode || !drawingCtx) return;

    if (isDrawing) {
        stopDrawing();
    }

    isErasing = true;
    drawingCtx.globalCompositeOperation = 'destination-out';
    currentStroke = {
        type: 'erase',
        points: [{ x, y }],
        width: 50
    };
    updateModeIndicator('erasing');
};

const addErasePoint = (x, y) => {
    if (!drawingMode || !isErasing || !currentStroke || !drawingCtx || !drawingCanvas) return;
    
    currentStroke.points.push({ x, y });
    
    drawingCtx.lineWidth = currentStroke.width;
    drawingCtx.beginPath();
    
    if (currentStroke.points.length >= 2) {
        const prev = currentStroke.points[currentStroke.points.length - 2];
        const curr = currentStroke.points[currentStroke.points.length - 1];
        drawingCtx.moveTo(prev.x * drawingCanvas.width, prev.y * drawingCanvas.height);
        drawingCtx.lineTo(curr.x * drawingCanvas.width, curr.y * drawingCanvas.height);
        drawingCtx.stroke();
    }
};

const stopErasing = () => {
    if (!drawingMode || !isErasing || !currentStroke) return;
    isErasing = false;
    
    if (currentStroke.points.length > 1) {
        if (!drawingPaths.has(currentPage)) {
            drawingPaths.set(currentPage, []);
        }
        drawingPaths.get(currentPage).push(currentStroke);
    }
    currentStroke = null;
    if (drawingCtx) {
        drawingCtx.globalCompositeOperation = 'source-over';
    }
};

const clearPageDrawings = () => {
    drawingPaths.delete(currentPage);
    if (drawingCtx && drawingCanvas) {
        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    }
};

// ============================================
// FUNCIONES DE RENDERIZADO PDF
// ============================================
const calculateAndSetBaseScale = async () => {
    if (!pdfDoc || !pdfContainer) return;
    
    try {
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale: 1.0 });
        const containerWidth = pdfContainer.clientWidth;
        const scaleX = containerWidth / viewport.width;
        baseScale = scaleX;
    } catch (err) {
        console.error("Error al calcular la escala base:", err);
        baseScale = 1.0;
    }
};

const renderPage = async (num, shouldScroll = false, scrollX = 0, scrollY = 0) => {
    if (!pdfDoc || num < 1 || num > pdfDoc.numPages || !canvas || !ctx) return;

    try {
        const page = await pdfDoc.getPage(num);
        const totalScale = baseScale * gestureZoom;
        const viewport = page.getViewport({ scale: totalScale });

        canvas.height = viewport.height;
        canvas.width = viewport.width;
        
        if (drawingCanvas) {
            drawingCanvas.width = canvas.width;
            drawingCanvas.height = canvas.height;
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        await page.render({ canvasContext: ctx, viewport: viewport }).promise;

        currentPage = num;
        
        if (pageInfoDisplay) {
            pageInfoDisplay.textContent = `Página ${currentPage} de ${pdfDoc.numPages}`;
        }
        updateZoomDisplay();

        // CORREGIDO: Verificar que los botones existen antes de modificarlos
        if (prevButton) {
            prevButton.disabled = currentPage <= 1;
        }
        if (nextButton) {
            nextButton.disabled = currentPage >= pdfDoc.numPages;
        }

        initializeDrawingCanvas();
        redrawCanvas();

        if (shouldScroll && pdfContainer) {
            pdfContainer.scrollTo({ left: scrollX, top: scrollY, behavior: 'smooth' });
        }
        
        if (isPointerActive) updatePointer(pointerX, pointerY, true);

    } catch (err) {
        console.error("Error al renderizar la página:", err);
        if (errorMessage) {
            errorMessage.textContent = "Error al renderizar la página.";
            errorMessage.style.display = 'block';
        }
    }
};

const loadPdf = async () => {
    try {
        const loadingTask = pdfjsLib.getDocument(url);
        pdfDoc = await loadingTask.promise;
        
        await calculateAndSetBaseScale();
        await renderPage(currentPage);
        
        if (errorMessage) {
            errorMessage.style.display = 'none';
        }
    } catch (err) {
        console.error("Error al cargar el documento:", err);
        if (errorMessage) {
            errorMessage.style.display = 'block';
        }
    }
};

// ============================================
// FUNCIONES DE NAVEGACIÓN
// ============================================
const goToPrevPage = () => {
    if (currentPage > 1) renderPage(currentPage - 1);
};

const goToNextPage = () => {
    if (pdfDoc && currentPage < pdfDoc.numPages) renderPage(currentPage + 1);
};

// ============================================
// FUNCIONES DE ZOOM
// ============================================
const zoomIn = () => setGestureZoom(gestureZoom + 0.2);
const zoomOut = () => setGestureZoom(gestureZoom - 0.2);
const resetZoom = () => setGestureZoom(1.0);

const setGestureZoom = async (zoomLevel, centerX = pointerX, centerY = pointerY) => {
    if (!pdfContainer || !canvas) return;
    
    const oldGestureZoom = gestureZoom;
    gestureZoom = Math.max(0.3, Math.min(4.0, zoomLevel));
    updateModeIndicator('zoom');

    if (Math.abs(oldGestureZoom - gestureZoom) < 0.01) return;

    const oldScrollLeft = pdfContainer.scrollLeft;
    const oldScrollTop = pdfContainer.scrollTop;
    const oldCanvasWidth = canvas.width;
    const oldCanvasHeight = canvas.height;

    await renderPage(currentPage);

    const deltaWidth = canvas.width - oldCanvasWidth;
    const deltaHeight = canvas.height - oldCanvasHeight;

    const newScrollLeft = oldScrollLeft + (deltaWidth * centerX);
    const newScrollTop = oldScrollTop + (deltaHeight * centerY);
    
    pdfContainer.scrollTo({
        left: newScrollLeft,
        top: newScrollTop,
        behavior: 'auto'
    });

    if (lastCommandDisplay) {
        lastCommandDisplay.textContent = `Zoom: ${Math.round(gestureZoom * 100)}% en punto (${(centerX * 100).toFixed(1)}%, ${(centerY * 100).toFixed(1)}%)`;
    }
};

// ============================================
// EVENT LISTENERS DE BOTONES
// ============================================
if (prevButton) prevButton.addEventListener("click", goToPrevPage);
if (nextButton) nextButton.addEventListener("click", goToNextPage);
if (zoomInButton) zoomInButton.addEventListener("click", zoomIn);
if (zoomOutButton) zoomOutButton.addEventListener("click", zoomOut);
if (resetZoomButton) resetZoomButton.addEventListener("click", resetZoom);
if (toggleDrawingButton) toggleDrawingButton.addEventListener("click", () => updateDrawingModeIndicator(!drawingMode));
if (clearDrawingsButton) clearDrawingsButton.addEventListener("click", clearPageDrawings);

// ============================================
// EVENT LISTENERS DE TECLADO
// ============================================
document.addEventListener("keydown", (event) => {
    switch(event.key) {
        case "ArrowLeft":
            event.preventDefault();
            goToPrevPage();
            break;
        case "ArrowRight":
            event.preventDefault();
            goToNextPage();
            break;
        case "+":
        case "=":
            event.preventDefault();
            zoomIn();
            break;
        case "-":
            event.preventDefault();
            zoomOut();
            break;
        case "0":
            event.preventDefault();
            resetZoom();
            break;
        case "d":
        case "D":
            event.preventDefault();
            updateDrawingModeIndicator(!drawingMode);
            break;
        case "c":
        case "C":
            if (drawingMode) {
                event.preventDefault();
                clearPageDrawings();
            }
            break;
        case "Escape":
            updatePointer(0.5, 0.5, false);
            break;
    }
});

// ============================================
// SISTEMA DE COOLDOWNS
// ============================================
const clientCooldowns = {
    next: { last: 0, duration: 2000 },
    prev: { last: 0, duration: 2000 },
    puntero: { last: 0, duration: 50 },
    zoom: { last: 0, duration: 100 },
    reset: { last: 0, duration: 1000 },
    toggle_draw_mode: { last: 0, duration: 1500 },
    start_draw: { last: 0, duration: 50 },
    drawing: { last: 0, duration: 20 },
    stop_draw: { last: 0, duration: 50 },
    start_erase: { last: 0, duration: 50 },
    erasing: { last: 0, duration: 20 },
    stop_erase: { last: 0, duration: 50 }
};

const canProcessCommand = (commandType) => {
    const now = Date.now();
    const cooldown = clientCooldowns[commandType];
    if (!cooldown) return true;
    
    const timePassed = now - cooldown.last;
    if (timePassed >= cooldown.duration) {
        cooldown.last = now;
        return true;
    }
    return false;
};

const getRemainingCooldown = (commandType) => {
    const now = Date.now();
    const cooldown = clientCooldowns[commandType];
    if (!cooldown) return 0;
    
    const timePassed = now - cooldown.last;
    return Math.max(0, cooldown.duration - timePassed);
};

// ============================================
// PROCESAMIENTO DE COMANDOS
// ============================================
const processCommand = (comando) => {
    const currentTime = Date.now();
    
    if (comando === "next") {
        if (canProcessCommand('next')) {
            goToNextPage();
            if (lastCommandDisplay) lastCommandDisplay.textContent = "✓ Página siguiente";
            updateModeIndicator('navigation');
        } else {
            const remaining = getRemainingCooldown('next');
            if (lastCommandDisplay) lastCommandDisplay.textContent = `⏳ Cooldown navegación: ${(remaining/1000).toFixed(1)}s`;
        }
    } 
    else if (comando === "prev") {
        if (canProcessCommand('prev')) {
            goToPrevPage();
            if (lastCommandDisplay) lastCommandDisplay.textContent = "✓ Página anterior";
            updateModeIndicator('navigation');
        } else {
            const remaining = getRemainingCooldown('prev');
            if (lastCommandDisplay) lastCommandDisplay.textContent = `⏳ Cooldown navegación: ${(remaining/1000).toFixed(1)}s`;
        }
    } 
    else if (comando === "toggle_draw_mode") {
        if (canProcessCommand('toggle_draw_mode')) {
            updateDrawingModeIndicator(!drawingMode);
            if (lastCommandDisplay) lastCommandDisplay.textContent = `✓ Modo dibujo: ${drawingMode ? 'ACTIVADO' : 'DESACTIVADO'}`;
        } else {
            const remaining = getRemainingCooldown('toggle_draw_mode');
            if (lastCommandDisplay) lastCommandDisplay.textContent = `⏳ Cooldown modo dibujo: ${(remaining/1000).toFixed(1)}s`;
        }
    }
    else if (comando.startsWith("puntero_")) {
        if (canProcessCommand('puntero')) {
            const parts = comando.split("_");
            if (parts.length >= 3) {
                const x = parseFloat(parts[1]);
                const y = parseFloat(parts[2]);
                if (!isNaN(x) && !isNaN(y)) {
                    updatePointer(x, y, true, 'pointer');
                    updateModeIndicator('pointer');
                }
            }
        }
    }
    else if (comando.startsWith("start_draw_")) {
        if (canProcessCommand('start_draw')) {
            const parts = comando.split("_");
            if (parts.length >= 4) {
                const x = parseFloat(parts[2]);
                const y = parseFloat(parts[3]);
                if (!isNaN(x) && !isNaN(y)) {
                    startDrawing(x, y);
                    updatePointer(x, y, true, 'drawing');
                }
            }
        }
    } 
    else if (comando.startsWith("drawing_")) {
        if (canProcessCommand('drawing')) {
            const parts = comando.split("_");
            if (parts.length >= 3) {
                const x = parseFloat(parts[1]);
                const y = parseFloat(parts[2]);
                if (!isNaN(x) && !isNaN(y)) {
                    addDrawingPoint(x, y);
                    updatePointer(x, y, true, 'drawing');
                }
            }
        }
    } 
    else if (comando.startsWith("stop_draw_")) {
        if (canProcessCommand('stop_draw')) {
            const parts = comando.split("_");
            if (parts.length >= 4) {
                const x = parseFloat(parts[2]);
                const y = parseFloat(parts[3]);
                if (!isNaN(x) && !isNaN(y)) {
                    stopDrawing();
                    updatePointer(x, y, true, 'pointer');
                    updateModeIndicator('pointer');
                }
            }
        }
    }
    else if (comando.startsWith("start_erase_")) {
        if (canProcessCommand('start_erase')) {
            const parts = comando.split("_");
            if (parts.length >= 4) {
                const x = parseFloat(parts[2]);
                const y = parseFloat(parts[3]);
                if (!isNaN(x) && !isNaN(y)) {
                    startErasing(x, y);
                    updatePointer(x, y, true, 'erasing');
                }
            }
        }
    } 
    else if (comando.startsWith("erasing_")) {
        if (canProcessCommand('erasing')) {
            const parts = comando.split("_");
            if (parts.length >= 3) {
                const x = parseFloat(parts[1]);
                const y = parseFloat(parts[2]);
                if (!isNaN(x) && !isNaN(y)) {
                    addErasePoint(x, y);
                    updatePointer(x, y, true, 'erasing');
                }
            }
        }
    } 
    else if (comando.startsWith("stop_erase_")) {
        if (canProcessCommand('stop_erase')) {
            const parts = comando.split("_");
            if (parts.length >= 4) {
                const x = parseFloat(parts[2]);
                const y = parseFloat(parts[3]);
                if (!isNaN(x) && !isNaN(y)) {
                    stopErasing();
                    updatePointer(x, y, true, 'pointer');
                    updateModeIndicator('pointer');
                }
            }
        }
    }
    else if (comando === "clear_drawings") {
        if (canProcessCommand('clear_drawings')) {
            clearPageDrawings();
            if (lastCommandDisplay) lastCommandDisplay.textContent = "✓ Dibujos limpiados";
            updateModeIndicator('pointer');
        }
    }
    else if (comando.startsWith("zoom_")) {
        if (canProcessCommand('zoom')) {
            const parts = comando.split("_");
            if (parts.length >= 2) {
                const zoomValue = parseFloat(parts[1]);
                const centerX = parts.length >= 3 ? parseFloat(parts[2]) : pointerX;
                const centerY = parts.length >= 4 ? parseFloat(parts[3]) : pointerY;
                if (!isNaN(zoomValue)) {
                    setGestureZoom(zoomValue, centerX, centerY);
                    if (isPointerActive) updatePointer(centerX, centerY, false);
                }
            }
        } else {
            const remaining = getRemainingCooldown('zoom');
            if (remaining > 50 && lastCommandDisplay) {
                lastCommandDisplay.textContent = `⏳ Cooldown zoom: ${remaining}ms`;
            }
        }
    }
    else if (comando.startsWith("start_move_")) {
        const parts = comando.split("_");
        isMoving = true;
        moveStartX = parseFloat(parts[2]);
        moveStartY = parseFloat(parts[3]);
        moveOffsetX = 0;
        moveOffsetY = 0;
        updateModeIndicator('moving');
        if (lastCommandDisplay) lastCommandDisplay.textContent = "👌 Agarrando dibujo...";
    }
    else if (comando.startsWith("moving_")) {
        if (!isMoving) return;
        const parts = comando.split("_");
        const currentX = parseFloat(parts[1]);
        const currentY = parseFloat(parts[2]);
        
        moveOffsetX = currentX - moveStartX;
        moveOffsetY = currentY - moveStartY;
        
        redrawCanvas();
        if (lastCommandDisplay) lastCommandDisplay.textContent = `Moviendo: dx=${(moveOffsetX*100).toFixed(1)}%, dy=${(moveOffsetY*100).toFixed(1)}%`;
    }
    else if (comando === "stop_move") {
        if (!isMoving) return;
        
        const pageDrawings = drawingPaths.get(currentPage);
        if (pageDrawings) {
            pageDrawings.forEach(path => {
                path.points.forEach(point => {
                    point.x += moveOffsetX;
                    point.y += moveOffsetY;
                });
            });
        }
        
        isMoving = false;
        moveOffsetX = 0;
        moveOffsetY = 0;
        
        redrawCanvas();
        updateModeIndicator('pointer');
        if (lastCommandDisplay) lastCommandDisplay.textContent = "Dibujo movido";
    }