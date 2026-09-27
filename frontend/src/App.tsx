import { PosScreen } from "./features/pos/PosScreen";
import { LoginScreen } from "./features/auth/LoginScreen";
import { useAuthStore } from "./features/pos/authStore";

export default function App() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const login = useAuthStore((s) => s.login);

  if (!isAuthenticated) {
    return <LoginScreen onLogin={login} />;
  }

  return <PosScreen />;
}
