import cv2
import mediapipe as mp
from django.core.management.base import BaseCommand
import requests
import time
import math

URL_ACTUALIZAR_COMANDO = "http://127.0.0.1:8000/comando-gesto/"

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

class Command(BaseCommand):
    help = "Detector de gestos con sistema de dibujo mejorado"

    def __init__(self):
        super().__init__()
        
        self.COOLDOWNS = {
            'next': 0.5,
            'prev': 0.5,
            'puntero': 0.02,
            'zoom': 0.05,
            'reset': 0.3,
            'toggle_draw_mode': 0.5,
            'start_draw': 0.02,
            'drawing': 0.01,
            'stop_draw': 0.02,
            'start_erase': 0.02,
            'erasing': 0.01,
            'stop_erase': 0.02,
            'clear_drawings': 1.0,
            'start_move': 0.1,        
            'moving': 0.02,            
            'stop_move': 0.1,
        }
        
        self.ultimos_tiempos = {key: 0 for key in self.COOLDOWNS.keys()}
        self.errores_consecutivos = 0
        
        self.modo_dibujo_activo = False
        self.esta_dibujando = False
        self.esta_borrando = False
        self.esta_moviendo = False
        
        self.TOLERANCIA_PULGAR_PISTOLA = 0.05
        self.TOLERANCIA_DIRECCION_PISTOLA = 0.015
        self.SENSIBILIDAD_ZOOM = 0.08
        self.FRAMES_PREPARACION_ZOOM = 2
        self.TOLERANCIA_PUNO = 0.035
        self.TOLERANCIA_PAZ = 0.04
        self.TOLERANCIA_CUERNOS = 0.04

        self.mostrar_feedback_toggle = False
        self.tiempo_inicio_feedback = 0
        self.duracion_feedback = 0.5

    def puede_enviar_comando(self, tipo_comando):
        tiempo_actual = time.time()
        tiempo_ultimo = self.ultimos_tiempos.get(tipo_comando, 0)
        cooldown = self.COOLDOWNS.get(tipo_comando, 0.1)
        puede_enviar = (tiempo_actual - tiempo_ultimo) >= cooldown
        return puede_enviar

    def obtener_tiempo_restante(self, tipo_comando):
        tiempo_actual = time.time()
        tiempo_ultimo = self.ultimos_tiempos.get(tipo_comando, 0)
        cooldown = self.COOLDOWNS.get(tipo_comando, 0.1)
        
        tiempo_restante = cooldown - (tiempo_actual - tiempo_ultimo)
        return max(0, tiempo_restante)

    def enviar_comando(self, comando, tipo_comando):
        if not self.puede_enviar_comando(tipo_comando):
            return False
        try:
            response = requests.post(
                URL_ACTUALIZAR_COMANDO, 
                json={"comando": comando},
                timeout=0.5)
            if response.status_code == 200:
                self.ultimos_tiempos[tipo_comando] = time.time() 

                self.errores_consecutivos = 0
                if tipo_comando in ['next', 'prev', 'toggle_draw_mode', 'clear_drawings']:
                    self.stdout.write(f"Comando enviado: {comando}")
                return True
            else:
                self.errores_consecutivos += 1
                if self.errores_consecutivos <= 3:
                    self.stderr.write(f"HTTP {response.status_code}")
                return False
        except requests.exceptions.Timeout:
            self.errores_consecutivos += 1
            if self.errores_consecutivos == 1:
                self.stderr.write(f"Timeouts detectados (normal)")
            return False

        except requests.exceptions.ConnectionError:
            self.errores_consecutivos += 1
            if self.errores_consecutivos <= 3:
                self.stderr.write(f"Error de conexión: {URL_ACTUALIZAR_COMANDO}")
            return False

        except Exception as e:
            self.errores_consecutivos += 1
            if self.errores_consecutivos <= 2:
                self.stderr.write(f" Error: {type(e).__name__}")
            return False

    def calcular_distancia(self, punto1, punto2, ancho_frame, alto_frame):
        x1, y1 = punto1.x * ancho_frame, punto1.y * alto_frame
        x2, y2 = punto2.x * ancho_frame, punto2.y * alto_frame
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def detectar_gesto_paz(self, hand_landmarks):
        landmarks = hand_landmarks.landmark
        
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.03
        medio_extendido = landmarks[12].y < landmarks[10].y - 0.03
        separacion_dedos = abs(landmarks[8].x - landmarks[12].x) > self.TOLERANCIA_PAZ * 1.3
        anular_doblado = landmarks[16].y > landmarks[14].y + 0.01
        menique_doblado = landmarks[20].y > landmarks[18].y + 0.01
        pulgar_controlado = abs(landmarks[4].x - landmarks[3].x) < self.TOLERANCIA_PAZ * 1.5
        
        return (indice_extendido and medio_extendido and separacion_dedos and 
                anular_doblado and menique_doblado and pulgar_controlado)

    def detectar_gesto_cuernos(self, hand_landmarks):
        landmarks = hand_landmarks.landmark
        
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.025
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.025
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        indice_mas_alto = landmarks[8].y < landmarks[12].y - 0.02
        menique_mas_alto = landmarks[20].y < landmarks[16].y - 0.02
        
        return (indice_extendido and menique_extendido and 
                medio_doblado and anular_doblado and 
                indice_mas_alto and menique_mas_alto)

    def detectar_mano_abierta_completa(self, hand_landmarks):
        landmarks = hand_landmarks.landmark
        
        pulgar_extendido = abs(landmarks[4].x - landmarks[3].x) > 0.025
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.01
        medio_extendido = landmarks[12].y < landmarks[10].y - 0.01
        anular_extendido = landmarks[16].y < landmarks[14].y - 0.01
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.01
        
        dedos_extendidos = sum([
            pulgar_extendido, indice_extendido, medio_extendido, 
            anular_extendido, menique_extendido
        ])
        
        return dedos_extendidos >= 4

    def detectar_gesto_pistola(self, hand_landmarks):
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
        landmarks = hand_landmarks.landmark
        
        indice_doblado = landmarks[8].y > landmarks[6].y
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        menique_doblado = landmarks[20].y > landmarks[18].y
        pulgar_doblado = abs(landmarks[4].x - landmarks[3].x) < self.TOLERANCIA_PUNO
        
        return (indice_doblado and medio_doblado and anular_doblado and 
                menique_doblado and pulgar_doblado)

    def obtener_posicion_puntero(self, hand_landmarks):
        centro_palma = hand_landmarks.landmark[0]
        dedo_medio_mcp = hand_landmarks.landmark[9]
        
        centro_x = (centro_palma.x + dedo_medio_mcp.x) / 2
        centro_y = (centro_palma.y + dedo_medio_mcp.y) / 2
        
        return centro_x, centro_y
    
    def obtener_posicion_indice(self, hand_landmarks):
        indice_tip = hand_landmarks.landmark[8]
        return indice_tip.x, indice_tip.y

    def detectar_manos_abiertas(self, hands_results):
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
        landmarks = hand_landmarks.landmark
        dedos = 0
        
        if abs(landmarks[4].x - landmarks[3].x) > 0.04:
            dedos += 1
        
        finger_tips = [8, 12, 16, 20]
        finger_mcps = [5, 9, 13, 17]
        
        for i, tip in enumerate(finger_tips):
            if landmarks[tip].y < landmarks[finger_mcps[i]].y:
                dedos += 1
        
        return dedos
    
    def detectar_pulgar_arriba(self, hand_landmarks):
        landmarks = hand_landmarks.landmark
        margen_seguridad = 0.05
        
        pulgar_arriba = landmarks[4].y < landmarks[0].y - 0.1
        
        pulgar_mas_alto = (landmarks[4].y < landmarks[8].y - margen_seguridad and 
                        landmarks[4].y < landmarks[12].y - margen_seguridad and
                        landmarks[4].y < landmarks[16].y - margen_seguridad and
                        landmarks[4].y < landmarks[20].y - margen_seguridad)

        indice_doblado = landmarks[8].y > landmarks[6].y + 0.02
        medio_doblado = landmarks[12].y > landmarks[10].y + 0.02
        anular_doblado = landmarks[16].y > landmarks[14].y + 0.02
        menique_doblado = landmarks[20].y > landmarks[18].y + 0.02

        orientacion_vertical = landmarks[0].y > landmarks[9].y
        
        return (pulgar_arriba and pulgar_mas_alto and orientacion_vertical and
                indice_doblado and medio_doblado and anular_doblado and menique_doblado)
    
    def detectar_gesto_pinza(self, hand_landmarks, ancho_frame, alto_frame):
        landmarks = hand_landmarks.landmark
        
        pulgar_tip = landmarks[4]
        indice_tip = landmarks[8]
        
        distancia = self.calcular_distancia(pulgar_tip, indice_tip, ancho_frame, alto_frame)
        return distancia < 30

    def mostrar_feedback_toggle_modo(self, frame, ancho_frame, alto_frame):
        tiempo_actual = time.time()
        
        if self.mostrar_feedback_toggle:
            tiempo_transcurrido = tiempo_actual - self.tiempo_inicio_feedback
            
            if tiempo_transcurrido < self.duracion_feedback:
                alpha = 1.0 - (tiempo_transcurrido / self.duracion_feedback)
                overlay = frame.copy()
                
                if self.modo_dibujo_activo:
                    cv2.rectangle(overlay, (0, 0), (ancho_frame, alto_frame), (0, 255, 0), 30)
                    texto = "MODO DIBUJO: ACTIVADO"
                    color = (0, 255, 0)
                else:
                    cv2.rectangle(overlay, (0, 0), (ancho_frame, alto_frame), (0, 0, 255), 30)
                    texto = "MODO DIBUJO: DESACTIVADO"
                    color = (0, 0, 255)
                
                tamaño_texto = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 1.8, 5)[0]
                x_centrado = (ancho_frame - tamaño_texto[0]) // 2
                y_centrado = alto_frame // 2
                
                cv2.putText(overlay, texto, (x_centrado, y_centrado),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.8, color, 5)
                
                cv2.addWeighted(overlay, alpha * 0.7, frame, 1 - (alpha * 0.7), 0, frame)
            else:
                self.mostrar_feedback_toggle = False

    def handle(self, *args, **kwargs):
        self.stdout.write("="*60)
        self.stdout.write("Iniciando detector de gestos...")
        self.stdout.write(f"URL: {URL_ACTUALIZAR_COMANDO}")
        self.stdout.write("="*60)
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.stderr.write("Error: No se puede abrir la cámara.")
            return

        distancia_referencia = None
        zoom_activo = False
        ultimo_zoom = 1.0
        contador_zoom = 0
        
        punto_zoom_x = 0.5
        punto_zoom_y = 0.5
        puntero_activo = False

        with mp_hands.Hands(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
            max_num_hands=2
        ) as hands:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                alto_frame, ancho_frame, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb)

                if results.multi_hand_landmarks:
                    num_manos = len(results.multi_hand_landmarks)
                    manos_abiertas, dedos_por_mano = self.detectar_manos_abiertas(results)
                    
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
                    
                    elif num_manos == 1:
                        contador_zoom = 0
                        hand_landmarks = results.multi_hand_landmarks[0]
                        
                        if zoom_activo:
                            zoom_activo = False
                            distancia_referencia = None
                            self.enviar_comando("zoom_1.0_0.5_0.5", 'reset')
                            ultimo_zoom = 1.0
                        
                        if self.modo_dibujo_activo:
                            if self.detectar_gesto_paz(hand_landmarks):
                                if self.enviar_comando("toggle_draw_mode", 'toggle_draw_mode'):
                                    self.modo_dibujo_activo = not self.modo_dibujo_activo
                                    self.esta_dibujando = False
                                    self.esta_borrando = False
                                    self.esta_moviendo = False
                                    
                                    self.mostrar_feedback_toggle = True
                                    self.tiempo_inicio_feedback = time.time()
                                    
                                    self.stdout.write(f"{'='*50}")
                                    self.stdout.write(f"MODO DIBUJO: {'ACTIVADO ' if self.modo_dibujo_activo else 'DESACTIVADO '}")
                                    self.stdout.write(f"{'='*50}")

                                else:
                                    tiempo_restante = self.obtener_tiempo_restante('toggle_draw_mode')
                                    cv2.putText(frame, f"SALIR EN COOLDOWN: {tiempo_restante:.2f}s", (10, 170),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                        
                            else:
                                punto_base_x, punto_base_y = self.obtener_posicion_puntero(hand_landmarks)
                                
                                if self.detectar_pulgar_arriba(hand_landmarks):
                                    if self.enviar_comando("clear_drawings", 'clear_drawings'):
                                        cv2.putText(frame, "LIMPIANDO DIBUJOS", (10, 130),
                                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
                                        self.esta_dibujando = False
                                        self.esta_borrando = False
                                        self.esta_moviendo = False

                                elif self.detectar_gesto_pinza(hand_landmarks, ancho_frame, alto_frame):
                                    if not self.esta_moviendo:
                                        self.esta_moviendo = True
                                        self.esta_dibujando = False
                                        self.esta_borrando = False
                                        comando_move = f"start_move_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_move, 'start_move')
                                    else:
                                        comando_move = f"moving_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_move, 'moving')

                                    puntero_px = (int(punto_base_x * ancho_frame), int(punto_base_y * alto_frame))
                                    cv2.circle(frame, puntero_px, 20, (255, 0, 255), 3)

                                elif self.detectar_gesto_cuernos(hand_landmarks):
                                    draw_x, draw_y = self.obtener_posicion_indice(hand_landmarks)
                                    
                                    if self.esta_moviendo:
                                        self.esta_moviendo = False
                                        self.enviar_comando("stop_move", 'stop_move')
                                
                                    if not self.esta_dibujando:
                                        self.esta_dibujando = True
                                        self.esta_borrando = False
                                        comando_draw = f"start_draw_{draw_x:.3f}_{draw_y:.3f}"
                                        self.enviar_comando(comando_draw, 'start_draw')
                                    else:
                                        comando_draw = f"drawing_{draw_x:.3f}_{draw_y:.3f}"
                                        self.enviar_comando(comando_draw, 'drawing')
                                    
                                    indice_px = (int(draw_x * ancho_frame), int(draw_y * alto_frame))
                                    cv2.circle(frame, indice_px, 25, (0, 255, 0), -1)
                                    cv2.circle(frame, indice_px, 27, (255, 255, 255), 2)
                                    cv2.line(frame, (indice_px[0] - 10, indice_px[1]), (indice_px[0] + 10, indice_px[1]), (255, 255, 255), 2)
                                    cv2.line(frame, (indice_px[0], indice_px[1] - 10), (indice_px[0], indice_px[1] + 10), (255, 255, 255), 2)

                                elif self.detectar_mano_abierta_completa(hand_landmarks):
                                    if self.esta_moviendo:
                                        self.esta_moviendo = False
                                        self.enviar_comando("stop_move", 'stop_move')
                                    if not self.esta_borrando:
                                        self.esta_borrando = True
                                        self.esta_dibujando = False
                                        comando_erase = f"start_erase_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_erase, 'start_erase')
                                    else:
                                        comando_erase = f"erasing_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_erase, 'erasing')
                                    
                                    puntero_px = (int(punto_base_x * ancho_frame), int(punto_base_y * alto_frame))
                                    cv2.circle(frame, puntero_px, 25, (0, 0, 255), 4)
                                
                                elif self.detectar_puno(hand_landmarks):
                                    if self.esta_dibujando:
                                        self.esta_dibujando = False
                                        comando_stop = f"stop_draw_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_stop, 'stop_draw')
                                    elif self.esta_borrando:
                                        self.esta_borrando = False
                                        comando_stop = f"stop_erase_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_stop, 'stop_erase')
                                    elif self.esta_moviendo:
                                        self.esta_moviendo = False
                                        self.enviar_comando("stop_move", 'stop_move')
                                    
                                    puntero_activo = True
                                    comando_puntero = f"puntero_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                    self.enviar_comando(comando_puntero, 'puntero')
                                    
                                    puntero_px = (int(punto_base_x * ancho_frame), int(punto_base_y * alto_frame))
                                    cv2.circle(frame, puntero_px, 25, (0, 255, 255), 3)
                                    cv2.circle(frame, puntero_px, 5, (0, 0, 255), -1)
                                
                                else:
                                    if self.esta_dibujando:
                                        self.esta_dibujando = False
                                        comando_stop = f"stop_draw_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_stop, 'stop_draw')
                                    elif self.esta_borrando:
                                        self.esta_borrando = False
                                        comando_stop = f"stop_erase_{punto_base_x:.3f}_{punto_base_y:.3f}"
                                        self.enviar_comando(comando_stop, 'stop_erase')
                                    elif self.esta_moviendo:
                                        self.esta_moviendo = False
                                        self.enviar_comando("stop_move", 'stop_move')
                        

                        elif self.detectar_gesto_paz(hand_landmarks):
                            if self.enviar_comando("toggle_draw_mode", 'toggle_draw_mode'):
                                self.modo_dibujo_activo = not self.modo_dibujo_activo
                                self.esta_dibujando = False
                                self.esta_borrando = False
                                self.esta_moviendo = False
                                self.mostrar_feedback_toggle = True
                                self.tiempo_inicio_feedback = time.time()
                                self.stdout.write(f"{'='*50}")
                                self.stdout.write(f"MODO DIBUJO: {'ACTIVADO ✓' if self.modo_dibujo_activo else 'DESACTIVADO ✗'}")
                                self.stdout.write(f"{'='*50}")
                            else:
                                tiempo_restante = self.obtener_tiempo_restante('toggle_draw_mode')
                                cv2.putText(frame, f"ENTRAR EN COOLDOWN: {tiempo_restante:.2f}s", (10, 170),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                        
                        else:
                            gesto_pistola = self.detectar_gesto_pistola(hand_landmarks)
                            
                            if gesto_pistola == 'pistola_derecha':
                                puntero_activo = False
                                if self.enviar_comando("next", 'next'):
                                    cv2.putText(frame, "SIGUIENTE >", (10, 130),
                                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                                else:
                                    tiempo_restante = self.obtener_tiempo_restante('next')
                                    cv2.putText(frame, f"Cooldown: {tiempo_restante:.2f}s", (10, 130),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                            
                            elif gesto_pistola == 'pistola_izquierda':
                                puntero_activo = False
                                if self.enviar_comando("prev", 'prev'):
                                    cv2.putText(frame, "<< ANTERIOR", (10, 130),
                                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                                else:
                                    tiempo_restante = self.obtener_tiempo_restante('prev')
                                    cv2.putText(frame, f"Cooldown: {tiempo_restante:.2f}s", (10, 130),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                            
                            elif self.detectar_puno(hand_landmarks):
                                puntero_activo = True
                                punto_zoom_x, punto_zoom_y = self.obtener_posicion_puntero(hand_landmarks)
                                
                                comando_puntero = f"puntero_{punto_zoom_x:.3f}_{punto_zoom_y:.3f}"
                                self.enviar_comando(comando_puntero, 'puntero')
                                
                                puntero_px = (int(punto_zoom_x * ancho_frame), int(punto_zoom_y * alto_frame))
                                cv2.circle(frame, puntero_px, 25, (0, 255, 255), 3)
                                cv2.circle(frame, puntero_px, 5, (0, 0, 255), -1)
                            
                            else:
                                puntero_activo = False
                    
                    else:
                        puntero_activo = False
                        contador_zoom = 0
                        if zoom_activo:
                            zoom_activo = False
                            distancia_referencia = None
                            self.enviar_comando("zoom_1.0_0.5_0.5", 'reset')
                            ultimo_zoom = 1.0

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
                    
                    if self.esta_dibujando:
                        self.esta_dibujando = False
                        self.enviar_comando("stop_draw_0.5_0.5", 'stop_draw')
                    elif self.esta_borrando:
                        self.esta_borrando = False
                        self.enviar_comando("stop_erase_0.5_0.5", 'stop_erase')
                    elif self.esta_moviendo:
                        self.esta_moviendo = False
                        self.enviar_comando("stop_move", 'stop_move')

                self.mostrar_feedback_toggle_modo(frame, ancho_frame, alto_frame)
                
                if self.modo_dibujo_activo:
                    cv2.rectangle(frame, (0, 0), (ancho_frame, 90), (0, 100, 255), -1)
                    cv2.rectangle(frame, (0, 0), (ancho_frame, 90), (255, 255, 255), 4)
                    
                    texto_principal = "MODO DIBUJO ACTIVADO"
                    tamaño_texto = cv2.getTextSize(texto_principal, cv2.FONT_HERSHEY_SIMPLEX, 1.3, 3)[0]
                    x_centrado = (ancho_frame - tamaño_texto[0]) // 2
                    cv2.putText(frame, texto_principal, (x_centrado, 38),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.3, (255, 255, 255), 3)
                    
                    if self.esta_dibujando:
                        estado_texto = "DIBUJANDO"
                        color_estado = (0, 255, 0)
                    elif self.esta_borrando:
                        estado_texto = "BORRANDO"
                        color_estado = (0, 165, 255)
                    elif self.esta_moviendo:
                        estado_texto = "MOVIENDO"
                        color_estado = (255, 0, 255)
                    else:
                        estado_texto = "PUNTERO"
                        color_estado = (255, 255, 0)
                    
                    tamaño_estado = cv2.getTextSize(estado_texto, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
                    x_estado = (ancho_frame - tamaño_estado[0]) // 2
                    cv2.putText(frame, estado_texto, (x_estado, 70),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.0, color_estado, 2)
                    
                    cv2.rectangle(frame, (0, 90), (20, alto_frame), (0, 255, 0), -1)
                    cv2.rectangle(frame, (ancho_frame - 20, 90), (ancho_frame, alto_frame), (0, 255, 0), -1)
                else:
                    cv2.rectangle(frame, (0, 0), (ancho_frame, 55), (50, 50, 50), -1)
                    cv2.rectangle(frame, (0, 0), (ancho_frame, 55), (100, 100, 100), 3)
                    
                    texto_nav = "MODO NAVEGACION"
                    tamaño_nav = cv2.getTextSize(texto_nav, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 2)[0]
                    x_nav = (ancho_frame - tamaño_nav[0]) // 2
                    cv2.putText(frame, texto_nav, (x_nav, 38),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.1, (200, 200, 200), 2)

                config_y = alto_frame - 30
                if not self.modo_dibujo_activo:
                    cv2.putText(frame, "PAZ =Activar Dibujo | Pistola =Navegar | Puno =Puntero | 2 Manos=Zoom", 
                        (10, config_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                else:
                    cv2.putText(frame, "PAZ =Salir | CUERNOS =Dibujar | MANO =Borrar | PUNO =Puntero | PINZA =Mover | MENIQUE =Limpiar", 
                        (10, config_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                cv2.imshow("Detector con Gestos Mejorados", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break

        cap.release()
        cv2.destroyAllWindows()