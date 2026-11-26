"""Pure prototype model. No host queries, subprocess, network or privileged backend."""
from dataclasses import dataclass,replace
from threading import Lock
from collections import deque

SERVICES={'apache':'apache2.service','mariadb':'mariadb.service','docker':'docker.service'}
ACTIONS=frozenset({'start','stop','restart','enable','disable'})
LABELS={'active':'Ativo','inactive':'Parado','failed':'Falhou','unknown':'Desconhecido'}

@dataclass(frozen=True)
class Service:
    key:str
    state:str='inactive'
    autostart:bool=False
    available:bool=True

class OperationError(ValueError):pass

def selection(service,action=None):
    if service not in SERVICES:raise OperationError('Serviço não permitido')
    if action is not None and action not in ACTIONS:raise OperationError('Operação não permitida')

def normalize_state(load,active):
    if load!='loaded':return 'unknown'
    return {'active':'active','inactive':'inactive','failed':'failed'}.get(active,'unknown')

def requires_confirmation(action):
    if action not in ACTIONS:raise OperationError('Operação não permitida')
    return action in {'stop','restart','disable'}

def admin_argv(service,action):
    """Architecture contract only. This module NEVER executes the returned command."""
    selection(service,action)
    return ['/usr/bin/pkexec','/usr/libexec/devlite-control2-helper',action,service]

class SimulatedBackend:
    simulated=True
    def __init__(self):
        self._lock=Lock()
        self._services={'apache':Service('apache','active'),
          'mariadb':Service('mariadb'), 'docker':Service('docker','failed')}
        self._logs={key:deque(['SIMULAÇÃO: nenhum log do hospedeiro foi consultado.'],maxlen=50) for key in SERVICES}
        self.next_error=None
    def status(self,service):
        selection(service)
        with self._lock:return self._services[service]
    def all_status(self):return {key:self.status(key) for key in SERVICES}
    def operate(self,service,action,confirmed=False):
        selection(service,action)
        if requires_confirmation(action) and not confirmed:raise OperationError('Confirmação necessária')
        with self._lock:
            if self.next_error:
                error=self.next_error;self.next_error=None;raise OperationError(error)
            old=self._services[service]
            if not old.available:raise OperationError('Serviço indisponível')
            if action in ('start','restart'):new=replace(old,state='active')
            elif action=='stop':new=replace(old,state='inactive')
            else:new=replace(old,autostart=action=='enable')
            self._services[service]=new
            verb={'start':'iniciar','stop':'parar','restart':'reiniciar','enable':'ativar no boot','disable':'desativar no boot'}[action]
            self._logs[service].append('SIMULAÇÃO: '+verb+' em '+SERVICES[service])
            return new
    def logs(self,service):
        selection(service)
        with self._lock:return '\n'.join(self._logs[service])
    def unavailable(self,service):
        selection(service)
        with self._lock:self._services[service]=replace(self._services[service],state='unknown',available=False)
    def system_info(self):
        return {'Versão':'DevLite OS 1.0 — dados de demonstração',
          'PHP':'8.3 (simulado)','Node.js':'LTS (simulado; consultar prefixo versionado na versão definitiva)',
          'TypeScript':'simulado','Composer':'simulado','Git':'simulado',
          'CPU':'7% (simulado)','Memória':'1,2 / 6 GiB (simulado)',
          'Disco':'24 / 80 GiB (simulado)','Endereço IP':'192.0.2.10 (simulado)',
          'Gateway':'192.0.2.1 (simulado)','DNS':'192.0.2.53 (simulado)'}
