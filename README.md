# Sitio web de Katalis Partners

Sitio estático de Gómez Hernández Consulting S.A.S. (Katalis Partners). Mientras se compra el dominio vive en `https://andrezgmz.github.io/katalis/`.

No usa frameworks ni paso de compilación: HTML, CSS y JavaScript que el navegador lee tal cual. Dos programas cortos en Python arman las páginas y las cifras.

## Estructura

| Carpeta | Qué tiene |
|---|---|
| `contenido/` | El texto de cada página. **Aquí se edita.** |
| `scripts/construir_sitio.py` | Pone encabezado, pie, contacto y política de seguridad a cada página de `contenido/` y escribe el HTML final. |
| `scripts/actualizar_cifras.py` | Convierte el Excel de cifras en `datos/cifras.json`. |
| `datos/cifras.json` | Las cifras que lee el tablero. No se edita a mano. |
| `assets/` | Estilos, letras, Chart.js y el código del tablero. |
| `pruebas/verificar.mjs` | La prueba que debe dar 0 fallas antes de publicar. |

Los `.html` de la raíz y de `blog/` se generan: no se editan a mano.

## Cambiar un texto

1. Edite el archivo en `contenido/`.
2. `python scripts/construir_sitio.py`
3. `node pruebas/verificar.mjs` → debe decir `0 fallas`.
4. Commit y push a `main`. GitHub Pages publica en uno o dos minutos.

El teléfono, el correo, LinkedIn y el enlace de Hotmart están al inicio de `scripts/construir_sitio.py`.

## Actualizar las cifras

1. Ponga el Excel nuevo en `datos/fuente/Datos_graficos_economia_solidaria.xlsx` (esa carpeta no se sube a GitHub).
2. `python scripts/actualizar_cifras.py`
3. Revise las referencias de inflación al inicio del mismo programa.
4. `node pruebas/verificar.mjs` y publique.

## Arquitectura de datos

```
Reporte oficial (Supersolidaria, BanRep, Banca de las Oportunidades)
   → Excel de trabajo validado (solo en el equipo, no en GitHub)
   → scripts/actualizar_cifras.py  (copia, no recalcula)
   → datos/cifras.json             (público, con fuente por serie)
   → assets/js/cifras.js           (dibuja; cuentas simples como variaciones y días)
   → cifras.html
```

Los plazos del Decreto 769 de 2025 se calculan en el navegador desde la vigencia (9 de julio de 2025), así nunca quedan desactualizados.

## Seguridad

Ver `SECURITY.md`.
