# Seguridad

Para reportar una vulnerabilidad escriba a hola@katalispartners.com.co con el asunto «Seguridad web Katalis». No abra un issue público. Respondemos en un máximo de 5 días hábiles.

## Controles del sitio

| Control | Cómo se cumple |
|---|---|
| Sin datos personales | No hay formularios, cookies, analítica ni píxeles. El contacto sale a WhatsApp, correo o LinkedIn. |
| Sin terceros en tiempo de ejecución | Letras, Chart.js y cifras se sirven desde este repositorio. La política de seguridad de contenido (CSP) bloquea cualquier otro origen. |
| Sin código en línea | Ningún `<script>` ni `style=` en el HTML: la CSP no necesita `unsafe-inline`. El tablero arma todo con `textContent`, nunca con `innerHTML`. |
| Dependencias fijadas | Chart.js 4.4.1 copiado en `assets/vendor/`, SHA-256 `74401d738dd3e03ee5dfb3b6841210fe2c4ead8a960c4011ca4ba0b78a9fd8f3`. Se cambia solo con revisión. |
| Cambios trazables | Todo cambio entra por commit en `main` con su autor y fecha, y con la prueba `node pruebas/verificar.mjs` en 0 fallas. Sin `--force` ni reescritura de historial. |
| Sin secretos | El sitio no usa claves. Si alguna vez se necesita una, va en los secretos de GitHub, nunca en el código. |

## Límite conocido

GitHub Pages no permite encabezados HTTP propios. La CSP va en una etiqueta `<meta>`, que no cubre `frame-ancestors` (protección contra incrustar el sitio en otra página) ni HSTS. Se resuelve al conectar el dominio propio detrás de Cloudflare (ver `README.md`, paso 3 del plan).
