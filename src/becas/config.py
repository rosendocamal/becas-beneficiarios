import re
from pathlib import Path

URL_PRINCIPAL = "https://www.datos.gob.mx"
RUTA_API = "api/3/action/"
ORGANIZACION = "cnbbbj"
PATRON_DATASET = re.compile(
    r"^programa_nacional_becas_bienestar_benito_juarez_(\d{4})_programa_(s\d{3})$"
)

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data"
RAW = DATOS / "raw" / "datos_gob_mx"
INTERMEDIOS = DATOS / "intermedios" / "datos_gob_mx"
ENTREGABLES = DATOS / "entregables"
CSV_ANUALES = ENTREGABLES / "csv"
BASE_DATOS = ENTREGABLES / "db"
BASE_GLOBAL = BASE_DATOS / "becas_global.db"
BASE_POR_ANIO = BASE_DATOS / "por_anio"
MANIFIESTO = RAW / "manifiesto.json"

TABLA = "BENEFICIARIOS"
CAMPOS = (
    "anio",
    "programa",
    "trimestre",
    "cve_edo",
    "nom_edo",
    "cve_mun",
    "nom_mun",
    "cve_loc",
    "nom_loc",
    "beca",
    "fecha_alta",
)
CAMPOS_TEXTO = ("cve_edo", "nom_edo", "cve_mun", "nom_mun", "cve_loc", "nom_loc")
TIPOS = {
    "anio": "INTEGER NOT NULL",
    "programa": "TEXT NOT NULL",
    "trimestre": "INTEGER NOT NULL",
    "cve_edo": "TEXT",
    "nom_edo": "TEXT",
    "cve_mun": "TEXT",
    "nom_mun": "TEXT",
    "cve_loc": "TEXT",
    "nom_loc": "TEXT",
    "beca": "REAL",
    "fecha_alta": "TEXT",
}
INDICES = (
    "CREATE INDEX IF NOT EXISTS idx_beneficiarios_anio ON BENEFICIARIOS (anio)",
    "CREATE INDEX IF NOT EXISTS idx_beneficiarios_programa ON BENEFICIARIOS (programa)",
    "CREATE INDEX IF NOT EXISTS idx_beneficiarios_edo ON BENEFICIARIOS (cve_edo)",
)
