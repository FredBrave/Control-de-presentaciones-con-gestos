import cv2
import mediapipe as mp
from django.core.management.base import BaseCommand
import requests
import time
import math

# URL de tu función en Django
URL_ACTUALIZAR_COMANDO = "http://127.0.0.1:8000/presentaciones/actualizar_comando/"

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

class Command(BaseCommand):
    help = "Detector de gestos con sistema de dibujo mejorado"

    def __init__(self):
        super().__init__()
        
        # ==========================================
        # CONFIGURACIÓN DE COOLDOWNS OPTIMIZADA (MAX 0.5s)
        # ==========================================
        self.COOLDOWNS = {
            'next': 0.5,                # Navegación
            'prev': 0.5,                # Navegación
            'puntero': 0.02,            # Puntero fluido
            'zoom': 0.05,               # Zoom fluido
            'reset': 0.3,               # Reset
            'toggle_draw_mode': 0.5,    # Toggle modo dibujo
            'start_draw': 0.02,         # Inicio de trazo
            'drawing': 0.01,            # Mientras dibuja (muy fluido)
            'stop_draw': 0.02,          # Fin de trazo
            'start_erase': 0.02,        # Inicio de borrado
            'erasing': 0.01,            # Mientras borra (muy fluido)
            'stop_erase': 0.02,         # Fin de borrado
            'clear_drawings': 1.0,
            'start_move': 0.1,        
            'moving': 0.02,            
            'stop_move': 0.1,
        }
        
        self.ultimos_tiempos = {key: 0 for key in self.COOLDOWNS.keys()}
        
        # ==========================================
        # ESTADO DEL SISTEMA DE DIBUJO
        # ==========================================
        self.modo_dibujo_activo = False
        self.esta_dibujando = False
        self.esta_borrando = False
        self.esta_moviendo = False
        
        # ==========================================
        # CONFIGURACIÓN DE SENSIBILIDADES
        # ==========================================
        self.TOLERANCIA_PULGAR_PISTOLA = 0.05
        self.TOLERANCIA_DIRECCION_PISTOLA = 0.015
        self.SENSIBILIDAD_ZOOM = 0.08
        self.FRAMES_PREPARACION_ZOOM = 2
        self.TOLERANCIA_PUNO = 0.035
        self.TOLERANCIA_PAZ = 0.04      # Para gesto de paz (V)
        self.TOLERANCIA_CUERNOS = 0.04  # Para gesto rock (cuernos)

    def puede_enviar_comando(self, tipo_comando):
        """Verifica si puede enviar un comando basado en su cooldown individual"""
        tiempo_actual = time.time()
        tiempo_ultimo = self.ultimos_tiempos.get(tipo_comando, 0)
        cooldown = self.COOLDOWNS.get(tipo_comando, 0.1)
        
        puede_enviar = (tiempo_actual - tiempo_ultimo) >= cooldown
        
        if puede_enviar:
            self.ultimos_tiempos[tipo_comando] = tiempo_actual
        
        return puede_enviar

    def obtener_tiempo_restante(self, tipo_comando):
        """Obtiene el tiempo restante de cooldown para un comando"""
        tiempo_actual = time.time()
        tiempo_ultimo = self.ultimos_tiempos.get(tipo_comando, 0)
        cooldown = self.COOLDOWNS.get(tipo_comando, 0.1)
        
        tiempo_restante = cooldown - (tiempo_actual - tiempo_ultimo)
        return max(0, tiempo_restante)

    def enviar_comando(self, comando, tipo_comando):
        """Envía comando solo si el cooldown lo permite"""
        if self.puede_enviar_comando(tipo_comando):
            try:
                requests.post(URL_ACTUALIZAR_COMANDO, json={"comando": comando})
                self.stdout.write(f"✓ Comando enviado: {comando} (tipo: {tipo_comando})")
                return True
            except Exception as e:
                self.stderr.write(f"✗ Error enviando comando: {e}")
                return False
        else:
            tiempo_restante = self.obtener_tiempo_restante(tipo_comando)
            if self.COOLDOWNS.get(tipo_comando, 0) > 0.05:
                self.stdout.write(f"⏳ Cooldown {tipo_comando}: {tiempo_restante:.2f}s restantes")
            return False

    def calcular_distancia(self, punto1, punto2, ancho_frame, alto_frame):
        """Calcula la distancia euclidiana entre dos puntos normalizados"""
        x1, y1 = punto1.x * ancho_frame, punto1.y * alto_frame
        x2, y2 = punto2.x * ancho_frame, punto2.y * alto_frame
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def detectar_gesto_paz(self, hand_landmarks):
        """Detecta gesto de PAZ - versión simple mejorada."""
        landmarks = hand_landmarks.landmark
        
        # Índice y medio extendidos (ligeramente más estricto)
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.03
        medio_extendido = landmarks[12].y < landmarks[10].y - 0.03
        
        # Bien separados formando V
        separacion_dedos = abs(landmarks[8].x - landmarks[12].x) > self.TOLERANCIA_PAZ * 1.3
        
        # Otros dedos doblados (más claro)
        anular_doblado = landmarks[16].y > landmarks[14].y + 0.01
        menique_doblado = landmarks[20].y > landmarks[18].y + 0.01
        
        # Pulgar no muy extendido
        pulgar_controlado = abs(landmarks[4].x - landmarks[3].x) < self.TOLERANCIA_PAZ * 1.5
        
        return (indice_extendido and medio_extendido and separacion_dedos and 
                anular_doblado and menique_doblado and pulgar_controlado)

    def detectar_gesto_cuernos(self, hand_landmarks):
        """Detecta gesto de ROCK/CUERNOS (índice y meñique extendidos) para DIBUJAR
        Gesto muy distintivo y fácil de mantener"""
        landmarks = hand_landmarks.landmark
        
        # Índice extendido
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.025
        
        # Meñique extendido  
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.025
        
        # Medio y anular doblados
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        
        # Pulgar puede estar extendido o no (más flexible)
        
        return (indice_extendido and menique_extendido and 
                medio_doblado and anular_doblado)

    def detectar_mano_abierta_completa(self, hand_landmarks):
        landmarks = hand_landmarks.landmark
        
        # Tolerancias más permisivas para mejor detección
        # Pulgar extendido (más sensible)
        pulgar_extendido = abs(landmarks[4].x - landmarks[3].x) > 0.025  # Reducido de 0.04 a 0.025
        
        # Otros dedos extendidos (más sensibles)
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.01   # Reducido de 0.02 a 0.01
        medio_extendido = landmarks[12].y < landmarks[10].y - 0.01  # Reducido de 0.02 a 0.01
        anular_extendido = landmarks[16].y < landmarks[14].y - 0.01 # Reducido de 0.02 a 0.01
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.01 # Reducido de 0.02 a 0.01
        
        # Contar dedos extendidos
        dedos_extendidos = sum([
            pulgar_extendido, indice_extendido, medio_extendido, 
            anular_extendido, menique_extendido
        ])
        
        # Más permisivo: acepta 4 o 5 dedos extendidos (en lugar de solo 5)
        return dedos_extendidos >= 4

    def detectar_gesto_pistola(self, hand_landmarks):
        """Detecta gesto de pistola con tolerancias configurables"""
        landmarks = hand_landmarks.landmark
        
        pulgar_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP]
        pulgar_mcp = landmarks[mp_hands.HandLandmark.THUMB_MCP]
        indice_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        indice_mcp = landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP]
        medio_tip = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        medio_pip = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_PIP]
        anular_tip = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP]
        anular_pip = landmarks[mp_hands.HandLandmark.RING_FINGER_PIP]
        menique_tip = landmarks[mp_hands.HandLandmark.PINKY_TIP]
        menique_pip = landmarks[mp_hands.HandLandmark.PINKY_PIP]
        
        indice_extendido = indice_tip.y < indice_mcp.y
        pulgar_extendido = abs(pulgar_tip.x - pulgar_mcp.x) > self.TOLERANCIA_PULGAR_PISTOLA
        medio_doblado = medio_tip.y > medio_pip.y
        anular_doblado = anular_tip.y > anular_pip.y
        menique_doblado = menique_tip.y > menique_pip.y
        
        if indice_extendido and pulgar_extendido and medio_doblado and anular_doblado and menique_doblado:
            if indice_tip.x > indice_mcp.x + self.TOLERANCIA_DIRECCION_PISTOLA:
                return 'pistola_derecha'
            elif indice_tip.x < indice_mcp.x - self.TOLERANCIA_DIRECCION_PISTOLA:
                return 'pistola_izquierda'
        
        return None

    def detectar_puno(self, hand_landmarks):
        """Detecta si la mano está cerrada en puño"""
        landmarks = hand_landmarks.landmark
        
        indice_doblado = landmarks[8].y > landmarks[6].y
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        menique_doblado = landmarks[20].y > landmarks[18].y
        pulgar_doblado = abs(landmarks[4].x - landmarks[3].x) < self.TOLERANCIA_PUNO
        
        return indice_doblado and medio_doblado and anular_doblado and menique_doblado and pulgar_doblado

    def obtener_posicion_puntero(self, hand_landmarks):
        """Obtiene la posición del centro de la mano para el puntero"""
        # Usar el centro de la palma (más estable que MCP del medio)
        centro_palma = hand_landmarks.landmark[0]  # WRIST landmark como referencia
        dedo_medio_mcp = hand_landmarks.landmark[9]  # MIDDLE_FINGER_MCP
        
        # Promedio entre muñeca y MCP del medio para mayor estabilidad
        centro_x = (centro_palma.x + dedo_medio_mcp.x) / 2
        centro_y = (centro_palma.y + dedo_medio_mcp.y) / 2
        
        return centro_x, centro_y

    def detectar_manos_abiertas(self, hands_results):
        """Detecta si hay al menos una mano abierta (3+ dedos)"""
        if not hands_results.multi_hand_landmarks:
            return 0, []
        
        manos_abiertas = 0
        dedos_por_mano = []
        
        for hand_landmarks in hands_results.multi_hand_landmarks:
            dedos = self.contar_dedos_extendidos(hand_landmarks)
            dedos_por_mano.append(dedos)
            if dedos >= 3:
                manos_abiertas += 1
        
        return manos_abiertas, dedos_por_mano

    def contar_dedos_extendidos(self, hand_landmarks):
        """Cuenta cuántos dedos están extendidos"""
        landmarks = hand_landmarks.landmark
        dedos = 0
        
        # Pulgar
        if abs(landmarks[4].x - landmarks[3].x) > 0.04:
            dedos += 1
        
        # Otros dedos
        finger_tips = [8, 12, 16, 20]
        finger_mcps = [5, 9, 13, 17]
        
        for i, tip in enumerate(finger_tips):
            if landmarks[tip].y < landmarks[finger_mcps[i]].y:
                dedos += 1
        
        return dedos
    
    def detectar_menique_solo(self, hand_landmarks):
        """Detecta solo el meñique levantado."""
        landmarks = hand_landmarks.landmark
        
        # Solo meñique extendido
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.04
        
        # Todos los demás doblados
        indice_doblado = landmarks[8].y > landmarks[6].y
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        pulgar_doblado = landmarks[4].y > landmarks[3].y
        
        # El meñique debe estar claramente por encima de todos
        menique_mas_alto = (landmarks[20].y < landmarks[8].y and
                        landmarks[20].y < landmarks[12].y and
                        landmarks[20].y < landmarks[16].y)
        
        return (menique_extendido and indice_doblado and medio_doblado and 
                anular_doblado and pulgar_doblado and menique_mas_alto)
        
    def mostrar_estado_dibujo(self, frame, y_offset=60):
        """Muestra el estado del modo dibujo con nuevos gestos"""
        if self.modo_dibujo_activo:
            color_fondo = (0, 100, 255)  # Naranja para modo activo
            texto_modo = "MODO DIBUJO: ON"
            
            # Mostrar estado específico
            if self.esta_dibujando:
                texto_estado = "DIBUJANDO (Cuernos)"
                color_estado = (0, 255, 0)
            elif self.esta_borrando:
                texto_estado = "BORRANDO (Mano Abierta)"
                color_estado = (0, 0, 255)
            else:
                texto_estado = "PUNTERO (Puno)"
                color_estado = (255, 255, 0)
            
            cv2.putText(frame, texto_modo, (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_fondo, 2)
            cv2.putText(frame, texto_estado, (10, y_offset + 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_estado, 2)
            
            return 50
        return 0
    
    def detectar_gesto_pinza(self, hand_landmarks, ancho_frame, alto_frame):
        """Detecta el gesto de pinza (índice y pulgar juntos)."""
        landmarks = hand_landmarks.landmark
        
        # Puntos de la punta del pulgar (4) e índice (8)
        pulgar_tip = landmarks[4]
        indice_tip = landmarks[8]
        
        # Calcular la distancia euclidiana entre ellos
        distancia = self.calcular_distancia(pulgar_tip, indice_tip, ancho_frame, alto_frame)
        
        # Si la distancia es menor a un umbral (ej. 30 píxeles), el gesto está activo
        # Este umbral puede necesitar ajuste según la resolución de tu cámara
        return distancia < 30

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando detector con gestos mejorados...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.stderr.write("Error: No se puede abrir la cámara.")
            return

        # Variables para el zoom
        distancia_referencia = None
        zoom_activo = False
        ultimo_zoom = 1.0
        contador_zoom = 0
        
        # Variables para el puntero
        punto_zoom_x = 0.5
        punto_zoom_y = 0.5
        puntero_activo = False

        with mp_hands.Hands(
            min_detection_confidence=0.7,  # Aumentar confianza para mejor detección
            min_tracking_confidence=0.5,
            max_num_hands=2
        ) as hands:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    self.stderr.write("Error: Fallo al recibir el 'frame'. Saliendo...")
                    break

                frame = cv2.flip(frame, 1)
                alto_frame, ancho_frame, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb)

                if results.multi_hand_landmarks:
                    num_manos = len(results.multi_hand_landmarks)
                    manos_abiertas, dedos_por_mano = self.detectar_manos_abiertas(results)
                    
                    # MODO ZOOM: 2 manos detectadas y al menos una abierta
                    if num_manos == 2 and manos_abiertas >= 1 and not self.modo_dibujo_activo:
                        puntero_activo = False
                        contador_zoom += 1
                        
                        if contador_zoom >= self.FRAMES_PREPARACION_ZOOM:
                            zoom_activo = True
                            
                            pulgar1 = results.multi_hand_landmarks[0].landmark[mp_hands.HandLandmark.THUMB_TIP]
                            pulgar2 = results.multi_hand_landmarks[1].landmark[mp_hands.HandLandmark.THUMB_TIP]
                            
                            distancia_actual = self.calcular_distancia(pulgar1, pulgar2, ancho_frame, alto_frame)
                            
                            if distancia_referencia is None:
                                distancia_referencia = distancia_actual
                                ultimo_zoom = 1.0
                            
                            factor_zoom = distancia_actual / distancia_referencia
                            factor_zoom = max(0.3, min(4.0, factor_zoom))
                            
                            if abs(factor_zoom - ultimo_zoom) > self.SENSIBILIDAD_ZOOM:
                                comando_zoom = f"zoom_{factor_zoom:.1f}_{punto_zoom_x:.2f}_{punto_zoom_y:.2f}"
                                if self.enviar_comando(comando_zoom, 'zoom'):
                                    ultimo_zoom = factor_zoom
                            
                            cv2.putText(frame, f"ZOOM: {factor_zoom:.1f}x", (10, 30),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                            
                            pulgar1_px = (int(pulgar1.x * ancho_frame), int(pulgar1.y * alto_frame))
                            pulgar2_px = (int(pulgar2.x * ancho_frame), int(pulgar2.y * alto_frame))
                            cv2.line(frame, pulgar1_px, pulgar2_px, (255, 0, 0), 5)
                            cv2.circle(frame, pulgar1_px, 12, (0, 255, 0), -1)
                            cv2.circle(frame, pulgar2_px, 12, (0, 255, 0), -1)
                    
                    # MODO UNA MANO
                    elif num_manos == 1:
                        contador_zoom = 0
                        hand_landmarks = results.multi_hand_landmarks[0]
                        
                        if zoom_activo:
                            zoom_activo = False
                            distancia_referencia = None
                            self.enviar_comando("zoom_1.0_0.5_0.5", 'reset')
                            ultimo_zoom = 1.0
                        
                        # DETECTAR TOGGLE MODO DIBUJO (Gesto PAZ ✌️)
                        if self.detectar_gesto_paz(hand_landmarks):
                            if self.enviar_comando("toggle_draw_mode", 'toggle_draw_mode'):
                                self.modo_dibujo_activo = not self.modo_dibujo_activo
                                self.esta_dibujando = False
                                self.esta_borrando = False
                                cv2.putText(frame, f"MODO DIBUJO: {'ACTIVADO ✌️' if self.modo_dibujo_activo else 'DESACTIVADO'}", 
                                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
                        
                        # SI MODO DIBUJO ACTIVO
                        elif self.modo_dibujo_activo:
                            # Siempre actualizar posición del puntero
                            punto_zoom_x, punto_zoom_y = self.obtener_posicion_puntero(hand_landmarks)
                            comando_puntero = f"puntero_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                            self.enviar_comando(comando_puntero, 'puntero')
                            
                            # !! NUEVO BLOQUE: Detectar gesto de limpiar pantalla (PULGAR ARRIBA 👍)
                            if self.detectar_menique_solo(hand_landmarks):
                                if self.enviar_comando("clear_drawings", 'clear_drawings'):
                                    cv2.putText(frame, "LIMPIANDO DIBUJOS 👍", (10, 30),
                                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
                                    # Detener cualquier acción de dibujo/borrado activa
                                    self.esta_dibujando = False
                                    self.esta_borrando = False

                            elif self.detectar_gesto_pinza(hand_landmarks, ancho_frame, alto_frame):
                                if not self.esta_moviendo:
                                    self.esta_moviendo = True
                                    # Detener otras acciones
                                    self.esta_dibujando = False
                                    self.esta_borrando = False
                                    comando_move = f"start_move_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_move, 'start_move')
                                else:
                                    comando_move = f"moving_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_move, 'moving')

                                # Visualización
                                puntero_px = (int(punto_zoom_x * ancho_frame), int(punto_zoom_y * alto_frame))
                                cv2.putText(frame, "MOVIENDO DIBUJO 👌", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 3)
                                cv2.circle(frame, puntero_px, 20, (255, 0, 255), 3)

                            # Detectar gesto de dibujo (CUERNOS 🤘)
                            if self.detectar_gesto_cuernos(hand_landmarks):
                                if self.esta_moviendo:
                                    self.esta_moviendo = False
                                    self.enviar_comando("stop_move", 'stop_move')
                                if not self.esta_dibujando:
                                    self.esta_dibujando = True
                                    self.esta_borrando = False
                                    comando_draw = f"start_draw_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_draw, 'start_draw')
                                else:
                                    comando_draw = f"drawing_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_draw, 'drawing')
                                
                                # Visualización
                                puntero_px = (int(punto_zoom_x * ancho_frame), int(punto_zoom_y * alto_frame))
                                cv2.circle(frame, puntero_px, 15, (0, 255, 0), -1)
                                cv2.putText(frame, "DIBUJANDO 🤘", (10, 30),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            
                            # Detectar gesto de borrado (MANO ABIERTA - más sensible)
                            elif self.detectar_mano_abierta_completa(hand_landmarks):
                                if self.esta_moviendo:
                                    self.esta_moviendo = False
                                    self.enviar_comando("stop_move", 'stop_move')
                                if not self.esta_borrando:
                                    self.esta_borrando = True
                                    self.esta_dibujando = False
                                    comando_erase = f"start_erase_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_erase, 'start_erase')
                                else:
                                    comando_erase = f"erasing_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_erase, 'erasing')
                                
                                # Visualización
                                puntero_px = (int(punto_zoom_x * ancho_frame), int(punto_zoom_y * alto_frame))
                                cv2.circle(frame, puntero_px, 25, (0, 0, 255), 4)
                                cv2.putText(frame, "BORRANDO (Mano Abierta)", (10, 30),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                            
                            # Solo puño (puntero normal en modo dibujo)
                            elif self.detectar_puno(hand_landmarks):
                                if self.esta_dibujando:
                                    self.esta_dibujando = False
                                    comando_stop = f"stop_draw_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_stop, 'stop_draw')
                                elif self.esta_borrando:
                                    self.esta_borrando = False
                                    comando_stop = f"stop_erase_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_stop, 'stop_erase')
                                
                                puntero_activo = True
                                puntero_px = (int(punto_zoom_x * ancho_frame), int(punto_zoom_y * alto_frame))
                                cv2.circle(frame, puntero_px, 25, (0, 255, 255), 3)
                                cv2.circle(frame, puntero_px, 5, (0, 0, 255), -1)
                                cv2.putText(frame, "PUNTERO ✊ (Modo Dibujo)", (10, 30),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                                
                            
                            else:
                                # Otro gesto - detener dibujo/borrado si estaba activo
                                if self.esta_dibujando:
                                    self.esta_dibujando = False
                                    comando_stop = f"stop_draw_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_stop, 'stop_draw')
                                elif self.esta_borrando:
                                    self.esta_borrando = False
                                    comando_stop = f"stop_erase_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                    self.enviar_comando(comando_stop, 'stop_erase')
                        
                        # MODO NORMAL (sin dibujo activo)
                        else:
                            # Detectar gesto de pistola
                            gesto_pistola = self.detectar_gesto_pistola(hand_landmarks)
                            
                            if gesto_pistola == 'pistola_derecha':
                                puntero_activo = False
                                if self.enviar_comando("next", 'next'):
                                    cv2.putText(frame, "SIGUIENTE >> 👉", (10, 30),
                                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                                else:
                                    tiempo_restante = self.obtener_tiempo_restante('next')
                                    cv2.putText(frame, f"Cooldown: {tiempo_restante:.2f}s", (10, 30),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                            
                            elif gesto_pistola == 'pistola_izquierda':
                                puntero_activo = False
                                if self.enviar_comando("prev", 'prev'):
                                    cv2.putText(frame, "👈 << ANTERIOR", (10, 30),
                                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                                else:
                                    tiempo_restante = self.obtener_tiempo_restante('prev')
                                    cv2.putText(frame, f"Cooldown: {tiempo_restante:.2f}s", (10, 30),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                            
                            # Detectar puño para mostrar puntero
                            elif self.detectar_puno(hand_landmarks):
                                puntero_activo = True
                                punto_zoom_x, punto_zoom_y = self.obtener_posicion_puntero(hand_landmarks)
                                
                                comando_puntero = f"puntero_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                self.enviar_comando(comando_puntero, 'puntero')
                                
                                puntero_px = (int(punto_zoom_x * ancho_frame), int(punto_zoom_y * alto_frame))
                                cv2.circle(frame, puntero_px, 25, (0, 255, 255), 3)
                                cv2.circle(frame, puntero_px, 5, (0, 0, 255), -1)
                                cv2.putText(frame, "PUNTERO ACTIVO ✊", (10, 30),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                            
                            else:
                                puntero_activo = False
                                cv2.putText(frame, "Esperando gesto...", (10, 30),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 128, 128), 2)
                    
                    else:
                        puntero_activo = False
                        contador_zoom = 0
                        if zoom_activo:
                            zoom_activo = False
                            distancia_referencia = None
                            self.enviar_comando("zoom_1.0_0.5_0.5", 'reset')
                            ultimo_zoom = 1.0

                    # Dibujar landmarks
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(
                            frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                            mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2),
                            mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2)
                        )

                else:
                    puntero_activo = False
                    contador_zoom = 0
                    if zoom_activo:
                        zoom_activo = False
                        distancia_referencia = None
                        self.enviar_comando("zoom_1.0_0.5_0.5", 'reset')
                        ultimo_zoom = 1.0
                    
                    # Si estaba dibujando o borrando, detener
                    if self.esta_dibujando:
                        self.esta_dibujando = False
                        self.enviar_comando("stop_draw_0.5_0.5", 'stop_draw')
                    elif self.esta_borrando:
                        self.esta_borrando = False
                        self.enviar_comando("stop_erase_0.5_0.5", 'stop_erase')

                # Mostrar estado del modo dibujo
                draw_offset = self.mostrar_estado_dibujo(frame, alto_frame - 200)
                
                # Mostrar cooldowns activos visualmente
                cooldown_offset = self.mostrar_cooldowns_activos(frame, alto_frame - 150 + draw_offset)

                # Estados y configuración
                estado_y = alto_frame - 100 + cooldown_offset + draw_offset
                if self.modo_dibujo_activo:
                    cv2.putText(frame, "MODO: DIBUJO", (10, estado_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 100, 255), 2)
                elif puntero_activo:
                    cv2.putText(frame, "MODO: PUNTERO", (10, estado_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                elif zoom_activo:
                    cv2.putText(frame, "MODO: ZOOM", (10, estado_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                else:
                    cv2.putText(frame, "MODO: NAVEGACION", (10, estado_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                # Mostrar configuración de gestos mejorados
                config_y = estado_y + 30
                cv2.putText(frame, "Gestos: PAZ=Toggle | CUERNOS=Dibujar | MANO ABIERTA=Borrar", 
                           (10, config_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

                cv2.imshow("Detector con Gestos Mejorados", frame)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC para salir
                    break

        cap.release()
        cv2.destroyAllWindows()
    
    def mostrar_cooldowns_activos(self, frame, y_offset=30):
        """Muestra visualmente los cooldowns activos en el frame"""
        tiempo_actual = time.time()
        cooldowns_activos = []
        
        for comando, ultimo_tiempo in self.ultimos_tiempos.items():
            cooldown_duracion = self.COOLDOWNS.get(comando, 0)
            tiempo_restante = cooldown_duracion - (tiempo_actual - ultimo_tiempo)
            
            if tiempo_restante > 0 and cooldown_duracion > 0.05:
                cooldowns_activos.append((comando, tiempo_restante))
        
        for i, (comando, tiempo_restante) in enumerate(cooldowns_activos):
            texto = f"{comando.upper()}: {tiempo_restante:.2f}s"
            color = (0, 165, 255)
            cv2.putText(frame, texto, (10, y_offset + i * 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return len(cooldowns_activos) * 25