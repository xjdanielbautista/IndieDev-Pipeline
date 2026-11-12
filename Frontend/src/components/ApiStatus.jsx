import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config/api";

// En el plan gratuito de Render el backend se duerme tras 15 min sin uso y tarda
// hasta ~1 minuto en despertar. Este aviso evita que parezca que la app está rota.
const SLOW_AFTER_MS = 4000;

export default function ApiStatus() {
  const [estado, setEstado] = useState("Comprobando conexión con el backend...");

  useEffect(() => {
    let done = false;
    const slowTimer = setTimeout(() => {
      if (!done) setEstado("Despertando el servidor, puede tardar hasta un minuto...");
    }, SLOW_AFTER_MS);

    fetch(`${API_BASE_URL}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then((d) => setEstado(`Conectado: ${d.service}`))
      .catch(() => setEstado("Sin conexión con el backend"))
      .finally(() => {
        done = true;
        clearTimeout(slowTimer);
      });

    return () => clearTimeout(slowTimer);
  }, []);

  return <p className="text-sm">{estado}</p>;
}
