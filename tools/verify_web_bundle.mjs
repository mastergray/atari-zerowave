// SPDX-FileCopyrightText: 2026 mastergray
// SPDX-License-Identifier: GPL-3.0-only

// Exercise the actual vendored loader, decompressor and core-selection code.
// Browser DOM/audio/graphics are not emulated; every requested file must be local.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { Worker } from "node:worker_threads";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const web = path.join(root, "web");
const data = path.join(web, "emulatorjs/data");
const read = (name) => readFile(path.join(web, name));
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const manifest = JSON.parse(await read("emulatorjs/manifest.json"));
for (const [name, hash] of Object.entries(manifest.files)) {
    assert.equal(sha256(await read("emulatorjs/" + name)), hash, name);
}
const romHash = sha256(await read("zerowave.bin"));
const requests = [];
for (const base of ["https://example.test/", "https://example.test/zerowave/",
                    "https://example.test/games/zerowave/index.html"]) {
    const directory = new URL(".", base);
    const local = async (url) => {
        const resolved = new URL(url, base);
        assert.equal(resolved.origin, directory.origin, "External request: " + url);
        assert.ok(resolved.pathname.startsWith(directory.pathname), "Escaped upload folder: " + url);
        requests.push(resolved.href);
        return read(decodeURIComponent(resolved.pathname.slice(directory.pathname.length)));
    };
    const scripts = [];
    const nodes = { status: { classList: { add() {} }, setAttribute() {} }, launch: {}, "start-action": {} };
    const context = vm.createContext({
        URL, console, Intl,
        location: new URL(base),
        document: {
            getElementById: id => nodes[id],
            createElement: () => ({}),
            body: { appendChild: script => scripts.push(script) },
            head: { appendChild(element) {
                local(element.src || element.href).then(bytes => {
                    if (element.src) new vm.Script(bytes.toString(), { filename: element.src });
                    element.onload();
                }).catch(error => { throw error; });
            } }
        },
        fetch: async url => ({ text: async () => (await local(url)).toString() }),
        // The loader is real; only its final DOM-heavy frontend constructor is substituted.
        EmulatorJS: class {
            constructor(selector, config) { this.config = config; }
            on() {}
        }
    });
    context.window = context;
    vm.runInContext((await read("rom-version.js")).toString(), context);
    vm.runInContext((await read("player.js")).toString(), context);
    assert.equal(new URL(context.EJS_gameUrl).searchParams.get("v"), romHash);
    assert.equal(sha256(await local(context.EJS_gameUrl)), romHash);
    assert.equal(context.EJS_Buttons.netplay, false);
    await vm.runInContext((await local(scripts[0].src)).toString(), context);
    assert.equal(context.EJS_emulator.config.dataPath, new URL("emulatorjs/data/", base).href);
    assert.equal(context.EJS_emulator.config.system, "atari2600");
}

async function decompress(filename) {
    // Run the shipped browser worker with the same message API, using real 7z data.
    return new Promise((resolve, reject) => {
        const worker = new Worker(`
            const { parentPort, workerData } = require("node:worker_threads");
            const fs = require("node:fs");
            const vm = require("node:vm");
            const browser = {
                console, setTimeout, clearTimeout,
                location: { href: "https://example.test/zerowave/emulatorjs/data/compression/extract7z.js" },
                importScripts() { throw Error("Unexpected external worker import"); },
                postMessage: message => parentPort.postMessage(message),
                close() {}
            };
            browser.self = browser;
            vm.runInNewContext(fs.readFileSync(workerData.script, "utf8"), browser,
                { filename: "extract7z.js", displayErrors: false });
            browser.onmessage({ data: new Uint8Array(fs.readFileSync(workerData.archive)) });
        `, { eval: true, workerData: {
            script: path.join(data, "compression/extract7z.js"),
            archive: path.join(data, "cores", filename)
        } });
        const files = {};
        const timeout = setTimeout(() => { worker.terminate(); reject(Error("Core extraction timed out")); }, 30000);
        worker.on("error", error => { clearTimeout(timeout); reject(Error(filename + ": " + error.message)); });
        worker.on("message", message => {
            if (message.t === 2) files[message.file] = message.data;
            if (message.t === 1) {
                clearTimeout(timeout);
                worker.terminate();
                resolve(files);
            }
        });
    });
}

const runtime = vm.createContext({ window: { SharedArrayBuffer }, TextDecoder, Uint8Array, console,
    fetch: url => { throw Error("External update check: " + url); } });
vm.runInContext((await read("emulatorjs/data/src/emulator.js")).toString(), runtime);
const prototype = runtime.window.EmulatorJS.prototype;
prototype.checkForUpdates.call({ ejs_version: "4.2.3" });
const coreReport = JSON.parse(await read("emulatorjs/data/cores/reports/stella2014.json"));
const variants = [];
for (const threads of [false, true]) {
    for (const modern of [false, true]) {
        const filename = "stella2014" + (threads ? "-thread" : "") + (modern ? "" : "-legacy") + "-wasm.data";
        const files = await decompress(filename);
        assert.ok(files["stella2014_libretro.js"], filename);
        assert.ok(WebAssembly.validate(files["stella2014_libretro.wasm"]), filename);
        assert.equal(JSON.parse(new TextDecoder().decode(files["core.json"])).name, "stella2014");
        for (const missing of [false, true]) {
            const fetched = [];
            await new Promise((resolve, reject) => {
                const emulator = {
                    config: { threads }, supportsWebgl2: modern, webgl2Enabled: modern,
                    debug: false, textElem: {},
                    elements: { bottomBar: { saveSavFiles: [{ style: {} }], loadSavFiles: [{ style: {} }] } },
                    localization: text => text, getCore: () => "stella2014",
                    requiresThreads: () => false, requiresWebGL2: () => false, preGetSetting: () => null,
                    storage: { core: { get: async () => null, put() {} } },
                    checkCompression: async () => files,
                    checkCoreCompatibility(build) { assert.equal(build.version, "2.0.2"); },
                    downloadFile: async url => {
                        fetched.push(url);
                        assert.ok(!/^https?:/.test(url), "Remote fallback: " + url);
                        if (url.endsWith(".json")) return { data: coreReport };
                        assert.equal(url, "cores/" + filename);
                        return missing ? -1 : { data: await read("emulatorjs/data/" + url) };
                    },
                    startGameError(message) {
                        if (!missing) reject(Error(message));
                        else resolve();
                    },
                    initGameCore(js, wasm) {
                        assert.ok(!missing);
                        assert.ok(WebAssembly.validate(wasm));
                        resolve();
                    }
                };
                prototype.downloadGameCore.call(emulator);
            });
            assert.equal(fetched.length, 2, "Only local report and core may be requested");
        }
        variants.push(filename);
    }
}
const report = { manifestFiles: Object.keys(manifest.files).length, localLoaderRequests: requests.length,
    basePaths: ["/", "/zerowave/", "/games/zerowave/index.html"], coreVariants: variants,
    remoteUpdateAndFallbackDisabled: true, romSha256: romHash,
    browserVisualCheck: "Not performed by this Node integration check." };
await mkdir(path.join(root, "build"), { recursive: true });
await writeFile(path.join(root, "build/web-bundle-validation.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
