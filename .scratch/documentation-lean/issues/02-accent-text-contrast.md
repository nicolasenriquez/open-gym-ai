# Revalidar contraste de texto y política de tinta de acentos

Status: needs-triage

## Pregunta

¿Los acentos y tintas actuales cumplen contraste de texto en ambos temas y estados?

## Contexto y alcance

La revisión visual del 2026-10-19 sobre runtime v1.4.1 midió el control claro
«Por músculo»: texto verde #34c759, 15px/600, sobre tinte 16% en #f2f2f7,
contraste calculado ~1.77:1; verde en blanco ~2.22:1. Cálculo de colores,
no escaneo de píxeles. No se revalidó en esta limpieza. Las fuentes eran
`frontend/src/index.css` y `frontend/src/lib/accent.js` (release v1.4.0 `28b7e4dc`).

## Cierre

Medir colores finales compuestos en revisión identificable, ambos temas, presets,
seleccionado y extremos de acento personalizado. Evaluar texto normal 4.5:1 y grande
3:1 según WCAG real: 17px/600 no basta para llamarlo grande. Diferenciar tinta de
texto de identidad de paleta; no reemplazar colores sin diseño autorizado. El verde
primario con tinta negra no tenía el mismo fallo. Revisar la explicación CSS de
contraste y probar la política elegida; no declarar que todos los botones fallan.

Fuente normativa: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
