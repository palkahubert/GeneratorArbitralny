"use strict";

const SAMPLE_COUNT = 4096;
const MAGIC = [0x41, 0x57, 0x47, 0x31];
const CMD_LOAD = 0x01;
const CMD_CONFIG = 0x02;
const CMD_ENABLE = 0x03;
const CMD_RESET = 0x04;
const CMD_PING = 0x05;

const state = {
  mode: "sine",
  samples: new Uint16Array(SAMPLE_COUNT),
  port: null,
  writer: null,
  reader: null,
  reading: false
};

const el = {};

function bindElements() {
  for (const id of [
    "serialStatus", "exportMemBtn", "copyCBtn", "sendWaveBtn", "modeGrid",
    "exportXsdbBtn", "copyXsdbConfigBtn",
    "freqHz", "clockHz", "amplitude", "offset", "cycles", "phase", "duty",
    "harmonics", "wildness", "seed", "formulaBox", "formulaInput",
    "softClip", "invert", "dcBlock", "waveCanvas", "histCanvas", "minValue",
    "maxValue", "meanValue", "phaseStepValue", "randomizeBtn", "resetBtn",
    "baudRate", "gainQ16", "offsetRaw", "connectBtn", "sendConfigBtn",
    "enableBtn", "resetAwgBtn", "progressFill", "progressText", "logBox",
    "packetSize"
  ]) {
    el[id] = document.getElementById(id);
  }
}

function numberValue(id) {
  return Number(el[id].value);
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function wrapSigned(value) {
  if (!Number.isFinite(value)) return 0;
  return clamp(value, -1, 1);
}

function mulberry32(seed) {
  let t = seed >>> 0;
  return function random() {
    t += 0x6D2B79F5;
    let x = t;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

function triangleWave(x) {
  const p = x - Math.floor(x);
  return 1 - 4 * Math.abs(p - 0.5);
}

function sawWave(x) {
  const p = x - Math.floor(x);
  return 2 * p - 1;
}

function makeFormulaEvaluator(expression) {
  const body = `
    const sin = Math.sin, cos = Math.cos, tan = Math.tan, abs = Math.abs;
    const pow = Math.pow, sqrt = Math.sqrt, floor = Math.floor, round = Math.round;
    const min = Math.min, max = Math.max, pi = Math.PI;
    const tri = (x) => 1 - 4 * Math.abs((x - Math.floor(x)) - 0.5);
    const saw = (x) => 2 * (x - Math.floor(x)) - 1;
    const sqr = (x, duty = 0.5) => ((x - Math.floor(x)) < duty ? 1 : -1);
    return (${expression});
  `;
  return new Function("t", "i", "n", "rand", body);
}

function baseValue(mode, t, i, random) {
  const cycles = numberValue("cycles");
  const phase = numberValue("phase") / 360;
  const x = cycles * t + phase;
  const duty = numberValue("duty") / 100;
  const wild = numberValue("wildness") / 100;
  const harmonics = numberValue("harmonics");

  if (mode === "sine") {
    return Math.sin(2 * Math.PI * x);
  }

  if (mode === "square") {
    return (x - Math.floor(x)) < duty ? 1 : -1;
  }

  if (mode === "triangle") {
    return triangleWave(x);
  }

  if (mode === "saw") {
    return sawWave(x);
  }

  if (mode === "noise") {
    const slow = Math.sin(2 * Math.PI * x) * (1 - wild);
    const rough = (random() * 2 - 1) * (0.35 + wild);
    return wrapSigned(slow + rough);
  }

  if (mode === "fm") {
    const modRate = 1 + Math.round(wild * 14);
    const depth = 0.1 + wild * 4.5;
    const warped = x + depth * Math.sin(2 * Math.PI * modRate * t) / (2 * Math.PI);
    return Math.sin(2 * Math.PI * warped);
  }

  if (mode === "additive") {
    let sum = 0;
    let norm = 0;
    for (let h = 1; h <= harmonics; h++) {
      const weight = 1 / Math.pow(h, 0.72 + wild);
      const sign = h % 2 === 0 ? 0.65 : 1;
      sum += sign * weight * Math.sin(2 * Math.PI * h * x);
      norm += Math.abs(sign * weight);
    }
    return norm > 0 ? sum / norm : 0;
  }

  if (mode === "spikes") {
    const base = 0.42 * Math.sin(2 * Math.PI * x);
    const p = x - Math.floor(x);
    const spikeWidth = 0.012 + 0.05 * wild;
    const spike = p < spikeWidth ? 1 : p > 1 - spikeWidth ? -1 : 0;
    const hash = Math.sin((i + 1) * 91.345 + numberValue("seed")) * 43758.5453;
    const rare = (hash - Math.floor(hash)) > 0.985 - wild * 0.03 ? random() * 2 - 1 : 0;
    return wrapSigned(base + 0.72 * spike + 0.55 * rare);
  }

  if (mode === "formula") {
    try {
      const fn = makeFormulaEvaluator(el.formulaInput.value);
      return wrapSigned(fn(t, i, SAMPLE_COUNT, random));
    } catch (error) {
      return 0;
    }
  }

  return 0;
}

function generateSamples() {
  const random = mulberry32(numberValue("seed"));
  const amp = numberValue("amplitude") / 100;
  const offset = (numberValue("offset") - 50) / 100;
  const wild = numberValue("wildness") / 100;
  let signed = new Float64Array(SAMPLE_COUNT);

  for (let i = 0; i < SAMPLE_COUNT; i++) {
    const t = i / SAMPLE_COUNT;
    let v = baseValue(state.mode, t, i, random);

    if (wild > 0 && state.mode !== "noise") {
      v += (random() * 2 - 1) * wild * 0.12;
    }

    if (el.softClip.checked) {
      v = Math.tanh(v * (1.05 + wild * 1.8));
    }

    if (el.invert.checked) {
      v = -v;
    }

    signed[i] = wrapSigned(v);
  }

  if (el.dcBlock.checked) {
    let mean = 0;
    for (const v of signed) mean += v;
    mean /= signed.length;
    for (let i = 0; i < signed.length; i++) signed[i] = wrapSigned(signed[i] - mean);
  }

  let min = 65535;
  let max = 0;
  let sum = 0;

  for (let i = 0; i < SAMPLE_COUNT; i++) {
    const level = clamp(0.5 + signed[i] * 0.5 * amp + offset, 0, 1);
    const sample = Math.round(level * 65535);
    state.samples[i] = sample;
    min = Math.min(min, sample);
    max = Math.max(max, sample);
    sum += sample;
  }

  el.minValue.textContent = String(min);
  el.maxValue.textContent = String(max);
  el.meanValue.textContent = String(Math.round(sum / SAMPLE_COUNT));
  el.phaseStepValue.textContent = "0x" + computePhaseStep().toString(16).toUpperCase().padStart(8, "0");
  el.packetSize.textContent = `${buildLoadPayload().length + 9} bytes`;

  drawWaveform();
  drawHistogram();
}

function drawWaveform() {
  const canvas = el.waveCanvas;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.fillStyle = "#101817";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "rgba(215, 239, 228, 0.12)";
  ctx.lineWidth = 1 * dpr;
  for (let x = 0; x <= 12; x++) {
    const px = (x / 12) * w;
    ctx.beginPath();
    ctx.moveTo(px, 0);
    ctx.lineTo(px, h);
    ctx.stroke();
  }
  for (let y = 0; y <= 8; y++) {
    const py = (y / 8) * h;
    ctx.beginPath();
    ctx.moveTo(0, py);
    ctx.lineTo(w, py);
    ctx.stroke();
  }

  const mid = h * 0.5;
  ctx.strokeStyle = "rgba(232, 186, 90, 0.45)";
  ctx.beginPath();
  ctx.moveTo(0, mid);
  ctx.lineTo(w, mid);
  ctx.stroke();

  ctx.strokeStyle = "#7ee0b4";
  ctx.lineWidth = Math.max(1.4 * dpr, 1);
  ctx.beginPath();
  const stride = Math.max(1, Math.floor(SAMPLE_COUNT / w));
  let first = true;
  for (let i = 0; i < SAMPLE_COUNT; i += stride) {
    const x = (i / (SAMPLE_COUNT - 1)) * w;
    const y = h - (state.samples[i] / 65535) * h;
    if (first) {
      ctx.moveTo(x, y);
      first = false;
    } else {
      ctx.lineTo(x, y);
    }
  }
  ctx.stroke();

  ctx.fillStyle = "rgba(126, 224, 180, 0.10)";
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fill();
}

function drawHistogram() {
  const canvas = el.histCanvas;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const bins = new Uint16Array(96);
  let maxBin = 1;

  for (const sample of state.samples) {
    const idx = Math.min(bins.length - 1, Math.floor(sample / 65536 * bins.length));
    bins[idx]++;
    maxBin = Math.max(maxBin, bins[idx]);
  }

  ctx.fillStyle = "#fbfcfa";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#d7ddd7";
  ctx.beginPath();
  ctx.moveTo(0, h - 0.5 * dpr);
  ctx.lineTo(w, h - 0.5 * dpr);
  ctx.stroke();

  const gap = 1 * dpr;
  const barW = w / bins.length;
  for (let i = 0; i < bins.length; i++) {
    const barH = (bins[i] / maxBin) * (h - 14 * dpr);
    ctx.fillStyle = i % 2 ? "#226a86" : "#1f7a5a";
    ctx.fillRect(i * barW + gap, h - barH, Math.max(1, barW - 2 * gap), barH);
  }
}

function computePhaseStep() {
  const freqHz = Math.max(0, numberValue("freqHz"));
  const clockHz = Math.max(1, numberValue("clockHz"));
  return Math.round(freqHz * 4294967296 / clockHz) >>> 0;
}

function writeU16(target, offset, value) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
}

function writeU32(target, offset, value) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
  target[offset + 2] = (value >>> 16) & 0xff;
  target[offset + 3] = (value >>> 24) & 0xff;
}

function buildLoadPayload() {
  const payload = new Uint8Array(2 + SAMPLE_COUNT * 2);
  writeU16(payload, 0, SAMPLE_COUNT);
  for (let i = 0; i < SAMPLE_COUNT; i++) {
    writeU16(payload, 2 + i * 2, state.samples[i]);
  }
  return payload;
}

function buildConfigPayload(enable) {
  const payload = new Uint8Array(9);
  writeU32(payload, 0, computePhaseStep());
  writeU16(payload, 4, clamp(numberValue("gainQ16"), 0, 65535));
  writeU16(payload, 6, clamp(numberValue("offsetRaw"), 0, 65535));
  payload[8] = enable ? 1 : 0;
  return payload;
}

function buildPacket(command, payload = new Uint8Array()) {
  const packet = new Uint8Array(4 + 1 + 2 + payload.length + 2);
  packet.set(MAGIC, 0);
  packet[4] = command;
  writeU16(packet, 5, payload.length);
  packet.set(payload, 7);

  let sum = command + packet[5] + packet[6];
  for (const byte of payload) sum = (sum + byte) & 0xffff;
  writeU16(packet, 7 + payload.length, sum);
  return packet;
}

function memText() {
  return Array.from(state.samples, sample => sample.toString(16).toUpperCase().padStart(4, "0")).join("\n") + "\n";
}

function cArrayText() {
  const lines = [];
  lines.push("static const unsigned short waveform[4096] = {");
  for (let i = 0; i < SAMPLE_COUNT; i += 8) {
    const chunk = Array.from(state.samples.slice(i, i + 8), value => String(value).padStart(5, " "));
    lines.push("    " + chunk.join(", ") + (i + 8 < SAMPLE_COUNT ? "," : ""));
  }
  lines.push("};");
  return lines.join("\n");
}

function hex32(value) {
  return "0x" + (value >>> 0).toString(16).toUpperCase().padStart(8, "0");
}

function xsdbHeader(title) {
  return [
    `# ${title}`,
    "# Generated by AWG Signal Forge",
    "# Run in Xilinx SDK XSCT/XSDB console while the board is connected.",
    "catch {connect -url tcp:127.0.0.1:3121}",
    "targets -set -nocase -filter {name =~ \"microblaze*#0\"} -index 1",
    "configparams force-mem-access 1",
    ""
  ];
}

function xsdbFooter() {
  return [
    "",
    "configparams force-mem-access 0",
    "puts \"AWG update done\"",
    ""
  ];
}

function xsdbConfigLines(enable = true) {
  const phaseStep = computePhaseStep();
  const gain = clamp(numberValue("gainQ16"), 0, 65535) >>> 0;
  const offset = clamp(numberValue("offsetRaw"), 0, 65535) >>> 0;
  const gainOffset = ((offset << 16) | gain) >>> 0;

  return [
    `mwr 0x44A00004 ${hex32(phaseStep)}`,
    `mwr 0x44A00008 ${hex32(gainOffset)}`,
    `mwr 0x44A00000 ${enable ? "0x00000001" : "0x00000000"}`
  ];
}

function xsdbConfigText() {
  return [
    ...xsdbHeader("AWG config-only update"),
    ...xsdbConfigLines(true),
    ...xsdbFooter()
  ].join("\n");
}

function xsdbFullText() {
  generateSamples();
  const lines = xsdbHeader("AWG waveform and config update");

  lines.push("mwr 0x44A00000 0x00000002");
  lines.push("mwr 0x44A00000 0x00000000");

  for (let i = 0; i < SAMPLE_COUNT; i++) {
    const word = (((i & 0x0fff) << 16) | state.samples[i]) >>> 0;
    lines.push(`mwr 0x44A0000C ${hex32(word)}`);
  }

  lines.push(...xsdbConfigLines(true));
  lines.push(...xsdbFooter());
  return lines.join("\n");
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function copyCArray() {
  const text = cArrayText();
  await navigator.clipboard.writeText(text);
  log("Copied C array to clipboard");
}

async function copyXsdbConfig() {
  await navigator.clipboard.writeText(xsdbConfigText());
  log("Copied XSDB config script to clipboard");
}

function setProgress(ratio, text) {
  el.progressFill.style.width = `${clamp(ratio, 0, 1) * 100}%`;
  el.progressText.textContent = text;
}

function log(message) {
  const time = new Date().toLocaleTimeString();
  el.logBox.textContent += `[${time}] ${message}\n`;
  el.logBox.scrollTop = el.logBox.scrollHeight;
}

function setConnected(connected) {
  el.serialStatus.textContent = connected ? "Serial connected" : "Serial disconnected";
  el.serialStatus.classList.toggle("connected", connected);
  el.connectBtn.textContent = connected ? "Disconnect" : "Connect";
}

async function connectSerial() {
  if (!("serial" in navigator)) {
    log("Web Serial is not available in this browser context");
    return;
  }

  if (state.port) {
    await disconnectSerial();
    return;
  }

  try {
    state.port = await navigator.serial.requestPort();
    await state.port.open({ baudRate: numberValue("baudRate") });
    state.writer = state.port.writable.getWriter();
    setConnected(true);
    log(`Opened UART at ${numberValue("baudRate")} baud`);
    readSerialLoop();
  } catch (error) {
    log(`Serial open failed: ${error.message}`);
    state.port = null;
    state.writer = null;
    setConnected(false);
  }
}

async function disconnectSerial() {
  try {
    state.reading = false;
    if (state.reader) {
      await state.reader.cancel();
      state.reader.releaseLock();
      state.reader = null;
    }
    if (state.writer) {
      state.writer.releaseLock();
      state.writer = null;
    }
    if (state.port) {
      await state.port.close();
      state.port = null;
    }
  } catch (error) {
    log(`Disconnect warning: ${error.message}`);
  }
  setConnected(false);
}

async function readSerialLoop() {
  if (!state.port || !state.port.readable || state.reading) return;
  state.reading = true;
  const decoder = new TextDecoder();

  try {
    state.reader = state.port.readable.getReader();
    while (state.reading) {
      const { value, done } = await state.reader.read();
      if (done) break;
      if (value && value.length) {
        const text = decoder.decode(value).replace(/\r/g, "");
        if (text.trim().length) log(`RX ${text.trim()}`);
      }
    }
  } catch (error) {
    if (state.reading) log(`RX stopped: ${error.message}`);
  } finally {
    if (state.reader) {
      state.reader.releaseLock();
      state.reader = null;
    }
    state.reading = false;
  }
}

async function writePacket(packet, label) {
  if (!state.writer) {
    log("No serial port open");
    return;
  }

  const chunkSize = 256;
  setProgress(0, `${label}: starting`);

  for (let offset = 0; offset < packet.length; offset += chunkSize) {
    const chunk = packet.slice(offset, offset + chunkSize);
    await state.writer.write(chunk);
    const ratio = Math.min(1, (offset + chunk.length) / packet.length);
    setProgress(ratio, `${label}: ${offset + chunk.length}/${packet.length} bytes`);
  }

  setProgress(1, `${label}: sent`);
  log(`${label} packet sent (${packet.length} bytes)`);
}

async function sendWaveform() {
  generateSamples();
  await writePacket(buildPacket(CMD_LOAD, buildLoadPayload()), "Waveform");
  await writePacket(buildPacket(CMD_CONFIG, buildConfigPayload(true)), "Config");
}

async function sendConfig() {
  await writePacket(buildPacket(CMD_CONFIG, buildConfigPayload(true)), "Config");
}

async function sendEnable(enable) {
  await writePacket(buildPacket(CMD_ENABLE, new Uint8Array([enable ? 1 : 0])), enable ? "Enable" : "Disable");
}

async function sendReset() {
  await writePacket(buildPacket(CMD_RESET), "Reset");
}

function syncOutputs() {
  for (const id of ["amplitude", "offset", "cycles", "phase", "duty", "harmonics", "wildness"]) {
    const out = el[`${id}Out`];
    if (!out) continue;
    const suffix = id === "phase" ? " deg" : ["amplitude", "offset", "duty", "wildness"].includes(id) ? "%" : "";
    out.textContent = `${el[id].value}${suffix}`;
  }
}

function selectMode(mode) {
  state.mode = mode;
  for (const button of el.modeGrid.querySelectorAll(".mode")) {
    button.classList.toggle("active", button.dataset.mode === mode);
  }
  el.formulaBox.classList.toggle("visible", mode === "formula");
  generateSamples();
}

function randomize() {
  const modes = ["sine", "square", "triangle", "saw", "fm", "additive", "noise", "spikes"];
  selectMode(modes[Math.floor(Math.random() * modes.length)]);
  el.cycles.value = String(1 + Math.floor(Math.random() * 9));
  el.phase.value = String(Math.floor(Math.random() * 360));
  el.duty.value = String(12 + Math.floor(Math.random() * 76));
  el.harmonics.value = String(2 + Math.floor(Math.random() * 18));
  el.wildness.value = String(10 + Math.floor(Math.random() * 74));
  el.seed.value = String(1 + Math.floor(Math.random() * 999999));
  syncOutputs();
  generateSamples();
}

function resetControls() {
  el.freqHz.value = "1000";
  el.clockHz.value = "100000000";
  el.amplitude.value = "92";
  el.offset.value = "50";
  el.cycles.value = "1";
  el.phase.value = "0";
  el.duty.value = "50";
  el.harmonics.value = "7";
  el.wildness.value = "18";
  el.seed.value = "1337";
  el.gainQ16.value = "65535";
  el.offsetRaw.value = "0";
  el.softClip.checked = true;
  el.invert.checked = false;
  el.dcBlock.checked = false;
  selectMode("sine");
  syncOutputs();
  generateSamples();
}

function attachEvents() {
  el.modeGrid.addEventListener("click", event => {
    const button = event.target.closest(".mode");
    if (button) selectMode(button.dataset.mode);
  });

  for (const id of [
    "freqHz", "clockHz", "amplitude", "offset", "cycles", "phase", "duty",
    "harmonics", "wildness", "seed", "formulaInput", "softClip", "invert",
    "dcBlock", "gainQ16", "offsetRaw"
  ]) {
    el[id].addEventListener("input", () => {
      syncOutputs();
      generateSamples();
    });
  }

  el.exportMemBtn.addEventListener("click", () => downloadText("waveform.mem", memText()));
  el.copyCBtn.addEventListener("click", () => copyCArray().catch(error => log(`Copy failed: ${error.message}`)));
  el.exportXsdbBtn.addEventListener("click", () => downloadText("awg_update.tcl", xsdbFullText()));
  el.copyXsdbConfigBtn.addEventListener("click", () => copyXsdbConfig().catch(error => log(`Copy failed: ${error.message}`)));
  el.randomizeBtn.addEventListener("click", randomize);
  el.resetBtn.addEventListener("click", resetControls);
  el.connectBtn.addEventListener("click", connectSerial);
  el.sendWaveBtn.addEventListener("click", () => sendWaveform().catch(error => log(`Send failed: ${error.message}`)));
  el.sendConfigBtn.addEventListener("click", () => sendConfig().catch(error => log(`Send failed: ${error.message}`)));
  el.enableBtn.addEventListener("click", () => sendEnable(true).catch(error => log(`Send failed: ${error.message}`)));
  el.resetAwgBtn.addEventListener("click", () => sendReset().catch(error => log(`Send failed: ${error.message}`)));

  window.addEventListener("resize", generateSamples);
}

function init() {
  bindElements();
  attachEvents();
  syncOutputs();
  generateSamples();

  if (!("serial" in navigator)) {
    log("Web Serial needs Chrome or Edge on a secure local page");
  } else {
    log("Ready");
  }
}

document.addEventListener("DOMContentLoaded", init);
