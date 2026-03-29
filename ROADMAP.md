# RIFF Roadmap — Learning & Practice Tool

Pivot from "jam companion that responds musically" to "tool for learning and improving your playing".

---

## Modes

### FREE — Jam libre con metricas

Lo que ya existe:
- Waveform animado + notas detectadas + chord pills
- Pitch (pyin), BPM (beat_track), dB (RMS)

Por implementar:
- **Metricas en tiempo real**:
  - Estabilidad de tempo: desviacion del BPM objetivo, tipo metronomo visual
  - Precision de afinacion: cents de desviacion respecto a la nota mas cercana (pyin ya da Hz, calcular cents es trivial)
  - Rango dinamico: min/max dB en ventana rolling, indicador de "todo al mismo volumen" vs "buen rango"
  - Notas por segundo: densidad de notas (DensityTracker ya existia en responder, reimplementar)
- **Historial de notas**: piano roll horizontal que va scrolleando (deque de ultimas N notas con timestamp)
- **Resumen de sesion**: al salir (o con tecla `s`), mostrar estadisticas acumuladas: notas mas tocadas, rango, tempo medio, tiempo total
- **Con fichero de cancion** (`--file`):
  - Panel RIFF muestra analisis de la cancion en tiempo real (notas, acordes, BPM, dinamica) como "partitura visual"
  - Panel YOU muestra lo que el usuario toca encima — permite comparar tempo, tonalidad, precision

### PRACTICE — Ejercicios guiados

- RIFF propone un ejercicio: escala, arpegio, progresion de acordes
- Muestra la siguiente nota que debes tocar (target note)
- Evalua en tiempo real: nota correcta/incorrecta, timing respecto al BPM
- Catalogo fijo inicial:
  - Escalas mayores (12 tonalidades)
  - Escalas menores naturales (12 tonalidades)
  - Pentatonicas mayor/menor
  - Arpegios basicos (mayor, menor, 7a)
- Progresion de dificultad: sube BPM automaticamente si el usuario acierta N notas seguidas
- Feedback visual: color verde (acierto) / rojo (fallo) en la nota del panel
- **Con fichero de cancion** (`--file`):
  - Extraer notas/acordes de la cancion y usarlos como ejercicio ("toca esto que suena en la cancion")
  - Detectar escala/tonalidad de la cancion y proponer ejercicios en esa tonalidad
  - Modo "slow down": reproducir la cancion mas lenta para practicar pasajes dificiles

### EAR TRAINING — Entrenamiento auditivo

- RIFF reproduce un sonido usando sintesis Karplus-Strong
- Niveles de dificultad:
  1. Notas sueltas: RIFF toca una nota, usuario la reproduce
  2. Intervalos: RIFF toca dos notas, usuario identifica el intervalo tocandolo
  3. Acordes: RIFF toca un acorde, usuario lo identifica
  4. Secuencias: RIFF toca 3-4 notas, usuario las reproduce en orden
- Evaluacion: comparar pitch detectado con nota objetivo (tolerancia configurable)
- Progresion: desbloquear niveles segun aciertos
- **Con fichero de cancion** (`--file`):
  - Reproducir fragmentos de la cancion y pedir al usuario que los reproduzca
  - Pausa en un acorde de la cancion y el usuario debe tocarlo
  - Progresion: notas sueltas de la cancion → frases → secciones completas

---

## Entrada de cancion (`--file`)

`--file` acepta dos tipos de entrada. Deteccion automatica por extension.

### Audio (mp3, wav, flac, ogg, ...)

RIFF analiza la señal con librosa para extraer informacion aproximada:

- **Tonalidad**: detectar escala/key de la cancion
- **Estructura**: identificar secciones (intro, verso, estribillo, puente, outro)
- **Progresion de acordes**: secuencia de acordes con timestamps
- **BPM**: tempo global y variaciones
- **Song map**: visualizacion compacta de la estructura en el panel RIFF

### MIDI (.mid, .midi)

Formato universal — cualquier instrumento, incluyendo voz. Ventajas:

- Informacion **exacta**: notas, octavas, duraciones, timing sin errores de analisis
- Facil de conseguir: miles disponibles online, y Guitar Pro / MuseScore / Finale exportan a MIDI
- Ligero de procesar: lista de eventos (note on/off), no requiere analisis de audio
- Libreria: `pretty_midi`

### Representacion interna comun

Ambas entradas se normalizan a la misma estructura:

```
--file cancion.mp3  → AudioAnalyzer (pyin, beat_track) → notas aproximadas ─┐
--file cancion.mid  → MidiParser (pretty_midi)         → notas exactas     ─┤
                                                                             ↓
                                                          lista de (nota, octava, tiempo, duracion)
                                                          → FREE / PRACTICE / EAR TRAINING
```

Modulo: `riff/audio/song.py` — preprocesa el fichero al arrancar y expone la informacion por timestamp para sincronizar con la reproduccion o alimentar ejercicios.

### Uso en cada modo

- FREE: muestra la "partitura visual" sincronizada con la reproduccion
- PRACTICE: genera ejercicios basados en el material de la cancion
- EAR TRAINING: usa fragmentos reales como retos auditivos

---

## Arquitectura post-pivot

```
AudioCapture → audio_queue → AudioAnalyzer → AppState → RiffDisplay
                                                ↑
                                          mode-specific logic
                                          (future: Practice engine,
                                           Ear Training engine,
                                           Song analyzer)
```

Cada modo tendra su propio modulo en `riff/modes/` que lee de AppState y escribe sus propios campos.

El analisis de cancion vivira en `riff/audio/song.py` — preprocesa el fichero completo al arrancar y expone la informacion por timestamp para que el display la sincronice con la reproduccion.

---

## Sintesis de audio

La sintesis Karplus-Strong (necesaria para Ear Training) se reimplementara como modulo independiente en `riff/audio/synth.py`. Parametros de timbre (CLEAN, WARM, BRIGHT, PAD, RAW) se mantienen en AppState para esto.
