import { FormEvent, useState } from "react";

import { FileUploadPanel } from "./components/FileUploadPanel";
import { useAuth } from "./hooks/useAuth";

export default function App() {
  const { isAuthenticated, login, logout, token } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedFileName, setSelectedFileName] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage("");

    try {
      await login({ username, password });
    } catch {
      setErrorMessage("login failed");
    }
  };

  return (
    <main style={{ fontFamily: "sans-serif", margin: "40px auto", maxWidth: 720 }}>
      <h1>Frontend Base</h1>

      <section>
        <h2>Login</h2>
        <form onSubmit={handleSubmit}>
          <div>
            <label htmlFor="username">username</label>
            <input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </div>
          <div style={{ marginTop: 8 }}>
            <label htmlFor="password">password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button type="submit" style={{ marginTop: 12 }}>
            Login
          </button>
          <button type="button" onClick={logout} style={{ marginLeft: 8 }}>
            Logout
          </button>
        </form>

        <p>authenticated: {isAuthenticated ? "true" : "false"}</p>
        <p>token: {token ?? "none"}</p>
        {errorMessage ? <p>{errorMessage}</p> : null}
      </section>

      <section style={{ marginTop: 32 }}>
        <FileUploadPanel
          uploadedFilePath={selectedFileName ? `sample/${selectedFileName}` : null}
          onFileSelect={(file) => setSelectedFileName(file?.name ?? "")}
        />
      </section>
    </main>
  );
}
