<?php

define('CONFIG_IncludeDir', 'includes/');

require_once(__DIR__ . '/' . CONFIG_IncludeDir . 'vendor/autoload.php');
include 'TIS_login.php';

$schema = new DBschema();
$sql = "SELECT * FROM tis_users WHERE users_id = ?";
$db->query("UPDATE tis_assets SET asset_name = 'demo'");
