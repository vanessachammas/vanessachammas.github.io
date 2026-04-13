document.addEventListener("DOMContentLoaded", function () {
    const page = location.pathname.split("/").pop() || "index.html";
    const links = [
        ["index.html", "Home"],
        ["about.html", "About"],
        ["projects.html", "Projects"],
        ["blog.html", "Blog"],
        ["books.html", "Books"],
        ["good-words.html", "Good Words"],
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
                <nav>
                ${nav}
                </nav>
            </div>`;
});
