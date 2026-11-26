"""Additional runtime diagnostics for the existing DevControl dashboard."""

if __package__:
    from v6.devcontrol.metrics import DevControlCollector as ExistingCollector
else:
    from metrics import DevControlCollector as ExistingCollector


class DevControlCollector(ExistingCollector):
    def overview(self):
        rows = super().overview()
        command = self._read('/proc/cmdline').split()
        live = 'boot=casper' in command or any(
            token.startswith('layerfs-path=') for token in command
        )
        return [('Ambiente', 'Sessão Live' if live else 'Sistema instalado'), *rows]

    def docker(self):
        details = super().docker()
        for line in self._read('/proc/self/mountinfo').splitlines():
            mount, separator, source = line.partition(' - ')
            if separator and mount.split()[4:5] == ['/'] and source.split()[:1] == ['overlay']:
                details.append((
                    'Armazenamento de contêineres',
                    'A raiz usa OverlayFS. O Docker pode não iniciar com o driver overlay2 '
                    'sobre essa camada. Use o sistema instalado se ocorrer essa limitação.',
                ))
                break
        return details
