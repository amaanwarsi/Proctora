const FULLSCREEN_EXIT_COUNT_KEY = "proctoraFullscreenExitCount";
const WORKSPACE_REQUESTED_KEY = "proctoraWorkspaceRequested";
const INTENTIONAL_FULLSCREEN_EXIT_KEY = "proctoraIntentionalFullscreenExit";

async function fetchAlerts() {
    const alertsContainer = document.getElementById("alerts");

    if (!alertsContainer) {
        return;
    }

    try {
        const response = await fetch("/alerts");
        const data = await response.json();
        alertsContainer.innerHTML = "";

        if (!data.alerts.length) {
            alertsContainer.innerHTML = "<li class='alerts__empty'>No alerts detected.</li>";
            return;
        }

        data.alerts.forEach((alert) => {
            const item = document.createElement("li");
            item.className = "alerts__item";
            item.innerHTML = `<span>${alert.message}</span><strong>${alert.count}</strong>`;
            alertsContainer.appendChild(item);
        });
    } catch (error) {
        alertsContainer.innerHTML = "<li class='alerts__empty'>Unable to load alerts.</li>";
        console.error("Error fetching alerts:", error);
    }
}

function getFullscreenExitCount() {
    return Number.parseInt(localStorage.getItem(FULLSCREEN_EXIT_COUNT_KEY) || "0", 10);
}

function setFullscreenExitCount(count) {
    localStorage.setItem(FULLSCREEN_EXIT_COUNT_KEY, String(count));
}

function incrementFullscreenExitCount() {
    const nextCount = getFullscreenExitCount() + 1;
    setFullscreenExitCount(nextCount);
    return nextCount;
}

function setupHomePage() {
    const trigger = document.querySelector("[data-enter-workspace]");
    const warning = document.getElementById("fullscreen-warning");
    const warningCount = document.getElementById("fullscreen-warning-count");
    const warningMessage = document.getElementById("fullscreen-warning-message");
    const params = new URLSearchParams(window.location.search);

    if (trigger) {
        trigger.addEventListener("click", () => {
            sessionStorage.setItem(WORKSPACE_REQUESTED_KEY, "true");
        });
    }

    if (!warning) {
        return;
    }

    const exitCount = getFullscreenExitCount();
    const shouldWarn = params.get("fullscreen") === "cancelled" && exitCount > 0;

    if (shouldWarn) {
        warning.hidden = false;
        if (warningCount) {
            warningCount.textContent = String(exitCount);
        }
        if (warningMessage) {
            warningMessage.textContent = `Fullscreen mode was cancelled ${exitCount} time${exitCount === 1 ? "" : "s"}. This count is preserved so developers can attach their own actions or penalties.`;
        }
    }
}

async function requestFullscreenMode() {
    if (document.fullscreenElement) {
        return true;
    }

    const target = document.documentElement;
    if (!target.requestFullscreen) {
        return false;
    }

    try {
        await target.requestFullscreen();
        return true;
    } catch (error) {
        console.error("Fullscreen request failed:", error);
        return false;
    }
}

function showWorkspace() {
    const workspace = document.getElementById("workspace");
    const gate = document.getElementById("fullscreen-gate");

    if (!workspace || !gate) {
        return;
    }

    gate.hidden = true;
    gate.classList.add("fullscreen-gate--hidden");
    workspace.classList.remove("workspace--hidden");
    workspace.setAttribute("aria-hidden", "false");
    workspace.focus({ preventScroll: true });
}

function redirectHomeForFullscreenExit() {
    incrementFullscreenExitCount();
    sessionStorage.removeItem(WORKSPACE_REQUESTED_KEY);
    window.location.replace("/?fullscreen=cancelled");
}

function openDoneModal() {
    const modal = document.getElementById("done-modal");
    if (!modal) {
        return;
    }

    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
}

function closeDoneModal() {
    const modal = document.getElementById("done-modal");
    if (!modal) {
        return;
    }

    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
}

function openQuitModal() {
    const modal = document.getElementById("quit-modal");
    if (!modal) {
        return;
    }

    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
}

function closeQuitModal() {
    const modal = document.getElementById("quit-modal");
    if (!modal) {
        return;
    }

    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
}

function finishExam() {
    sessionStorage.setItem(INTENTIONAL_FULLSCREEN_EXIT_KEY, "true");
    sessionStorage.removeItem(WORKSPACE_REQUESTED_KEY);

    const redirect = () => {
        window.location.assign("/confirmation");
    };

    if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().finally(redirect);
        return;
    }

    redirect();
}

function quitExam() {
    closeQuitModal();
    finishExam();
}

function setupWorkspaceNavbar() {
    const navbar = document.querySelector(".panel--workspace-bar");
    const workspace = document.getElementById("workspace");

    let isVisible = true;

    const show = () => {
        if (isVisible) return;
        navbar.classList.remove("nav-hidden");
        workspace.classList.remove("nav-hidden");
        isVisible = true;
    };

    const hide = () => {
        if (!isVisible) return;
        navbar.classList.add("nav-hidden");
        workspace.classList.add("nav-hidden");
        isVisible = false;
    };

    // Hover navbar → show
    navbar.addEventListener("mouseenter", show);
    navbar.addEventListener("mouseleave", hide);

    // Move mouse to top → show
    document.addEventListener("mousemove", (e) => {
        if (e.clientY <= 10) {
            show();
        }
    });

}

function setupWorkspacePage() {
    const workspace = document.getElementById("workspace");
    const enterButton = document.getElementById("enter-fullscreen");
    const errorMessage = document.getElementById("fullscreen-error");
    const doneButton = document.getElementById("done-exam");
    const quitButton = document.getElementById("quit-exam");
    const confirmDoneButton = document.getElementById("confirm-done");
    const confirmQuitButton = document.getElementById("confirm-quit");
    const closeModalButtons = document.querySelectorAll("[data-close-modal]");
    const closeQuitModalButtons = document.querySelectorAll("[data-close-quit-modal]");

    if (!workspace || !enterButton) {
        return;
    }

    setupWorkspaceNavbar();

    const updateWorkspaceState = () => {
        if (document.fullscreenElement) {
            showWorkspace();
            return;
        }

        if (sessionStorage.getItem(INTENTIONAL_FULLSCREEN_EXIT_KEY) === "true") {
            sessionStorage.removeItem(INTENTIONAL_FULLSCREEN_EXIT_KEY);
            return;
        }

        if (!document.fullscreenElement && !workspace.classList.contains("workspace--hidden")) {
            redirectHomeForFullscreenExit();
        }
    };

    document.addEventListener("fullscreenchange", updateWorkspaceState);

    enterButton.addEventListener("click", async () => {
        const entered = await requestFullscreenMode();
        if (entered) {
            sessionStorage.setItem(WORKSPACE_REQUESTED_KEY, "true");
            showWorkspace();
            return;
        }

        if (errorMessage) {
            errorMessage.hidden = false;
            errorMessage.textContent = "Fullscreen permission was denied. Please try again to continue.";
        }
    });

    if (doneButton) {
        doneButton.addEventListener("click", openDoneModal);
    }

    if (quitButton) {
        quitButton.addEventListener("click", openQuitModal);
    }

    if (confirmDoneButton) {
        confirmDoneButton.addEventListener("click", finishExam);
    }

    if (confirmQuitButton) {
        confirmQuitButton.addEventListener("click", quitExam);
    }

    closeModalButtons.forEach((button) => {
        button.addEventListener("click", closeDoneModal);
    });

    closeQuitModalButtons.forEach((button) => {
        button.addEventListener("click", closeQuitModal);
    });

    if (sessionStorage.getItem(WORKSPACE_REQUESTED_KEY) === "true") {
        requestFullscreenMode().then((entered) => {
            if (entered) {
                showWorkspace();
            }
        });
    }
}

setupHomePage();
setupWorkspacePage();
setInterval(fetchAlerts, 5000);
fetchAlerts();
