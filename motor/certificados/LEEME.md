# Certificados intermedios públicos

Algunos servidores oficiales no envían la cadena completa de su certificado y la verificación TLS falla
(«unable to get local issuer certificate»). En lugar de desactivar la verificación, se añaden aquí los
intermedios públicos que faltan. `motor/http.py` los junta con las raíces de `certifi`.

Cada intermedio se descargó de la dirección de su emisor (AIA) con `motor/provinciales/sonda_tls.py` y se
comprobó con `openssl verify -CAfile certifi` que está firmado por una raíz de `certifi`.

| Fichero | Para | Emisor (raíz en certifi) | Caduca | Huella SHA-256 |
|---|---|---|---|---|
| sectigo-public-server-authentication-ca-ov-r36.pem | www.diputaciodetarragona.cat (BOP de Tarragona) | Sectigo Public Server Authentication Root R46 | 21/03/2036 | 65:42:D1:76:BE:D5:0F:19:3C:0C:E2:97:AE:44:EC:D8:A0:A8:6B:EC:2E:DE:68:27:69:34:40:59:B4:E7:85:30 |
| globalsign-gcc-r6-alphassl-ca-2025.pem | bop.dipucr.es (BOP de Ciudad Real) | GlobalSign Root CA - R6 | 21/05/2027 | A8:83:55:92:31:F8:38:8D:AF:35:CE:41:C8:10:10:40:AE:8F:D9:B6:56:43:42:47:B9:47:5A:F5:92:CC:08:CA |

Revisar antes de la caducidad: si el servidor cambia de certificado, puede necesitar otro intermedio.
