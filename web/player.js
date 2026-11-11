// SPDX-FileCopyrightText: 2026 mastergray
// SPDX-License-Identifier: GPL-3.0-only

(() => {
    "use strict";

    const status = document.getElementById("status");
    const launch = document.getElementById("launch");
    const startAction = document.getElementById("start-action");
    const fail = (message) => {
        status.hidden = false;
        status.textContent = message;
        status.classList.add("error");
        status.setAttribute("role", "alert");
        startAction.textContent = "Player unavailable";
    };

    if (window.location.protocol === "file:") {
        fail("Serve this folder with python3 -m http.server 8000, then open http://127.0.0.1:8000/.");
        return;
    }

    // Pin the wrapper and its Stella 2014 core to one release. The original
    // cartridge is served alongside this page, keeping web/ portable.
    const dataPath = new URL("emulatorjs/data/", window.location.href).href;
    window.EJS_player = "#game";
    window.EJS_core = "atari2600";
    const romUrl = new URL("zerowave.bin", window.location.href);
    // Each ROM hash gets its own cache entry, even though F8 size never changes.
    romUrl.searchParams.set("v", window.ZEROWAVE_ROM_VERSION);
    window.EJS_gameUrl = romUrl.href;
    window.EJS_gameName = "ZeroWave";
    window.EJS_pathtodata = dataPath;
    window.EJS_threads = false;
    window.EJS_startOnLoaded = false; // The player's click unlocks browser audio.
    window.EJS_startButtonName = "CLICK TO PLAY";
    window.EJS_alignStartButton = "center";
    window.EJS_color = "#f5dfb3";
    window.EJS_backgroundColor = "#000000";
    window.EJS_volume = 0.5;
    window.EJS_language = "en-US";
    window.EJS_disableAutoLang = true;

    // EmulatorJS replaces its defaults with this complete mapping. In
    // particular, remove the default Space-to-rewind binding (control 28).
    const controls = Object.fromEntries(Array.from({ length: 30 }, (_, id) =>
        [id, { value: "", value2: "" }]));
    Object.assign(controls, {
        0: { value: "space", value2: "BUTTON_1" },
        2: { value: "v", value2: "SELECT" },
        3: { value: "enter", value2: "START" },
        4: { value: "up arrow", value2: "DPAD_UP" },
        5: { value: "down arrow", value2: "DPAD_DOWN" },
        6: { value: "left arrow", value2: "DPAD_LEFT" },
        7: { value: "right arrow", value2: "DPAD_RIGHT" }
    });
    window.EJS_defaultControls = { 0: controls, 1: {}, 2: {}, 3: {} };
    window.EJS_Buttons = {
        fullscreen: true,
        netplay: false,
        cheat: false,
        screenRecord: false,
        saveSavFiles: false,
        loadSavFiles: false
    };
    window.EJS_ready = () => {
        // Move the actual 4.2.3 button into our panel, retaining its original
        // click/touch handlers so browser audio and touch controls still start
        // through the user's gesture. No private emulator methods are called.
        const button = document.querySelector("#game .ejs_start_button");
        if (!button) {
            fail("The start button could not load. Reload this page to try again.");
            return;
        }
        button.setAttribute("role", "button");
        button.setAttribute("tabindex", "0");
        button.setAttribute("aria-describedby", "start-note");
        button.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                if (!event.repeat) button.click();
            }
        });
        button.addEventListener("click", () => { launch.hidden = true; }, { once: true });
        startAction.replaceChildren(button);
        status.hidden = true;
    };
    window.EJS_onGameStart = () => {
        launch.hidden = true;
        status.hidden = true;
    };

    const loader = document.createElement("script");
    loader.src = dataPath + "loader.js";
    loader.onerror = () => fail("The player could not load. Check that the complete web folder was uploaded, then reload this page.");
    document.body.appendChild(loader);
})();
