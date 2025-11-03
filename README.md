# Control de Presentaciones con Gestos

Este proyecto permite controlar presentaciones mediante gestos de la mano, utilizando OpenCV y MediaPipe para el reconocimiento visual en tiempo real.
Fue desarrollado en Python 3.11 y está diseñado para ejecutarse en entornos locales (VS Code recomendado).

# Requisitos previos

Asegúrate de tener instalado:

Python 3.11

Git

Visual Studio Code

# Instalación del proyecto

Clona este repositorio:

git clone https://github.com/FredBrave/Control-de-presentaciones-con-gestos.git
cd Control-de-presentaciones-con-gestos


Crea un entorno virtual con Python 3.11:

python3.11 -m venv venv


Activa el entorno virtual:

En Windows:

venv\Scripts\activate


En macOS / Linux:

source venv/bin/activate


Instala las dependencias necesarias:

pip install -r requirements.txt

# Ejecución del proyecto

Ejecuta el script principal (por ejemplo main.py o el archivo que controle la cámara):

python main.py


Si al ejecutar el proyecto se presenta un error relacionado con la cámara, asegúrate de:

Seleccionar el intérprete de Python correcto en Visual Studio Code (Ctrl + Shift + P → “Python: Select Interpreter” → elige el entorno virtual creado).

Cerrar otras aplicaciones que puedan estar usando la cámara.

Verificar que tu dispositivo tenga permisos para acceder a la cámara.

# Tecnologías utilizadas

Python 3.11

OpenCV – procesamiento de imágenes y detección de movimiento

MediaPipe – reconocimiento y seguimiento de manos

NumPy – manipulación de datos numéricos

# Descripción del funcionamiento

La aplicación detecta los gestos de la mano del usuario en tiempo real mediante la cámara, y los traduce en acciones sobre la presentación, como:

Avanzar diapositiva

Retroceder

Pausar o reanudar la presentación

El modelo usa puntos de referencia (landmarks) detectados por MediaPipe para interpretar los movimientos y posiciones de los dedos.

# Problemas comunes
Problema	Solución
Error de cámara (no se abre o da “cap.read() failed”)	Selecciona el intérprete correcto en VS Code o revisa permisos de cámara
“ModuleNotFoundError”	Asegúrate de haber activado el entorno virtual y ejecutado pip install -r requirements.txt
FPS bajo o lentitud	Cierra programas que usen la cámara o GPU; reduce la resolución de captura en el código