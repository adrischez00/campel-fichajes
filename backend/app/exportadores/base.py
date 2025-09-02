# backend/app/exportadores/base.py

from abc import ABC, abstractmethod

class ExportadorBase(ABC):
    @abstractmethod
    def exportar(self, datos):
        """
        Genera la respuesta exportada a partir de los datos proporcionados.
        Debe devolver un objeto Response.
        """
        pass

    @abstractmethod
    def nombre_archivo(self) -> str:
        """
        Devuelve el nombre del archivo exportado (incluyendo extensión).
        """
        pass

    @abstractmethod
    def tipo_mime(self) -> str:
        """
        Devuelve el tipo MIME correspondiente al archivo exportado.
        """
        pass
