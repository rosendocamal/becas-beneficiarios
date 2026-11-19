import csv
from pathlib import Path
from typing import Any, cast

import requests

from becas import descarga
from becas.modelos import Recurso

CONTENIDO = b"col1,col2,col3,col4,col5\n1,2,3,4,5\n"
CAMPOS_DATASTORE = [
    "trimestre",
    "cve_edo",
    "nom_edo",
    "cve_mun",
    "nom_mun",
    "cve_loc",
    "nom_loc",
    "beca",
    "fecha_alta",
]
FILAS_DATASTORE = [
    [
        "4",
        "01",
        "Aguascalientes",
        "005",
        "Jesus Maria",
        "0041",
        "Jesus Gomez",
        "5700",
        "2022-02-01",
    ],
    [
        "4",
        "02",
        "Baja California",
        "003",
        "Tijuana",
        "0123",
        "Otra Localidad",
        "1500",
        "2022-02-01",
    ],
]


class RespuestaDescargaFalsa:
    def __init__(self, contenido: bytes) -> None:
        self.contenido = contenido

    def __enter__(self) -> "RespuestaDescargaFalsa":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [self.contenido]


class SesionDescargaFalsa:
    def __init__(self, datos: dict[str, bytes]) -> None:
        self.datos = datos

    def get(self, url: str, **kwargs: Any) -> RespuestaDescargaFalsa:
        return RespuestaDescargaFalsa(self.datos[url])


class RespuestaJsonFalsa:
    def __init__(self, contenido: dict[str, Any]) -> None:
        self.contenido = contenido

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.contenido


class SesionDatastoreFalsa:
    def __init__(self, campos: list[str], filas: list[list[str]]) -> None:
        self.campos = campos
        self.filas = filas
        self.llamadas: list[dict[str, Any]] = []

    def get(
        self, url: str, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> RespuestaJsonFalsa:
        datos = dict(params or {})
        self.llamadas.append(datos)
        if datos.get("limit") == 1 and "records_format" not in datos:
            campos = [{"id": "_id"}, *({"id": campo} for campo in self.campos)]
            return RespuestaJsonFalsa(
                {"success": True, "result": {"total": len(self.filas), "fields": campos}}
            )
        inicio = int(datos["offset"])
        fin = inicio + int(datos["limit"])
        pagina = "\n".join(",".join(fila) for fila in self.filas[inicio:fin])
        if pagina:
            pagina += "\n"
        return RespuestaJsonFalsa(
            {"success": True, "result": {"total": len(self.filas), "records": pagina}}
        )


def descargar_directa_falsa(recurso: Recurso, destino: Path, fragmento: int) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(CONTENIDO)
    return destino


def test_descargar_en_paralelo(tmp_path: Path, recurso: Recurso) -> None:
    segundo = Recurso(
        anio=2022,
        programa="S311",
        cve_edo="02",
        nom_edo="Baja California",
        trimestre=4,
        url=recurso.url.replace("s072", "s311").replace("01_", "02_"),
        id_recurso="abc-125",
        nombre="Beneficiarios en Baja California (4to. trim. 2022)",
    )
    datos = {recurso.url: CONTENIDO, segundo.url: CONTENIDO}

    def fabricar() -> requests.Session:
        return cast(requests.Session, SesionDescargaFalsa(datos))

    rutas = descarga.descargar(
        [recurso, segundo],
        raiz=tmp_path / "raw",
        concurrencia=2,
        fabricar_sesion=fabricar,
        fuente="directo",
        descargar_directa=descargar_directa_falsa,
    )
    assert rutas == [
        descarga.ruta_raw(recurso, tmp_path / "raw"),
        descarga.ruta_raw(segundo, tmp_path / "raw"),
    ]
    assert all(ruta.read_bytes() == CONTENIDO for ruta in rutas)


class SesionSinDatastore:
    def get(self, url: str, **kwargs: Any) -> Any:
        raise requests.HTTPError("404 Client Error")


def test_datastore_ausente_cae_a_descarga_directa(tmp_path: Path, recurso: Recurso) -> None:
    destino = descarga.ruta_raw(recurso, tmp_path / "raw")
    llamadas: list[Path] = []

    def directa(recurso: Recurso, ruta: Path, fragmento: int) -> Path:
        llamadas.append(ruta)
        return descargar_directa_falsa(recurso, ruta, fragmento)

    resultado = descarga.descargar_recurso(
        recurso,
        destino,
        cast(requests.Session, SesionSinDatastore()),
        fuente="datastore",
        descargar_directa=directa,
    )
    assert resultado == destino
    assert llamadas == [destino]
    assert resultado.read_bytes() == CONTENIDO


def test_descargar_datastore(tmp_path: Path, recurso: Recurso) -> None:
    sesion = SesionDatastoreFalsa(CAMPOS_DATASTORE, FILAS_DATASTORE)
    destino = descarga.ruta_raw(recurso, tmp_path / "raw")
    ruta = descarga.descargar_recurso(
        recurso,
        destino,
        cast(requests.Session, sesion),
        fuente="datastore",
    )
    with ruta.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.reader(archivo))
    assert filas[0] == CAMPOS_DATASTORE
    assert filas[1:] == FILAS_DATASTORE
    assert sesion.llamadas[0]["limit"] == 1
    assert sesion.llamadas[1]["limit"] == descarga.LIMITE_DATASTORE
    assert sesion.llamadas[1]["fields"] == ",".join(CAMPOS_DATASTORE)
    assert "_id" not in sesion.llamadas[1]["fields"]
