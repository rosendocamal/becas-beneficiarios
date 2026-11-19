import csv
from pathlib import Path

import pytest

from becas.config import CAMPOS
from becas.descarga import ruta_raw
from becas.limpieza import limpiar_recurso, ruta_intermedia, ruta_unificada, unificar_anio
from becas.modelos import Recurso

CONTENIDO = (
    "TRIMESTRE;CVE_EDO;NOM_EDO;CVE_MUN;NOM_MUN;CVE_LOC;NOM_LOC;BECA;FECHA_ALTA\n"
    "4;01;Aguascalientes;005;Jesus Maria;0041;Jesus Gomez Portugal;5700;01/02/2022\n"
    "4;01;Aguascalientes;005;Jesus Maria;0042;Otro Lugar;abc;fecha-invalida\n"
)


def crear_raw(recurso: Recurso, raiz: Path, contenido: str = CONTENIDO) -> Path:
    ruta = ruta_raw(recurso, raiz)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_limpiar_recurso(tmp_path: Path, recurso: Recurso) -> None:
    origen = crear_raw(recurso, tmp_path / "raw")
    destino = ruta_intermedia(recurso, tmp_path / "intermedios")
    total = limpiar_recurso(recurso, origen, destino)
    assert total == 2
    with destino.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert tuple(filas[0].keys()) == CAMPOS
    assert filas[0]["anio"] == "2022"
    assert filas[0]["programa"] == "S072"
    assert filas[0]["fecha_alta"] == "2022-02-01"
    assert filas[0]["beca"] == "5700.0"
    assert filas[1]["beca"] == ""
    assert filas[1]["fecha_alta"] == ""


@pytest.mark.parametrize("concurrencia", [1, 2])
def test_unificar_anio(tmp_path: Path, recurso: Recurso, concurrencia: int) -> None:
    segundo = Recurso(
        anio=2022,
        programa="S311",
        cve_edo="02",
        nom_edo="Baja California",
        trimestre=4,
        url=recurso.url.replace("s072", "s311").replace("S072", "S311").replace("01_", "02_"),
        id_recurso="abc-125",
        nombre="Beneficiarios en Baja California (4to. trim. 2022)",
    )
    crear_raw(recurso, tmp_path / "raw")
    crear_raw(segundo, tmp_path / "raw")
    destino = unificar_anio(
        2022,
        [recurso, segundo],
        raiz_raw=tmp_path / "raw",
        raiz_intermedia=tmp_path / "intermedios",
        raiz_csv=tmp_path / "csv",
        concurrencia=concurrencia,
    )
    assert destino == ruta_unificada(2022, tmp_path / "csv")
    with destino.open(encoding="utf-8", newline="") as archivo:
        lector = csv.reader(archivo)
        assert next(lector) == list(CAMPOS)
        assert len(list(lector)) == 4
