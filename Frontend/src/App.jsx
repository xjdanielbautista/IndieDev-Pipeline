import { useCallback, useEffect, useState } from "react";
import LoginScreen from "./components/LoginScreen";
import Workspace from "./components/Workspace";
import { ToastProvider } from "./components/ui";
import { AUTH_EXPIRED_EVENT, getToken, getTokenExpiration, isTokenValid } from "./api/client";
import { getCurrentUser, logout } from "./api/auth";

const EXPIRED_MESSAGE = "Tu sesión expiró (dura 30 minutos). Vuelve a iniciar sesión.";

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(() => isTokenValid(getToken()));
  const [currentUser, setCurrentUser] = useState(null);
  const [authNotice, setAuthNotice] = useState("");

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
    getCurrentUser().then(setCurrentUser).catch(() => {});

    const exp = getTokenExpiration(getToken());
    if (!exp) return undefined;
    const timer = setTimeout(() => handleLogout(EXPIRED_MESSAGE), Math.max(exp - Date.now(), 0));
    return () => clearTimeout(timer);
  }, [isLoggedIn, handleLogout]);

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
        <div className="min-h-screen bg-[#0B0D14] flex items-center justify-center text-sm font-mono text-gray-500">
          Cargando...
        </div>
      ) : (
        <Workspace currentUser={currentUser} onLogout={() => handleLogout()} />
      )}
    </ToastProvider>
  );
}
