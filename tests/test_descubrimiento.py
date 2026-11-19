from pathlib import Path
from typing import Any

from becas import descubrimiento
from tests.conftest import SesionFalsa


def test_procesar_paquete(paquete: dict[str, Any]) -> None:
    recursos = descubrimiento.procesar_paquete(paquete)
    assert len(recursos) == 2
    assert recursos[0].anio == 2022
    assert recursos[0].programa == "S072"
    assert recursos[0].cve_edo == "01"
    assert recursos[0].trimestre == 4
    assert recursos[0].id_recurso == "abc-123"
    assert recursos[1].cve_edo == "02"


def test_procesar_paquete_ignora_datasets_ajenos(paquete: dict[str, Any]) -> None:
    paquete["name"] = "otro_conjunto_de_datos"
    assert descubrimiento.procesar_paquete(paquete) == []


def test_descubrir_pagina_y_filtra(paquete: dict[str, Any]) -> None:
    paginas = {
        0: {
            "success": True,
            "result": {
                "count": 2,
                "results": [paquete, {"name": "plan_apertura_datos_cnbbbj", "resources": []}],
            },
        },
    }
    sesion = SesionFalsa(paginas)
    recursos = descubrimiento.descubrir(sesion=sesion)
    assert len(recursos) == 2
    assert [recurso.cve_edo for recurso in recursos] == ["01", "02"]
    assert sesion.llamadas[0]["params"]["fq"] == "organization:cnbbbj"


def test_manifiesto_ida_y_vuelta(tmp_path: Path, paquete: dict[str, Any]) -> None:
    recursos = descubrimiento.procesar_paquete(paquete)
    ruta = descubrimiento.guardar_manifiesto(recursos, tmp_path / "manifiesto.json")
    assert descubrimiento.cargar_manifiesto(ruta) == recursos


def test_url_api() -> None:
    assert descubrimiento.url_api("https://www.datos.gob.mx/") == (
        "https://www.datos.gob.mx/api/3/action/"
    )


def test_crear_sesion_incluye_headers_de_navegador() -> None:
    sesion = descubrimiento.crear_sesion()
    assert sesion.headers["User-Agent"].startswith("Mozilla/5.0")
    assert "es-MX" in sesion.headers["Accept-Language"]
    assert "application/json" in sesion.headers["Accept"]
