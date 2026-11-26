<?php
// Executar futuramente com PHP 8.3 isolado: php -n test-policy.php
require __DIR__ . '/policy.php';
$s = ['REMOTE_ADDR'=>'127.0.0.1','HTTP_HOST'=>'127.0.0.1:8081','SERVER_PORT'=>'8081','REQUEST_URI'=>'/devlite-adminer'];
$checks = [devlite_request_allowed($s, [], []), !devlite_user_allowed('root'), !devlite_user_allowed('mysql')];
foreach (['192.0.2.1','::','127.0.0.2'] as $ip) {
    $bad = $s; $bad['REMOTE_ADDR'] = $ip; $checks[] = !devlite_request_allowed($bad, [], []);
}
$checks[] = !devlite_request_allowed($s, ['server'=>'example.org'], []);
$checks[] = !devlite_request_allowed($s, [], ['auth'=>['server'=>'localhost','username'=>'root','password'=>'x']]);
$checks[] = devlite_request_allowed($s, [], ['auth'=>['server'=>'localhost','username'=>'devlite_admin','password'=>'x']]);
foreach (['root','ROOT','mysql.sys','mysql.session','mariadb.sys',null,[], 'bad name'] as $user) $checks[] = !devlite_user_allowed($user);
foreach (['server','username'] as $key) $checks[] = !devlite_request_allowed($s, [$key=>null], []);
$checks[] = !devlite_request_allowed($s, [], ['auth'=>null]);
foreach (['evil.example:8081','127.0.0.1','localhost:80'] as $host) { $bad=$s; $bad['HTTP_HOST']=$host; $checks[] = !devlite_request_allowed($bad,[],[]); }
$ip6=$s; $ip6['REMOTE_ADDR']='::1'; $ip6['HTTP_HOST']='[::1]:8081'; $checks[] = devlite_request_allowed($ip6,[],[]);
$bad=$s; $bad['REQUEST_URI']='/devlite-adminer/adminer.php'; $checks[] = !devlite_request_allowed($bad,[],[]);
foreach ($checks as $check) if ($check !== true) exit(1);
echo count($checks), " verificações PHP aprovadas\n";
