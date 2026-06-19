document.addEventListener("DOMContentLoaded", function () {
    // load sparkle cursor on every page
    const sparkleScript = document.createElement("script");
    sparkleScript.src = "sparkle.js";
    document.head.appendChild(sparkleScript);

    const page = location.pathname.split("/").pop() || "spotify.html";
    const links = [
        ["spotify.html", "Spotify Stats"],
        ["books.html", "Books"],
        
    ];

    const nav = links
        .map(([href, label]) => {
            const active = href === page ? ' class="active"' : "";
            return `<a href="${href}"${active}>${label}</a>`;
        })
        .join("\n                ");

    const sidebar = document.querySelector(".sidebar");
    sidebar.innerHTML = `
            <img src="photos/fishies.jpg" alt="Avatar" class="avatar">
            <div class="sidebar-card">
                <p class="description">go placidly.</p>
                <p class="welcome">Hi, this is my personal site and its in progress</p>
                <nav>
                ${nav}
                </nav>
            </div>`;
});
