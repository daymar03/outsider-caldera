import os
import json
from pathlib import Path
from datetime import datetime

class BaseHandler:
    def __init__(self, model_dir: Path):
        """
        model_dir: ruta al directorio del modelo (ej: ./models/web)
        """
        self.model_dir = model_dir
        self.payloads_dir = model_dir / "payloads"
        self.payloads = self._load_payloads()
        self.target = ""
        self.port = 1234
        self.script = []

    def _load_payloads(self):
        """
        Carga los nombres de los payloads disponibles (sin extensión).
        """
        payloads = []
        if self.payloads_dir.exists():
            for file in os.listdir(self.payloads_dir):
                if file.endswith(".json"):
                    payload = {}
                    with open(self.payloads_dir / file, "r", encoding="utf-8") as f:
                        temp = json.load(f)
                        payload["description"] = temp["description"]
                        payload["tags"] = temp["tags"]
                        payload["categories"] = temp["categories"]
                        payload["name"] = os.path.splitext(file)[0]
                        payloads.append(payload)
        return payloads

        
    def load_scripts(self):
        """
        Devuelve todos los scripts disponibles.
        Retorna: array de objetos con name, description y payload_count
        """
        scripts_dir = self.model_dir / "scripts"
        scripts = []
        
        if not scripts_dir.exists():
            return scripts
        
        for file in scripts_dir.iterdir():
            if file.is_file() and file.name.endswith("_script.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        script_data = json.load(f)
                        
                    # Extraer solo la información necesaria para el frontend
                    script_info = {
                        "name": script_data.get("name", ""),
                        "description": script_data.get("description", ""),
                        "payload_count": script_data.get("payload_count", 0),
                        "script_id": file.name.split("_")[0]  # Extraer el ID numérico
                    }
                    
                    scripts.append(script_info)
                    
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error al cargar script {file}: {e}")
                    continue
        
        # Ordenar por script_id (numérico)
        scripts.sort(key=lambda x: int(x.get("script_id", 0)))
        return scripts
    
    def load_script(self, name: str):
        """
        Devuelve un script específico por nombre.
        Retorna: objeto completo del script con name, description y payloads
        """
        scripts_dir = self.model_dir / "scripts"
        
        if not scripts_dir.exists():
            raise FileNotFoundError(f"No hay scripts disponibles para este modelo")
        
        # Buscar el script por nombre en todos los archivos
        for file in scripts_dir.iterdir():
            if file.is_file() and file.name.endswith("_script.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        script_data = json.load(f)
                    
                    # Verificar si este es el script buscado
                    if script_data.get("name") == name:
                        # Asegurar que tenemos todos los campos necesarios
                        result = {
                            "name": script_data.get("name", ""),
                            "description": script_data.get("description", ""),
                            "payloads": script_data.get("payloads", []),
                            "payload_count": script_data.get("payload_count", len(script_data.get("payloads", []))),
                            "script_id": file.name.split("_")[0]
                        }
                        return result
                        
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error al cargar script {file}: {e}")
                    continue
        
        raise FileNotFoundError(f"Script '{name}' no encontrado")

    def create_script(self, script_data):
        """
        Crea un nuevo script JSON con la estructura:
        {
            "name": "Nombre del script",
            "description": "Descripción del script",
            "payloads": ["0001_XSS", "0002_XSS", ...]
        }
        
        El archivo se guarda en model_dir/scripts como ####_script.json
        """

        # Validar estructura de datos
        if not isinstance(script_data, dict):
            raise ValueError("script_data debe ser un diccionario con name, description y payloads")
        
        required_fields = ["name", "payloads"]
        for field in required_fields:
            if field not in script_data:
                raise ValueError(f"Campo requerido faltante: {field}")
        
        name = script_data.get("name", "").strip()
        description = script_data.get("description", "").strip()
        payloads_list = script_data.get("payloads", [])
        
        if not name:
            raise ValueError("El nombre del script no puede estar vacío")
        
        if not isinstance(payloads_list, list) or not payloads_list:
            raise ValueError("payloads debe ser una lista no vacía de payload IDs")
        
        # Validar que los payloads existan
        valid_names = {p["name"] for p in self.payloads}
        invalid_payloads = [p for p in payloads_list if p not in valid_names]
        if invalid_payloads:
            raise ValueError(f"Payloads no válidos: {invalid_payloads}")
        
        print("BVVVVVVVVVVVVVVVVVVV")

        scripts_dir = self.model_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Buscar el último ID de script existente
        max_id = 0
        for file in scripts_dir.iterdir():
            if file.is_file() and file.name.endswith("_script.json"):
                try:
                    prefix = file.name.split("_")[0]
                    num = int(prefix)
                    max_id = max(max_id, num)
                except ValueError:
                    # Ignorar archivos que no sigan el patrón
                    continue
        
        next_id = max_id + 1
        script_filename = f"{next_id:04d}_script.json"
        script_path = scripts_dir / script_filename
        
        print("AAAAAAAAAAAAAAA")

        # Crear estructura completa del script
        script_structure = {
            "name": name,
            "description": description,
            "payloads": payloads_list,
            "payload_count": len(payloads_list)
        }
        print("AAAAAsadafsafAA")
        # Guardar el script
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_structure, f, indent=2, ensure_ascii=False)
        print("KKKKKKKKKKKKKKKKK")
        # Retornar respuesta para el frontend
        return {
            "script_id": f"{next_id:04d}",
            "name": name,
            "payload_count": len(payloads_list),
            "filename": script_filename,
        }
        
    def get_payloads(
        self,
        offset: int = 0,
        size: int = None,
        category: str = None,
        tag: str = None
    ):
        """
        Devuelve payloads filtrados por categoría y/o tag con paginación.
        """

        results = self.payloads

        if category:
            results = [
                p for p in results
                if category.upper() in p.get("categories", [])
            ]

        if tag:
            results = [
                p for p in results
                if tag.lower() in p.get("tags", [])
            ]

        total = len(results)

        if size is not None:
            results = results[offset:offset + size]
        else:
            results = results[offset:]

        return {
            "total": total,
            "offset": offset,
            "size": size,
            "payloads": results
        }

    def get_payload_info(self, payload_id: str):
        """
        Devuelve el contenido del archivo JSON de un payload.
        payload_id: nombre del archivo sin extensión (ej: '0001_XSS')
        """
        file_path = self.payloads_dir / f"{payload_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Payload {payload_id} no encontrado")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def execute_payload(self, payload_id: str):
        """
        Método genérico: debe ser sobreescrito por cada handler específico.
        """
        raise NotImplementedError("Este método debe implementarse en el handler específico")

    def set_target(self, target: str):
        raise NotImplementedError("Este método debe implementarse en el handler específico")

    def set_port(self, port: int):
        self.port = port
