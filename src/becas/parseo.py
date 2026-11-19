import re
from datetime import datetime

from .catalogos import ENTIDADES

PATRON_TRIMESTRE = re.compile(r"(?<!\d)([1-4])(?:er|do|to|ro|o)?[\s._-]*trim", re.I)
PATRON_TRIMESTRE_INVERSO = re.compile(r"trim[\s._-]*([1-4])", re.I)
PATRON_ORDINAL = re.compile(r"(?<!\d)([1-4])(?:er|do|to|ro|o)?(?!\d)", re.I)

ALIAS = {
    "programa": "programa",
    "trimestre": "trimestre",
    "trim": "trimestre",
    "cveedo": "cve_edo",
    "cve_edo": "cve_edo",
    "cveentidad": "cve_edo",
    "cve_entidad": "cve_edo",
    "nomedo": "nom_edo",
    "nom_edo": "nom_edo",
    "nombreedo": "nom_edo",
    "cvemun": "cve_mun",
    "cve_mun": "cve_mun",
    "cvemunicipio": "cve_mun",
    "nommun": "nom_mun",
    "nom_mun": "nom_mun",
    "nombremunicipio": "nom_mun",
    "cveloc": "cve_loc",
    "cve_loc": "cve_loc",
    "cvelocalidad": "cve_loc",
    "nomloc": "nom_loc",
    "nom_loc": "nom_loc",
    "nombrelocalidad": "nom_loc",
    "beca": "beca",
    "monto": "beca",
    "fechaalta": "fecha_alta",
    "fecha_alta": "fecha_alta",
    "fecha": "fecha_alta",
}


def normalizar_encabezado(valor: str) -> str:
    clave = re.sub(r"[\s\-_]", "", str(valor).strip().lower())
    return ALIAS.get(clave, clave)


def extraer_trimestre(texto: str) -> int | None:
    for patron in (PATRON_TRIMESTRE, PATRON_TRIMESTRE_INVERSO, PATRON_ORDINAL):
        coincidencia = patron.search(texto)
        if coincidencia:
            return int(coincidencia.group(1))
    return None


def extraer_estado(texto: str) -> tuple[str, str] | None:
    partes = [parte for parte in re.split(r"[\s_/-]+", texto.strip()) if parte]
    for indice, parte in enumerate(partes):
        if parte.lower() != "edo" or indice + 1 >= len(partes):
            continue
        if not partes[indice + 1].isdigit():
            continue
        clave = partes[indice + 1].zfill(2)
        nombres: list[str] = []
        for token in partes[indice + 2 :]:
            if extraer_trimestre(token) or token.lower().endswith(".csv"):
                break
            nombres.append(token)
        nombre = " ".join(nombres).strip(" .")
        return clave, ENTIDADES.get(clave, nombre.title())
    return None


def normalizar_fecha(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip().strip('"').replace("/", "-")
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
        try:
            fecha = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        if 1900 <= fecha.year <= 2100:
            return fecha.isoformat()
    return None


def normalizar_beca(valor: object) -> float | None:
    texto = str(valor or "").strip().strip('"').replace(",", "").replace("$", "")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def normalizar_texto(valor: object) -> str | None:
    texto = " ".join(str(valor or "").strip().strip('"').split())
    return texto or None


def detectar_delimitador(primera_linea: str) -> str:
    return ";" if primera_linea.count(";") > primera_linea.count(",") else ","
