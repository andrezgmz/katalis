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

## Tubería de datos (Katalis Cifras · Fase 0: Pulso macro)

Los datos llegan solos desde fuentes oficiales y pasan por 4 capas antes de llegar a la web. Las fuentes, sus URL y qué pasa si cambian están en `scripts/tuberia/FUENTES.md`.

```
Fuente oficial (SFC/datos.gov.co, Banco de la República, DANE)
   → datos/crudo/<fuente>/<AAAA-MM-DD>/  respuesta tal cual (nunca se edita)      extraer.py
   → datos/limpio/<fuente>.json          formato común, números convertidos      validar.py
   → datos/indicadores/<fuente>.json     cálculos listos                         calcular.py
   → datos/web/macro.json                lo único que lee la web                 empaquetar.py
   → scripts/construir_sitio.py          franja «Pulso macro» en las 11 páginas
datos/registro.jsonl: una línea por fuente y ejecución (URL, consulta, hora UTC, filas, sha256, resultado)
```

- **Correr a mano:** `python scripts/tuberia/correr.py`, después `python scripts/construir_sitio.py` y `node pruebas/verificar.mjs`. Solo usa la librería estándar de Python y no necesita claves.
- **Pruebas de los validadores:** `python -m unittest discover -s pruebas -p "test_*.py"`.
- **Si una fuente falla:** no avanza, las demás siguen y la web conserva su último valor bueno. Si un dato pasa del plazo (TRM 7 días; tasa del Emisor 45 días sin consulta exitosa; IPC 45 días desde su publicación), la franja lo marca como «desactualizado».
- **Automático:** `.github/workflows/datos.yml` corre todos los días a las 6:17 a. m. de Bogotá (11:17 UTC) y también a mano (`workflow_dispatch`).
  - En `main` (modo publicación): si todo pasa, hace commit «datos: corte AAAA-MM-DD» y abre o actualiza un issue «Falla en la tubería: <fuente>» por cada fuente que falló. Los issues tienen que estar activados en el repositorio.
  - En cualquier otra rama (modo prueba): no hace commit ni abre issues; deja el resultado como artifact.

**Ojo con la protección de `main`:** el robot hace push directo a `main` con el `GITHUB_TOKEN`. Hoy se puede porque la protección solo bloquea `--force` y el borrado. Si después se exigen PR o revisiones en `main`, el robot necesitará una de dos cosas:
- una excepción para GitHub Actions en la regla de protección;
- o cambiar el paso «Publicar» para que abra un PR con auto-merge, que hoy está apagado en el repositorio.

## Seguridad

Ver `SECURITY.md`.
