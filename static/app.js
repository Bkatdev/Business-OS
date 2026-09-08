document.addEventListener("DOMContentLoaded", () => {
    const openButtons = document.querySelectorAll("[data-open-modal]");
    const closeButtons = document.querySelectorAll("[data-close-modal]");
    const mobileMenu = document.querySelector("[data-mobile-menu]");
    const sidebar = document.getElementById("sidebar");

    openButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const modal = document.getElementById(button.dataset.openModal);
            if (modal) {
                modal.classList.add("open");
                document.body.classList.add("modal-open");
            }
        });
    });

    const closeModal = (modal) => {
        modal.classList.remove("open");
        document.body.classList.remove("modal-open");
    };

    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const modal = button.closest(".modal-backdrop");
            if (modal) closeModal(modal);
        });
    });

    document.querySelectorAll(".modal-backdrop").forEach((modal) => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) closeModal(modal);
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            document.querySelectorAll(".modal-backdrop.open").forEach(closeModal);
        }
    });

    if (mobileMenu && sidebar) {
        mobileMenu.addEventListener("click", () => {
            sidebar.classList.toggle("mobile-open");
        });
    }
});
