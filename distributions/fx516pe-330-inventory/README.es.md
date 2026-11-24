# Diagnóstico FX516PE / BIOS 330

Este paquete es la primera fase del port de investigación para RTX 3050 Ti Laptop `10de:25a0 / 1043:13dc`. **No ejecuta ni habilita un desbloqueo.** La primera prueba física del EFI está pendiente.

[Descargar el paquete ZIP](./FX516PE-330-inventory.zip?raw=true) · [Guía completa](../../research/fx516pe-330/README.es.md)

El ZIP contiene el ejecutable UEFI de inventario, sus fuentes correspondientes, licencias, manifiesto y hashes. Escribe únicamente logs nuevos en el USB de arranque; no formatea, no cambia entradas de arranque, no lee MMIO/PROM y no libera controladores. El ejecutable sin firma requiere que el operador prepare Secure Boot y verifique antes el estado de recuperación del cifrado. No se cambió esa configuración en la sesión.

- ZIP SHA-256: `50c6ac48944b90d3091146dcad7d88c184eb4b1d2262987261f5c172458342ed`
- EFI SHA-256: `267597b1ae883f55e31d468bd315e64a31ca03e864f21dbb894ad2c9d369fc84`
- Validación: 8 pruebas Python, 54 comprobaciones C con servicios en RAM, 12 rechazos de compilación y 85 archivos del paquete verificados.
- Las mediciones CUDA de Windows son del arranque normal. No existe todavía una comparación con unlock de esta máquina.

Conserva los logs originales localmente y usa `review_capture.py` para obtener un resumen que omite direcciones y GUIDs. No publiques archivos de recuperación, inventarios crudos ni firmware.
