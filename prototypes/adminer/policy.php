<?php
// Protótipo não instalado. Nenhuma credencial persistente ou conexão aqui.
function devlite_user_allowed($user) {
    return is_string($user) && preg_match('/\A[A-Za-z0-9_.-]{1,80}\z/D', $user)
        && !in_array(strtolower($user), ['root','mysql','mariadb.sys','mysql.sys','mysql.session'], true);
}
function devlite_request_allowed($server, $get, $post) {
    if (!in_array($server['REMOTE_ADDR'] ?? '', ['127.0.0.1','::1'], true)) return false;
    if (!in_array(strtolower($server['HTTP_HOST'] ?? ''), ['127.0.0.1:8081','localhost:8081','[::1]:8081'], true)) return false;
    if ((string)($server['SERVER_PORT'] ?? '') !== '8081') return false;
    $path = parse_url($server['REQUEST_URI'] ?? '', PHP_URL_PATH);
    if (!in_array($path, ['/devlite-adminer','/devlite-adminer/'], true)) return false;
    if (array_key_exists('server', $get) && $get['server'] !== 'localhost') return false;
    if (array_key_exists('username', $get) && !devlite_user_allowed($get['username'])) return false;
    if (array_key_exists('auth', $post)) {
        $a = $post['auth'];
        if (!is_array($a) || ($a['driver'] ?? 'server') !== 'server' || ($a['server'] ?? '') !== 'localhost') return false;
        if (!devlite_user_allowed($a['username'] ?? null) || !is_string($a['password'] ?? null) || $a['password'] === '') return false;
    }
    return true;
}
