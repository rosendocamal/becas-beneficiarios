from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Recurso:
    anio: int
    programa: str
    cve_edo: str
    nom_edo: str
    trimestre: int
    url: str
    id_recurso: str
    nombre: str
    actualizado: str | None = None

    @property
    def nombre_archivo(self) -> str:
        return f"{self.programa.lower()}_edo_{self.cve_edo}_q{self.trimestre}.csv"

    def to_dict(self) -> dict[str, object]:
        return {
            "anio": self.anio,
            "programa": self.programa,
            "cve_edo": self.cve_edo,
            "nom_edo": self.nom_edo,
            "trimestre": self.trimestre,
            "url": self.url,
            "id_recurso": self.id_recurso,
            "nombre": self.nombre,
            "actualizado": self.actualizado,
        }

    @classmethod
    def from_dict(cls, datos: dict[str, object]) -> "Recurso":
        actualizado = datos.get("actualizado")
        return cls(
            anio=int(str(datos["anio"])),
            programa=str(datos["programa"]),
            cve_edo=str(datos["cve_edo"]),
            nom_edo=str(datos["nom_edo"]),
            trimestre=int(str(datos["trimestre"])),
            url=str(datos["url"]),
            id_recurso=str(datos["id_recurso"]),
            nombre=str(datos["nombre"]),
            actualizado=str(actualizado) if actualizado else None,
        )
