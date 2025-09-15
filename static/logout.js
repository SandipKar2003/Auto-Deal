
function showLogoutConfirm(event) {
    event.preventDefault();
    document.getElementById("logoutConfirmBox").style.display = "block";
}

function hideLogoutConfirm() {
    document.getElementById("logoutConfirmBox").style.display = "none";
}

function confirmLogout() {
    window.location.href = "/logout";
}

