"""
UI Helper para SlideMotion
Funciones de visualización para el detector de gestos
"""

import cv2


class UIHelper:
    """Helper para visualización en OpenCV"""
    
    @staticmethod
    def mostrar_estado_dibujo(frame, modo_activo, esta_dibujando, esta_borrando, y_offset=60):
        """Muestra el estado del modo dibujo"""
        if modo_activo:
            color_fondo = (0, 100, 255)
            texto_modo = "MODO DIBUJO: ON"
            
            if esta_dibujando:
                texto_estado = "DIBUJANDO (Cuernos)"
                color_estado = (0, 255, 0)
            elif esta_borrando:
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
    
    @staticmethod
    def mostrar_cooldowns_activos(frame, cooldowns_activos, y_offset=30):
        """Muestra visualmente los cooldowns activos en el frame"""
        try:
            if not cooldowns_activos:
                return 0
            
            offset_actual = 0
            for cooldown in cooldowns_activos:
                try:
                    # Manejar tanto tuplas como diccionarios
                    if isinstance(cooldown, dict):
                        comando = cooldown.get('comando', 'unknown')
                        tiempo_restante = cooldown.get('tiempo_restante', 0)
                    elif isinstance(cooldown, (tuple, list)):
                        comando, tiempo_restante = cooldown
                    else:
                        continue
                    
                    texto = f"{comando.upper()}: {tiempo_restante:.2f}s"
                    color = (0, 165, 255)
                    cv2.putText(frame, texto, (10, y_offset + offset_actual), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    offset_actual += 25
                except Exception as e:
                    continue
            
            return offset_actual
        except Exception as e:
            return 0
        
    @staticmethod
    def dibujar_puntero(frame, x, y, ancho_frame, alto_frame, color=(0, 255, 255)):
        """Dibuja el puntero en el frame"""
        puntero_px = (int(x * ancho_frame), int(y * alto_frame))
        cv2.circle(frame, puntero_px, 25, color, 3)
        cv2.circle(frame, puntero_px, 5, (0, 0, 255), -1)
    
    @staticmethod
    def dibujar_indicador_dibujando(frame, x, y, ancho_frame, alto_frame):
        """Dibuja el indicador de dibujo activo"""
        puntero_px = (int(x * ancho_frame), int(y * alto_frame))
        cv2.circle(frame, puntero_px, 15, (0, 255, 0), -1)
    
    @staticmethod
    def dibujar_indicador_borrando(frame, x, y, ancho_frame, alto_frame):
        """Dibuja el indicador de borrado activo"""
        puntero_px = (int(x * ancho_frame), int(y * alto_frame))
        cv2.circle(frame, puntero_px, 25, (0, 0, 255), 4)
    
    @staticmethod
    def dibujar_indicador_moviendo(frame, x, y, ancho_frame, alto_frame):
        """Dibuja el indicador de movimiento activo"""
        puntero_px = (int(x * ancho_frame), int(y * alto_frame))
        cv2.circle(frame, puntero_px, 20, (255, 0, 255), 3)
    
    @staticmethod
    def dibujar_linea_zoom(frame, pulgar1, pulgar2, ancho_frame, alto_frame):
        """Dibuja la línea entre pulgares para zoom"""
        pulgar1_px = (int(pulgar1.x * ancho_frame), int(pulgar1.y * alto_frame))
        pulgar2_px = (int(pulgar2.x * ancho_frame), int(pulgar2.y * alto_frame))
        cv2.line(frame, pulgar1_px, pulgar2_px, (255, 0, 0), 5)
        cv2.circle(frame, pulgar1_px, 12, (0, 255, 0), -1)
        cv2.circle(frame, pulgar2_px, 12, (0, 255, 0), -1)
    
    @staticmethod
    def mostrar_texto_estado(frame, texto, y, color=(128, 128, 128)):
        """Muestra texto de estado en el frame"""
        cv2.putText(frame, texto, (10, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    @staticmethod
    def mostrar_texto_grande(frame, texto, y, color=(0, 255, 0)):
        """Muestra texto grande para comandos"""
        cv2.putText(frame, texto, (10, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
    
    @staticmethod
    def mostrar_informacion_inferior(frame, modo_activo, puntero_activo, zoom_activo, 
                                     alto_frame, draw_offset=0, cooldown_offset=0):
        """Muestra la información en la parte inferior del frame"""
        estado_y = alto_frame - 100 + cooldown_offset + draw_offset
        
        if modo_activo:
            texto = "MODO: DIBUJO"
            color = (0, 100, 255)
        elif puntero_activo:
            texto = "MODO: PUNTERO"
            color = (0, 255, 255)
        elif zoom_activo:
            texto = "MODO: ZOOM"
            color = (255, 0, 0)
        else:
            texto = "MODO: NAVEGACION"
            color = (0, 255, 0)
        
        cv2.putText(frame, texto, (10, estado_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        
        # Mostrar ayuda de gestos
        config_y = estado_y + 30
        cv2.putText(frame, "Gestos: PAZ=Toggle | CUERNOS=Dibujar | MANO ABIERTA=Borrar", 
                   (10, config_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)