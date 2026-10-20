import { useState } from "react";
import { ArrowRight, Code, Lock, Mail, User } from "lucide-react";
import ApiStatus from "./ApiStatus";
import { login, register } from "../api/auth";

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
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [identifier, setIdentifier] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isRegister = mode === "register";

  const switchMode = (newMode) => {
    setMode(newMode);
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegister) {
        await register({ username: username.trim(), email: email.trim(), password });
        // Tras registrarse, inicia sesión directamente con lo que escribió.
        await login(username.trim(), password);
      } else {
        await login(identifier.trim(), password);
      }
      setPassword("");
      onLoggedIn();
    } catch (err) {
      setError(err.message);
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
                mode === id ? "bg-[#1C202D] text-white font-medium" : "text-gray-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {notice && !error && (
          <p className="mb-4 text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 rounded p-2">{notice}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {isRegister ? (
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

          <Field
            label="password"
            icon={Lock}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isRegister ? "new-password" : "current-password"}
            required
            minLength={isRegister ? 8 : undefined}
            maxLength={128}
            placeholder={isRegister ? "Mínimo 8 caracteres" : ""}
          />

          {error && (
            <p className="text-xs text-[#FF3D00] bg-[#FF3D00]/10 border border-[#FF3D00]/30 rounded p-2 whitespace-pre-line">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 bg-[#00F0FF] hover:bg-cyan-400 disabled:opacity-60 disabled:cursor-wait text-black font-bold rounded-lg px-4 py-3 transition-colors shadow-[0_0_15px_rgba(0,240,255,0.4)] flex justify-center items-center gap-2 group focus-visible:ring-2 focus-visible:ring-white"
          >
            <span>{loading ? "CONECTANDO..." : isRegister ? "CREAR CUENTA" : "INICIAR SESIÓN"}</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </form>

        <div className="mt-6 text-center text-xs font-mono text-gray-400">
          <ApiStatus />
        </div>
      </div>
    </div>
  );
}
