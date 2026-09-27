import { create } from "zustand";
import { persist } from "zustand/middleware";

type User = {
  id: number;
  username: string;
  role: "admin" | "user";
};

type AuthState = {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;

  login: (token: string, user: User) => void;
  logout: () => void;
  isAdmin: () => boolean;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      login: (token, user) => {
        set({ token, user, isAuthenticated: true });
      },

      logout: () => {
        set({ token: null, user: null, isAuthenticated: false });
      },

      isAdmin: () => {
        const { user } = get();
        return user?.role === "admin";
      },
    }),
    {
      name: "auth-storage",
    }
  )
);
