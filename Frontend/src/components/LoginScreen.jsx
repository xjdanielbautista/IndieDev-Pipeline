import { useState } from "react";
import { ArrowRight, Code, KeyRound, Lock, Mail, User } from "lucide-react";
import ApiStatus from "./ApiStatus";
import { confirmPasswordReset, login, register, requestPasswordReset, resendVerification, verifyEmailCode } from "../api/auth";
import { clearResetTokenFromUrl, getResetTokenFromUrl } from "../utils/resetToken";

const inputClasses =
  "w-full bg-[#0B0D14] border border-[#272B3B] text-white text-sm rounded-lg pl-10 pr-4 py-2.5 focus:outline-none focus:border-[#00F0FF] focus:ring-1 focus:ring-[#00F0FF] transition-colors";

function Field({ label, icon: Icon, ...inputProps }) {
  return (
    <div>
      <label className="block text-xs font-mono text-gray-400 mb-1">{label}</label>
      <div className="relative">
        <Icon className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
        <input {...inputProps} className={inputClasses} />
      </div>
    </div>
  );
}

export default function LoginScreen({ onLoggedIn, notice }) {
  const [resetToken] = useState(getResetTokenFromUrl);
  // "login" | "register" | "forgot" (pedir enlace) | "reset" (nueva contraseña)
  // | "verify" (escribir el código de 6 dígitos que llegó al correo)
  const [mode, setMode] = useState(resetToken ? "reset" : "login");
  const [code, setCode] = useState("");
  const [resending, setResending] = useState(false);
  // Usuario y contraseña recién escritos, para entrar solo en cuanto se confirme el código.
  const [pendingLogin, setPendingLogin] = useState(null);
  const [identifier, setIdentifier] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  // El backend exige confirmar el correo (REQUIRE_EMAIL_VERIFICATION) y esta cuenta no lo ha hecho.
  const [needsVerification, setNeedsVerification] = useState(false);

  const isRegister = mode === "register";
  const isForgot = mode === "forgot";
  const isReset = mode === "reset";
  const isVerify = mode === "verify";
  const asksEmailOnly = isForgot;

  const switchMode = (newMode) => {
    setMode(newMode);
    setError("");
    setInfo("");
    setNeedsVerification(false);
    setCode("");
    if (newMode !== "verify") setPendingLogin(null);
  };

  // Abre el paso del código. `credentials` permite entrar solo al confirmarlo.
  const goToVerify = (emailValue, credentials, message) => {
    switchMode("verify");
    if (emailValue) setEmail(emailValue);
    setPendingLogin(credentials);
    setInfo(message);
  };

  const enterAfterVerify = async (message) => {
    if (pendingLogin) {
      try {
        await login(pendingLogin.identifier, pendingLogin.password);
        setPassword("");
        onLoggedIn();
        return;
      } catch (err) {
        if (err.status !== 403) throw err;
      }
    }
    setIdentifier(pendingLogin?.identifier || email.trim());
    switchMode("login");
    setInfo(message);
  };

  const resendCode = async () => {
    setError("");
    setInfo("");
    setResending(true);
    try {
      const data = await resendVerification(email.trim());
      setCode("");
      setInfo(data?.detail || "Te enviamos un código nuevo.");
    } catch (err) {
      setError(err.message);
    } finally {
      setResending(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setNeedsVerification(false);
    if (isReset && password !== confirmPassword) {
      setError("Las contraseñas no coinciden");
      return;
    }
    setLoading(true);
    try {
      if (isForgot) {
        const data = await requestPasswordReset(email.trim());
        setInfo(data?.detail || "Revisa tu correo.");
        return;
      }
      if (isVerify) {
        await verifyEmailCode(email.trim(), code);
        await enterAfterVerify("Tu correo quedó confirmado. Ya puedes iniciar sesión.");
        return;
      }
      if (isReset) {
        await confirmPasswordReset(resetToken, password);
        clearResetTokenFromUrl();
        setPassword("");
        setConfirmPassword("");
        setMode("login");
        setInfo("Tu contraseña se actualizó. Ya puedes iniciar sesión.");
        return;
      }
      if (isRegister) {
        await register({ username: username.trim(), email: email.trim(), password });
        // Tras registrarse se pide el código que llegó al correo; al confirmarlo entra solo.
        goToVerify(
          email.trim(),
          { identifier: username.trim(), password },
          `Cuenta creada. Te enviamos un código de 6 dígitos a ${email.trim()}.`,
        );
        setPassword("");
        return;
      } else {
        await login(identifier.trim(), password);
      }
      setPassword("");
      onLoggedIn();
    } catch (err) {
      setError(err.message);
      if (err.status === 403 && mode === "login") setNeedsVerification(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0D14] text-gray-300 font-sans flex items-center justify-center relative overflow-hidden px-4 selection:bg-[#00F0FF] selection:text-black">
      <div className="absolute top-[10%] left-[20%] w-96 h-96 bg-[#00F0FF]/10 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[10%] right-[20%] w-96 h-96 bg-[#FF0055]/10 rounded-full blur-[120px] pointer-events-none"></div>

      <div className="z-10 w-full max-w-md p-8 bg-[#151822] border border-[#272B3B] rounded-xl shadow-2xl backdrop-blur-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-gradient-to-br from-[#151822] to-[#272B3B] border border-[#272B3B] shadow-[0_0_15px_rgba(0,240,255,0.2)] mb-4">
            <Code className="w-8 h-8 text-[#00F0FF]" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            IndieDev <span className="text-[#00F0FF]">Pipeline</span>
          </h1>
          <p className="text-xs text-gray-400 mt-2 font-mono uppercase tracking-widest">Workspace Gateway</p>
        </div>

        <div className="grid grid-cols-2 gap-1 p-1 mb-6 bg-[#0B0D14] border border-[#272B3B] rounded-lg">
          {[
            ["login", "Iniciar sesión"],
            ["register", "Crear cuenta"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => switchMode(id)}
              className={`py-2 text-sm rounded-md transition-colors ${
                mode === id || (id === "login" && (asksEmailOnly || isReset || isVerify)) ? "bg-[#1C202D] text-white font-medium" : "text-gray-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {(asksEmailOnly || isReset || isVerify) && (
          <p className="mb-4 text-xs text-gray-400">
            {isForgot
              ? "Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una contraseña nueva."
              : isVerify
                ? "Confirma tu correo: escribe el código de 6 dígitos que te enviamos. Si no llega, revisa spam o pide otro."
                : "Elige tu nueva contraseña. Al guardarla se cerrarán las sesiones abiertas."}
          </p>
        )}

        {info && !error && (
          <p className="mb-4 text-xs text-emerald-400 bg-emerald-400/10 border border-emerald-400/30 rounded p-2">{info}</p>
        )}

        {notice && !error && !info && (
          <p className="mb-4 text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 rounded p-2">{notice}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {isVerify ? (
            <>
              <Field
                label="email"
                icon={Mail}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alex@pixelninja.dev"
                autoComplete="email"
                required
              />
              <div>
                <label htmlFor="verify-code" className="block text-xs font-mono text-gray-400 mb-1">
                  código de verificación
                </label>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-3.5 w-4 h-4 text-gray-400" />
                  <input
                    id="verify-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="\d{6}"
                    title="Los 6 dígitos del correo"
                    placeholder="000000"
                    required
                    autoFocus
                    className={`${inputClasses} text-lg font-mono tracking-[0.5em]`}
                  />
                </div>
              </div>
            </>
          ) : asksEmailOnly ? (
            <Field
              label="email"
              icon={Mail}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex@pixelninja.dev"
              autoComplete="email"
              required
            />
          ) : isReset ? null : isRegister ? (
            <>
              <Field
                label="username"
                icon={User}
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="alex_dev"
                autoComplete="username"
                required
                minLength={3}
                maxLength={50}
                pattern="[a-zA-Z0-9_.\-]+"
                title="Solo letras, números, punto, guion y guion bajo (3 a 50 caracteres)"
              />
              <Field
                label="email"
                icon={Mail}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alex@pixelninja.dev"
                autoComplete="email"
                required
              />
            </>
          ) : (
            <Field
              label="usuario o email"
              icon={User}
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="alex_dev o alex@pixelninja.dev"
              autoComplete="username"
              required
            />
          )}

          {!asksEmailOnly && !isVerify && (
            <Field
              label={isReset ? "nueva password" : "password"}
              icon={Lock}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isRegister || isReset ? "new-password" : "current-password"}
              required
              minLength={isRegister || isReset ? 8 : undefined}
              maxLength={128}
              placeholder={isRegister || isReset ? "Mínimo 8 caracteres" : ""}
            />
          )}

          {isReset && (
            <Field
              label="confirmar password"
              icon={Lock}
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
            />
          )}

          {mode === "login" && (
            <div className="-mt-3 text-right">
              <button
                type="button"
                onClick={() => switchMode("forgot")}
                className="text-xs text-gray-400 hover:text-[#00F0FF] transition-colors"
              >
                ¿Olvidaste tu contraseña?
              </button>
            </div>
          )}

          {error && (
            <p className="text-xs text-[#FF3D00] bg-[#FF3D00]/10 border border-[#FF3D00]/30 rounded p-2 whitespace-pre-line">
              {error}
              {needsVerification && (
                <button
                  type="button"
                  onClick={() =>
                    goToVerify(
                      identifier.includes("@") ? identifier.trim() : "",
                      { identifier: identifier.trim(), password },
                      "",
                    )
                  }
                  className="block mt-2 text-[#00F0FF] hover:underline"
                >
                  Escribir el código de verificación
                </button>
              )}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || (isVerify && code.length !== 6)}
            className="w-full mt-2 bg-[#00F0FF] hover:bg-cyan-400 disabled:opacity-60 disabled:cursor-wait text-black font-bold rounded-lg px-4 py-3 transition-colors shadow-[0_0_15px_rgba(0,240,255,0.4)] flex justify-center items-center gap-2 group focus-visible:ring-2 focus-visible:ring-white"
          >
            <span>
              {loading
                ? "CONECTANDO..."
                : isVerify
                  ? "CONFIRMAR CORREO"
                  : asksEmailOnly
                  ? "ENVIAR ENLACE"
                  : isReset
                    ? "GUARDAR CONTRASEÑA"
                    : isRegister
                      ? "CREAR CUENTA"
                      : "INICIAR SESIÓN"}
            </span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </form>

        {isVerify && (
          <div className="mt-4 flex flex-wrap justify-between gap-2 text-xs">
            <button
              type="button"
              onClick={resendCode}
              disabled={resending || !email.trim()}
              className="text-[#00F0FF] hover:underline disabled:opacity-50"
            >
              {resending ? "Enviando..." : "Reenviar código"}
            </button>
            <button
              type="button"
              onClick={async () => {
                if (!pendingLogin) return switchMode("login");
                setError("");
                setLoading(true);
                try {
                  // Si el backend exige el correo confirmado, responde 403 y se queda en este paso.
                  await login(pendingLogin.identifier, pendingLogin.password);
                  onLoggedIn();
                } catch (err) {
                  setError(err.message);
                } finally {
                  setLoading(false);
                }
              }}
              className="text-gray-400 hover:text-white"
            >
              {pendingLogin ? "Confirmar después →" : "← Volver a iniciar sesión"}
            </button>
          </div>
        )}

        {(asksEmailOnly || isReset) && (
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => {
                if (isReset) clearResetTokenFromUrl();
                switchMode("login");
              }}
              className="text-xs text-gray-400 hover:text-white transition-colors"
            >
              ← Volver a iniciar sesión
            </button>
          </div>
        )}

        <div className="mt-6 text-center text-xs font-mono text-gray-400">
          <ApiStatus />
        </div>
      </div>
    </div>
  );
}
