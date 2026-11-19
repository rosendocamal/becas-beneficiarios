from dataclasses import dataclass
from typing import Any

import pytest

from becas.modelos import Recurso


@dataclass
class RespuestaFalsa:
    contenido: dict[str, Any]

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.contenido


class SesionFalsa:
    def __init__(self, paginas: dict[int, dict[str, Any]]) -> None:
        self.paginas = paginas
        self.llamadas: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: Any = None) -> Any:
        self.llamadas.append({"url": url, "params": params or {}, "timeout": timeout})
        inicio = int((params or {}).get("start", 0))
        return RespuestaFalsa(self.paginas[inicio])


@pytest.fixture
def recurso() -> Recurso:
    return Recurso(
        anio=2022,
        programa="S072",
        cve_edo="01",
        nom_edo="Aguascalientes",
        trimestre=4,
        url=(
            "https://repodatos.atdt.gob.mx/api_update/cnbbbj/"
            "programa_nacional_becas_bienestar_benito_juarez_2022_programa_s072/"
            "S072_EDO_01_Aguascalientes_4to_Trim2022.csv"
        ),
        id_recurso="abc-123",
        nombre="Beneficiarios en Aguascalientes (4to. trim. 2022)",
        actualizado="2025-12-01T00:00:00Z",
    )


@pytest.fixture
def paquete() -> dict[str, Any]:
    return {
        "name": "programa_nacional_becas_bienestar_benito_juarez_2022_programa_s072",
        "metadata_modified": "2025-12-01T00:00:00Z",
        "resources": [
            {
                "id": "abc-123",
                "name": "Beneficiarios en Aguascalientes (4to. trim. 2022)",
                "url": (
                    "https://repodatos.atdt.gob.mx/api_update/cnbbbj/"
                    "programa_nacional_becas_bienestar_benito_juarez_2022_programa_s072/"
                    "S072_EDO_01_Aguascalientes_4to_Trim2022.csv"
                ),
                "last_modified": "2025-12-02T00:00:00Z",
            },
            {
                "id": "abc-124",
                "name": "Beneficiarios en Baja California (4to. trim. 2022)",
                "url": (
                    "https://repodatos.atdt.gob.mx/api_update/cnbbbj/"
                    "programa_nacional_becas_bienestar_benito_juarez_2022_programa_s072/"
                    "S072_EDO_02_Baja_California_4to_Trim2022.csv"
                ),
            },
            {"id": "no-csv", "name": "Documentación", "url": "https://ejemplo.mx/doc.pdf"},
        ],
    }
