import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config/api";

export default function ApiStatus() {
  const [estado, setEstado] = useState("Comprobando conexión con el backend...");

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then((d) => setEstado(`Conectado: ${d.service}`))
      .catch(() => setEstado("Sin conexión con el backend"));
  }, []);

  return <p className="text-sm">{estado}</p>;
}
