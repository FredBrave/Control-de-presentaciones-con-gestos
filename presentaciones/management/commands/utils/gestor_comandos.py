import requests
import time


class CommandManager:
    
    def __init__(self, url_actualizar_comando, stdout=None, stderr=None):
        self.url = url_actualizar_comando
        self.stdout = stdout
        self.stderr = stderr
        
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
        self.max_errores_antes_advertir = 5
        self.sesion = self._crear_sesion()
    
    def _crear_sesion(self):
        sesion = requests.Session()
        sesion.request = lambda *args, **kwargs: requests.Session.request(
            sesion, *args, timeout=kwargs.get('timeout', 0.5), **kwargs
        )
        return sesion
    
    def puede_enviar_comando(self, tipo_comando):
        tiempo_actual = time.time()
        tiempo_ultimo = self.ultimos_tiempos.get(tipo_comando, 0)
        cooldown = self.COOLDOWNS.get(tipo_comando, 0.1)
        
        puede_enviar = (tiempo_actual - tiempo_ultimo) >= cooldown
        
        if puede_enviar:
            self.ultimos_tiempos[tipo_comando] = tiempo_actual
        
        return puede_enviar
    
    def obtener_tiempo_restante(self, tipo_comando):
        tiempo_actual = time.time()
        tiempo_ultimo = self.ultimos_tiempos.get(tipo_comando, 0)
        cooldown = self.COOLDOWNS.get(tipo_comando, 0.1)
        
        tiempo_restante = cooldown - (tiempo_actual - tiempo_ultimo)
        return max(0, tiempo_restante)
    
    def enviar_comando(self, comando, tipo_comando):
        print(f"\n[CommandManager] Intentando enviar: {comando} (tipo: {tipo_comando})")  # DEBUG
        
        if not self.puede_enviar_comando(tipo_comando):
            tiempo_restante = self.obtener_tiempo_restante(tipo_comando)
            print(f"  ✗ En cooldown: {tiempo_restante:.2f}s restantes")  # DEBUG
            if self.COOLDOWNS.get(tipo_comando, 0) > 0.05:
                if self.stdout:
                    self.stdout.write(f"Cooldown {tipo_comando}: {tiempo_restante:.2f}s restantes")
            return False
        
        print(f"  → Enviando a: {self.url}")  # DEBUG
        
        try:
            response = self.sesion.post(
                self.url, 
                json={"comando": comando},
                timeout=0.5
            )
            
            print(f"  ← Respuesta: HTTP {response.status_code}")  # DEBUG
            
            if response.status_code == 200:
                self.errores_consecutivos = 0
                print(f"  ✓ Comando enviado exitosamente")  # DEBUG
                if self.stdout and tipo_comando in ['next', 'prev', 'toggle_draw_mode', 'clear_drawings']:
                    self.stdout.write(f"✓ Comando enviado: {comando} (tipo: {tipo_comando})")
                return True
            else:
                self.errores_consecutivos += 1
                print(f"  ✗ Error HTTP {response.status_code}")  # DEBUG
                if self.stderr and self.errores_consecutivos <= 3:
                    self.stderr.write(f"HTTP {response.status_code} para comando: {tipo_comando}")
                return False
        
        except requests.exceptions.Timeout:
            self.errores_consecutivos += 1
            print(f"  ✗ Timeout")  # DEBUG
            if self.stderr and self.errores_consecutivos == 1:
                self.stderr.write(f"Timeouts detectados (normal si el servidor está ocupado)")
            return False
        
        except requests.exceptions.ConnectionError as e:
            self.errores_consecutivos += 1
            print(f"  ✗ Error de conexión: {e}")  # DEBUG
            if self.stderr and self.errores_consecutivos <= 3:
                self.stderr.write(f"Error de conexión al servidor: {self.url}")
            return False
        
        except Exception as e:
            self.errores_consecutivos += 1
            print(f"  ✗ Error inesperado: {type(e).__name__} - {e}")  # DEBUG
            if self.stderr and self.errores_consecutivos <= 2:
                self.stderr.write(f"Error inesperado en envío: {type(e).__name__} - {str(e)}")
            return False
    
    def obtener_cooldowns_activos(self):
        """Retorna lista de cooldowns activos para visualización"""
        try:
            tiempo_actual = time.time()
            cooldowns_activos = []
            
            for comando, ultimo_tiempo in self.ultimos_tiempos.items():
                cooldown_duracion = self.COOLDOWNS.get(comando, 0)
                tiempo_restante = cooldown_duracion - (tiempo_actual - ultimo_tiempo)
                
                if tiempo_restante > 0 and cooldown_duracion > 0.05:
                    cooldowns_activos.append({
                        'comando': comando,
                        'tiempo_restante': tiempo_restante
                    })
            
            return cooldowns_activos
        except Exception as e:
            if self.stderr:
                self.stderr.write(f"Error obteniendo cooldowns: {e}")
            return []