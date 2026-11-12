import { useCallback, useEffect, useState } from "react";
import LoginScreen from "./components/LoginScreen";
import Workspace from "./components/Workspace";
import { ToastProvider } from "./components/ui";
import { AUTH_EXPIRED_EVENT, getToken, getTokenExpiration, isTokenValid } from "./api/client";
import { getCurrentUser, logout } from "./api/auth";

const EXPIRED_MESSAGE = "Tu sesión expiró. Vuelve a iniciar sesión.";

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(() => isTokenValid(getToken()));
  const [currentUser, setCurrentUser] = useState(null);
  const [authNotice, setAuthNotice] = useState("");
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const handleLogout = useCallback((notice = "") => {
    logout();
    setCurrentUser(null);
    setAuthNotice(typeof notice === "string" ? notice : "");
    setIsLoggedIn(false);
  }, []);

  // Si el backend responde 401 (token vencido o inválido), regresa al login.
  useEffect(() => {
    const onExpired = () => handleLogout(EXPIRED_MESSAGE);
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [handleLogout]);

  // Al iniciar sesión: carga el usuario del token y programa el cierre cuando venza.
  useEffect(() => {
    if (!isLoggedIn) return undefined;
    getCurrentUser()
      .then((user) => {
        setLoadError("");
        setCurrentUser(user);
      })
      // Un 401 ya regresa al login; cualquier otro error (backend apagado o
      // despertando en Render) se muestra con opción de reintentar.
      .catch((err) => {
        if (err.status !== 401) setLoadError(err.message);
      });

    const exp = getTokenExpiration(getToken());
    if (!exp) return undefined;
    const timer = setTimeout(() => handleLogout(EXPIRED_MESSAGE), Math.max(exp - Date.now(), 0));
    return () => clearTimeout(timer);
  }, [isLoggedIn, handleLogout, reloadKey]);

  return (
    <ToastProvider>
      {!isLoggedIn ? (
        <LoginScreen
          notice={authNotice}
          onLoggedIn={() => {
            setAuthNotice("");
            setIsLoggedIn(true);
          }}
        />
      ) : !currentUser ? (
        <div className="min-h-screen bg-[#0B0D14] flex flex-col items-center justify-center gap-4 px-4 text-center text-sm font-mono text-gray-500">
          {loadError ? (
            <>
              <p className="max-w-md text-[#FF3D00]">{loadError}</p>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setLoadError("");
                    setReloadKey((k) => k + 1);
                  }}
                  className="px-4 py-2 rounded-md bg-[#00F0FF] text-[#0B0D14] font-semibold"
                >
                  Reintentar
                </button>
                <button
                  onClick={() => handleLogout()}
                  className="px-4 py-2 rounded-md border border-[#272B3B] text-gray-300"
                >
                  Cerrar sesión
                </button>
              </div>
            </>
          ) : (
            "Cargando..."
          )}
        </div>
      ) : (
        <Workspace currentUser={currentUser} onLogout={() => handleLogout()} />
      )}
    </ToastProvider>
  );
}
