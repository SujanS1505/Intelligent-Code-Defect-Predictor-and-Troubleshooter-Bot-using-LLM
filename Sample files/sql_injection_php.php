<?php
$id = $_GET['id'];
$query = "SELECT * FROM users WHERE id='$id'"; // vulnerable query
mysqli_query($conn, $query);
?>
