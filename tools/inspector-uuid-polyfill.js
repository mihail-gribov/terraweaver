// Local patch: crypto.randomUUID exists only in secure contexts (HTTPS or localhost).
// Opened over plain http from the LAN it is missing, so build it from getRandomValues,
// which is available everywhere.
if (window.crypto && !window.crypto.randomUUID) {
  window.crypto.randomUUID = function () {
    const b = window.crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  };
}
