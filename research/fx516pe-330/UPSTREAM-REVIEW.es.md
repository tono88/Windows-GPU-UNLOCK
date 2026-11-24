# Revisión de Zagitta/gpu-unlock y Turing-unlock para FX516PE.330

Revisión: 24 de noviembre de 2026. Objetivo: RTX 3050 Ti Laptop `10de:25a0 / 1043:13dc`, VBIOS local `94.07.42.00.3a`, Windows. El unlock de esta máquina continúa sin validar.

| Fuente | Qué aporta | Límite para este port |
|---|---|---|
| [Zagitta/gpu-unlock](https://github.com/Zagitta/gpu-unlock/tree/7eb51bccae0a0b7e599e084d971170e9a1e82d0c) | Receta GA10x, carga de firmware y estado antes del controlador | Es un módulo Linux; el main inspeccionado todavía no incluye GA107 ni 25a0 en recipes.c |
| [PR #231](https://github.com/Zagitta/gpu-unlock/pull/231) | Propone GA107 con chip 0x177 sobre ga10x, incluyendo 25a0 | Sigue abierto; una entrada en la tabla no valida BIOS, pantalla ni recuperación Windows |
| [Turing-unlock](https://github.com/haohervchb/Turing-unlock/tree/a188b24a392414f29f931ea886329227cfbc2f98) | Ejemplo de comprobaciones previas, restauración DMA y medición numérica | Objetivo TU102/RTX 2080 Ti; su firmware y política de hardware no corresponden a GA107 |

## Evidencia más cercana

El [reporte #246](https://github.com/Zagitta/gpu-unlock/issues/246) describe una FX516PE con RTX 3050 Ti 25a0 de 4 GB en Ubuntu, VBIOS `94.07.2B.00.54`. Reporta +68% FP16 y +74% BF16 con una modificación local GA107. También informa que el apagado runtime D3 eliminaba el efecto y que desactivarlo permitió conservarlo. Es evidencia del autor del reporte, con otra VBIOS y sistema operativo; no prueba nuestra BIOS 330 ni Windows.

## Qué reutilizar

La hipótesis de trabajo es conservar la receta GA10x y revisar su admisión para GA107. El chip 0xb77000a1, las direcciones, el estado frío y el mapa de memoria siguen requiriendo observación en este equipo. Ningún valor del reporte se convierte en una constante local validada.

En `recipes.c`, GA10x y Turing seleccionan distintos Booter/firmware, versiones FWSEC y aperturas FEAT. Por ejemplo, el encabezado `registers.h` sitúa SS0 en 0x82381c para GA10x y 0x409664 para TU102. Por ello, Turing sirve como referencia de diseño de comprobaciones, no como payload intercambiable. No se incorporó código de Turing ni se alteraron sus avisos de licencia.

## Consecuencia para Windows y Hermes

El plan de validación debe comprobar el rendimiento después de cargar el controlador, después de un periodo de inactividad y después de suspender/reanudar. Un log UEFI satisfactorio por sí solo no demuestra persistencia. No se trasladará la opción Linux `NVreg_DynamicPowerManagement` a valores del registro Windows por similitud de nombres; hace falta una evaluación Windows específica.

[CUDA en WSL utiliza el controlador del host Windows](https://docs.nvidia.com/cuda/wsl-user-guide/). Por tanto, WSL no proporciona la secuencia de módulo Linux sobre la GPU física antes de cargar ese controlador. Esta conclusión es una inferencia de esa arquitectura y de `main.c`, no una prueba ejecutada del unlock en WSL.

## Sin memoria USB

La revisión de código y las pruebas con servicios simulados pueden continuar en Windows. Una futura utilidad de diagnóstico podría arrancar desde el disco interno mediante UEFI, pero necesita una implementación separada, pruebas de medio/archivos y preparación de recuperación. El ejecutable actual conserva su restricción USB. Esta revisión no instala esa ruta, no cambia Secure Boot y no prepara particiones ni entradas de arranque.

La siguiente prioridad es diseñar la captura profunda específica y la comprobación de persistencia Windows, usando la evidencia GA107 como referencia y conservando las identidades locales. El acceso previo a Windows, Secure Boot y la recuperación siguen siendo condiciones de la prueba física.

## Referencias exactas inspeccionadas

- Zagitta main: `7eb51bccae0a0b7e599e084d971170e9a1e82d0c`; `recipes.c` blob `21e4aca7af17fb1e3118901f1bc4f9ad96b17db9`.
- PR #231: cabeza `f8bc9936e1842b6052c07c21becc7086b5747c7d`, abierto al revisar.
- Turing-unlock main: `a188b24a392414f29f931ea886329227cfbc2f98`; README, BOOT-STATUS, plantilla GRUB y NOTICE.
- El paquete USB publicado anteriormente corresponde a su propio manifiesto; esta revisión no cambia ese binario.
