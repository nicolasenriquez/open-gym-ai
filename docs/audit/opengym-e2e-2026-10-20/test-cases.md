---
type: Audit
title: Casos E2E de OpenGym
description: Casos y resultados históricos de la verificación E2E.
---
# Casos E2E de OpenGym

Base: UI española, kg/cm, `http://localhost:8080`, invitado en navegador efímero propio. Cada ejecución parte vacía salvo que el caso declare datos previos. Usar datos ficticios; nunca el perfil del usuario.

**A** = automatizado por `guest-smoke.js`; su PASS depende de completar el runner y validar la exportación. **O** = observado mediante acciones manuales de CLI/inspección, sin caso automatizado independiente. **R** = renderizado o redirección observados, sin probar todas las acciones. **F** = fallo reproducido. **P** = pendiente. No sumar R como E2E funcional completo.

| ID | Precondición y acciones desde la UI | Resultado esperado / evidencia | Estado |
|---|---|---|---|
| G01 | Perfil nuevo; abrir raíz | Login sin cuenta previa; health ok | A |
| G02 | Continuar sin cuenta | Bienvenida, sin pesajes y aviso de datos locales | A |
| G03 | Recargar invitado con datos | No volver al login ni perder registros | A, transversal |
| G04 | Login: cancelar autenticación passkey | Mensaje recuperable, sin crear sesión ni perder invitado | P, credenciales |
| G05 | Iniciar sesión con datos locales | Decisión explícita de adopción, sin sobrescritura silenciosa | P, cuenta |
| G06 | Logout y segundo usuario | Datos y medios del usuario anterior inaccesibles | P, dos cuentas |
| L01 | Ejercicios; búsqueda imposible | Estado 0 ejercicios, sin resultados, sin fila de sentadilla | A |
| L02 | Buscar squat; abrir sentadilla; Escape | Detalle correcto; volver al catálogo | A |
| L03 | Combinar grupo, tipo, equipo; limpiar | Resultados satisfacen intersección; reset restaura catálogo | P |
| L04 | Ejercicios > Por músculo > músculo | Lista coherente; detalle alcanzable; volver conserva contexto | R en /muscles; acciones P |
| L05 | Cambiar tarjetas/lista y Mostrar más | Mismos resultados; paginación sin duplicados | P |
| L06 | Crear ejercicio propio sin medios | Aparece en catálogo y puede añadirse a rutina tras recarga | P |
| L07 | Cargar still y reproducir clip del ejercicio | Medios reales cargan; controles y pausa operativos | O visual parcial; red/clip P |
| L08 | Detalle abierto; Tab y lector de pantalla | Diálogo nombrado; foco dentro; retorno al cerrar | F, modal |
| P01 | Plan > Rutinas > Nueva rutina; nombre; añadir squat | Rutina con 3 × 10 | A |
| P02 | Recargar editor | Nombre y ejercicio conservados | A |
| P03 | Horario > Lunes > rutina > Listo; recargar | Lunes contiene la rutina | A |
| P04 | Inicio > Cargar plan inicial, elegir y confirmar | Rutinas/horario corresponden al plan; historial previo preservado | P |
| P05 | Inicio > Crear mi propio plan | Llega al plan; edición/creación accesibles | O entrada identificada; recorrido específico P |
| P06 | Catálogo > Plan y detalle > Añadir a mi plan | Rutina elegida recibe ejercicio una vez | P, ambos puntos |
| P07 | Duplicar rutina; editar copia | Original independiente; IDs distintos; recarga conserva ambos | P |
| P08 | Reordenar ejercicios; superserie; desagrupar | Orden/grupo persisten y se reflejan al entrenar | P |
| P09 | Dos rutinas en un día; quitar una | Ambas se inician juntas; quitar no borra rutinas | P |
| P10 | Rotación; añadir rutinas/descanso; terminar sesión | Cola avanza según contrato, sin saltos al recargar | P |
| P11 | Cambiar rotación a semana fija; cancelar/confirmar | Cancelar conserva cola; confirmar cambia modo sin borrar rutinas | P |
| P12 | Eliminar rutina usada en plan/historial | Confirmación, horario consistente, historial legible | P, solo perfil desechable |
| P13 | Progresión, descarga y reglas por ejercicio | Valores válidos y persistentes; próximas sesiones coherentes | P, contrastar helpers puros |
| W01 | Inicio > Elegir otro entrenamiento > rutina | Tres series disponibles, sesión activa | A |
| W02 | Minimizar > Seguir > recargar; completar 3 series; terminar | Mismo entrenamiento; resumen; finalización única | A |
| W03 | Empezar tab en descanso y día con rutina | Selector o rutina correcta según horario | O selector; calendario completo P |
| W04 | Elegir rutina con Tab/Enter | Rutina alcanzable e iniciable por teclado | F, div sin semántica |
| W05 | Entrenamiento libre; añadir ejercicio | Sin necesidad de rutina; historial se guarda correctamente | P |
| W06 | Editar peso/reps, marcar y desmarcar serie | Estado y valores persisten al minimizar/recargar | P |
| W07 | Añadir/copiar/quitar serie y ejercicio | Conteos y navegación actualizados; sin editar otro ejercicio | P |
| W08 | Terminar parcialmente; cancelar confirmación | Cancelar mantiene sesión; confirmar guarda solo lo hecho | P |
| W09 | Descartar entrenamiento | No crea historial; elimina activo solo en perfil de prueba | P |
| W10 | Descanso iniciar/pausar/ajustar/saltar | Tiempo coherente; alerta una sola vez; control accesible | P |
| W11 | Esfuerzo RIR/RPE, nota de serie y sesión | Aparecen al reabrir registro; persisten en exportación | P |
| W12 | Cambiar Tarjetas/Lista/Focus | Mismos datos y serie actual; sin reiniciar sesión | P |
| W13 | Superserie y ejercicio cronometrado/cardio | Secuencia, unidades y validación según modalidad | P |
| H01 | Progreso > Todo 1; recargar historial | Un entrenamiento de 3 series | A |
| H02 | Abrir registro guardado desde Historial | Detalle contiene rutina/series correctas | A apertura; comparación detallada en export |
| H03 | Abrir desde recientes, calendario e Inicio hecho | Mismo registro; volver conserva contexto | P, tres entradas |
| H04 | Editar sesión guardada; salir y cancelar/guardar | Borrador y confirmación coherentes; sin duplicar registro | P |
| H05 | Registrar entrenamiento pasado | Fecha correcta; no temporizador activo; aparece en orden | P |
| H06 | Eliminar registro; cancelar y confirmar | Cancelar no cambia nada; confirmar actualiza métricas | P, solo desechable |
| A01 | Progreso tras primera sesión | Conteos 1; series reales; sin pesajes ficticios | O + H01 |
| A02 | Cambiar semana/30d/90d/todo y vistas de fatiga/fuerza | Periodo aplicado sin inventar datos; vacíos explícitos | P |
| A03 | Progreso > Balance estructural | Página renderiza; vacío/suficiencia explícitos | R |
| A04 | Varias sesiones y progresión/e1RM | Gráficas corresponden a registros/unidades y fórmula elegida | P |
| B01 | Inicio Registrar peso 72.5; guardar y recargar | 72,5 kg visible; export w=72.5 | A |
| B02 | Medidas > Registrar > Guardar vacío | Introduce al menos una medida; formulario abierto | A |
| B03 | Cintura 85; guardar y recargar | 85 cm; demás campos vacíos | A |
| B04 | Progreso Registrar/Meta/Todos los pesajes | Entradas equivalentes; meta y edición persisten | P |
| B05 | Medidas: negativo, texto, fecha futura/duplicada, grasa >100 | Rechazo comprensible, sin corrupción de registros | P |
| B06 | Campos: medida personalizada y selección | Formulario/gráfica actualizados; duplicados rechazados | P |
| B07 | Convertir kg/lb y cm/in; alternativa solo etiqueta | Conversión explícita; sin doble conversión al recargar | P |
| F01 | Progreso > Fotos > Abrir sin fotos | Estado vacío | R |
| F02 | Foto ficticia desde sesión terminada y galería | Mismo vínculo de sesión, persistencia de medio | P, fixture |
| F03 | Dos fotos, antes/después, vídeo y eliminación | Orden correcto; comparación accesible; límites/errores claros | P, fixtures |
| C01 | Inicio > En el gimnasio | Página sin tarjetas y acción para añadir | R |
| C02 | Importar QR ficticio, editar etiqueta, reordenar | Código decodificable, etiqueta y orden persistentes | P, fixture |
| C03 | Cámara denegada o imagen sin QR | Mensaje y recuperación; sin tarjeta corrupta | P, permisos/fixture |
| S01 | Ajustes buscar Tema | Resultado Tema accesible | A |
| S02 | Aspecto e Inicio > Claro; recargar | Tema light persistente | A |
| S03 | Cambiar idioma, nombres/instrucciones y volver | Traducción completa, estados conservados y locale correcto | P |
| S04 | Equipo/discos/mancuernas y ajustes finos | Inventario/valores persisten y afectan pantallas correspondientes | R páginas; mutaciones P |
| D01 | Datos y copias > Exportar JSON | Descarga real con rutina, 3 series hechas, peso y medida | A, runner valida archivo |
| D02 | Importar copia en segundo invitado limpio | Recupera mismos datos y medios según formato | P |
| D03 | JSON/ZIP corrupto y CSV de otra app | Error recuperable sin reemplazar estado válido | P |
| D04 | Importar con conflictos de datos | Cancelación segura; merge/reemplazo según decisión | P |
| D05 | Restablecer todo, cancelar/confirmar | Cancelación conserva; confirmación solo borra perfil desechable | P |
| X01 | Visitar admin, coach/setup y reminders como invitado | Home/Settings sin acceso privilegiado | R |
| X02 | Abrir coach/intake en frío como invitado | Redirigir o mostrar estado no disponible | F |
| X03 | Coach habilitado, consentimiento y error proveedor | Sin llamadas antes de consentimiento; errores recuperables | P, proveedor de prueba |
| X04 | Cuenta, dispositivos, API/MCP y sincronización offline | Contratos de acceso/propiedad y recuperación cumplidos | P, stack de prueba separado |
| X05 | PWA instalada/offline/actualización del SW | Arranca sin red y conserva datos; actualización recuperable | P |
| X06 | Android/iOS: alarmas, permisos, compartir, backup | Prueba en dispositivo real con permisos explícitos | P |

## Orden sugerido de ampliación

1. Corregir y automatizar L08/W04/X02 como regresiones esperadas, sin convertir el fallo actual en contrato.
2. Importación/restauración D02-D04: datos de invitado dependen del navegador y de sus copias.
3. Cancelar, editar y registrar sesiones pasadas W08-W09/H04-H06.
4. Rotación, superseries y progresión P08-P13/W13 con resultados contrastados contra tests de dominio.
5. Archivos/permisos, offline y autenticación con fixtures y cuentas desechables.

No adjuntar credenciales ni datos del usuario a evidencias. Una prueba pendiente conserva su estado hasta ejercer todos sus puntos de entrada relevantes y verificar efectos observables.
