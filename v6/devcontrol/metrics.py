"""Additional dashboard metrics from Linux procfs."""
import json
import platform
import subprocess
from pathlib import Path

if __package__:
    from v5.devcontrol.collector import DevControlCollector as V5Collector
else:
    from collector import DevControlCollector as V5Collector


TOOLS = (
    ('cURL', '/usr/bin/curl', ('--version',)),
    ('Python', '/usr/bin/python3', ('--version',)),
    ('Composer', '/usr/bin/composer', ('--version',)),
    ('Apache', '/usr/sbin/apache2', ('-v',)),
    ('MariaDB', '/usr/sbin/mariadbd', ('--version',)),
    ('Docker Compose', '/usr/bin/docker', ('compose', 'version')),
    ('LibreOffice', '/usr/bin/libreoffice', ('--version',)),
)


class DevControlCollector(V5Collector):
    previous_cpu = None

    def cpu_usage(self):
        row = self._read('/proc/stat').partition('\n')[0].split()
        if len(row) < 6 or row[0] != 'cpu':
            return 'Indisponível'
        try:
            fields = [int(value) for value in row[1:9]]
        except ValueError:
            return 'Indisponível'
        total, idle = sum(fields), sum(fields[3:5])
        previous = self.previous_cpu
        self.previous_cpu = total, idle
        if not previous or total <= previous[0] or idle < previous[1]:
            return 'Coletando amostra'
        elapsed = total - previous[0]
        busy = max(0, elapsed - (idle - previous[1]))
        return f'{busy / elapsed:.0%}'

    def overview(self):
        rows = super().overview()
        uptime = self._read('/proc/uptime').split()
        try:
            seconds = int(float(uptime[0]))
            days, hours = divmod(seconds // 3600, 24)
            duration = f'{days} d {hours:02d} h {seconds // 60 % 60:02d} min'
        except (IndexError, ValueError, OverflowError):
            duration = 'Indisponível'
        memory = {}
        for line in self._read('/proc/meminfo').splitlines():
            name, _, value = line.partition(':')
            fields = value.split()
            if len(fields) == 2 and fields[1] == 'kB' and fields[0].isdecimal():
                memory[name] = int(fields[0])
        swap = 'Indisponível'
        if {'SwapTotal', 'SwapFree'} <= memory.keys():
            total = memory['SwapTotal']
            used = max(0, total - memory['SwapFree'])
            swap = f'{used // 1024} / {total // 1024} MiB'
        total = memory.get('MemTotal', 0)
        if total and 'MemAvailable' in memory:
            available = min(total, memory['MemAvailable'])
            rows = [(key, f'{(total - available) / total:.0%} · {value}'
                     if key == 'Memória RAM' else value) for key, value in rows]
        try:
            disk = self.disk_usage(self.root)
            if disk.total:
                rows = [(key, f'{disk.used / disk.total:.0%} · {value}'
                         if key == 'Armazenamento raiz' else value) for key, value in rows]
        except OSError:
            pass
        if memory.get('SwapTotal'):
            swap = f'{used / memory["SwapTotal"]:.0%} · {swap}'
        try:
            identity = json.loads(self._read('/usr/share/devlite-os/identity.json'))
            if identity.get('name') == 'DevLite OS':
                rows = [(key, 'Xubuntu 24.04 LTS' if key == 'Distribuição base' else value)
                        for key, value in rows]
        except (ValueError, AttributeError):
            pass
        return rows + [
            ('Kernel', platform.release()),
            ('Arquitetura', platform.machine()),
            ('Tempo de atividade', duration),
            ('Uso da CPU', self.cpu_usage()),
            ('Swap', swap),
        ]

    def network(self):
        rows = super().network()
        for raw, translated in (('UP', 'Ativa'), ('DOWN', 'Inativa'), ('UNKNOWN', 'Desconhecida'),
                                ('LOWERLAYERDOWN', 'Sem enlace'), ('DORMANT', 'Em espera')):
            rows = [(key, value.replace(f'({raw})', f'({translated})'))
                    if key == 'Interfaces e endereços' else (key, value) for key, value in rows]
        result, error = self._run('nmcli', '-t', '-f', 'CONNECTIVITY', 'general')
        states = {'full': 'Completa', 'limited': 'Limitada', 'portal': 'Portal cativo',
                  'none': 'Sem conexão', 'unknown': 'Desconhecida'}
        value = states.get(result[1].strip(), 'Desconhecida') if not error and result[0] == 0 else 'Indisponível'
        return [('Conectividade informada pelo NetworkManager', value), *rows]

    def appearance(self):
        return [('Papel de parede por monitor' if key == 'Wallpaper por monitor' else key, value)
                for key, value in super().appearance()]

    def snapshot(self):
        result = super().snapshot()
        network = result['Rede']
        relevant = {'Conectividade informada pelo NetworkManager', 'Interfaces e endereços'}
        result['Visão geral'].extend((key, value) for key, value in network if key in relevant)
        return result

    def development(self):
        rows = super().development()
        if not (self.root / 'usr/bin/code').exists():
            rows = [(label, 'Instalação sob demanda pela fonte oficial'
                     if label == 'Visual Studio Code' else value) for label, value in rows]
        for label, binary, arguments in TOOLS:
            if not (self.root / binary.lstrip('/')).is_file():
                status = 'Não instalado'
            elif self.root != Path('/'):
                status = 'Instalado · versão a verificar no sistema em execução'
            else:
                try:
                    result = self.runner(
                        [binary, *arguments], text=True, capture_output=True,
                        stdin=subprocess.DEVNULL, timeout=3, check=True,
                        env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                             'HOME': '/nonexistent', 'COMPOSER_ALLOW_SUPERUSER': '0'},
                    )
                    status = 'Instalado · ' + self._version_line(result.stdout)
                except (OSError, subprocess.SubprocessError):
                    status = 'Instalado · versão indisponível'
            rows.append((label, status))
        return rows
