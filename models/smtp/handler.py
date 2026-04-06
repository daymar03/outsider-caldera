# models/smtp/handler.py
from pathlib import Path
from plugins.outsider.models.baseHandler import BaseHandler
import smtplib
import socket
import dns.resolver
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional, Tuple
import time
import ssl
import re
import warnings

class SmtpHandler(BaseHandler):
    def __init__(self, model_dir: Path):
        super().__init__(model_dir)
        self.smtp_server = None
        self.smtp_port = None
        self.smtp_connection = None
        self.use_tls = False
        self.use_ssl = False
        self.requires_auth = False
        self.username = None
        self.password = None
        self.ssl_context = None
        self.verify_cert = False  # Por defecto, no verificar certificados
        
    def set_target(self, target: str):
        """
        Establece el servidor SMTP objetivo.
        Formato soportado:
        - smtp://host:port
        - smtp://host (puerto por defecto 25)
        - smtp://user:pass@host:port (con credenciales)
        - smtp://host:port?verify_cert=false (deshabilitar verificación SSL)
        """
        # Extraer parámetros de query string
        verify_cert_param = True
        if '?' in target:
            target, query = target.split('?', 1)
            params = dict(param.split('=') for param in query.split('&') if '=' in param)
            if 'verify_cert' in params:
                verify_cert_param = params['verify_cert'].lower() == 'true'
        
        self.verify_cert = verify_cert_param
        
        # Extraer credenciales si existen
        credentials = None
        if '@' in target:
            # Formato: smtp://user:pass@host:port
            pattern = r'^smtp://(?:([^:]+):([^@]+)@)?([^:/]+)(?::(\d+))?/?$'
            match = re.match(pattern, target)
            if match:
                username, password, host, port = match.groups()
                if username and password:
                    self.username = username
                    self.password = password
                    self.requires_auth = True
                target = f"smtp://{host}:{port}" if port else f"smtp://{host}"
        
        # Parsear URL
        if not target.startswith('smtp://'):
            target = f'smtp://{target}'
        
        # Extraer host y puerto
        match = re.match(r'^smtp://([^:/]+)(?::(\d+))?/?$', target)
        if not match:
            raise ValueError(f"Formato de target SMTP inválido: {target}")
        
        host, port = match.groups()
        self.smtp_server = host
        
        # Determinar puerto por defecto basado en protocolo
        if port:
            self.smtp_port = int(port)
        else:
            # Puertos por defecto comunes
            if target.startswith('smtps://') or ':465' in target:
                self.smtp_port = 465
                self.use_ssl = True
            elif ':587' in target:
                self.smtp_port = 587
                self.use_tls = True
            else:
                self.smtp_port = 25
        
        # Detectar protocolo desde el target
        if 'smtps://' in target or self.smtp_port in [465, 587]:
            if self.smtp_port == 465:
                self.use_ssl = True
            elif self.smtp_port == 587:
                self.use_tls = True
        
        # Crear contexto SSL con configuración apropiada
        self._create_ssl_context()
    
    def _create_ssl_context(self):
        """
        Crea un contexto SSL configurado según la verificación requerida.
        """
        try:
            if self.verify_cert:
                # Verificación normal de certificados
                self.ssl_context = ssl.create_default_context()
            else:
                # Sin verificación de certificados (para self-signed)
                self.ssl_context = ssl.create_default_context()
                self.ssl_context.check_hostname = False
                self.ssl_context.verify_mode = ssl.CERT_NONE
                warnings.warn("SSL certificate verification is disabled. This is insecure for production use.")
        except:
            # Fallback a contexto no verificador
            self.ssl_context = ssl._create_unverified_context()
    
    def execute_payload(self, payload_id: str) -> Dict[str, Any]:
        """
        Ejecuta un payload específico del tipo SMTP.
        """
        try:
            payload_info = self.get_payload_info(payload_id)
            payload = payload_info.get("payload", {})
            attack_type = payload.get("attack_type", "")
            
            # Configurar conexión si se especifica en el payload
            connection_config = payload.get("connection", {})
            if connection_config:
                self._configure_connection(connection_config)
            
            # Sobrescribir verificación SSL si se especifica en payload
            if "verify_cert" in payload:
                self.verify_cert = payload["verify_cert"]
                self._create_ssl_context()
            
            # Ejecutar el tipo de ataque especificado
            if attack_type == "smtp_banner":
                result = self._check_smtp_banner()
            elif attack_type == "smtp_user_enum":
                result = self._enumerate_users(payload)
            elif attack_type == "smtp_open_relay":
                result = self._test_open_relay(payload)
            elif attack_type == "smtp_auth_bruteforce":
                result = self._bruteforce_auth(payload)
            elif attack_type == "smtp_spoof_test":
                result = self._test_email_spoofing(payload)
            elif attack_type == "smtp_send_test":
                result = self._send_test_email(payload)
            elif attack_type == "smtp_capabilities":
                result = self._check_capabilities()
            elif attack_type == "smtp_vrfy":
                result = self._test_vrfy_command(payload)
            elif attack_type == "smtp_starttls":
                result = self._test_starttls()
            elif attack_type == "smtp_dns_checks":
                result = self._perform_dns_checks()
            else:
                result = {
                    "success": False,
                    "response": f"Tipo de ataque SMTP no soportado: {attack_type}"
                }
            
            # Cerrar conexión si está abierta
            if self.smtp_connection:
                try:
                    self.smtp_connection.quit()
                except:
                    try:
                        self.smtp_connection.close()
                    except:
                        pass
                finally:
                    self.smtp_connection = None
            
            return result
            
        except Exception as e:
            # Asegurarse de cerrar la conexión en caso de error
            if self.smtp_connection:
                try:
                    self.smtp_connection.quit()
                except:
                    try:
                        self.smtp_connection.close()
                    except:
                        pass
            
            return {
                "success": False,
                "response": f"Error ejecutando payload SMTP: {str(e)}"
            }
    
    def _connect_smtp(self) -> smtplib.SMTP:
        """
        Establece conexión SMTP basada en configuración.
        Maneja certificados self-signed.
        """
        try:
            if self.use_ssl:
                # SSL desde el inicio (puerto 465)
                self.smtp_connection = smtplib.SMTP_SSL(
                    self.smtp_server, 
                    self.smtp_port,
                    context=self.ssl_context,
                    timeout=10
                )
            else:
                # Conexión normal (puerto 25, 587)
                self.smtp_connection = smtplib.SMTP(
                    self.smtp_server, 
                    self.smtp_port,
                    timeout=10
                )
                self.smtp_connection.set_debuglevel(0)
                
                # Saludar al servidor
                self.smtp_connection.ehlo_or_helo_if_needed()
                
                # STARTTLS si está disponible y configurado
                if self.use_tls:
                    try:
                        # Primero verificar si soporta STARTTLS
                        self.smtp_connection.ehlo()
                        if 'starttls' in self.smtp_connection.esmtp_features:
                            self.smtp_connection.starttls(context=self.ssl_context)
                            self.smtp_connection.ehlo()
                        else:
                            # Si no soporta STARTTLS pero use_tls=True, intentar igual
                            try:
                                self.smtp_connection.starttls(context=self.ssl_context)
                                self.smtp_connection.ehlo()
                            except:
                                pass  # Continuar sin TLS
                    except:
                        pass  # Continuar sin TLS
            
            # Autenticación si se requiere
            if self.requires_auth and self.username and self.password:
                try:
                    self.smtp_connection.login(self.username, self.password)
                except smtplib.SMTPNotSupportedError:
                    # Algunos servidores no soportan AUTH
                    pass
                except Exception as e:
                    # Si falla la autenticación, continuar si es posible
                    if "requires authentication" in str(e).lower():
                        raise  # Relanzar si es necesario autenticar
            
            return self.smtp_connection
            
        except (ssl.SSLError, ssl.CertificateError) as e:
            # Error específico de SSL, intentar sin verificación
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                # Reintentar sin verificación SSL
                self.verify_cert = False
                self._create_ssl_context()
                return self._connect_smtp_retry()
            else:
                raise Exception(f"Error SSL conectando a SMTP: {str(e)}")
        except Exception as e:
            raise Exception(f"Error conectando a SMTP: {str(e)}")
    
    def _connect_smtp_retry(self) -> smtplib.SMTP:
        """
        Reintento de conexión después de fallo SSL.
        """
        # Crear contexto sin verificación
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        try:
            if self.use_ssl:
                self.smtp_connection = smtplib.SMTP_SSL(
                    self.smtp_server, 
                    self.smtp_port,
                    context=context,
                    timeout=10
                )
            else:
                self.smtp_connection = smtplib.SMTP(
                    self.smtp_server, 
                    self.smtp_port,
                    timeout=10
                )
                self.smtp_connection.set_debuglevel(0)
                
                if self.use_tls:
                    try:
                        self.smtp_connection.ehlo()
                        if 'starttls' in self.smtp_connection.esmtp_features:
                            self.smtp_connection.starttls(context=context)
                            self.smtp_connection.ehlo()
                    except:
                        pass
            
            # Autenticación si se requiere
            if self.requires_auth and self.username and self.password:
                try:
                    self.smtp_connection.login(self.username, self.password)
                except:
                    pass
            
            return self.smtp_connection
            
        except Exception as e:
            raise Exception(f"Error en reintento de conexión SMTP: {str(e)}")
    
    def _configure_connection(self, config: Dict):
        """
        Configura parámetros de conexión desde el payload.
        """
        if 'use_tls' in config:
            self.use_tls = config['use_tls']
        if 'use_ssl' in config:
            self.use_ssl = config['use_ssl']
        if 'username' in config:
            self.username = config['username']
            self.requires_auth = True
        if 'password' in config:
            self.password = config['password']
            self.requires_auth = True
        if 'verify_cert' in config:
            self.verify_cert = config['verify_cert']
            self._create_ssl_context()
    
    def _check_smtp_banner(self) -> Dict[str, Any]:
        """
        Obtiene y analiza el banner del servidor SMTP.
        """
        try:
            connection = self._connect_smtp()
            banner = connection.ehlo()[1]  # Obtener respuesta del EHLO
            
            # También obtener HELO response
            connection.helo()
            
            # Analizar banner
            banner_info = {
                "server_banner": banner.decode('utf-8', errors='ignore') if isinstance(banner, bytes) else banner,
                "server_hostname": self.smtp_server,
                "port": self.smtp_port,
                "tls_enabled": self.use_tls or self.use_ssl,
                "ssl_verification": self.verify_cert,
                "auth_required": self.requires_auth,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_banner",
                    "banner_info": banner_info,
                    "status": "SUCCESS",
                    "ssl_warning": "SSL verification disabled" if not self.verify_cert else None
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error obteniendo banner SMTP: {str(e)}"
            }
    
    def _enumerate_users(self, payload: Dict) -> Dict[str, Any]:
        """
        Enumera usuarios usando comandos VRFY, EXPN o RCPT TO.
        Maneja conexiones con certificados self-signed.
        """
        user_list = payload.get("users", [])
        enumeration_method = payload.get("method", "VRFY")  # VRFY, EXPN, RCPT
        
        if not user_list:
            return {
                "success": False,
                "response": "Se requiere lista de usuarios para enumeración"
            }
        
        # Configurar SSL no verificador si se especifica
        if "verify_cert" in payload:
            self.verify_cert = payload.get("verify_cert", True)
            self._create_ssl_context()
        
        try:
            connection = self._connect_smtp()
            valid_users = []
            failed_users = []
            
            for username in user_list:
                try:
                    if enumeration_method.upper() == "VRFY":
                        # Usar comando VRFY
                        resp = connection.verify(username)
                        if resp[0] == 250:  # 250 User OK
                            valid_users.append({
                                "username": username,
                                "method": "VRFY",
                                "response": resp[1].decode('utf-8', errors='ignore') if isinstance(resp[1], bytes) else resp[1]
                            })
                    elif enumeration_method.upper() == "EXPN":
                        # Usar comando EXPN (expandir lista)
                        resp = connection.expn(username)
                        if resp[0] == 250:
                            valid_users.append({
                                "username": username,
                                "method": "EXPN",
                                "response": resp[1].decode('utf-8', errors='ignore') if isinstance(resp[1], bytes) else resp[1]
                            })
                    elif enumeration_method.upper() == "RCPT":
                        # Usar RCPT TO en un correo de prueba
                        test_from = payload.get("test_from", f"test@{self.smtp_server}")
                        msg = MIMEText("Test")
                        msg["From"] = test_from
                        msg["To"] = username
                        
                        connection.mail(test_from)
                        resp = connection.rcpt(username)
                        if resp[0] in [250, 251]:  # 250 OK, 251 User not local
                            valid_users.append({
                                "username": username,
                                "method": "RCPT",
                                "response": resp[1].decode('utf-8', errors='ignore') if isinstance(resp[1], bytes) else resp[1]
                            })
                        connection.rset()  # Resetear estado
                    
                    time.sleep(0.5)  # Rate limiting
                    
                except smtplib.SMTPResponseException as e:
                    failed_users.append({
                        "username": username,
                        "error_code": e.smtp_code,
                        "error_message": e.smtp_error.decode('utf-8', errors='ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error
                    })
                except Exception as e:
                    failed_users.append({
                        "username": username,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_user_enum",
                    "enumeration_method": enumeration_method,
                    "ssl_verification": self.verify_cert,
                    "total_users_tested": len(user_list),
                    "valid_users_found": len(valid_users),
                    "valid_users": valid_users,
                    "failed_attempts": failed_users,
                    "status": "COMPLETED"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error en enumeración de usuarios: {str(e)}"
            }
    
    def _test_open_relay(self, payload: Dict) -> Dict[str, Any]:
        """
        Prueba si el servidor SMTP es un open relay.
        """
        test_cases = payload.get("test_cases", [
            {
                "from": "attacker@external.com",
                "to": "victim@external.com",
                "expected": "RELAY_ALLOWED"
            }
        ])
        
        if not test_cases:
            test_cases = [{
                "from": "test@" + self.smtp_server,
                "to": "test@external-domain.com",
                "expected": "RELAY_DENIED"
            }]
        
        results = []
        
        try:
            connection = self._connect_smtp()
            
            for i, test_case in enumerate(test_cases):
                test_from = test_case.get("from", f"test{i}@{self.smtp_server}")
                test_to = test_case.get("to", f"test{i}@external-domain.com")
                
                try:
                    # Resetear conexión para cada prueba
                    connection.rset()
                    
                    # Configurar remitente
                    connection.mail(test_from)
                    
                    # Intentar añadir destinatario
                    resp = connection.rcpt(test_to)
                    
                    relay_allowed = resp[0] in [250, 251]
                    
                    results.append({
                        "test_case": i + 1,
                        "from": test_from,
                        "to": test_to,
                        "relay_allowed": relay_allowed,
                        "response_code": resp[0],
                        "response_message": resp[1].decode('utf-8', errors='ignore') if isinstance(resp[1], bytes) else resp[1],
                        "vulnerable": relay_allowed and "external" in test_to.lower()
                    })
                    
                    time.sleep(1)
                    
                except smtplib.SMTPResponseException as e:
                    results.append({
                        "test_case": i + 1,
                        "from": test_from,
                        "to": test_to,
                        "relay_allowed": False,
                        "response_code": e.smtp_code,
                        "response_message": str(e),
                        "vulnerable": False
                    })
                except Exception as e:
                    results.append({
                        "test_case": i + 1,
                        "from": test_from,
                        "to": test_to,
                        "error": str(e),
                        "vulnerable": False
                    })
            
            # Determinar si es vulnerable
            vulnerable = any(r.get("vulnerable", False) for r in results)
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_open_relay",
                    "server": self.smtp_server,
                    "is_open_relay": vulnerable,
                    "test_cases": results,
                    "vulnerability_status": "VULNERABLE" if vulnerable else "SECURE",
                    "recommendation": "Configure authentication and relay restrictions" if vulnerable else "Properly configured"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error probando open relay: {str(e)}"
            }
    
    def _bruteforce_auth(self, payload: Dict) -> Dict[str, Any]:
        """
        Fuerza bruta de autenticación SMTP.
        """
        username_list = payload.get("usernames", [])
        password_list = payload.get("passwords", [])
        
        if not username_list or not password_list:
            return {
                "success": False,
                "response": "Se requieren listas de usuarios y contraseñas"
            }
        
        max_attempts = payload.get("max_attempts", 10)
        found_credentials = []
        attempts = []
        
        try:
            for username in username_list[:5]:  # Limitar para no bloquear
                for password in password_list[:5]:  # Limitar para no bloquear
                    if len(found_credentials) >= max_attempts:
                        break
                    
                    try:
                        # Crear nueva conexión para cada intento
                        temp_connection = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=5)
                        
                        if self.use_tls:
                            temp_connection.starttls()
                        
                        temp_connection.ehlo()
                        
                        # Intentar autenticación
                        temp_connection.login(username, password)
                        
                        # Si llega aquí, las credenciales son válidas
                        found_credentials.append({
                            "username": username,
                            "password": password,
                            "status": "VALID"
                        })
                        
                        temp_connection.quit()
                        
                    except smtplib.SMTPAuthenticationError:
                        attempts.append({
                            "username": username,
                            "password": password,
                            "status": "INVALID"
                        })
                    except Exception as e:
                        attempts.append({
                            "username": username,
                            "password": password,
                            "error": str(e),
                            "status": "ERROR"
                        })
                    
                    time.sleep(2)  # Rate limiting importante
                
                if len(found_credentials) >= max_attempts:
                    break
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_auth_bruteforce",
                    "total_attempts": len(attempts) + len(found_credentials),
                    "valid_credentials_found": len(found_credentials),
                    "found_credentials": found_credentials,
                    "attempts_made": attempts[:10],  # Limitar output
                    "status": "COMPLETED"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error en fuerza bruta: {str(e)}"
            }
    
    def _test_email_spoofing(self, payload: Dict) -> Dict[str, Any]:
        """
        Prueba la capacidad de spoofing de emails.
        """
        spoof_from = payload.get("spoof_from", "admin@microsoft.com")
        target_to = payload.get("target_to", "test@example.com")
        test_body = payload.get("body", "This is a spoofing test email")
        
        try:
            connection = self._connect_smtp()
            
            # Crear mensaje
            msg = MIMEMultipart()
            msg["From"] = spoof_from
            msg["To"] = target_to
            msg["Subject"] = payload.get("subject", "Test Spoofing Email")
            msg.attach(MIMEText(test_body, "plain"))
            
            # Enviar email
            connection.sendmail(spoof_from, [target_to], msg.as_string())
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_spoof_test",
                    "spoofed_from": spoof_from,
                    "sent_to": target_to,
                    "status": "SUCCESS - Email spoofing possible",
                    "message": "Server allows spoofing from address",
                    "security_implication": "HIGH - Can be used for phishing"
                }
            }
            
        except smtplib.SMTPResponseException as e:
            return {
                "success": True,  # Técnicamente exitoso, no vulnerable
                "response": {
                    "attack_type": "smtp_spoof_test",
                    "spoofed_from": spoof_from,
                    "sent_to": target_to,
                    "status": "FAILED - Spoofing prevented",
                    "response_code": e.smtp_code,
                    "response_message": e.smtp_error.decode('utf-8', errors='ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error,
                    "security_implication": "LOW - Server validates senders"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "response": f"Error en prueba de spoofing: {str(e)}"
            }
    
    def _send_test_email(self, payload: Dict) -> Dict[str, Any]:
        """
        Envía un email de prueba legítimo.
        """
        sender = payload.get("sender", f"test@{self.smtp_server}")
        recipient = payload.get("recipient", "test@example.com")
        subject = payload.get("subject", "SMTP Test Email")
        body = payload.get("body", "This is a test email sent for SMTP validation")
        
        try:
            connection = self._connect_smtp()
            
            # Crear mensaje
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            
            # Enviar email
            connection.sendmail(sender, [recipient], msg.as_string())
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_send_test",
                    "sender": sender,
                    "recipient": recipient,
                    "status": "SUCCESS",
                    "message": "Test email sent successfully"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error enviando email de prueba: {str(e)}"
            }
    
    def _check_capabilities(self) -> Dict[str, Any]:
        """
        Verifica las capacidades/extensions del servidor SMTP.
        """
        try:
            connection = self._connect_smtp()
            
            # Obtener capacidades con EHLO
            capabilities = connection.ehlo()[1]
            if isinstance(capabilities, bytes):
                capabilities = capabilities.decode('utf-8', errors='ignore')
            
            # Parsear capacidades
            cap_list = capabilities.split('\n') if capabilities else []
            cap_dict = {}
            
            for cap in cap_list:
                if ' ' in cap:
                    key, value = cap.split(' ', 1)
                    cap_dict[key.strip()] = value.strip()
                else:
                    cap_dict[cap.strip()] = True
            
            # Analizar seguridad
            security_analysis = {
                "starttls_available": "STARTTLS" in cap_dict,
                "auth_mechanisms": cap_dict.get("AUTH", "").split(),
                "pipelining": "PIPELINING" in cap_dict,
                "chunking": "CHUNKING" in cap_dict,
                "8bitmime": "8BITMIME" in cap_dict,
                "dsn": "DSN" in cap_dict,
                "size": cap_dict.get("SIZE", "Not specified")
            }
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_capabilities",
                    "server": self.smtp_server,
                    "capabilities": cap_dict,
                    "security_analysis": security_analysis,
                    "raw_capabilities": capabilities,
                    "status": "COMPLETED"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error obteniendo capacidades: {str(e)}"
            }
    
    def _test_vrfy_command(self, payload: Dict) -> Dict[str, Any]:
        """
        Prueba específica del comando VRFY.
        """
        test_users = payload.get("test_users", ["postmaster", "admin", "root", "webmaster"])
        
        results = []
        
        try:
            connection = self._connect_smtp()
            
            for user in test_users:
                try:
                    resp = connection.verify(user)
                    results.append({
                        "username": user,
                        "response_code": resp[0],
                        "response_message": resp[1].decode('utf-8', errors='ignore') if isinstance(resp[1], bytes) else resp[1],
                        "vrfy_enabled": resp[0] != 502  # 502 Command not implemented
                    })
                except smtplib.SMTPResponseException as e:
                    results.append({
                        "username": user,
                        "response_code": e.smtp_code,
                        "error": str(e),
                        "vrfy_enabled": e.smtp_code != 502
                    })
                
                time.sleep(0.5)
            
            vrfy_enabled = any(r.get("vrfy_enabled", False) for r in results)
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_vrfy",
                    "vrfy_command_enabled": vrfy_enabled,
                    "test_results": results,
                    "security_implication": "INFORMATION DISCLOSURE" if vrfy_enabled else "SECURE",
                    "recommendation": "Disable VRFY command in SMTP server" if vrfy_enabled else "Good configuration"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error probando comando VRFY: {str(e)}"
            }
    
    def _test_starttls(self) -> Dict[str, Any]:
        """
        Prueba de soporte STARTTLS y análisis de cifrado.
        """
        try:
            connection = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            connection.ehlo()
            
            # Verificar si STARTTLS está en capacidades
            has_starttls = 'starttls' in connection.esmtp_features
            
            tls_info = {
                "starttls_supported": has_starttls,
                "esmtp_features": dict(connection.esmtp_features) if connection.esmtp_features else {},
                "initial_response": connection.ehlo()[1].decode('utf-8', errors='ignore') if isinstance(connection.ehlo()[1], bytes) else connection.ehlo()[1]
            }
            
            if has_starttls:
                try:
                    # Intentar STARTTLS
                    context = ssl.create_default_context()
                    connection.starttls(context=context)
                    connection.ehlo()
                    
                    # Obtener información del socket cifrado
                    if connection.sock:
                        cipher_info = connection.sock.cipher()
                        tls_info.update({
                            "tls_established": True,
                            "cipher": cipher_info[0] if cipher_info else None,
                            "protocol_version": connection.sock.version() if hasattr(connection.sock, 'version') else None,
                            "cipher_bits": cipher_info[2] if cipher_info else None
                        })
                    
                except Exception as e:
                    tls_info.update({
                        "tls_established": False,
                        "tls_error": str(e)
                    })
            
            connection.quit()
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_starttls",
                    "tls_analysis": tls_info,
                    "security_recommendation": "Enable STARTTLS with strong ciphers" if not tls_info.get("tls_established") else "TLS properly configured",
                    "status": "COMPLETED"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error analizando STARTTLS: {str(e)}"
            }
    
    def _perform_dns_checks(self) -> Dict[str, Any]:
        """
        Realiza verificaciones DNS relacionadas con el servidor SMTP.
        """
        try:
            dns_checks = {}
            
            # Verificar registros MX
            try:
                mx_records = dns.resolver.resolve(self.smtp_server, 'MX')
                dns_checks["mx_records"] = [str(r.exchange) for r in mx_records]
                dns_checks["mx_preferences"] = [r.preference for r in mx_records]
            except:
                dns_checks["mx_records"] = "Not found or not an email domain"
            
            # Verificar SPF
            try:
                txt_records = dns.resolver.resolve(self.smtp_server, 'TXT')
                spf_records = [r.to_text() for r in txt_records if 'spf' in r.to_text().lower()]
                dns_checks["spf_records"] = spf_records
                dns_checks["has_spf"] = len(spf_records) > 0
            except:
                dns_checks["spf_records"] = []
                dns_checks["has_spf"] = False
            
            # Verificar DKIM (común en selector._domainkey)
            dns_checks["dkim_selectors"] = []
            common_selectors = ['default', 'google', 'selector1', 'selector2', 'k1']
            
            for selector in common_selectors:
                try:
                    dkim_record = dns.resolver.resolve(f"{selector}._domainkey.{self.smtp_server}", 'TXT')
                    dns_checks["dkim_selectors"].append({
                        "selector": selector,
                        "record": [r.to_text() for r in dkim_record]
                    })
                except:
                    pass
            
            # Verificar DMARC
            try:
                dmarc_record = dns.resolver.resolve(f"_dmarc.{self.smtp_server}", 'TXT')
                dns_checks["dmarc_record"] = [r.to_text() for r in dmarc_record]
            except:
                dns_checks["dmarc_record"] = "Not found"
            
            # Verificar PTR (reverse DNS)
            try:
                ptr_records = socket.gethostbyaddr(socket.gethostbyname(self.smtp_server))
                dns_checks["ptr_record"] = ptr_records[0]
            except:
                dns_checks["ptr_record"] = "Not found"
            
            # Análisis de seguridad
            security_score = 0
            if dns_checks.get("has_spf", False):
                security_score += 1
            if dns_checks.get("dkim_selectors"):
                security_score += 1
            if dns_checks.get("dmarc_record") != "Not found":
                security_score += 1
            
            dns_checks["dns_security_score"] = f"{security_score}/3"
            
            return {
                "success": True,
                "response": {
                    "attack_type": "smtp_dns_checks",
                    "domain": self.smtp_server,
                    "dns_records": dns_checks,
                    "security_analysis": {
                        "spf_configured": dns_checks.get("has_spf", False),
                        "dkim_configured": bool(dns_checks.get("dkim_selectors")),
                        "dmarc_configured": dns_checks.get("dmarc_record") != "Not found",
                        "ptr_matches": "ptr_record" in dns_checks,
                        "overall_security": "GOOD" if security_score >= 2 else "POOR"
                    },
                    "status": "COMPLETED"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error en verificaciones DNS: {str(e)}"
            }