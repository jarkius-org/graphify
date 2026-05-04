<?php

if ($saved) {
    header("Location: asset_list.php");
}

if ($target) {
    header("Location: " . $target);
}

if ($base) {
    header("Location: $base/asset.php");
}

echo '<a href="' . htmlspecialchars($url) . '">Ignore Dynamic Echo Link</a>';
echo '<a href="' . htmlspecialchars(rtrim(mmsGetBaseURL(), '/') . '/TIS_module.php?name=TIS-Asset') . '">Ignore Dynamic Base Link</a>';
?>

<form action="save_asset.php" method="post">
  <input type="text" name="asset_serial_no">
  <button type="submit">Save Asset</button>
  <input type="submit" value="Print Form">
</form>

<a href="asset_detail.php?id=1">View Detail</a>
<a href="#">Ignore Placeholder</a>
<a href="mailto:help@example.com">Ignore Mail</a>
<a href="http://'.($datarow[11]).'">Ignore Dynamic Legacy String</a>
<a href="http://[bad">Ignore Malformed URL</a>

<script>
  window.location = "asset_print.php";
  location.href = 'logout.php';
  document.location = redirectTarget;
</script>
