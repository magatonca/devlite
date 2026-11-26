<?php
require __DIR__ . '/policy.php';
if (!devlite_request_allowed($_SERVER, $_GET, $_POST)) { http_response_code(403); exit; }
$vendor = __DIR__ . '/adminer-6.3.1-mysql.php';
if (!is_file($vendor) || hash_file('sha256', $vendor) !== '97fdb49c3e941636fe4b0559b2b042de3ac105dff0daafec3c255cd6bd81d4b6') {
    http_response_code(503); exit;
}
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_samesite', 'Strict');
ini_set('session.cookie_path', '/devlite-adminer');
foreach (array_keys($_SERVER) as $key) {
    if (str_starts_with($key, 'HTTP_X_FORWARDED_') || $key === 'HTTP_FORWARDED') unset($_SERVER[$key]);
}
$_GET['server'] = 'localhost';
function adminer_object() {
    return new class extends \Adminer\Adminer {
        function loginFormField($name, $heading, $field) {
            if ($name === 'server') return '<input type="hidden" name="auth[server]" value="localhost">';
            return parent::loginFormField($name, $heading, $field);
        }
        function credentials() {
            $credentials = parent::credentials();
            $credentials[0] = 'localhost';
            return $credentials;
        }
        function login($login, $password) {
            if (!devlite_user_allowed($login) || !is_string($password) || $password === '') return false;
            return parent::login($login, $password);
        }
        function permanentLogin($create = false) { return ''; }
        function verifyVersion() { return false; }
        function serviceWorker() {}
    };
}
require $vendor;
