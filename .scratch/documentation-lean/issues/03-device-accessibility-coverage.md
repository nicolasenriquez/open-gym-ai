# Delimitar y verificar accesibilidad en dispositivos

Status: needs-triage

## Pregunta

¿Qué contrato soporta la PWA/WebView para zoom, movimiento reducido, medios y targets?

## Contexto y alcance

La revisión de diseño del 2026-10-19 (runtime v1.4.1; fuente v1.4.0 `28b7e4dc`)
observó `user-scalable=no`, supresión CSS de animaciones bajo reduce, excepciones
JS de smooth scroll y autoplay sin verificar, y chips de ~30px. No hubo pruebas
físicas de zoom, toque, teclado nativo ni lector de pantalla. No se revalidó aquí.
30px no implica incumplir el mínimo WCAG 2.2 de 24px; el área pintada tampoco es
siempre el target efectivo. Los switches expandían su área por CSS.

## Cierre

Acordar plataformas/expectativas antes de cambios. Verificar zoom, teclado y safe
areas en dispositivos autorizados, movimiento reducido incluyendo JS/medios, y
áreas efectivas/solapamiento con toque. Conservar dismissal apilado, bloqueo,
scroll y foco de `docs/dev/ui-accessibility-fixes.md`. No convertir emulación de
viewport en evidencia Safari/Android/iOS ni crear una nueva librería UI.
