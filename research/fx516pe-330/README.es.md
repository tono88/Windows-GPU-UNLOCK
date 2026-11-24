# ASUS TUF Dash F15 FX516PE / BIOS FX516PE.330 / RTX 3050 Ti Laptop

Estado: primera fase del port, con inventario Windows confirmado, medición CUDA normal y diagnóstico UEFI de configuración compilado. **Todavía no existe un desbloqueo validado para esta máquina.**

El nuevo diagnóstico no añade GA107 a los perfiles de desbloqueo ni modifica `gpu-family.h`, `proven.json`, el generador LOCAL o la transacción existente. No debe usarse un binario de una RTX 3090, 3060 o de otra laptop.

## Identidad confirmada desde Windows

| Dato | Observación |
|---|---|
| Equipo | ASUS TUF Dash F15 FX516PE_TUF516PE |
| Placa | FX516PE |
| BIOS | FX516PE.330 |
| GPU | RTX 3050 Ti Laptop, 4096 MiB |
| PCI / subsistema | `10de:25a0` / `1043:13dc` |
| VBIOS | `94.07.42.00.3a` |
| Capacidad CUDA | 8.6 |
| Controlador observado | 621.24 |
| Secure Boot observado | Activado |

`target.json` conserva los datos de modelo y deja chip, PROM, selectores y ruta de pantalla como desconocidos. La coincidencia de identidad Windows no autoriza escrituras. El diagnóstico EFI valida el dispositivo y subsistema; **no valida la versión de BIOS por SMBIOS**. Su nombre identifica el objetivo de investigación, no una certificación de BIOS.

## Qué hace el diagnóstico

Lee la configuración PCI, observa los atributos con la operación Get y registra el grafo de protocolos, controladores y pantallas mediante `internal-boot/boot/diagnostic.c`. Admite observar COMMAND=0 sin habilitar acceso a memoria. Comprueba que la configuración y la ubicación no cambien alrededor de la observación.

No lee MMIO, no extrae PROM ni imágenes de firmware, no habilita MSE/BME, no reserva DMA, no libera controladores y no ejecuta FLR. No escribe variables UEFI, no cambia entradas de arranque y no inicia un desbloqueo. Escribe un archivo nuevo solamente en la unidad USB desde la que fue cargado. Rechaza rutas de arranque internas y no sobrescribe archivos DIAG existentes.

El binario vuelve al firmware; no contiene el arranque automático del proyecto original ni requiere GUIDs de partición. Una captura completa sigue teniendo `can_unlock=false`.

## Compilar y verificar desde Windows

Requiere Python 3.10+ y MSVC x64 con soporte C11. Se utilizó Visual Studio Build Tools 2019 16.11, compilador 14.29.30133. No instala herramientas ni modifica el sistema.

```powershell
python -I .\research\fx516pe-330\build.py
```

Si MSVC está en otra ubicación, añade `--vcvars 'RUTA\vcvars64.bat'`. El proceso ejecuta pruebas Python, simulaciones C de PCI/archivos, pruebas de rechazo en compilación y verifica que el resultado sea PE32+ x64, EFI Application, sin imports y con relocaciones. No ejecuta el EFI en hardware.

Resultados: `research/fx516pe-330/build/BOOTX64.EFI` y `manifest.json`, con hashes de fuentes y dependencias locales. El manifiesto declara `hardware_tested=false`.

## Preparar y usar el diagnóstico USB

```powershell
python -I .\research\fx516pe-330\prepare_package.py
```

Esto crea una carpeta y ZIP locales nuevos. No selecciona unidades, no formatea y no escribe un USB real. Usa una memoria FAT32 vacía y copia su contenido, conservando `EFI/BOOT/BOOTX64.EFI`. No copies el archivo a la partición EFI de Windows.

La máquina observada tiene Secure Boot activado, por lo que rechazará este EFI sin firma. Antes de cambiar esa configuración, comprueba localmente el estado de BitLocker/cifrado del dispositivo y conserva su clave de recuperación, si existe. No compartas la clave ni borres llaves de Secure Boot. El estado de cifrado no se pudo consultar en la sesión sin privilegios administrativos. Este proyecto no desactiva Secure Boot ni el cifrado automáticamente.

Cuando el operador haya preparado esa condición, apaga completamente y selecciona el USB desde el menú de arranque del ASUS. Al terminar, vuelve a Windows Boot Manager. No configures el USB como arranque predeterminado. La primera ejecución física sigue pendiente; las pruebas en RAM no la sustituyen.

El archivo se guarda como `FX516PE-INVENTORY/DIAG00.TXT`; las siguientes ejecuciones usan el siguiente número libre. Conserva las capturas de arranques distintos. Para generar un resumen compartible:

```powershell
python -I .\research\fx516pe-330\review_capture.py E:\FX516PE-INVENTORY\DIAG00.TXT --output .\research\fx516pe-330\local\capture-summary.json
```

Sustituye E: por tu unidad. Los logs crudos pueden incluir rutas y GUIDs de partición; consérvalos localmente. El resumen omite direcciones y contenido del grafo. No publiques logs crudos, firmware, PROM, seriales ni claves de recuperación.

## Medición de rendimiento normal

```powershell
python -I .\research\fx516pe-330\collect_windows.py --output .\research\fx516pe-330\local\windows-inventory.json
python -I .\research\fx516pe-330\benchmark_cuda.py --output .\research\fx516pe-330\local\stock-gemm.json
```

El benchmark requiere NumPy y CUDA Toolkit local con `cublas64_11.dll` (probado con CUDA 11.8). Usa cuBLAS GEMM, matrices aleatorias de valores exactamente representables, acumulación FP32, siete muestras, cinco lanzamientos por muestra y eventos CUDA. Compara 32 resultados con referencias CPU y comprueba que toda la salida sea finita. No es una validación numérica exhaustiva ni una prueba de estabilidad. Mantén alimentación, temperatura, tamaño y software constantes al comparar.

La ejecución de referencia con el runner final y n=2048 dio aproximadamente FP32 4.77, FP16 17.35, BF16 15.49 y TF32 9.13 TFLOP/s. La ejecución inicial dio FP16 14.68: esta variación refuerza que una comparación requiere controlar potencia, relojes y condiciones. Son mediciones de esta sesión, no el máximo teórico, una comparación desbloqueada ni una predicción de tokens/s. Los datos originales permanecen locales; el resumen de evidencia identifica sus hashes.

## Trabajo pendiente para el desbloqueo

1. Capturar PCI y grafo real antes de Windows, con al menos dos arranques completos y la misma configuración de pantalla. Revisar cuál GOP controla el panel y quién posee la NVIDIA.
2. Según el COMMAND observado, diseñar una captura profunda acotada para esta placa. Si MSE está desactivado, no se debe leer BAR0 ni activar memoria sin validar un procedimiento específico de restauración. La utilidad entregada no lo intenta.
3. Obtener localmente chip/revisión, BAR y sus descriptores, PROM/hash, código de controladores UEFI, regiones WPR y estados fríos SS0/SS1. No copiar máscara fría, hashes ni direcciones de la FX506HCB con GPU `25a2`.
4. Implementar el perfil GA107 y la política de restauración únicamente con esas observaciones, incluyendo pruebas negativas de identidad, rango, DMA, FLR y fallos. Mantener separados los datos de diagnóstico y la admisión de escrituras.
5. Tras revisión y pruebas, realizar un primer arranque USB supervisado del unlock con retorno limpio a Windows. Comparar GEMM y la carga real de Hermes: procesamiento de prompt, generación, VRAM y errores del controlador. Un resultado Tensor mejor no garantiza más tokens/s.

Antecedentes: [reporte independiente GA107M en otra ASUS TUF](https://github.com/windows-GPU-UNLOCK/Windows-GPU-UNLOCK/issues/36), [familias admitidas](../../docs/GPU-FAMILIES.en.md), [criterios de portabilidad](../../docs/PORTABILITY.en.md). El antecedente no valida este equipo.

## Hermes y 4 GB

El desbloqueo no amplía la VRAM. El equipo ya tenía unos 3.8 GiB libres, por lo que cerrar procesos ofrece poco margen en la sesión observada. Para una prueba inicial con llama.cpp reciente: un modelo GGUF cuantizado que quepa, contexto de 4096, una sola solicitud y Flash Attention/caché KV q8_0 cuando el modelo y el backend lo soporten. Ajustar descarga a GPU y medir prompt y generación por separado. No se modificó la configuración de Hermes.

## Licencias

Código nuevo GPL-2.0-only. Se reutilizan el diagnóstico y runtime del proyecto original, conservando sus avisos. Los encabezados EDK2 mantienen BSD-2-Clause-Patent y sus avisos. No se distribuyen firmware NVIDIA, VBIOS, PROM ni DLLs de CUDA.
