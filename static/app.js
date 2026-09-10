// Business OS browser interactions.
// Server actions remain explicit and backend-controlled.

document.addEventListener("DOMContentLoaded", () => {

    setupSidebar();
    setupClickableRows();
    setupLeadFilters();
    setupCallFilters();

});


function setupSidebar() {

    const toggle = document.querySelector(
        "[data-sidebar-toggle]"
    );

    if (!toggle) {
        return;
    }

    const storageKey =
        "business-os-sidebar-collapsed";

    const saved =
        localStorage.getItem(storageKey);

    if (saved === "true") {
        document.body.classList.add(
            "sidebar-collapsed"
        );
    }


    updateSidebarButton(toggle);


    toggle.addEventListener(
        "click",
        () => {

            const collapsed =
                document.body.classList.toggle(
                    "sidebar-collapsed"
                );

            localStorage.setItem(
                storageKey,
                String(collapsed)
            );

            updateSidebarButton(toggle);

        }
    );

}


function updateSidebarButton(toggle) {

    const collapsed =
        document.body.classList.contains(
            "sidebar-collapsed"
        );

    toggle.textContent =
        collapsed ? "›" : "‹";

    toggle.setAttribute(
        "aria-label",
        collapsed
            ? "Expand sidebar"
            : "Collapse sidebar"
    );

    toggle.setAttribute(
        "title",
        collapsed
            ? "Expand sidebar"
            : "Collapse sidebar"
    );

}


function setupClickableRows() {

    const rows =
        document.querySelectorAll(
            ".clickable-row[data-href]"
        );

    rows.forEach((row) => {

        row.addEventListener(
            "click",
            (event) => {

                const interactive =
                    event.target.closest(
                        "a, button, input, select, textarea"
                    );

                if (interactive) {
                    return;
                }

                const href =
                    row.dataset.href;

                if (href) {
                    window.location.href =
                        href;
                }

            }
        );

    });

}


function setupLeadFilters() {

    const search =
        document.querySelector(
            "[data-lead-search]"
        );

    const status =
        document.querySelector(
            "[data-lead-status]"
        );

    const priority =
        document.querySelector(
            "[data-lead-priority]"
        );

    const reset =
        document.querySelector(
            "[data-lead-reset]"
        );

    const rows = [
        ...document.querySelectorAll(
            "[data-lead-row]"
        ),
    ];

    if (
        !search
        || !status
        || !priority
        || rows.length === 0
    ) {
        return;
    }


    const apply = () => {

        const query =
            search.value
                .trim()
                .toLowerCase();

        const wantedStatus =
            status.value
                .trim()
                .toLowerCase();

        const wantedPriority =
            priority.value
                .trim()
                .toLowerCase();


        let visible = 0;


        rows.forEach((row) => {

            const searchText =
                (
                    row.dataset.search
                    || ""
                ).toLowerCase();

            const rowStatus =
                (
                    row.dataset.status
                    || ""
                ).toLowerCase();

            const rowPriority =
                (
                    row.dataset.priority
                    || ""
                ).toLowerCase();


            const searchMatch =
                !query
                || searchText.includes(
                    query
                );

            const statusMatch =
                !wantedStatus
                || rowStatus ===
                    wantedStatus;

            const priorityMatch =
                !wantedPriority
                || rowPriority ===
                    wantedPriority;


            const show =
                searchMatch
                && statusMatch
                && priorityMatch;


            row.hidden = !show;


            if (show) {
                visible += 1;
            }

        });


        updateCount(
            "[data-lead-count]",
            "[data-lead-plural]",
            visible
        );


        const empty =
            document.querySelector(
                "[data-lead-empty]"
            );

        if (empty) {
            empty.hidden =
                visible !== 0;
        }

    };


    search.addEventListener(
        "input",
        apply
    );

    status.addEventListener(
        "change",
        apply
    );

    priority.addEventListener(
        "change",
        apply
    );


    if (reset) {

        reset.addEventListener(
            "click",
            () => {

                search.value = "";
                status.value = "";
                priority.value = "";

                apply();

                search.focus();

            }
        );

    }


    apply();

}


function setupCallFilters() {

    const search =
        document.querySelector(
            "[data-call-search]"
        );

    const status =
        document.querySelector(
            "[data-call-status]"
        );

    const reset =
        document.querySelector(
            "[data-call-reset]"
        );

    const rows = [
        ...document.querySelectorAll(
            "[data-call-row]"
        ),
    ];


    if (
        !search
        || !status
        || rows.length === 0
    ) {
        return;
    }


    const apply = () => {

        const query =
            search.value
                .trim()
                .toLowerCase();

        const wantedStatus =
            status.value
                .trim()
                .toLowerCase();

        let visible = 0;


        rows.forEach((row) => {

            const searchText =
                (
                    row.dataset.search
                    || ""
                ).toLowerCase();

            const rowStatus =
                (
                    row.dataset.status
                    || ""
                ).toLowerCase();


            const searchMatch =
                !query
                || searchText.includes(
                    query
                );

            const statusMatch =
                !wantedStatus
                || rowStatus ===
                    wantedStatus;

            const show =
                searchMatch
                && statusMatch;


            row.hidden = !show;


            if (show) {
                visible += 1;
            }

        });


        updateCount(
            "[data-call-count]",
            "[data-call-plural]",
            visible
        );


        const empty =
            document.querySelector(
                "[data-call-empty]"
            );

        if (empty) {
            empty.hidden =
                visible !== 0;
        }

    };


    search.addEventListener(
        "input",
        apply
    );

    status.addEventListener(
        "change",
        apply
    );


    if (reset) {

        reset.addEventListener(
            "click",
            () => {

                search.value = "";
                status.value = "";

                apply();

                search.focus();

            }
        );

    }


    apply();

}


function updateCount(
    countSelector,
    pluralSelector,
    count
) {

    const countElement =
        document.querySelector(
            countSelector
        );

    const pluralElement =
        document.querySelector(
            pluralSelector
        );


    if (countElement) {
        countElement.textContent =
            String(count);
    }


    if (pluralElement) {
        pluralElement.textContent =
            count === 1 ? "" : "s";
    }

}
