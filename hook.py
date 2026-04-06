from app.utility.base_world import BaseWorld
from plugins.outsider.app.outsider_gui import OutsiderGUI
from plugins.outsider.app.outsider_svc import OutsiderService

name = 'outsider'
description = 'This is a plugin oriented to simulate Real Adversary Behaivor against Services, in order to test SIEM, WAF, and other Defense oriented solutions'
address = '/plugin/outsider/gui'
access = BaseWorld.Access.RED


async def enable(services):
    app = services.get('app_svc').application
    OutsiderGUI(services, name, description)
    outsider_svc = OutsiderService(services)
    await outsider_svc.add_routes(app.router)
    
    app.router.add_route("GET", "/plugin/outsider/techniques", outsider_svc.get_techniques)
    app.router.add_route("GET", "/plugin/outsider/assets", outsider_svc.get_assets)
