from app.utility.base_service import BaseService
#from aiohttp import web
from aiohttp_jinja2 import template, web
from app.service.auth_svc import for_all_public_methods, check_authorization
from pathlib import Path
import os
import importlib
import json

from plugins.outsider.models.baseHandler import BaseHandler

models_dir = Path(__file__).parent / "../models"

@for_all_public_methods(check_authorization)
class OutsiderService(BaseService):

    def __init__(self, services):
        self.services = services
        self.auth_svc = self.services.get('auth_svc')
        self.rest_svc = self.services.get('rest_svc')
        self.name = "Outsider"
        self.description = 'This is a plugin oriented to simulate Real Adversary Behaivor against Services, in order to test SIEM, WAF, and other Defense oriented solutions'
        self.models_dir = Path(__file__).parent.parent / "models"
        self.handlers = {}
        self._load_handlers()
        self.assets = self._load_assets()

    def _load_assets(self):
        a = []

        for subdir in models_dir.iterdir():
            if subdir.is_dir():
                handler_file = subdir / "handler.py"
                if handler_file.exists():
                    a.append(subdir.name)
                    # El nombre del modelo es el nombre del directorio
        return a
                        
    def _load_handlers(self):
        """
        Itera sobre los subdirectorios de models, importa el handler si existe,
        instancia la clase y guarda en self.handlers.
        """
        for subdir in self.models_dir.iterdir():
            if subdir.is_dir():
                handler_file = subdir / "handler.py"
                if handler_file.exists():
                    model_name = subdir.name
                    module_path = f"plugins.outsider.models.{model_name}.handler"
                    module = importlib.import_module(module_path)
                    class_name = f"{model_name.capitalize()}Handler"
                    handler_class = getattr(module, class_name)
                    self.handlers[model_name] = handler_class(subdir)


    async def add_routes(self, router):
        """
        Registra dinámicamente las rutas para cada handler cargado.
        """
        for model_name, handler in self.handlers.items():
            base = f"/plugin/outsider/{model_name}"

            # GET /plugin/outsider/<model>/payloads
            async def get_payloads(request, handler=handler):
                offset = int(request.query.get("offset", 0))
                size = request.query.get("size")
                size = int(size) if size is not None else None

                category = request.query.get("category")
                tag = request.query.get("tag")

                data = handler.get_payloads(
                    offset=offset,
                    size=size,
                    category=category,
                    tag=tag
                )
                return web.json_response(data)

            # GET /plugin/outsider/<model>/scripts - Lista todos los scripts
            async def get_scripts(request, handler=handler, model_name=model_name):
                try:
                    scripts = handler.load_scripts()
                    return web.json_response(scripts)
                except Exception as e:
                    print(f"Error al cargar scripts para {model_name}: {e}")
                    return web.json_response({"error": str(e)}, status=500)

            # GET /plugin/outsider/<model>/scripts/{name} - Obtiene un script específico
            async def get_script(request, handler=handler, model_name=model_name):
                try:
                    script_name = request.match_info["name"]
                    script_data = handler.load_script(script_name)
                    return web.json_response(script_data)
                except FileNotFoundError as e:
                    return web.json_response({"error": str(e)}, status=404)
                except Exception as e:
                    print(f"Error al cargar script {script_name} para {model_name}: {e}")
                    return web.json_response({"error": str(e)}, status=500)

            # POST /plugin/outsider/<model>/create_script
            async def create_script(request, handler=handler):
                try:
                    data = await request.json()
                except Exception:
                    return web.json_response({"error": "Invalid JSON"}, status=400)

                try:
                    result = handler.create_script(data)
                    return web.json_response({
                        "script_id": result["script_id"],
                        "name": result["name"],
                        "payload_count": result["payload_count"]
                    })
                except ValueError as ve:
                    return web.json_response({"error": str(ve)}, status=400)
                except Exception as e:
                    return web.json_response({"error": f"Unexpected error: {e}"}, status=500)


            # GET /plugin/outsider/<model>/payloads/{id}
            async def get_payload_info(request, handler=handler):
                payload_id = request.match_info["id"]
                return web.json_response(handler.get_payload_info(payload_id))

            # POST /plugin/outsider/<model>/payloads/{id}/execute
            async def execute_payload(request, handler=handler):
                payload_id = request.match_info["id"]
                result = handler.execute_payload(payload_id)
                return web.json_response({"result": result})

                # POST /plugin/outsider/<model>/target
            async def set_target(request, handler=handler):
                data = await request.json()
                print(data)
                handler.set_target(data.get("target", ""))
                return web.json_response({"status": "ok"})

            # POST /plugin/outsider/<model>/port
            async def set_port(request, handler=handler):
                data = await request.json()
                handler.set_port(int(data.get("port", 1234)))
                return web.json_response({"status": "ok"})

            # Registrar todas las rutas
            router.add_get(f"{base}/scripts", get_scripts)
            router.add_get(f"{base}/scripts/{{name}}", get_script)
            router.add_post(f"{base}/create_script", create_script)
            router.add_get(f"{base}/payloads", get_payloads)
            router.add_get(f"{base}/payloads/{{id}}", get_payload_info)
            router.add_post(f"{base}/payloads/{{id}}/execute", execute_payload)
            router.add_post(f"{base}/target", set_target)
            router.add_post(f"{base}/port", set_port)


        self.techniques = [
            {
                'id': 'xss',
                'name': 'Cross-Site Scripting (XSS)'
            },
            {
                'id': 'lfi',
                'name': 'Local File Inclusion (LFI)'
            },
            {
                'id': 'sqli',
                'name': 'SQL Injection (SQLi)'
            },
            {
                'id': 'ssrf',
                'name': 'Server-Side Request Forgery (SSRF)'
            }
        ]

    async def get_techniques(self, request):
        return web.json_response(self.techniques)

    async def get_assets(self, request):
        return web.json_response(self.assets)
