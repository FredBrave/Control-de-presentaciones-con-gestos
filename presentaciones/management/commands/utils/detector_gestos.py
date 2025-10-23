"""
Detector de Gestos para SlideMotion
Clase principal que gestiona la detección de gestos con MediaPipe
"""

import time
import math
import mediapipe as mp


class GestureDetector:
    """Detector de gestos con MediaPipe"""
    
    def __init__(self):
        # Configuración de MediaPipe
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Estado del sistema
        self.modo_dibujo_activo = False
        self.esta_dibujando = False
        self.esta_borrando = False
        self.esta_moviendo = False
        
        # Tolerancias y sensibilidades
        self.TOLERANCIA_PULGAR_PISTOLA = 0.05
        self.TOLERANCIA_DIRECCION_PISTOLA = 0.015
        self.SENSIBILIDAD_ZOOM = 0.08
        self.FRAMES_PREPARACION_ZOOM = 2
        self.TOLERANCIA_PUNO = 0.035
        self.TOLERANCIA_PAZ = 0.04
        self.TOLERANCIA_CUERNOS = 0.04
    
    def calcular_distancia(self, punto1, punto2, ancho_frame, alto_frame):
        """Calcula la distancia euclidiana entre dos puntos normalizados"""
        x1, y1 = punto1.x * ancho_frame, punto1.y * alto_frame
        x2, y2 = punto2.x * ancho_frame, punto2.y * alto_frame
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def detectar_gesto_paz(self, hand_landmarks):
        """Detecta gesto de PAZ (✌️) - índice y medio extendidos"""
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
        """Detecta gesto de ROCK/CUERNOS (🤘) - índice y meñique extendidos"""
        landmarks = hand_landmarks.landmark
        
        indice_extendido = landmarks[8].y < landmarks[6].y - 0.025
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.025
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        
        return (indice_extendido and menique_extendido and 
                medio_doblado and anular_doblado)
    
    def detectar_mano_abierta_completa(self, hand_landmarks):
        """Detecta mano completamente abierta (4-5 dedos extendidos)"""
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
        """Detecta gesto de pistola (👉 o 👈) para navegación"""
        landmarks = hand_landmarks.landmark
        
        pulgar_tip = landmarks[self.mp_hands.HandLandmark.THUMB_TIP]
        pulgar_mcp = landmarks[self.mp_hands.HandLandmark.THUMB_MCP]
        indice_tip = landmarks[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        indice_mcp = landmarks[self.mp_hands.HandLandmark.INDEX_FINGER_MCP]
        medio_tip = landmarks[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        medio_pip = landmarks[self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP]
        anular_tip = landmarks[self.mp_hands.HandLandmark.RING_FINGER_TIP]
        anular_pip = landmarks[self.mp_hands.HandLandmark.RING_FINGER_PIP]
        menique_tip = landmarks[self.mp_hands.HandLandmark.PINKY_TIP]
        menique_pip = landmarks[self.mp_hands.HandLandmark.PINKY_PIP]
        
        indice_extendido = indice_tip.y < indice_mcp.y
        pulgar_extendido = abs(pulgar_tip.x - pulgar_mcp.x) > self.TOLERANCIA_PULGAR_PISTOLA
        medio_doblado = medio_tip.y > medio_pip.y
        anular_doblado = anular_tip.y > anular_pip.y
        menique_doblado = menique_tip.y > menique_pip.y
        
        print(f"DEBUG Pistola:")
        print(f"  Índice ext: {indice_extendido} (tip.y={indice_tip.y:.3f} < mcp.y={indice_mcp.y:.3f})")
        print(f"  Pulgar ext: {pulgar_extendido} (diff={abs(pulgar_tip.x - pulgar_mcp.x):.3f} > {self.TOLERANCIA_PULGAR_PISTOLA})")
        print(f"  Medio dob: {medio_doblado}")
        print(f"  Anular dob: {anular_doblado}")
        print(f"  Meñique dob: {menique_doblado}")
        
        if indice_extendido and pulgar_extendido and medio_doblado and anular_doblado and menique_doblado:
            diff_x = indice_tip.x - indice_mcp.x
            print(f"  ¡Pistola detectada! diff_x={diff_x:.3f} (tolerancia={self.TOLERANCIA_DIRECCION_PISTOLA})")
            
            if diff_x > self.TOLERANCIA_DIRECCION_PISTOLA:
                print("  → PISTOLA DERECHA")
                return 'pistola_derecha'
            elif diff_x < -self.TOLERANCIA_DIRECCION_PISTOLA:
                print("  → PISTOLA IZQUIERDA")
                return 'pistola_izquierda'
        
        return None
    
    def detectar_puno(self, hand_landmarks):
        """Detecta puño cerrado (✊)"""
        landmarks = hand_landmarks.landmark
        
        indice_doblado = landmarks[8].y > landmarks[6].y
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        menique_doblado = landmarks[20].y > landmarks[18].y
        pulgar_doblado = abs(landmarks[4].x - landmarks[3].x) < self.TOLERANCIA_PUNO
        
        return (indice_doblado and medio_doblado and anular_doblado and 
                menique_doblado and pulgar_doblado)
    
    def detectar_menique_solo(self, hand_landmarks):
        """Detecta solo el meñique levantado para limpiar pantalla"""
        landmarks = hand_landmarks.landmark
        
        menique_extendido = landmarks[20].y < landmarks[18].y - 0.04
        indice_doblado = landmarks[8].y > landmarks[6].y
        medio_doblado = landmarks[12].y > landmarks[10].y
        anular_doblado = landmarks[16].y > landmarks[14].y
        pulgar_doblado = landmarks[4].y > landmarks[3].y
        
        menique_mas_alto = (landmarks[20].y < landmarks[8].y and
                           landmarks[20].y < landmarks[12].y and
                           landmarks[20].y < landmarks[16].y)
        
        return (menique_extendido and indice_doblado and medio_doblado and 
                anular_doblado and pulgar_doblado and menique_mas_alto)
    
    def detectar_gesto_pinza(self, hand_landmarks, ancho_frame, alto_frame):
        """Detecta gesto de pinza (👌) - pulgar e índice juntos"""
        landmarks = hand_landmarks.landmark
        
        pulgar_tip = landmarks[4]
        indice_tip = landmarks[8]
        
        distancia = self.calcular_distancia(pulgar_tip, indice_tip, ancho_frame, alto_frame)
        return distancia < 30
    
    def obtener_posicion_puntero(self, hand_landmarks):
        """Obtiene la posición del centro de la mano para el puntero"""
        centro_palma = hand_landmarks.landmark[0]  # WRIST
        dedo_medio_mcp = hand_landmarks.landmark[9]  # MIDDLE_FINGER_MCP
        
        centro_x = (centro_palma.x + dedo_medio_mcp.x) / 2
        centro_y = (centro_palma.y + dedo_medio_mcp.y) / 2
        
        return centro_x, centro_y
    
    def detectar_manos_abiertas(self, hands_results):
        """Detecta cuántas manos abiertas hay (para zoom)"""
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