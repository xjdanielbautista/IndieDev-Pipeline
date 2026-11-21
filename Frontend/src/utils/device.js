// Convierte el User-Agent de una sesión en algo legible: "Chrome en Windows".
const BROWSERS = [
  [/Edg\//, "Edge"],
  [/OPR\/|Opera/, "Opera"],
  [/Firefox\//, "Firefox"],
  [/Chrome\//, "Chrome"],
  [/Safari\//, "Safari"],
];

const SYSTEMS = [
  [/Android/, "Android"],
  [/iPhone|iPad|iPod/, "iOS"],
  [/Windows/, "Windows"],
  [/Mac OS X|Macintosh/, "macOS"],
  [/CrOS/, "ChromeOS"],
  [/Linux/, "Linux"],
];

export function describeDevice(userAgent) {
  if (!userAgent) return "Dispositivo desconocido";
  const browser = BROWSERS.find(([pattern]) => pattern.test(userAgent))?.[1];
  const system = SYSTEMS.find(([pattern]) => pattern.test(userAgent))?.[1];
  if (browser && system) return `${browser} en ${system}`;
  if (browser || system) return browser || system;
  // Clientes que no son navegador (curl, scripts): se muestra el nombre tal cual.
  return userAgent.split(/[\s/]/)[0] || "Dispositivo desconocido";
}

export function isMobileDevice(userAgent = "") {
  return /Android|iPhone|iPad|iPod|Mobile/.test(userAgent ?? "");
}
