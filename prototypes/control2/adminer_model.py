"""Pure Adminer proposal; no service, browser or database operations."""
import ipaddress

URL='http://127.0.0.1:8081/devlite-adminer'
IPV6_URL='http://[::1]:8081/devlite-adminer'
LISTEN='Listen 127.0.0.1:8081\nListen [::1]:8081\n'
APACHE='# PROTÓTIPO: não habilitado. Porta 80 existente preservada.\nListen 127.0.0.1:8081\nListen [::1]:8081\n<VirtualHost 127.0.0.1:8081 [::1]:8081>\n    ServerName localhost\n    DocumentRoot /usr/share/devlite-os/adminer/empty\n    SetEnvIfNoCase Host "^(127\\.0\\.0\\.1|\\[::1\\]|localhost):8081$" devlite_adminer_host_ok\n    Alias "/devlite-adminer" "/usr/share/devlite-os/adminer/index.php"\n    <Directory "/usr/share/devlite-os/adminer">\n        Options -Indexes\n        AllowOverride None\n        Require all denied\n    </Directory>\n    <LocationMatch "^/devlite-adminer/?$">\n        <RequireAll>\n            Require ip 127.0.0.1 ::1\n            Require env devlite_adminer_host_ok\n        </RequireAll>\n    </LocationMatch>\n    <LocationMatch "^/adminer(?:/|$)">\n        Require all denied\n    </LocationMatch>\n    <Directory "/etc/adminer">\n        Require all denied\n    </Directory>\n    <Directory "/usr/share/adminer">\n        Require all denied\n    </Directory>\n</VirtualHost>\n'

def browser_request(apache_active,mariadb_active):
    if apache_active is not True or mariadb_active is not True:
        raise ValueError('Inicie Apache e MariaDB pelo fluxo autorizado; nenhum serviço será iniciado automaticamente')
    # Future launcher may pass only this constant URL to Gio.AppInfo, never credentials.
    return URL

def loopback_peer(address):
    """Model of the strict two-address proposal, not a substitute for Apache tests."""
    try:return ipaddress.ip_address(address) in (ipaddress.ip_address('127.0.0.1'),ipaddress.ip_address('::1'))
    except ValueError:return False

def release_gate(chain_authenticated,deb_hash_verified,security_review_passed,guest_tests_passed):
    return all(x is True for x in (chain_authenticated,deb_hash_verified,security_review_passed,guest_tests_passed))

