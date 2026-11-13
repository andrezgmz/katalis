# Fuentes de la tubería de datos (Fase 0)

Todas son públicas, sin claves ni tokens. Cada consulta queda en `datos/registro.jsonl` con:
- la URL exacta y, si aplica, la consulta SoQL;
- la hora UTC;
- el número de filas;
- el `sha256` de la respuesta;
- el resultado.

La respuesta tal cual queda en `datos/crudo/<fuente>/<AAAA-MM-DD>/`. Solo se guarda si cambió frente a la anterior; si pasa de 200 KB se comprime con gzip, y al descomprimirla son los mismos bytes.

**Regla general:** si una fuente cambia de forma (columnas, tipos, estructura), la validación la detiene con un mensaje claro. La web conserva su último valor bueno y, en `main`, se abre el issue «Falla en la tubería: <fuente>». Ningún valor se escribe a mano.

## TRM · Superintendencia Financiera (datos.gov.co `32sa-8pi3`)

| | |
|---|---|
| Página oficial | https://www.datos.gov.co/d/32sa-8pi3 |
| Consulta | `https://www.datos.gov.co/resource/32sa-8pi3.json?$where=vigenciadesde >= '<hoy − 45 días>T00:00:00'&$order=vigenciadesde DESC&$limit=100` |
| Interfaz | API SODA de datos.gov.co (documentada) |
| Frecuencia | Diaria. La TRM del fin de semana se publica el viernes. |
| Formato | JSON: `valor`, `unidad` (COP), `vigenciadesde`, `vigenciahasta` |
| Controles | Columnas presentes; unidad COP; valor entre 2.000 y 8.000; vigencia no futura más de 1 día; sin fechas repetidas |
| Se publica | Último valor vigente hoy (Bogotá); los últimos 30 días quedan en `datos/indicadores/trm.json` |
| «Desactualizado» | Más de 7 días desde su vigencia |

## Tasa de política monetaria · Banco de la República (serie 59)

| | |
|---|---|
| Página oficial | https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/59/tasas_interes_politica_monetaria |
| Consulta | `https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/estadisticaEconomicaRestService/consultaInformacionSerie?idSerie=59` |
| Interfaz | **No es una API oficial.** Es el servicio que usa la propia página del portal; puede cambiar sin aviso. Lo cubre la validación de estructura. Decisión de Andrés (12-nov-2026): se queda y no se exploran más servicios no documentados. |
| Frecuencia | Serie diaria; la tasa cambia por decisión de la Junta Directiva |
| Formato | JSON: lista con una serie (`id`, `unidadCorta`, `fuente`, `fechaUltimoCargue`, `data` = pares [fecha en milisegundos, valor]). Unos 560 KB, se guarda comprimido. |
| Controles | Una sola serie con `id` 59 y unidad `%`; al menos 100 datos; último valor entre 0 % y 30 %; fecha no futura |
| Se publica | Último valor y la fecha desde la que rige |
| «Desactualizado» | Más de 45 días sin una consulta exitosa |
| Certificado | El servidor no envía su certificado intermedio (ver «Certificado intermedio» abajo) |

**Alternativa documentada (no usada todavía):**
- El Banco publica un servicio **SDMX** oficial: «Guía para la consulta de información económica y financiera publicada por el Banco de la República mediante el uso del servicio web SDMX», versión 3.0, agosto de 2025, en https://suameca.banrep.gov.co/archivos/webservices/documento_tecnico_ws_consumo_sdmx.pdf.
- Según la guía, está disponible para el público en general y no requiere registro.
- Endpoint REST: `https://totoro.banrep.gov.co/nsi-jax-ws/rest/data`.
- Trae la tasa de política monetaria (`DF_CBR_DAILY_LATEST` y `DF_CBR_DAILY_HIST`), la TRM, el IBR, la DTF y la UVR, pero **no el IPC**.
- El portal anuncia una versión nueva de esa API desde el 26-oct-2026; la anterior queda disponible hasta el 15-nov-2026.
- Cuando la versión nueva esté estable, conviene pasar la tasa del Emisor a SDMX, que es documentado y mucho más liviano. Esa decisión es de Andrés.

## IPC e inflación anual · DANE

| | |
|---|---|
| Página oficial (URL fija) | https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc |
| Archivo | Anexo de índices del último mes publicado. Ejemplo: `https://www.dane.gov.co/files/operaciones/IPC/oct2026/anex-IPC-Indices-oct2026.xlsx` |
| Cómo cambia la URL | Cada mes cambian la carpeta y el nombre: `/files/operaciones/IPC/<mes><año>/anex-IPC-Indices-<mes><año>.xlsx`, con el mes en tres letras (`ene` … `dic`). La tubería lee la página oficial y toma el único enlace que cumple ese patrón. Si no hay ninguno o hay más de uno, para con error. |
| Por qué el DANE | El IPC lo produce el DANE. El SDMX del Banco de la República no lo trae (ver arriba). Decisión de Andrés, 12-nov-2026, paso b. |
| Frecuencia | Mensual, a inicios del mes siguiente |
| Formato | xlsx con una hoja (`IndicesIPC`): fila «Mes», años desde 2003 en columnas, meses Enero…Diciembre en filas, «Base Diciembre de 2018 = 100». Se lee con la librería estándar (zip + XML). |
| Fecha de publicación | Encabezado HTTP `Last-Modified` del archivo. Ejemplo: `Mon, 09 Nov 2026 22:41:00 GMT`, que coincide con la fecha de modificación interna del xlsx. |
| Controles | Fila «Mes» única; base dic-2018 = 100; años consecutivos; los 12 meses en orden; índices > 0; el mes de la URL igual al último mes con dato; fecha de publicación presente y no futura; variación anual entre −5 % y 40 % |
| Cálculo | Variación anual = (índice del mes / índice del mismo mes del año anterior − 1) × 100 |
| Contraste | Octubre de 2026: índice 161,32 contra 151,76 de octubre de 2025, es decir **6,30 %** anual. La variación mensual calculada (0,20 %) coincide con la del anexo oficial de variaciones del DANE (`anex-IPC-Variacion-oct2026.xlsx`: 0,2). |
| «Desactualizado» | Más de 45 días desde su publicación |

## Cartera · Superintendencia Financiera (datos.gov.co `rvii-eis8`)

Solo se extrae y se valida en esta fase; se publica en la Fase 1.

| | |
|---|---|
| Página oficial | https://www.datos.gov.co/d/rvii-eis8 |
| Consultas | 1) `$select=max(fecha_corte) as ultimo` · 2) `$where=fecha_corte = '<último corte>' AND renglon = '5'&$order=tipo_entidad, codigo_entidad, unicap&$limit=10000`. Las dos quedan exactas en `registro.jsonl` y en `consulta.json`. |
| Qué se guarda | Solo el último corte filtrado a `renglon = 5` (total por producto), unas 630 filas (decisión de Andrés, 12-nov-2026) |
| Frecuencia | Mensual. El corte del 31-ago-2026 era el último disponible el 12-nov-2026. |
| Controles | Columnas presentes; solo renglón 5; un solo corte; menos de 10.000 filas (si llega al límite, el corte podría estar incompleto); total entre 500 y 2.000 billones; más de 20 bancos (`tipo_entidad = 1`) |

## Certificado intermedio del Banco de la República

El servidor `suameca.banrep.gov.co` entrega su certificado y la raíz «DigiCert Global Root G2», pero **no el intermedio** «GeoTrust EV RSA CA G2». Con `openssl s_client` se ve `Verify return code: 21 (unable to verify the first certificate)`. Windows completa la cadena solo; los servidores de GitHub Actions no (error 60 de `curl`).

**Solución aprobada por Andrés (12-nov-2026):**
- Guardar el intermedio público en `scripts/tuberia/certificados/GeoTrustEVRSACAG2.crt.pem`.
- Usarlo **solo** para ese host, en un contexto TLS propio que suma ese certificado a los del sistema (`comun.contexto_banrep`).
- La verificación del certificado y del nombre del host sigue activa: nunca `verify=False`.

| | |
|---|---|
| Origen | https://cacerts.digicert.com/GeoTrustEVRSACAG2.crt.pem. Es el mismo contenido que `GeoTrustEVRSACAG2.crt`, la URL que declara el propio certificado del Banco en su campo AIA. |
| Sujeto / emisor | `CN=GeoTrust EV RSA CA G2, O=DigiCert Inc, C=US` / `CN=DigiCert Global Root G2` |
| SHA-256 | `2D:14:0F:20:B8:A9:6E:2B:4D:2F:1C:C5:AC:A5:E5:A1:E7:DC:56:A7:49:1E:51:09:06:96:0F:38:D2:D2:1A:EF` (fijada en `comun.CERT_BANREP_SHA256`; si el archivo cambia, el Banco de la República falla) |
| SHA-1 | `68:7D:4A:4D:47:01:4F:91:21:7E:4A:06:2B:BF:9D:23:83:58:94:3E` |
| Serie | `0D:60:12:62:C8:A7:72:1A:6E:AB:03:61:E5:61:95:80` |
| Vigencia | 2-jul-2020 a **2-jul-2030** (12:42:57 UTC) |
| Contraste con DigiCert | La página oficial https://knowledge.digicert.com/general-information/digicert-trusted-root-authority-certificates (antes digicert.com/kb/digicert-root-certificates.htm), en la entrada «GeoTrust EV RSA CA G2», lista la misma SHA-256, SHA-1, serie y vencimiento. Los tres identificadores coinciden con el archivo guardado. Nota del 12-nov-2026: esa página es larga y su entrada se leyó a través de un resumen automático, no del texto literal. Conviene que una persona la confirme a ojo una vez. |
| Coincide con el Banco | El identificador de clave del intermedio (`28:D2:CF:EE:…:5D:1F`) es el mismo que pide el certificado del Banco, y `openssl verify` da `OK`. |
| Vencimiento | 2-jul-2030 12:42:57 UTC (campo `notAfter`, leído con `openssl`). Va fijo en `comun.py` (`CERT_BANREP_VENCE`) junto a la huella, sin usar APIs privadas de `ssl`: si se cambia el archivo, hay que actualizar las dos. La tubería revisa la fecha en cada ejecución y, **30 días antes** (desde el 2-jun-2030), abre en `main` el issue «Certificado por vencer: GeoTrust EV RSA CA G2». Si el Banco corrige su servidor y envía la cadena completa, este archivo sobra y no estorba. |

## Controles comunes a todas las fuentes

- **Solo https y sin redirecciones raras:** `comun.descargar` rechaza cualquier URL que no sea `https://`, y cualquier redirección a otro esquema (por ejemplo `http://`) o a otro host. Las dos cosas son un error de la fuente: no avanza y la web conserva el último valor bueno.
- **Saltos anómalos** (`saltos.py`): cada valor nuevo se compara con el último valor bueno publicado en `datos/limpio/` y `datos/indicadores/`. Un salto no se publica solo: espera la aprobación de Andrés (ver README, «Aprobar un salto anómalo»). Umbrales: TRM ±5 %; tasa del Emisor múltiplo de 0,25 puntos y máximo 1 punto; inflación anual 1,5 puntos; cualquier valor ya publicado de un periodo pasado que cambie (TRM de días anteriores, cambios de la tasa del Emisor, índices del IPC); cartera ±10 % (Fase 1).
- **Segunda fuente para la TRM: pendiente.** La regla está escrita y probada (`saltos.contraste_trm`: si la TRM de la SFC y la del Banco de la República difieren más de 0,1 % en la última fecha común, es salto). Falta la consulta al SDMX del Banco en su **versión nueva**: al 13-nov-2026 no se encontró documentación oficial de esa versión (la guía publicada es la 3.0, de la versión anterior, y la página de servicios web del Banco responde 404). No se conecta a un servicio sin documentar.
