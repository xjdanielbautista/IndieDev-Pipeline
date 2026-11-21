import { describe, expect, it } from "vitest";
import { describeDevice, isMobileDevice } from "../utils/device";

const CHROME_WINDOWS =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";
const EDGE_WINDOWS = `${CHROME_WINDOWS} Edg/130.0.0.0`;
const SAFARI_IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0";
const CHROME_ANDROID =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36";

describe("describeDevice", () => {
  it("reconoce navegador y sistema", () => {
    expect(describeDevice(CHROME_WINDOWS)).toBe("Chrome en Windows");
    expect(describeDevice(EDGE_WINDOWS)).toBe("Edge en Windows");
    expect(describeDevice(SAFARI_IPHONE)).toBe("Safari en iOS");
    expect(describeDevice(FIREFOX_LINUX)).toBe("Firefox en Linux");
    expect(describeDevice(CHROME_ANDROID)).toBe("Chrome en Android");
  });

  it("muestra el nombre de clientes que no son navegador", () => {
    expect(describeDevice("curl/8.5.0")).toBe("curl");
    expect(describeDevice("python-requests/2.32")).toBe("python-requests");
  });

  it("no falla sin User-Agent", () => {
    expect(describeDevice(null)).toBe("Dispositivo desconocido");
    expect(describeDevice("")).toBe("Dispositivo desconocido");
  });
});

describe("isMobileDevice", () => {
  it("distingue celular de computadora", () => {
    expect(isMobileDevice(SAFARI_IPHONE)).toBe(true);
    expect(isMobileDevice(CHROME_ANDROID)).toBe(true);
    expect(isMobileDevice(CHROME_WINDOWS)).toBe(false);
    expect(isMobileDevice(null)).toBe(false);
  });
});
