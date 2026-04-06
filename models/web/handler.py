# models/web/handler.py
from pathlib import Path
from plugins.outsider.models.baseHandler import BaseHandler
import requests  # ejemplo para web
from urllib.parse import urlparse

class WebHandler(BaseHandler):
    def __init__(self, model_dir: Path):
        super().__init__(model_dir)

    def execute_payload(self, payload_id: str):
        try:
            # Obtener la info completa del payload
            payload_info = self.get_payload_info(payload_id)
            payload = payload_info.get("payload", {})

            # Construir la URL base
            url = self.target + payload.get("route","/")

            # Ejecutar la petición
            response = requests.request(
                method=payload.get("method", "GET"),
                url=url,
                headers=payload.get("headers", {}),
                params=payload.get("query", {}),
                data=payload.get("body", {}),
                timeout=10  # buena práctica: evitar bloqueos indefinidos
            )

            # Devolver resultado exitoso
            return {
                "success": True,
                "response": response.text
            }

        except requests.exceptions.RequestException as e:
            # Errores de red, timeout, conexión, etc.
            return {
                "success": False,
                "response": f"Error en la petición: {str(e)}"
            }
        except Exception as e:
            # Cualquier otro error inesperado
            return {
                "success": False,
                "response": f"Error inesperado: {str(e)}"
            }

    def set_target(self, target: str):
        """
        Establece el target validando que sea una URL correcta.
        """
        print("JJJJJJJJJJJJJ")
        parsed = urlparse(target)
        print("AAAAAAAAAAAAA")
        # Validar que tenga esquema y netloc (ej: http://example.com)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Target inválido: '{target}'. Debe ser una URL completa (ej: http://host:puerto).")
        print("BBBBBBBBBBBBBB")
        # Opcional: restringir a esquemas soportados
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Esquema inválido: '{parsed.scheme}'. Solo se permiten http o https.")
        
        # Si pasa las validaciones, guardar
        self.target = target
